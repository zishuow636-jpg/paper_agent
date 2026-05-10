# Paper Agent（论文检索 CLI）

基于 **Google Gemini** 的本地命令行 Agent：支持 **arXiv / PubMed** 检索、**PDF → Word**、**直链下载转 Word**、**PMID 开放获取 PDF 转 Word**；可选交互式多轮对话（带简短会话上下文）。

## 功能概览

| 能力 | 说明 |
|------|------|
| 文献检索 | 工具 `search_arxiv`、`search_pubmed`（真实 API，禁止模型编造条目） |
| 本地 PDF → Word | `convert_local_pdf_to_docx`（路径须在用户主目录或当前工作目录） |
| 链接 PDF → Word | `download_pdf_url_to_docx`（http/https，有体积与 SSRF 防护） |
| PMID → Word | `download_pubmed_pmid_to_docx`（经 Europe PMC 解析 OA PDF；闭源文献可能无法下载） |
| 交互 CLI | `/help`、`/quit`、`/clear`、`/paste`；闲聊可不调用工具（工具模式为 `AUTO`） |

## 环境要求

- **Python 3.12**（推荐；仓库含 `.python-version`）
- 网络可访问：Google Gemini API、arXiv、PubMed（NCBI）、Europe PMC（PMID 流程），以及你提供的 PDF 直链域名

## 安装

```bash
cd /path/to/Agent
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

- **`GEMINI_API_KEY`**：在 [Google AI Studio](https://aistudio.google.com/apikey) 创建（必填）
- **`GEMINI_MODEL`**：例如 `gemini-2.5-flash`（以 Studio 中可用模型为准）
- **`NCBI_EMAIL`**：选填，便于 NCBI 合理使用与联系

## 使用方式

**一次性提问（非交互）：**

```bash
source .venv/bin/activate
python -m paper_agent "请检索 PubMed 上 wearable ECG 的论文，并简要中文总结"
```

**交互式 REPL：**

```bash
python -m paper_agent
```

出现 `论文Agent> ` 后输入问题；内置命令见 `/help`。多行输入用 `/paste`，结束时单独一行输入 `END`。

## 配额与费用

Gemini 通过 **Google AI Studio / 项目计费** 限流；免费层对单模型常有 **RPD（每日请求数）** 等限制。若出现 **429 / RESOURCE_EXHAUSTED**，请到 [速率与配额说明](https://ai.google.dev/gemini-api/docs/rate-limits) 与 [用量面板](https://ai.dev/rate-limit) 查看。

**说明**：每轮用户消息及多轮工具编排可能产生 **多次** `generateContent` 调用，容易较快触达日限额。

## 安全说明

- **本地 / 输出路径**：仅允许落在 **用户主目录**或**启动终端时的当前工作目录**（解析后的绝对路径）。
- **下载链接**：拒绝内网、环回等地址；单文件下载上限 **50MB**；校验 PDF 文件头 `%PDF`。
- **勿将 `.env` 提交到 Git**（已列入 `.gitignore`）。

## 项目结构

```
Agent/
├── .env.example
├── requirements.txt
├── paper_agent/
│   ├── __main__.py          # CLI 入口
│   ├── agent_loop.py        # Gemini + 工具循环
│   ├── config.py
│   ├── search_arxiv.py
│   ├── search_pubmed.py
│   ├── pdf_to_docx.py
│   ├── download_pdf_convert.py
│   └── pubmed_pmid_pdf.py
└── README.md
```

## 第三方与合规

- 使用 **arXiv、NCBI E-utilities、Europe PMC** 等接口时请遵守各自服务条款与访问频率。
- **PDF → Word** 使用 [pdf2docx](https://github.com/dothinking/pdf2docx)；复杂排版、扫描件、加密 PDF 可能效果不佳或失败。

## 许可证

若仓库根目录另有 `LICENSE` 以该文件为准；若无，建议仅作个人学习使用。
