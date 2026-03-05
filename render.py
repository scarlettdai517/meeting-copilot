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
        field_labels = {}
        section_key = ""
        if template.startswith("dev:"):
            section_key = template.split(":", 1)[1]
            dev_labels = {
                "architecture_changes": {
                    "change": "变更内容",
                    "component": "受影响系统部分",
                },
                "api_protocol_definitions": {
                    "item": "协议/接口项",
                    "field_or_behavior": "定义内容或当前状态",
                },
                "bug_issue_list": {
                    "description": "问题描述",
                    "repro_condition": "复现条件",
                    "severity": "严重级别",
                },
                "env_dependencies": {
                    "requirement": "前置条件/资源需求",
                    "owner_or_deadline": "负责人或截止时间",
                },
            }
            field_labels = dev_labels.get(section_key, {})
        elif template.startswith("growth:"):
            section_key = template.split(":", 1)[1]
            growth_labels = {
                "pain_points": {
                    "insight": "痛点结论",
                    "scene_or_quote": "用户场景/原话",
                },
                "core_selling_points": {
                    "point": "卖点主张",
                    "version_or_scope": "生效范围与边界（版本/场景）",
                },
                "launch_countdown": {
                    "feature_or_milestone": "功能/里程碑项",
                    "mvp_status": "MVP状态",
                    "expected_delivery": "预计交付时间",
                },
                "competitor_mentions": {
                    "competitor": "竞品/友商",
                    "dynamic": "对方动态或动作",
                    "response": "我方应对策略",
                },
            }
            field_labels = growth_labels.get(section_key, {})
        elif template.startswith("exec:"):
            section_key = template.split(":", 1)[1]
            exec_labels = {
                "management_interventions": {
                    "item": "介入事项",
                    "request_type": "请求类型",
                    "specific_request": "具体请求",
                    "owner_and_collaborators": "牵头人/协同方",
                    "time_window": "时间窗口",
                },
                "risk_traffic_light": {
                    "risk": "风险描述",
                    "level": "风险等级（红/黄/绿）",
                    "mitigation_strategy": "缓解策略",
                },
                "milestone_confidence": {
                    "overall": "整体置信度",
                    "notes": "关键依赖或时间压力",
                },
            }
            field_labels = exec_labels.get(section_key, {})
        elif template.startswith("external:"):
            section_key = template.split(":", 1)[1]
            external_labels = {
                "deliverables": {
                    "item": "交付项",
                    "owner_side": "责任方",
                    "due": "截止时间",
                },
                "raci_matrix": {
                    "task_or_area": "任务或领域",
                    "R": "负责方（R）",
                    "A": "执行方（A）",
                    "C": "咨询方（C）",
                    "I": "知情方（I）",
                },
                "commercial_milestones": {
                    "milestone": "商务节点/里程碑",
                    "criteria_or_payment": "验收标准/付款条件",
                    "due": "时间",
                },
                "next_sync_time": {
                    "datetime_or_desc": "下次同步时间或说明",
                },
            }
            field_labels = external_labels.get(section_key, {})
        for k, v in it.items():
            if k == "evidence" or not v:
                continue
            if isinstance(v, str) and v.strip():
                label = field_labels.get(k, k)
                val = v.strip()
                # 高管模板风险等级使用显眼颜色
                if template.startswith("exec:") and section_key == "risk_traffic_light" and k == "level":
                    lv = val.lower()
                    color = {"red": "#ef4444", "yellow": "#f59e0b", "green": "#22c55e"}.get(lv, "#9ca3af")
                    parts.append(f"**{label}**: <span style=\"color:{color};font-weight:700;\">{val}</span>")
                else:
                    parts.append(f"**{label}**: {val}")
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
            lines.append(f"- **{text}**  \n  _原文依据_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "action_items" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for a in value:
            task = (a.get("task") or "").strip()
            owner = (a.get("owner") or "—").strip() or "—"
            due = (a.get("due") or "—").strip() or "—"
            prio = (a.get("priority") or "P1").strip()
            ev = (a.get("evidence") or "").strip()
            lines.append(f"- [ ] **{task}**（负责人：{owner}，截止时间：{due}，优先级：{prio}）  \n  _原文依据_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "risks" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for r in value:
            risk = (r.get("risk") or "").strip()
            mit = (r.get("mitigation") or "").strip()
            ev = (r.get("evidence") or "").strip()
            lines.append(f"- **{risk}**  \n  缓解措施：{mit}  \n  _原文依据_: {ev}".rstrip())
        return "\n".join(lines) + "\n\n" if lines else "## " + section_label + "\n\n- （暂无）\n\n"
    if key == "open_questions" and isinstance(value, list):
        lines = ["## " + section_label + "\n"]
        for q in value:
            question = (q.get("question") or "").strip()
            owner = (q.get("owner") or "—").strip() or "—"
            ev = (q.get("evidence") or "").strip()
            lines.append(f"- **{question}**（建议跟进人：{owner}）  \n  _原文依据_: {ev}".rstrip())
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
        label = sec.get("label_zh") if tid in ("general", "dev", "growth", "exec", "external") else get_section_display(sec)
        value = data.get(key)
        # 兼容：高管模板旧字段 resource_blockers -> 新字段 management_interventions
        if tid == "exec" and key == "management_interventions" and value is None:
            value = data.get("resource_blockers")
        if is_general and key in ("summary_tldr", "decisions", "action_items", "risks", "open_questions"):
            block = _render_general_section(key, value, label)
        else:
            if value is None:
                block = f"## {label}\n\n- （暂无）\n\n"
            elif isinstance(value, list):
                format_template = f"{tid}:{key}" if tid in ("dev", "growth", "exec", "external") else tid
                block = f"## {label}\n\n" + (_format_item_list(value, template=format_template) or "- （暂无）") + "\n\n"
            elif isinstance(value, dict):
                if tid == "exec":
                    block = f"## {label}\n\n" + (_format_item_list([value], template=f"exec:{key}") or "- （暂无）") + "\n\n"
                else:
                    block = f"## {label}\n\n" + _format_single_obj(value) + "\n\n"
            else:
                block = f"## {label}\n\n- {value}\n\n"
        lines.append(block.strip())
    return "\n".join(lines)


# 兼容：旧代码可能只传 data, title
def to_markdown_legacy(data: dict, title: str) -> str:
    return to_markdown(data, title, template_name="")
