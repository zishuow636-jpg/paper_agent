from __future__ import annotations

from typing import Any

import httpx

from paper_agent.config import ncbi_email, ncbi_tool

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def _ncbi_params(extra: dict[str, Any]) -> dict[str, Any]:
    p: dict[str, Any] = {"tool": ncbi_tool(), **extra}
    email = ncbi_email()
    if email:
        p["email"] = email
    return p


def search_pubmed(query: str, max_results: int = 8) -> str:
    """检索 PubMed，返回标题、期刊、年份、PMID、摘要片段等文本。"""
    q = query.strip()
    if not q:
        return "query 为空。"
    n = max(1, min(int(max_results), 25))
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r = client.get(
            ESEARCH,
            params=_ncbi_params(
                {
                    "db": "pubmed",
                    "term": q,
                    "retmax": n,
                    "retmode": "json",
                }
            ),
        )
        r.raise_for_status()
        data = r.json()
    idlist = data.get("esearchresult", {}).get("idlist") or []
    if not idlist:
        return "PubMed 无结果（可尝试 MeSH/英文术语或缩小范围）。"
    ids = ",".join(idlist)
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        r2 = client.get(
            ESUMMARY,
            params=_ncbi_params(
                {
                    "db": "pubmed",
                    "id": ids,
                    "retmode": "json",
                }
            ),
        )
        r2.raise_for_status()
        sm = r2.json()
    result = sm.get("result", {})
    lines: list[str] = []
    for pmid in idlist:
        rec = result.get(pmid)
        if not isinstance(rec, dict):
            continue
        title = (rec.get("title") or "").strip()
        source = (rec.get("source") or "").strip()
        pubdate = (rec.get("pubdate") or "").strip()
        # esummary 的摘要字段因记录类型而异，这里用较长字段兜底
        excerpt = (
            (rec.get("elocationid") or "")
            or (rec.get("sorttitle") or "")
            or ""
        )
        if not excerpt and rec.get("authors"):
            authors = rec.get("authors", [])
            if isinstance(authors, list) and authors:
                names = [a.get("name", "") for a in authors[:3] if isinstance(a, dict)]
                excerpt = "作者: " + ", ".join(names)
        lines.append(
            f"- {title}\n  期刊/来源: {source}  发表: {pubdate}  PMID: {pmid}\n"
            f"  线索: {excerpt}\n"
        )
    if not lines:
        return "PubMed 有 ID 但未能解析详情，请稍后重试。"
    return "PubMed 结果：\n" + "\n".join(lines)
