from __future__ import annotations

import ipaddress
import re
import socket
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from paper_agent.pdf_to_docx import convert_local_pdf_to_docx

# 单次下载上限（字节）
_MAX_BYTES = 50 * 1024 * 1024

_USER_AGENT = "paper-agent/1.0 (+https://arxiv.org)"


def _blocked_host(hostname: str | None) -> str | None:
    """若主机名不应被访问则返回原因，否则返回 None。"""
    if not hostname:
        return "缺少主机名"
    host = hostname.strip().lower().strip(".")
    if host in ("localhost", "0.0.0.0"):
        return "禁止访问本地环回或保留主机名"
    try:
        ip = ipaddress.ip_address(host)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            return "禁止访问内网或保留 IP"
        return None
    except ValueError:
        pass
    if host in ("metadata.google.internal",):
        return "禁止访问元数据类主机名"
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as e:
        return f"无法解析主机名：{e}"
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
        ):
            return "解析到的地址属于内网或保留段，已拒绝（防 SSRF）"
    return None


def _safe_filename_from_url(parsed: object) -> str:
    path = getattr(parsed, "path", "") or ""
    seg = path.rstrip("/").split("/")[-1] or "download"
    seg = re.sub(r"[^\w.\-]", "_", seg)[:120]
    if not seg.lower().endswith(".pdf"):
        seg = f"{seg}.pdf" if seg != "download" else "download.pdf"
    return seg


def download_pdf_url_to_docx(url: str, output_docx: str = "") -> str:
    """
    从 http(s) 链接下载 PDF，保存到 ~/.paper_agent/downloads/ 后转为 Word。
    校验最终 URL 主机，限制体积，并检查 %PDF 文件头。
    """
    raw = (url or "").strip()
    if not raw:
        return "错误：url 为空。"

    try:
        parsed = urlparse(raw)
    except ValueError as e:
        return f"错误：URL 无效：{e}"

    if parsed.scheme not in ("http", "https"):
        return "错误：仅支持 http 或 https 链接。"

    reason = _blocked_host(parsed.hostname)
    if reason:
        return f"错误：{reason}"

    download_dir = Path.home() / ".paper_agent" / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{uuid.uuid4().hex}_{_safe_filename_from_url(parsed)}"
    pdf_path = (download_dir / fname).resolve()

    try:
        with httpx.Client(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            with client.stream("GET", raw) as resp:
                resp.raise_for_status()
                final = urlparse(str(resp.url))
                if final.scheme not in ("http", "https"):
                    return "错误：重定向到了非 http(s) 地址。"
                fr = _blocked_host(final.hostname)
                if fr:
                    return f"错误：重定向目标被拒绝：{fr}"

                total = 0
                with open(pdf_path, "wb") as out:
                    for chunk in resp.iter_bytes():
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > _MAX_BYTES:
                            return f"错误：下载超过上限 {_MAX_BYTES // (1024 * 1024)} MB，已中止。"
                        out.write(chunk)
    except httpx.HTTPStatusError as e:
        pdf_path.unlink(missing_ok=True)
        return f"下载失败：HTTP {e.response.status_code}"
    except httpx.RequestError as e:
        pdf_path.unlink(missing_ok=True)
        return f"下载失败：{e}"
    except OSError as e:
        pdf_path.unlink(missing_ok=True)
        return f"写入临时文件失败：{e}"

    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        pdf_path.unlink(missing_ok=True)
        return "错误：未下载到有效内容。"

    with open(pdf_path, "rb") as f:
        head = f.read(5)
    if not head.startswith(b"%PDF"):
        pdf_path.unlink(missing_ok=True)
        return "错误：下载内容不是 PDF（缺少 %PDF 文件头）。可能是网页或登录页。"

    out_arg = (output_docx or "").strip()
    conv = convert_local_pdf_to_docx(str(pdf_path), out_arg)
    ok = conv.startswith("转换成功")
    if ok:
        try:
            pdf_path.unlink()
        except OSError:
            pass
        return conv + f"\n（已删除临时 PDF：{fname}）"
    return conv + f"\n（临时 PDF 仍保留在：{pdf_path}，便于排查）"
