# -*- coding: utf-8 -*-
"""
按模板渲染纪要：每个模板的板块与字段不同，展示标题为「中文（English）」。
"""

from templates import (
    get_template_sections,
    get_section_display,
    detect_template_id_from_data,
    display_name_to_template_id,
    template_id_to_display_name,
)


def _top_bullets(items, k=10):
    if not items:
        return []
    cleaned = []
    for it in items:
        if it is None:
            continue
        s = str(it).strip()
        if s:
            cleaned.append(s)
    return cleaned[:k]


def _format_item_list(items: list, template: str = "general") -> str:
    """将 list of dict 或 list of str 格式化为 markdown 行。"""
    lines = []
    for it in items:
        if it is None:
            continue
        if isinstance(it, str):
            lines.append(f"- {it}")
            continue
        if not isinstance(it, dict):
            lines.append(f"- {it}")
            continue
        parts = []
        for k, v in it.items():
            if k == "evidence" or not v:
                continue
            if isinstance(v, str) and v.strip():
                parts.append(f"**{k}**: {v.strip()}")
        if parts:
            lines.append("- " + " | ".join(parts))
        else:
            lines.append("- " + str(it))
    return "\n".join(lines) if lines else ""


def _format_single_obj(obj: dict) -> str:
    if not obj or not isinstance(obj, dict):
        return "- （暂无）"
    lines = []
    for k, v in obj.items():
        if k == "evidence" or v is None:
            continue
        if isinstance(v, str) and v.strip():
            lines.append(f"- **{k}**: {v.strip()}")
    return "\n".join(lines) if lines else "- （暂无）"


def _render_general_section(key: str, value, section_label: str) -> str:
    """通用模板的固定格式（保留旧版展示效果）。"""
    if key == "summary_tldr":
        bullets = _top_bullets(value, k=5)
        if not bullets:
            return f"## {section_label}\n\n- （暂无）\n"
        return "## " + section_label + "\n\n" + "\n".join(f"- {x}" for x in bullets) + "\n\n"
    if key == "decisions" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for d in value:
            text = (d.get("text") or "").strip()
            ev = (d.get("evidence") or "").strip()
            lines.append(f"- **{text}**  \n  _evidence_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "action_items" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for a in value:
            task = (a.get("task") or "").strip()
            owner = (a.get("owner") or "—").strip() or "—"
            due = (a.get("due") or "—").strip() or "—"
            prio = (a.get("priority") or "P1").strip()
            ev = (a.get("evidence") or "").strip()
            lines.append(f"- [ ] **{task}** (Owner: {owner}, Due: {due}, Priority: {prio})  \n  _evidence_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "risks" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for r in value:
            risk = (r.get("risk") or "").strip()
            mit = (r.get("mitigation") or "").strip()
            ev = (r.get("evidence") or "").strip()
            lines.append(f"- **{risk}**  \n  Mitigation: {mit}  \n  _evidence_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "open_questions" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for q in value:
            question = (q.get("question") or "").strip()
            owner = (q.get("owner") or "—").strip() or "—"
            ev = (q.get("evidence") or "").strip()
            lines.append(f"- **{question}** (Owner: {owner})  \n  _evidence_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    return "## " + section_label + "\n\n" + _format_item_list(value if isinstance(value, list) else []) + "\n\n"


def to_markdown(data: dict, title: str, template_name: str = "") -> str:
    """
    按模板渲染 JSON 为 Markdown。template_name 可为展示名或 id。
    若 template_name 为空或为旧版名称，则根据 data 的 key 推断模板。
    """
    if not data:
        return f"# {title}\n\n（无内容）"

    # 解析当前模板 id
    if template_name:
        tid = display_name_to_template_id(template_name)
    else:
        tid = detect_template_id_from_data(data)
    sections = get_template_sections(tid)
    is_general = tid == "general"

    lines = [f"# {title}\n"]
    for sec in sections:
        key = sec.get("key")
        if not key:
            continue
        label = get_section_display(sec)
        value = data.get(key)
        if is_general and key in ("summary_tldr", "decisions", "action_items", "risks", "open_questions"):
            block = _render_general_section(key, value, label)
        else:
            if value is None:
                block = f"## {label}\n\n- （暂无）\n\n"
            elif isinstance(value, list):
                block = f"## {label}\n\n" + (_format_item_list(value) or "- （暂无）") + "\n\n"
            elif isinstance(value, dict):
                block = f"## {label}\n\n" + _format_single_obj(value) + "\n\n"
            else:
                block = f"## {label}\n\n- {value}\n\n"
        lines.append(block.strip())
    return "\n".join(lines)


# 兼容：旧代码可能只传 data, title
def to_markdown_legacy(data: dict, title: str) -> str:
    return to_markdown(data, title, template_name="")
