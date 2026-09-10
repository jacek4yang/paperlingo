# PaperLingo

把论文中没看懂的英文放到这里。我们不只翻译它，还会把它拆开讲明白。

PaperLingo 是一个面向中文母语论文阅读者的 Windows 桌面工具：把难懂的英文学术论文句子拆解成**精准翻译 + 句子结构 + 语法 + 单词 + 短语 + 学术表达 + 专业概念 + 阅读思路**，并把阅读过程沉淀成个人英语知识库。

## 工作流

```text
输入论文英文 → 生成 Prompt → 复制到 ChatGPT / Claude / Grok / Gemini 等Web AI
→ AI 返回 JSON → 粘贴回 PaperLingo → 交互式拆解展示 → 收藏知识点 → 长期复习
```

第一版不依赖任何 LLM API——你只需要一个能联网的 Web AI 对话框。

## 当前功能

- **阅读页**：粘贴英文原句/段落（支持上下文、论文标题/DOI、研究领域、分析深度），一键生成并复制结构化 Prompt
- **结果解析**：粘贴 Web AI 返回内容，自动提取 JSON（支持 Markdown 围栏、前后噪声文本、BOM、常见截断），Pydantic 严格校验，失败时给出错误位置与"复制修复 Prompt"
- **交互式句子**：原句按语法角色着色（主语/谓语/宾语/从句……），悬停查看，点击跳转对应卡片
- **渐进式展示**：先翻译 + 核心含义 + 句子主干，再展开结构、语法、单词、短语、学术表达、指代、概念、易错理解
- **知识库**：单词/短语/语法/学术表达/概念/句型自动沉淀，同一条目去重并累计出现次数、来源论文
- **复习**：认识/不熟/不会三态标记，不熟与不会进入队列，SM-2 风格间隔复习（接口抽象，未来可换 FSRS）
- **历史记录**：全文搜索、按论文筛选、收藏、恢复完整分析界面、重新分析
- **草稿自动保存**：页面切换、异常退出不丢原文
- **主题**：浅色 / 深色 / 跟随系统，高 DPI 支持

## 截图

（见 `assets/screenshots/`）

## 开发环境

- Windows 10/11
- [uv](https://docs.astral.sh/uv/)（唯一的包管理工具，不需要手动激活虚拟环境，不需要单独安装 Python 之外的任何东西）

### 安装 uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 同步依赖

```powershell
uv sync
```

`uv sync` 会根据 `pyproject.toml` + `uv.lock` 自动创建 `.venv`、安装锁定版本的依赖（Python、PyQt6、pydantic 等全部自动就位）。**不需要手动激活虚拟环境，不需要单独安装 PyQt 或 Qt**——`uv run` 会自动使用项目环境。

### 运行程序

```powershell
uv run python -m paperlingo
```

### 运行测试

```powershell
uv run pytest
```

### 代码检查

```powershell
uv run ruff check .
uv run ruff format --check .
```

### 打包

```powershell
.\scripts\build.ps1
```

产物：`dist\PaperLingo\PaperLingo.exe`（免安装，双击即用；不需要 Python / Qt / uv）。

## 目录结构

```text
src/paperlingo/
├─ app.py               # 应用启动
├─ domain/              # 领域模型（AI Schema、学习模型、论文信息）
├─ prompt/              # Prompt 模板（版本化）/ Profile / 编译器
├─ parser/              # AI Response 解析与有限修复
├─ database/            # SQLite（迁移、参数化查询的仓库层）
├─ learning/            # 复习调度器（可替换 FSRS）
├─ services/            # 剪贴板、设置、草稿
└─ ui/                  # 主窗口、页面、组件、主题
tests/                  # pytest（通过 uv 运行）
scripts/build.ps1       # 打包脚本
```

## LLM Response Protocol

AI 只返回结构化 JSON（当前 `schema_version = "1.0"`，见 `src/paperlingo/domain/analysis.py` 中的 `PaperAnalysis`）。程序绝不渲染 AI 返回的 HTML/CSS/Markdown——所有展示由 PaperLingo 自己的组件完成。原始 AI Response 永久保存在数据库中，可随时回看。

Prompt 模板版本：`paper_analysis_v1`（见 `src/paperlingo/prompt/templates.py`）。

## 数据存储位置

- 数据库：`%APPDATA%\PaperLingo\paperlingo.db`
- 草稿：`%APPDATA%\PaperLingo\draft.json`

## License 注意事项

本项目代码以 MIT 许可发布。**PyQt6 采用 GPL v3 / 商业双许可**：个人使用与配合本项目开源分发没有问题；若你闭源分发基于 PyQt6 的程序，需要遵守 GPL v3 或向 [Qt 公司](https://www.qt.io/licensing/)购买商业许可。

## Roadmap

- [ ] 一键直连 OpenAI / Anthropic / Gemini / 自定义 API（架构已预留 Provider 层）
- [ ] FSRS 正式接入（`Scheduler` 接口已抽象）
- [ ] PDF 拖入自动取句
- [ ] 导入 / 导出 Anki 卡组
