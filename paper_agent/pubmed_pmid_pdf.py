from __future__ import annotations

import re
from typing import Any

import httpx

from paper_agent.download_pdf_convert import download_pdf_url_to_docx

_EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _normalize_pmid(raw: str) -> str | None:
    s = (raw or "").strip()
    if not s:
        return None
    m = re.search(r"\b(\d{5,9})\b", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d{5,9}", s):
        return s
    return None


def _flatten_full_text_urls(ft: Any) -> list[dict[str, Any]]:
    if not ft or not isinstance(ft, dict):
        return []
    raw = ft.get("fullTextUrl")
    if raw is None:
        return []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _pdf_urls_from_epmc_result(rec: dict[str, Any]) -> list[str]:
    """按优先级收集可尝试的 PDF 直链（多为 OA）。"""
    urls: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        u = (u or "").strip()
        if not u or u in seen:
            return
        seen.add(u)
        urls.append(u)

    for entry in _flatten_full_text_urls(rec.get("fullTextUrlList")):
        if (entry.get("documentStyle") or "").lower() != "pdf":
            continue
        if (entry.get("availabilityCode") or "").upper() not in ("OA", "F", "H"):
            # OA=开放获取；F/H 为部分免费/混合，仍可能有可用 PDF
            if (entry.get("availabilityCode") or "").upper() == "S":
                continue
        u = entry.get("url")
        if isinstance(u, str) and u.startswith(("http://", "https://")):
            add(u)

    # 若有 PMCID，补 Europe PMC 官方 PDF 入口（常与 fullTextUrl 重复，会去重）
    pmcid = rec.get("pmcid")
    if isinstance(pmcid, str) and pmcid.upper().startswith("PMC"):
        add(f"https://europepmc.org/articles/{pmcid}?pdf=render")

    # 优先 Europe PMC / NCBI 域，再试出版社直链（部分需 Cookie 会失败）
    def score(u: str) -> tuple[int, str]:
        h = httpx.URL(u).host or ""
        if "europepmc.org" in h or "ebi.ac.uk" in h:
            return (0, u)
        if "nih.gov" in h or "ncbi.nlm.nih.gov" in h:
            return (1, u)
        return (2, u)

    urls.sort(key=score)
    return urls


def resolve_pubmed_pmid_to_pdf_urls(pmid: str) -> tuple[str | None, list[str]]:
    """
    用 Europe PMC 按 PMID 查记录并提取 PDF URL 列表。
    返回 (规范化 pmid 或 None, url 列表)。
    """
    norm = _normalize_pmid(pmid)
    if not norm:
        return None, []

    query = f"EXT_ID:{norm} AND SRC:MED"
    params = {
        "query": query,
        "format": "json",
        "pageSize": 5,
        "resultType": "core",
    }
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(_EPMC_SEARCH, params=params)
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return norm, []

    results = (data.get("resultList") or {}).get("result") or []
    if not isinstance(results, list):
        results = []

    for rec in results:
        if not isinstance(rec, dict):
            continue
        rec_pmid = str(rec.get("pmid") or "").strip()
        if rec_pmid and rec_pmid != norm:
            continue
        urls = _pdf_urls_from_epmc_result(rec)
        if urls:
            return norm, urls

    return norm, []


def download_pubmed_pmid_to_docx(pmid: str, output_docx: str = "") -> str:
    """
    根据 PubMed PMID 尝试获取开放获取 PDF 并转为 Word。
    依赖 Europe PMC 提供的 PDF 链接；无 OA / 无 PDF 时会说明原因。
    """
    norm, urls = resolve_pubmed_pmid_to_pdf_urls(pmid)
    if not norm:
        return "错误：无法识别 PMID。请提供 5～9 位数字，例如 30384843。"

    if not urls:
        return (
            f"未找到 PMID {norm} 的可下载 PDF（Europe PMC 无开放获取 PDF 链接）。"
            "常见原因：期刊闭源、仅摘要入 PubMed、或尚未收录到 Europe PMC。"
            "可改用「期刊官网 PDF 直链」调用 download_pdf_url_to_docx，或自行下载后用 convert_local_pdf_to_docx。"
        )

    last_err = ""
    for u in urls:
        out = download_pdf_url_to_docx(u, output_docx)
        if out.startswith("转换成功"):
            return f"PMID {norm}：{out}"
        last_err = out

    return f"PMID {norm}：已尝试 {len(urls)} 个 PDF 链接均未成功。最后一次详情：\n{last_err}"
