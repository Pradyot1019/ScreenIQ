"""FakeLLMProvider: replays recorded LLM responses so tests are fast, free and deterministic.

Each queued item is either a response text (usually loaded from tests/fixtures/llm/)
or an exception to raise. Every call is recorded so tests can assert on the prompt
that was sent.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.llm.provider import LLMResponse

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(relative_path: str) -> str:
    return (FIXTURES / relative_path).read_text(encoding="utf-8")


@dataclass
class FakeCall:
    system: str
    user: str
    json_schema: dict[str, Any]
    temperature: float


@dataclass
class FakeLLMProvider:
    replies: list[str | Exception]
    model_name: str = "gemini-3.5-flash-lite"
    input_tokens: int = 1200
    output_tokens: int = 400
    calls: list[FakeCall] = field(default_factory=list)

    @property
    def model(self) -> str:
        return self.model_name

    async def generate_json(
        self, *, system: str, user: str, json_schema: dict[str, Any], temperature: float
    ) -> LLMResponse:
        self.calls.append(FakeCall(system, user, json_schema, temperature))
        if not self.replies:
            raise AssertionError("FakeLLMProvider: no more queued replies")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(
            text=reply,
            model=self.model_name,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
        )


# ---- Phase 3 fakes ----------------------------------------------------------------------


@dataclass
class InMemoryStorage:
    objects: dict[str, tuple[bytes, str]] = field(default_factory=dict)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def get(self, key: str) -> bytes:
        return self.objects[key][0]

    async def signed_url(self, key: str, expires_s: int = 300) -> str:
        return f"http://storage.test/{key}?expires={expires_s}"


@dataclass
class FakeQueue:
    jobs: list[tuple[str, tuple[Any, ...], str]] = field(default_factory=list)

    async def enqueue(self, function: str, *args: Any, job_id: str) -> None:
        self.jobs.append((function, args, job_id))


def make_pdf(text: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()  # type: ignore[no-untyped-call]
    page = doc.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=9)
    data: bytes = doc.tobytes()
    doc.close()
    return data


def make_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    import io

    import docx

    document = docx.Document()
    for p in paragraphs:
        document.add_paragraph(p)
    if table:
        t = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
