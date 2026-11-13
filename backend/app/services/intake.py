"""Resume intake (FR-20 to FR-25).

API side (`IntakeService`): validate and store files, create a batch, return fast.
Worker side (`ResumeParser`): extract text, LLM-parse, dedupe the candidate, create the
application. Parsing takes seconds per file, so it can't happen inside the HTTP request.
"""

import hashlib
import logging
import uuid
from decimal import Decimal

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import OrgContext
from app.core.errors import (
    AppError,
    BadGatewayError,
    ConflictError,
    GatewayTimeoutError,
    ServiceUnavailableError,
)
from app.llm.prompts import load_prompt
from app.llm.provider import LLMProvider
from app.llm.runner import LLMRunner
from app.llm.schemas import ParsedResume
from app.models import (
    Application,
    Batch,
    BatchStatus,
    Candidate,
    JobStatus,
    LLMPurpose,
    ParseStatus,
    Resume,
)
from app.pipeline.extract import (
    EXTENSION,
    MAX_FILES_PER_BATCH,
    UnsupportedFileError,
    check_file,
    extract_text,
)
from app.repositories.intake import (
    ApplicationRepository,
    BatchRepository,
    CandidateRepository,
    ResumeRepository,
)
from app.services.jobs import JobService
from app.storage.s3 import Storage

logger = logging.getLogger(__name__)
RESUME_PARSE_PROMPT = load_prompt("resume_parse", 1)


class InvalidUploadError(AppError):
    status, type_, title = 422, "invalid-upload", "Invalid upload"


# ---- API side ---------------------------------------------------------------------------


class IntakeService:
    def __init__(self, session: AsyncSession, ctx: OrgContext, storage: Storage) -> None:
        self.session = session
        self.ctx = ctx
        self.storage = storage

    async def upload(
        self, job_id: uuid.UUID, files: list[tuple[str, bytes]]
    ) -> tuple[Batch, list[uuid.UUID]]:
        """Returns the batch and the resume ids to enqueue for parsing.

        Bad files don't fail the whole upload: each is recorded as `failed` with a reason,
        so one broken file in 50 doesn't make the recruiter start over.
        """
        job = await JobService(self.session, self.ctx).get(job_id)  # 404 across orgs
        if job.status == JobStatus.CLOSED:
            raise ConflictError("This job is closed; it can't receive new resumes.")
        if not 1 <= len(files) <= MAX_FILES_PER_BATCH:
            raise InvalidUploadError(f"Upload between 1 and {MAX_FILES_PER_BATCH} files.")

        batch = await BatchRepository(self.session, self.ctx.org_id).add(
            Batch(job_id=job.id, total=len(files), processed=0, failed=0)
        )
        resumes = ResumeRepository(self.session, self.ctx.org_id)
        queued: list[uuid.UUID] = []
        for filename, data in files:
            name = (filename or "resume")[:255]
            try:
                checked = check_file(data)
            except UnsupportedFileError as e:
                batch.failed += 1
                await resumes.add(
                    Resume(
                        batch_id=batch.id,
                        filename=name,
                        file_hash=hashlib.sha256(data).hexdigest(),
                        mime_type="application/octet-stream",
                        size_bytes=len(data),
                        parse_status=ParseStatus.FAILED,
                        error=str(e),
                    )
                )
                continue
            resume_id = uuid.uuid4()
            # Org-scoped key: even a storage-level bug can't mix tenants' files.
            key = f"orgs/{self.ctx.org_id}/resumes/{resume_id}.{EXTENSION[checked.mime_type]}"
            await self.storage.put(key, data, checked.mime_type)
            await resumes.add(
                Resume(
                    id=resume_id,
                    batch_id=batch.id,
                    filename=name,
                    storage_key=key,
                    file_hash=checked.sha256,
                    mime_type=checked.mime_type,
                    size_bytes=len(data),
                )
            )
            queued.append(resume_id)

        if not queued:
            batch.status = BatchStatus.DONE
        await self.session.commit()
        await self.session.refresh(batch)  # load DB-generated created_at (async-safe)
        return batch, queued


# ---- Worker side ------------------------------------------------------------------------


class TransientParseError(Exception):
    """Worth retrying later (LLM busy/timeout, storage hiccup)."""


