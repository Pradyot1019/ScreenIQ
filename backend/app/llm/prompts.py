"""Versioned prompt files.

Prompts live in `app/llm/prompts/<name>_v<N>.md`, never inline in Python. A prompt
change is a new file (jd_parse_v2.md), not an edit, so every llm_calls row and every
eval report says exactly which prompt produced it, and versions can be A/B compared.

File format:
    ## System
    ...instructions...
    ## User
    ...template with {{placeholders}}...
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    system: str
    user_template: str

    @property
    def id(self) -> str:
        """What gets stored in llm_calls.prompt_version, e.g. "jd_parse_v1"."""
        return f"{self.name}_v{self.version}"

    def render(self, **variables: str) -> tuple[str, str]:
        """Returns (system, user). Every {{placeholder}} must be supplied, and no extras."""
        expected = set(_PLACEHOLDER.findall(self.user_template))
        if expected != set(variables):
            raise ValueError(f"{self.id} expects {sorted(expected)}, got {sorted(variables)}")
        user = _PLACEHOLDER.sub(lambda m: variables[m.group(1)], self.user_template)
        return self.system, user


@cache
def load_prompt(name: str, version: int) -> Prompt:
    text = (PROMPTS_DIR / f"{name}_v{version}.md").read_text(encoding="utf-8")
    match = re.search(r"^## System\s*$(.*?)^## User\s*$(.*)", text, re.S | re.M)
    if not match:
        raise ValueError(f"{name}_v{version}.md needs '## System' and '## User' sections")
    return Prompt(name, version, match.group(1).strip(), match.group(2).strip())
