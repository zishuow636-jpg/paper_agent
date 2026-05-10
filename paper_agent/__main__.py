from __future__ import annotations

import argparse
import sys

try:
    import readline  # noqa: F401  — 启用行编辑与方向键历史（若系统可用）
except ImportError:
    readline = None  # type: ignore[misc, assignment]

from paper_agent.agent_loop import run_agent


def _format_agent_error(exc: BaseException) -> str:
    msg = str(exc)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
        return (
            "Gemini API 配额或频率已达上限（常见于免费层「每日每模型请求次数」用尽，"
            "或短时间内请求过密）。\n"
            "处理办法：稍后再试；换用其它有额度的模型名；或在 Google AI Studio 开通/绑定付费计划以提升限额。\n"
            "说明文档：https://ai.google.dev/gemini-api/docs/rate-limits\n"
            "（技术详情）" + msg
        )
    return msg


_BANNER = """
论文检索 Agent（Gemini + arXiv + PubMed）
输入问题后回车即可；内置少量命令（以 / 开头）。
输入 /help 查看说明，/quit 退出。
"""

_HELP = """命令说明
  /help     显示本说明
  /quit     退出程序（同 quit、exit）
  /clear    清空本会话「追问上下文」（不影响已打印结果）
  /paste    多行粘贴：随后粘贴内容，单独一行输入 END 并回车结束

直接输入文字则视为检索问题（单行）。连续追问时会带上最近几轮简要上下文。
若要把本机 PDF 转成 Word，请说明路径（须在用户主目录或当前终端工作目录下）。若提供 **http(s) 的 PDF 直链**，会先下载再转 Word。若提供 **PubMed 的 PMID**，会尝试通过 Europe PMC 获取开放获取 PDF 再转 Word（闭源文献可能无法自动下载）。
"""


def _read_paste_block(end_token: str = "END") -> str:
    print(f"多行粘贴模式：结束后请单独一行输入 {end_token} 并回车。\n")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            return ""
        if line.strip() == end_token:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _with_session_context(user_msg: str, transcript: list[tuple[str, str]], *, max_pairs: int = 3) -> str:
    if not transcript:
        return user_msg
    parts = [
        "以下为同一会话中此前的问答（仅作上下文，请重点回答最后一个「当前问」）。"
    ]
    for u, a in transcript[-max_pairs:]:
        short = a if len(a) <= 2000 else a[:2000] + "…"
        parts.append(f"问：{u}\n答：{short}")
    parts.append(f"当前问：{user_msg}")
    return "\n\n".join(parts)


def _interactive() -> int:
    print(_BANNER.strip())
    transcript: list[tuple[str, str]] = []
    while True:
        try:
            line = input("论文Agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0
        if not line:
            continue
        low = line.lower()
        if low in ("/quit", "/exit", "quit", "exit", "q"):
            print("再见。")
            return 0
        if low in ("/help", "help", "/?"):
            print(_HELP)
            continue
        if low == "/clear":
            transcript.clear()
            print("已清空本轮追问上下文。")
            continue
        if low == "/paste":
            user_msg = _read_paste_block()
            if not user_msg:
                print("（未输入内容，已取消）")
                continue
        else:
            user_msg = line

        block = _with_session_context(user_msg, transcript)
        print("\n…检索与生成中，请稍候…\n")
        try:
            out = run_agent(block)
        except Exception as e:
            print(_format_agent_error(e) + "\n")
            continue
        print(out)
        print()
        transcript.append((user_msg, out))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="论文检索 CLI Agent（Gemini + arXiv + PubMed）")
    p.add_argument(
        "query",
        nargs="?",
        default="",
        help="检索问题；省略则进入交互式 REPL",
    )
    args = p.parse_args(argv)
    q = (args.query or "").strip()
    if not q:
        return _interactive()
    try:
        print(run_agent(q))
    except Exception as e:
        print(_format_agent_error(e))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
