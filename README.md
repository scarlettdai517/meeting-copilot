# Meeting Copilot

AI 会议智能助手：输入会议转写文本，自动生成按角色区分的结构化纪要，并支持基于会议内容的智能问答。

**在线体验（Streamlit Community Cloud）**  
<!-- 部署完成后将链接填入下方 -->
> 链接：https://meeting-copilot-yulin-dai.streamlit.app/  

---

## 功能概览

- **结构化纪要生成**：选择模板、粘贴转写、一键生成 JSON 结构化纪要并渲染为 Markdown。
- **五类会议模板**：通用纪要、技术执行、业务增长与产品、高管决策简报、外部协作与商务；每类模板板块不同，适配不同角色与场景。
- **多模型支持**：支持 OpenAI、Claude、Gemini、DeepSeek、智谱、Moonshot；在页面配置 API Key 与模型即可切换，纪要与问答共用同一模型。
- **Smart RAG 智能问答**：基于会议内容的自然语言问答；短会全文、长会分块 + 语义检索与动态 Top-K，带 Embedding 缓存。
- **质量检查**：对纪要做可执行性与可追溯性检查（如 Owner/Due/Evidence、决策与风险覆盖等），并给出评分与建议。
- **导出与历史**：支持 JSON 全量导出、按模板导出列表 CSV；历史会议本地存储，可加载后继续问答。

---

## 本地运行

```bash
# 克隆后进入项目目录
cd meeting-copilot

# 安装依赖
pip install -r requirements.txt

# 启动应用（可选：在 .env 中配置 LLM_PROVIDER、OPENAI_API_KEY 等）
streamlit run app.py
```

浏览器打开 http://localhost:8501/，在侧栏选择模型并在「配置当前模型 API」中填写 API Key 后即可使用。

---

## 技术栈

- 前端 / 服务：Streamlit  
- 大模型：多提供商统一接口（OpenAI API 兼容），通过 Prompt 工程（Schema、Few-Shot、CoT）约束结构化输出  
- 问答：语义检索（Embedding + 余弦相似度）、长会分块与 Top-K 检索、Embedding 缓存  
- 数据：本地 JSON 存储（纪要与历史），可选 .env 与页面内配置 API

---

## 项目结构（核心文件）

| 文件 | 说明 |
|------|------|
| `app.py` | Streamlit 主应用：模板选择、输入、生成、历史、问答、质量检查、导出 |
| `extract.py` | 按模板调用 LLM 生成纪要（Schema + Prompt + CoT） |
| `templates.py` | 五类模板定义：板块、JSON Schema、提炼指引、中英文标题 |
| `llm.py` / `providers.py` | 多模型统一入口与各提供商实现 |
| `smart_rag.py` | 基于会议内容的智能问答（RAG） |
| `quality_check.py` | 纪要质量检查（可执行性、可追溯性、Coverage） |
| `render.py` / `export_utils.py` | Markdown 渲染与 JSON/CSV 导出 |
| `data/meetings/` | 本地会议记录存储 |

---

## 部署说明（Streamlit Community Cloud）

1. 将本项目推送到 GitHub（可私有仓库）。  
2. 在 [share.streamlit.io](https://share.streamlit.io) 用 GitHub 登录，选择该仓库，主文件设为 `app.py`，部署。  
3. 在应用的 Settings → Secrets 中配置所需环境变量（如 `OPENAI_API_KEY`、`LLM_PROVIDER` 等）。  
4. 部署完成后，将应用链接填入本 README 顶部的「在线体验」处即可。

---

## License

MIT（或按你的选择填写）
