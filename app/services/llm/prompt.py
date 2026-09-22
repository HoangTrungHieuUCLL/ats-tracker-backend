import json
from pathlib import Path

PROMPT_VERSION = "v1"

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / f"extract_{PROMPT_VERSION}.md"
SYSTEM_INSTRUCTION = _PROMPT_PATH.read_text()


def build_user_content(job_text: str, json_ld_hints: dict | None) -> str:
    hints_block = ""
    if json_ld_hints:
        filtered = {k: v for k, v in json_ld_hints.items() if v}
        if filtered:
            hints_block = (
                "json_ld_hints: " + json.dumps(filtered, ensure_ascii=False, default=str) + "\n\n"
            )
    return f"{hints_block}<job_posting>\n{job_text}\n</job_posting>"
