"""Manually test one job posting against the real Gemini API.

Usage:
    python -m app.scripts.try_extract path/to/posting.txt
"""

import asyncio
import sys

from app.config import settings
from app.services.llm.gemini_client import GeminiClient


async def main(path: str) -> None:
    text = open(path, encoding="utf-8").read()
    client = GeminiClient(api_key=settings.gemini_api_key, model=settings.llm_model)
    analysis = await client.analyze(text, json_ld_hints=None)
    print(analysis.model_dump_json(indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
