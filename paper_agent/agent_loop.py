from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from paper_agent.config import gemini_api_key, gemini_model
from paper_agent.download_pdf_convert import download_pdf_url_to_docx
from paper_agent.pdf_to_docx import convert_local_pdf_to_docx
from paper_agent.pubmed_pmid_pdf import download_pubmed_pmid_to_docx
from paper_agent.search_arxiv import search_arxiv
from paper_agent.search_pubmed import search_pubmed

for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.WARNING)

_SYSTEM = """你是「论文检索助手」，擅长计算机科学与生物医学工程方向的文献检索，并可在用户需要时协助 PDF/Word 相关操作。

何时**不要**调用工具：
- 闲聊、问候、概念解释、学习方法、对之前回答的追问与澄清等，直接用中文自然语言回答即可。
- 不要为了「显得专业」而主动调用工具。

何时**需要**调用工具（仅在实际需要时）：
1) 用户**明确要查论文/文献/最新进展**等：用 search_arxiv 和/或 search_pubmed 获取真实结果，**禁止编造**论文条目。
   - CS、AI、数学、物理预印本优先 arXiv；医学、临床、生物医学工程优先 PubMed。
2) 用户**明确要**把本机 PDF 转 Word：convert_local_pdf_to_docx（路径须在主目录或当前工作目录下）。
3) 用户给出 **http(s) PDF 直链** 并要求下载转 Word：download_pdf_url_to_docx。
4) 用户给出 **PMID** 并要求下载/转 Word：download_pubmed_pmid_to_docx（无开放获取时会失败，需如实说明）。

使用工具后的回答：用中文，保留工具返回的链接或 PMID，并简要说明相关性。
"""


def _arxiv_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "英文或常用 arXiv 检索式关键词。",
            },
            "max_results": {
                "type": "integer",
                "description": "返回条数，1-25，默认 8。",
            },
        },
        "required": ["query"],
    }


def _pubmed_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "PubMed 检索式，可用英文主题词或作者等。",
            },
            "max_results": {
                "type": "integer",
                "description": "返回条数，1-25，默认 8。",
            },
        },
        "required": ["query"],
    }


def _pdf_to_docx_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "input_pdf": {
                "type": "string",
                "description": "本机 PDF 路径（绝对路径，或相对当前工作目录）。须位于用户主目录或当前工作目录下。",
            },
            "output_docx": {
                "type": "string",
                "description": "可选，输出 .docx 路径；留空则与 PDF 同目录同名。",
            },
        },
        "required": ["input_pdf"],
    }


def _download_pdf_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "指向 PDF 文件的 http(s) 直链（例如 arxiv.org/pdf/...）。不支持 file:// 或内网地址。",
            },
            "output_docx": {
                "type": "string",
                "description": "可选，输出 .docx 的绝对或相对路径；留空则保存在 ~/.paper_agent/downloads/ 下与临时 PDF 同名。",
            },
        },
        "required": ["url"],
    }


def _pmid_to_docx_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "pmid": {
                "type": "string",
                "description": "PubMed 文献 ID（PMID），5～9 位数字，可含在句子中由你提取。",
            },
            "output_docx": {
                "type": "string",
                "description": "可选，输出 .docx 路径；规则同 download_pdf_url_to_docx。",
            },
        },
        "required": ["pmid"],
    }


def _tool() -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_arxiv",
                description="在 arXiv 上按关键词检索预印本论文（偏 CS/AI/数学/物理）。",
                parameters_json_schema=_arxiv_schema(),
            ),
            types.FunctionDeclaration(
                name="search_pubmed",
                description="在 PubMed 上检索生物医学与医学工程相关论文。",
                parameters_json_schema=_pubmed_schema(),
            ),
            types.FunctionDeclaration(
                name="convert_local_pdf_to_docx",
                description="将用户本机上的 PDF 转为 Word（.docx）。仅允许主目录或当前工作目录下的路径。",
                parameters_json_schema=_pdf_to_docx_schema(),
            ),
            types.FunctionDeclaration(
                name="download_pdf_url_to_docx",
                description="从 http(s) 链接下载 PDF 并转为 Word（.docx）。链接须为公网可访问的 PDF 直链；有体积与 SSRF 防护。",
                parameters_json_schema=_download_pdf_schema(),
            ),
            types.FunctionDeclaration(
                name="download_pubmed_pmid_to_docx",
                description="根据 PubMed PMID 从 Europe PMC 获取开放获取 PDF 并转为 Word。无 OA 时会失败并提示原因。",
                parameters_json_schema=_pmid_to_docx_schema(),
            ),
        ]
    )


def _int_default(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _normalize_args(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    return dict(raw)


def _dispatch(name: str, args: dict[str, Any]) -> str:
    if name == "search_arxiv":
        return search_arxiv(
            str(args.get("query", "")),
            _int_default(args.get("max_results"), 8),
        )
    if name == "search_pubmed":
        return search_pubmed(
            str(args.get("query", "")),
            _int_default(args.get("max_results"), 8),
        )
    if name == "convert_local_pdf_to_docx":
        return convert_local_pdf_to_docx(
            str(args.get("input_pdf", "")),
            str(args.get("output_docx", "") or ""),
        )
    if name == "download_pdf_url_to_docx":
        return download_pdf_url_to_docx(
            str(args.get("url", "")),
            str(args.get("output_docx", "") or ""),
        )
    if name == "download_pubmed_pmid_to_docx":
        return download_pubmed_pmid_to_docx(
            str(args.get("pmid", "")),
            str(args.get("output_docx", "") or ""),
        )
    return f"未知工具: {name}"


def run_agent(user_message: str, *, max_tool_rounds: int = 6) -> str:
    client = genai.Client(api_key=gemini_api_key())
    model = gemini_model()
    tool = _tool()
    history: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)],
        )
    ]
    config = types.GenerateContentConfig(
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.AUTO,
            ),
        ),
        system_instruction=_SYSTEM,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True,
        ),
    )
    last_text = ""
    response: types.GenerateContentResponse | None = None
    for _ in range(max_tool_rounds):
        response = client.models.generate_content(
            model=model,
            contents=history,
            config=config,
        )
        if not response.candidates:
            return "模型未返回候选（可能被安全策略拦截）。请换更中性的检索问题重试。"
        fcs = list(response.function_calls or [])
        if not fcs:
            last_text = (response.text or "").strip()
            break
        model_content = response.candidates[0].content
        if model_content:
            history.append(model_content)
        tool_parts: list[types.Part] = []
        for fc in fcs:
            name = fc.name
            # google-genai：function_calls 项为 FunctionCall，参数在 .args
            raw_args = getattr(fc, "args", None)
            if raw_args is None:
                fc_body = getattr(fc, "function_call", None)
                if fc_body is not None:
                    raw_args = getattr(fc_body, "args", None)
            args = _normalize_args(raw_args)
            payload = _dispatch(name, args)
            tool_parts.append(
                types.Part.from_function_response(
                    name=name,
                    response={"content": payload},
                )
            )
        history.append(types.Content(role="tool", parts=tool_parts))
    if last_text:
        return last_text
    if response is not None and (response.text or "").strip():
        return response.text.strip()
    return "模型未返回文本（可能被安全策略拦截或无候选）。请换更中性的检索问题重试。"
