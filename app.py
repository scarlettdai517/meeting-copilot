import os
import glob
import uuid
import json
import hashlib
from datetime import datetime
from quality_check import run_quality_checks

# 导入智能RAG模块
try:
    from smart_rag import answer_question
    SMART_RAG_AVAILABLE = True
except ImportError as e:
    SMART_RAG_AVAILABLE = False
    print(f"⚠️ 智能RAG模块不可用: {e}")
    print(f"   错误详情: {e}")

import streamlit as st
from templates import template_names, get_template_desc
from extract import extract_structured
from render import to_markdown
from export_utils import export_json, action_items_to_csv

# ----------------------------
# Storage (local persistence)
# ----------------------------
DATA_DIR = "data/meetings"
os.makedirs(DATA_DIR, exist_ok=True)

def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "untitled"
    keep = []
    for ch in s:
        if ch.isalnum() or ch in (" ", "-", "_"):
            keep.append(ch)
    s = "".join(keep).strip().replace(" ", "_")
    return s[:60] if len(s) > 60 else s

def save_meeting_record(record: dict) -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = _safe_filename(record.get("title", "untitled"))
    file_id = f"{now}__{title}__{uuid.uuid4().hex[:8]}.json"
    path = os.path.join(DATA_DIR, file_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return file_id

def list_meeting_files() -> list[str]:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")), reverse=True)
    return [os.path.basename(p) for p in files]

def load_meeting_record(file_id: str) -> dict:
    path = os.path.join(DATA_DIR, file_id)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def display_name_from_file(file_id: str) -> str:
    # 形如: 20260212_101112__My_Title__abcd1234.json
    name = file_id.replace(".json", "")
    parts = name.split("__")
    if len(parts) >= 2:
        ts = parts[0]
        title = parts[1].replace("_", " ")
        # ts: YYYYMMDD_HHMMSS
        if "_" in ts and len(ts) >= 15:
            date = ts[:8]
            time = ts[9:15]
            return f"{date} {time} · {title}"
        return f"{ts} · {title}"
    return file_id

# ----------------------------
# Streamlit state init
# ----------------------------
if "template_name" not in st.session_state:
    st.session_state["template_name"] = template_names()[0]
if "meeting_title" not in st.session_state:
    st.session_state["meeting_title"] = "Untitled Meeting"
if "transcript_text" not in st.session_state:
    st.session_state["transcript_text"] = ""
if "result_json" not in st.session_state:
    st.session_state["result_json"] = None
if "last_saved_file" not in st.session_state:
    st.session_state["last_saved_file"] = None
try:
    from providers import (
        get_provider_list,
        is_provider_available,
        get_provider_config_for_ui,
        get_default_model,
        get_model_placeholder,
        provider_has_base_url,
        load_llm_config,
        save_llm_config,
    )
    PROVIDER_OPTIONS = get_provider_list()
except ImportError:
    PROVIDER_OPTIONS = [("openai", "OpenAI (GPT-4o-mini / GPT-4)")]
    def is_provider_available(_): return True
    def get_provider_config_for_ui(_): return {"api_key": "", "base_url": "", "model": ""}
    def get_default_model(_): return "gpt-4o-mini"
    def get_model_placeholder(_): return ""
    def provider_has_base_url(_): return True
    def load_llm_config(): return {}
    def save_llm_config(_): pass

if "llm_provider" not in st.session_state:
    st.session_state["llm_provider"] = os.getenv("LLM_PROVIDER", "openai")

# ----------------------------
# Page UI
# ----------------------------
st.set_page_config(page_title="Meeting Copilot", layout="wide")
st.title("Meeting Copilot 🤖")
st.caption("AI驱动的会议助手 | 结构化纪要生成 + Smart RAG智能问答")

# ----------------------------
# Sidebar: 模型提供商 + 历史会议
# ----------------------------
st.sidebar.markdown("## 模型 / 提供商")
provider_ids = [p[0] for p in PROVIDER_OPTIONS]
def _provider_label(pid):
    name = next((n for i, n in PROVIDER_OPTIONS if i == pid), pid)
    return f"{name}" + (" ✓" if is_provider_available(pid) else " (未配置)")
current_idx = provider_ids.index(st.session_state["llm_provider"]) if st.session_state["llm_provider"] in provider_ids else 0
chosen = st.sidebar.selectbox(
    "选择使用的模型（纪要生成与智能问答均使用此模型）",
    options=provider_ids,
    index=current_idx,
    format_func=_provider_label,
)
st.session_state["llm_provider"] = chosen
st.sidebar.caption("纪要生成与智能问答统一使用上方所选模型。")

# 配置当前模型 API（选择模型后在此填写，与 .env 等效；保存后纪要+问答都会用此配置）
with st.sidebar.expander("🔑 配置当前模型 API", expanded=not is_provider_available(chosen)):
    ui_cfg = get_provider_config_for_ui(chosen)
    # 用 key 区分不同 provider，避免切换时串值
    api_key_placeholder = "已配置（留空则不修改）" if ui_cfg.get("api_key") else "在此粘贴 API Key"
    new_api_key = st.sidebar.text_input(
        "API Key",
        value="",
        placeholder=api_key_placeholder,
        type="password",
        key=f"api_key_{chosen}",
    )
    new_model = st.sidebar.text_input(
        "模型名（可选，留空则自动使用当前账号第一个可用模型）",
        value=ui_cfg.get("model") or "",
        placeholder=get_model_placeholder(chosen),
        key=f"model_{chosen}",
    )
    if provider_has_base_url(chosen):
        new_base_url = st.sidebar.text_input(
            "Base URL（可选）",
            value=ui_cfg.get("base_url") or "",
            placeholder="留空使用默认地址",
            key=f"base_url_{chosen}",
        )
    else:
        new_base_url = ""
    if st.sidebar.button("保存 API 配置", key=f"save_cfg_{chosen}"):
        full = load_llm_config()
        if chosen not in full:
            full[chosen] = {}
        if new_api_key.strip():
            full[chosen]["api_key"] = new_api_key.strip()
        # API Key 留空则不修改（保留文件中已有值）
        if new_model.strip():
            full[chosen]["model"] = new_model.strip()
        else:
            full[chosen]["model"] = ui_cfg.get("model") or get_default_model(chosen)
        if provider_has_base_url(chosen):
            full[chosen]["base_url"] = (new_base_url or "").strip() or None
        save_llm_config(full)
        st.sidebar.success("已保存，纪要生成与智能问答将统一使用此模型与配置。")

st.sidebar.markdown("---")
st.sidebar.markdown("## 历史会议")

# ① 搜索框
query = st.sidebar.text_input("🔎 搜索历史会议（标题/内容关键词）", value="").strip().lower()

files = list_meeting_files()

# ② 根据关键词过滤
if query:
    filtered = []
    for fid in files:
        try:
            rec = load_meeting_record(fid)
            title = (rec.get("title") or "").lower()
            transcript = (rec.get("transcript") or "").lower()
            # 命中：标题 / 转写 / 文件名标题（兜底）
            if query in title or query in transcript or query in fid.lower():
                filtered.append(fid)
        except Exception:
            # 读不了就跳过，不影响使用
            continue
    files_to_show = filtered
else:
    files_to_show = files

if query and not files_to_show:
    st.sidebar.info("没有匹配到历史会议。试试更短的关键词。")

options = ["（新建/不加载历史）"] + files_to_show

# ③ 默认选中：如果 last_saved_file 仍在过滤结果里，就选它，否则选“新建”
default_index = 0
last = st.session_state.get("last_saved_file")
if last and last in files_to_show:
    default_index = options.index(last)

selected_file = st.sidebar.selectbox(
    "选择一条会议记录查看",
    options=options,
    index=default_index,
    format_func=lambda x: x if x == "（新建/不加载历史）" else display_name_from_file(x),
)


if selected_file != "（新建/不加载历史）":
    try:
        rec = load_meeting_record(selected_file)
        st.session_state["meeting_title"] = rec.get("title", "Untitled Meeting")
        saved_tpl = rec.get("template_name")
        st.session_state["template_name"] = saved_tpl if saved_tpl in template_names() else template_names()[0]
        st.session_state["transcript_text"] = rec.get("transcript", "")
        st.session_state["result_json"] = rec.get("result_json", None)
    except Exception as e:
        st.sidebar.error(f"加载历史会议失败：{e}")

# ----------------------------
# Main layout
# ----------------------------
col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("1) 输入")

    template = st.selectbox(
        "选择模板",
        template_names(),
        key="template_name",
    )
    st.write(f"**模板说明：** {get_template_desc(template)}")

    title = st.text_input(
        "会议标题（可选）",
        key="meeting_title",
    )

    transcript = st.text_area(
        "粘贴会议转写文本",
        height=380,
        placeholder="把你的会议转写粘贴在这里...",
        key="transcript_text",
    )

    run = st.button("Generate", type="primary", disabled=not transcript.strip())

with col2:
    st.subheader("2) 输出")

    # 如果本次点击 Generate，就生成并保存
    if run:
        with st.spinner("Generating structured notes..."):
            try:
                data = extract_structured(template, transcript, provider=st.session_state["llm_provider"])
                st.session_state["result_json"] = data

                # 保存到本地（历史会议）
                record = {
                    "title": title,
                    "template_name": template,
                    "transcript": transcript,
                    "result_json": data,
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                }
                file_id = save_meeting_record(record)
                st.session_state["last_saved_file"] = file_id

                st.success(f"Done! 已保存到历史会议：{display_name_from_file(file_id)}")

            except Exception as e:
                st.error(str(e))
                st.info("常见原因：API Key/BASE_URL/模型名不对，或模型输出不是合法 JSON。可将侧边栏「模型名」留空并保存，将自动使用当前账号第一个可用模型。")

    # 统一的输出展示区域（无论是新生成的还是历史加载的）
    if st.session_state.get("result_json"):
        try:
            # 显示 Markdown 输出
            md = to_markdown(
                st.session_state["result_json"],
                title=st.session_state.get("meeting_title", "Untitled Meeting"),
                template_name=st.session_state.get("template_name", ""),
            )
            st.markdown(md)

            # ----------------------------
            # 问答区域（对所有有 result_json 的会议都显示）
            # ----------------------------
            st.divider()
            st.subheader("3) 智能问答（AI检索增强）")

            # 使用 session_state 中的 transcript
            current_transcript = st.session_state.get("transcript_text", "")

            if current_transcript.strip():
                if SMART_RAG_AVAILABLE:
                    question = st.text_input(
                        "输入你的问题",
                        placeholder="例如：这次会议的行动项有哪些？谁负责？截止时间？",
                        key="qa_question"
                    )

                    ask = st.button("Ask", type="primary", disabled=not question.strip())

                    if ask and question.strip():
                        # 生成缓存ID（基于transcript的hash）
                        transcript_hash = hashlib.md5(current_transcript.encode('utf-8')).hexdigest()[:16]
                        cache_id = f"transcript_{transcript_hash}"

                        with st.spinner("🤖 AI正在分析并回答..."):
                            try:
                                result = answer_question(
                                    question,
                                    current_transcript,
                                    cache_id=cache_id,
                                    provider=st.session_state["llm_provider"],
                                )

                                # 显示回答
                                st.markdown("### 💡 回答")
                                st.markdown(result['answer'])

                                # 显示检索信息（可折叠）
                                with st.expander("🔍 检索详情（调试信息）", expanded=False):
                                    st.caption(f"**检索模式**: {result['metadata']['method']}")
                                    st.caption(f"**原因**: {result['metadata']['reason']}")

                                    if result['mode'] == 'rag':
                                        st.caption(f"**检索到的片段数**: {result['metadata']['chunks_count']}")
                                        st.caption(f"**覆盖率**: {result['metadata']['coverage']}")
                                        st.caption(f"**平均相似度**: {result['metadata']['avg_similarity']}")

                                        st.write("**检索到的内容片段**:")
                                        for chunk in result['chunks'][:5]:  # 只显示前5个
                                            st.code(f"[片段 {chunk['id']}]\n{chunk['text'][:300]}...", language="text")
                                    else:
                                        st.info("使用了完整会议内容（会议较短）")

                            except Exception as e:
                                st.error(f"问答失败: {e}")
                                import traceback
                                st.code(traceback.format_exc())
                else:
                    st.warning("⚠️ 智能问答模块不可用，请检查依赖安装（numpy、openai）")
            else:
                st.info("没有会议转写文本，无法进行问答。")

            # ----------------------------
            # Quality Check Panel（对所有会议都显示）
            # ----------------------------
            if current_transcript.strip():
                qc = run_quality_checks(
                    st.session_state["result_json"],
                    transcript=current_transcript,
                    template_name=st.session_state.get("template_name", ""),
                )

                st.divider()
                st.subheader("质量检查（可执行性 & 可追溯性）")

                # 用颜色表达分数
                score = qc["score"]
                if score >= 85:
                    st.success(f"整体评分：{score}/100（输出质量较好）")
                elif score >= 70:
                    st.warning(f"整体评分：{score}/100（可用，但建议补全关键信息）")
                else:
                    st.error(f"整体评分：{score}/100（存在较多缺失，建议调整模板/重试/手动补全）")

                # 展示统计
                st.caption(
                    f"Confidence: {qc['confidence']} | "
                    f"Input chars: {qc['stats']['input_chars']} | "
                    f"Coverage: {qc['stats']['coverage']['sections_present']}/{qc['stats']['coverage']['total_sections']}"
                )

                # 错误与警告
                if qc["errors"]:
                    with st.expander("❌ Errors（必须修复）", expanded=True):
                        for e in qc["errors"]:
                            st.write(f"- {e}")

                if qc["warnings"]:
                    with st.expander("⚠️ Warnings（建议优化）", expanded=True):
                        for w in qc["warnings"]:
                            st.write(f"- {w}")

                if not qc["errors"] and not qc["warnings"]:
                    st.info("没有检测到明显问题。✅")
            else:
                st.divider()
                st.subheader("质量检查（可执行性 & 可追溯性）")
                st.info("缺少会议转写文本，无法进行质量检查。")

            # ----------------------------
            # Exports（对所有有 result_json 的会议都显示）
            # ----------------------------
            st.divider()
            st.subheader("Exports")
            st.download_button(
                "Download JSON",
                export_json(st.session_state["result_json"]),
                file_name="meeting_notes.json"
            )
            csv = action_items_to_csv(
                st.session_state["result_json"],
                template_name=st.session_state.get("template_name", ""),
            )
            if csv:
                st.download_button(
                    "Download 列表 CSV",
                    csv,
                    file_name="meeting_export.csv"
                )
            st.code(export_json(st.session_state["result_json"]), language="json")

        except Exception as e:
            st.info("渲染输出失败（可能是旧数据结构变化）。")
            st.code(str(e))
    else:
        st.info("左侧输入转写文本，点击 Generate。或在左侧「历史会议」中选择一条记录。")