class ResumeParser:
    """Parses one resume. Idempotent: running it twice for the same id is harmless,
    which matters because queues deliver "at least once"."""

    def __init__(
        self, session: AsyncSession, storage: Storage, provider: LLMProvider | None = None
    ) -> None:
        self.session = session
        self.storage = storage
        self.provider = provider

    async def run(self, resume_id: uuid.UUID) -> None:
        # Looked up by id alone: the id came from our own queue, not from a user. Every
        # query after this is scoped to the resume's own org.
        resume = await self.session.get(Resume, resume_id)
        if resume is None or resume.parse_status in (ParseStatus.PARSED, ParseStatus.FAILED):
            return
        org_id = resume.org_id
        resume.parse_status = ParseStatus.PARSING
        await self.session.commit()

        try:
            assert resume.storage_key is not None
            data = await self.storage.get(resume.storage_key)
            text = extract_text(data, resume.mime_type)
            resume.raw_text = text
            parsed = await self._parse(resume, text)
        except UnsupportedFileError as e:
            await self.fail(resume_id, str(e))
            return
        except BadGatewayError:
            await self.fail(resume_id, "The AI couldn't read this resume. Try re-uploading it.")
            return
        except (ServiceUnavailableError, GatewayTimeoutError, BotoCoreError, ClientError) as e:
            await self._requeue(resume_id)
            raise TransientParseError(type(e).__name__) from e

        try:
            candidate = await self._upsert_candidate(org_id, parsed)
            resume.candidate_id = candidate.id
            resume.parse_status = ParseStatus.PARSED
            resume.error = None
            if resume.batch_id:
                batch = await BatchRepository(self.session, org_id).get(resume.batch_id)
                if batch:
                    await self._ensure_application(org_id, batch.job_id, candidate.id, resume.id)
                    await BatchRepository(self.session, org_id).record_result(
                        batch.id, failed=False
                    )
            await self.session.commit()
        except IntegrityError as e:
            # Another worker created the same candidate/application a moment ago (two
            # copies of one person's resume parsed in parallel). Retry: next time the
            # email lookup finds the existing candidate.
            await self.session.rollback()
            await self._requeue(resume_id)
            raise TransientParseError("duplicate_race") from e
        logger.info(
            "resume_parsed",
            extra={
                "extra_fields": {"resume_id": str(resume.id), "candidate_id": str(candidate.id)}
            },
        )

    async def _requeue(self, resume_id: uuid.UUID) -> None:
        resume = await self.session.get(Resume, resume_id)
        if resume is not None:
            resume.parse_status = ParseStatus.QUEUED  # back in line for the retry
            await self.session.commit()

    async def fail(self, resume_id: uuid.UUID, reason: str) -> None:
        resume = await self.session.get(Resume, resume_id)
        if resume is None or resume.parse_status in (ParseStatus.PARSED, ParseStatus.FAILED):
            return
        resume.parse_status = ParseStatus.FAILED
        resume.error = reason
        if resume.batch_id:
            await BatchRepository(self.session, resume.org_id).record_result(
                resume.batch_id, failed=True
            )
        await self.session.commit()
        logger.info("resume_failed", extra={"extra_fields": {"resume_id": str(resume_id)}})

    async def _parse(self, resume: Resume, text: str) -> ParsedResume:
        # Same file already parsed in this org? Reuse it: no second LLM call (FR-24).
        dup = await ResumeRepository(self.session, resume.org_id).find_parsed_duplicate(
            resume.file_hash, exclude_id=resume.id
        )
        if dup is not None and dup.candidate_id is not None:
            candidate = await CandidateRepository(self.session, resume.org_id).get(dup.candidate_id)
            if candidate is not None:
                return ParsedResume.model_validate(candidate.parsed)

        if self.provider is None:
            raise ServiceUnavailableError("No LLM provider configured.")
        runner = LLMRunner(self.session, resume.org_id, self.provider)
        return await runner.run(
            purpose=LLMPurpose.RESUME_PARSE,
            prompt=RESUME_PARSE_PROMPT,
            variables={"resume_text": text},
            output=ParsedResume,
        )

    async def _upsert_candidate(self, org_id: uuid.UUID, parsed: ParsedResume) -> Candidate:
        """One candidate per email per org: a re-upload updates them instead of duplicating."""
        repo = CandidateRepository(self.session, org_id)
        email = parsed.email.strip().lower() if parsed.email else None
        candidate = await repo.get_by_email(email) if email else None
        fields = {
            "full_name": parsed.name,
            "phone": parsed.phone,
            "links": parsed.links,
            "parsed": parsed.model_dump(mode="json"),
            "total_experience_years": (
                Decimal(str(round(parsed.total_experience_years, 1)))
                if parsed.total_experience_years is not None
                else None
            ),
        }
        if candidate is None:
            return await repo.add(Candidate(email=email, **fields))
        for key, value in fields.items():
            setattr(candidate, key, value)
        return candidate

    async def _ensure_application(
        self, org_id: uuid.UUID, job_id: uuid.UUID, candidate_id: uuid.UUID, resume_id: uuid.UUID
    ) -> None:
        repo = ApplicationRepository(self.session, org_id)
        existing = await repo.get_for(job_id, candidate_id)
        if existing is None:
            await repo.add(
                Application(job_id=job_id, candidate_id=candidate_id, resume_id=resume_id)
            )
        else:
            existing.resume_id = resume_id  # same person applied again: keep the newest resume
