from __future__ import annotations

from pathlib import Path


def _allowed_roots() -> tuple[Path, Path]:
    return (Path.home().resolve(), Path.cwd().resolve())


def _is_under_allowed(path: Path) -> bool:
    rp = path.resolve()
    for root in _allowed_roots():
        try:
            rp.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def convert_local_pdf_to_docx(input_pdf: str, output_docx: str = "") -> str:
    """
    将本地 PDF 转为 .docx。仅允许主目录或当前工作目录下的路径（解析后），防路径穿越。

    output_docx 为空时，在与 PDF 同目录下生成同名 .docx。
    """
    raw_in = (input_pdf or "").strip()
    if not raw_in:
        return "错误：input_pdf 为空。请提供本机 PDF 的绝对路径或相对当前目录的路径。"

    pdf_path = Path(raw_in).expanduser()
    if not pdf_path.is_absolute():
        pdf_path = (Path.cwd() / pdf_path).resolve()
    else:
        pdf_path = pdf_path.resolve()

    if not pdf_path.is_file():
        return f"错误：找不到文件：{pdf_path}"
    if pdf_path.suffix.lower() != ".pdf":
        return "错误：仅支持 .pdf 文件。"

    if not _is_under_allowed(pdf_path):
        return (
            "错误：出于安全考虑，仅允许转换「用户主目录」或「当前工作目录」下的 PDF。"
            f"当前文件解析为：{pdf_path}"
        )

    out_raw = (output_docx or "").strip()
    if out_raw:
        out_path = Path(out_raw).expanduser()
        if not out_path.is_absolute():
            out_path = (Path.cwd() / out_path).resolve()
        else:
            out_path = out_path.resolve()
        if out_path.suffix.lower() != ".docx":
            out_path = out_path.with_suffix(".docx")
    else:
        out_path = pdf_path.with_suffix(".docx")

    if not _is_under_allowed(out_path):
        return (
            "错误：输出路径必须在用户主目录或当前工作目录下。"
            f"当前解析为：{out_path}"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import logging

        from pdf2docx import Converter

        # pdf2docx 在 import 时会 basicConfig(level=INFO)，把 root 拉回 INFO；这里压回 WARNING 减少刷屏
        logging.getLogger().setLevel(logging.WARNING)

        cv = Converter(str(pdf_path))
        try:
            cv.convert(str(out_path))
        finally:
            cv.close()
    except Exception as e:
        return f"转换失败：{e}"

    if not out_path.is_file():
        return "转换结束但未生成输出文件，请检查 PDF 是否损坏或受密码保护。"

    return f"转换成功。Word 文件已保存为：{out_path}"
