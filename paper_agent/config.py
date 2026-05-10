from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(
            f"环境变量 {name} 未设置或为空。请在项目根目录 `.env` 里填写（等号后不要留空），"
            "保存文件后重试；不要只改 `.env.example`。"
        )
    return v


def gemini_api_key() -> str:
    return _req("GEMINI_API_KEY")


def gemini_model() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()


def ncbi_email() -> Optional[str]:
    v = os.getenv("NCBI_EMAIL", "").strip()
    return v or None


def ncbi_tool() -> str:
    return os.getenv("NCBI_TOOL", "paper_agent_cli").strip()
