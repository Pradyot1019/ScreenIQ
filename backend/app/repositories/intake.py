import uuid
from collections.abc import Sequence

from sqlalchemy import select, update

from app.models import Application, Batch, BatchStatus, Candidate, ParseStatus, Resume
from app.repositories.base import TenantRepository


class CandidateRepository(TenantRepository[Candidate]):
    model = Candidate

    async def get_by_email(self, email: str) -> Candidate | None:
        result = await self.session.execute(self._select().where(Candidate.email == email))
        return result.scalar_one_or_none()


class ResumeRepository(TenantRepository[Resume]):
    model = Resume

    async def list_for_batch(
        self, batch_id: uuid.UUID
    ) -> Sequence[tuple[Resume, Candidate | None]]:
        result = await self.session.execute(
            select(Resume, Candidate)
            .outerjoin(Candidate, Candidate.id == Resume.candidate_id)
            .where(Resume.org_id == self.org_id, Resume.batch_id == batch_id)
            .order_by(Resume.created_at, Resume.filename)
        )
        return [(r, c) for r, c in result.all()]

    async def find_parsed_duplicate(self, file_hash: str, exclude_id: uuid.UUID) -> Resume | None:
        """An already-parsed copy of the same file in this org (FR-24 dedupe by hash)."""
        result = await self.session.execute(
            self._select()
            .where(
                Resume.file_hash == file_hash,
                Resume.id != exclude_id,
                Resume.parse_status == ParseStatus.PARSED,
                Resume.candidate_id.is_not(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()


class ApplicationRepository(TenantRepository[Application]):
    model = Application

    async def get_for(self, job_id: uuid.UUID, candidate_id: uuid.UUID) -> Application | None:
        result = await self.session.execute(
            self._select().where(
                Application.job_id == job_id, Application.candidate_id == candidate_id
            )
        )
        return result.scalar_one_or_none()


class BatchRepository(TenantRepository[Batch]):
    model = Batch

    async def record_result(self, batch_id: uuid.UUID, *, failed: bool) -> None:
        """Atomic counter bump: several workers finish files of the same batch at once,
        so read-modify-write in Python would lose updates. SQL `x = x + 1` can't."""
        column = Batch.failed if failed else Batch.processed
        await self.session.execute(
            update(Batch)
            .where(Batch.id == batch_id, Batch.org_id == self.org_id)
            .values({column: column + 1})
        )
        await self.session.execute(
            update(Batch)
            .where(
                Batch.id == batch_id,
                Batch.org_id == self.org_id,
                Batch.processed + Batch.failed >= Batch.total,
            )
            .values(status=BatchStatus.DONE)
        )
