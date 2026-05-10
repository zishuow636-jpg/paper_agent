from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx

ARXIV_API = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}


def search_arxiv(query: str, max_results: int = 8) -> str:
    """检索 arXiv，返回给人读的多行文本（含标题、链接、摘要片段）。"""
    q = query.strip()
    if not q:
        return "query 为空。"
    n = max(1, min(int(max_results), 25))
    url = f"{ARXIV_API}?search_query=all:{quote_plus(q)}&start=0&max_results={n}"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
    root = ET.fromstring(r.text)
    lines: list[str] = []
    for entry in root.findall("atom:entry", _NS):
        title_el = entry.find("atom:title", _NS)
        title = (title_el.text or "").strip().replace("\n", " ")
        id_el = entry.find("atom:id", _NS)
        link = (id_el.text or "").strip()
        summ_el = entry.find("atom:summary", _NS)
        summary = (summ_el.text or "").strip().replace("\n", " ")
        summary = textwrap.shorten(summary, width=400, placeholder="…")
        pub_el = entry.find("atom:published", _NS)
        published = (pub_el.text or "").strip()[:10]
        lines.append(f"- {title}\n  时间: {published}\n  链接: {link}\n  摘要: {summary}\n")
    if not lines:
        return "未找到条目（可尝试换英文关键词或更具体的主题）。"
    return "arXiv 结果：\n" + "\n".join(lines)
