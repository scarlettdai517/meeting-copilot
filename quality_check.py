import re
from datetime import datetime

VAGUE_WORDS = [
    "asap", "later", "sometime", "soon", "tomorrow", "next time", "maybe",
    "尽快", "稍后", "回头", "之后", "有空", "不久", "下次", "可能",
]
# 截止时间若为以下词也视为模糊
VAGUE_DUE_VALUES = ("待定", "未明确", "未定", "tbd")
# 转写中与「风险」相关的关键词，用于启发式检查遗漏
RISK_HINT_WORDS = ["风险", "可能", "问题", "崩", "来不及", "不够", "掉频", "过热", "延期", "不稳定"]

DATE_HINT_REGEX = re.compile(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2})\b")
TIME_HINT_REGEX = re.compile(r"\b(\d{1,2}:\d{2})\b")
WEEKDAY_CN = ["周一","周二","周三","周四","周五","周六","周日"]
WEEKDAY_EN = ["mon","tue","wed","thu","fri","sat","sun"]

def _contains_vague(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in VAGUE_WORDS)

def _has_due_hint(due: str) -> bool:
    if not due:
        return False
    d = due.strip().lower()
    if DATE_HINT_REGEX.search(d) or TIME_HINT_REGEX.search(d):
        return True
    if any(w.lower() in d for w in WEEKDAY_CN) or any(w in d for w in WEEKDAY_EN):
        return True
    if any(x in d for x in ["today","tonight","this week","next week","tomorrow"]):
        return True
    if any(x in d for x in ["今天","今晚","本周","下周","明天"]):
        return True
    return False


def _is_vague_due_value(due: str) -> bool:
    """截止时间是否为「待定/未明确」等占位值（视为模糊）。"""
    if not due:
        return True
    d = (due or "").strip()
    return d in VAGUE_DUE_VALUES or d.lower() == "tbd"


def _transcript_has_risk_hints(transcript: str) -> bool:
    t = (transcript or "").strip()
    return any(w in t for w in RISK_HINT_WORDS)

def _count_missing_ev(items, key="evidence"):
    c = 0
    for it in items:
        if not (it.get(key) or "").strip():
            c += 1
    return c


def _section_has_content(val) -> bool:
    """某板块是否有内容（非空 list 或非空 dict）。"""
    if val is None:
        return False
    if isinstance(val, list):
        return len(val) > 0
    if isinstance(val, dict):
        return bool(val)
    return False

def run_quality_checks(data: dict, transcript: str | None = None, template_name: str | None = None) -> dict:
    """
    返回：
    {
      "score": 0-100,
      "confidence": "high|medium|low",
      "errors": [str...],
      "warnings": [str...],
      "stats": {...}
    }
    仅对「通用纪要」模板做完整检查；其他模板做基础检查（输入长度 + 是否有内容）。
    """
    errors = []
    warnings = []

    # 推断是否为通用模板（旧数据或未传 template_name 时按 data key 判断）
    try:
        from templates import display_name_to_template_id, detect_template_id_from_data
        tid = display_name_to_template_id(template_name) if template_name else detect_template_id_from_data(data)
        is_general = tid == "general"
    except Exception:
        is_general = "summary_tldr" in (data or {}) or "action_items" in (data or {})

    action_items = data.get("action_items", []) or []
    decisions = data.get("decisions", []) or []
    risks = data.get("risks", []) or []
    questions = data.get("open_questions", []) or []
    tldr = data.get("summary_tldr", []) or []

    # ----------------------------
    # 0) 输入信息量检查（解决“短文本虚高”）
    # ----------------------------
    transcript_len = len((transcript or "").strip())
    # 你可以按自己的体验调整阈值：200~400 之间都合理
    MIN_CHARS = 200

    confidence = "high"
    if transcript_len == 0:
        confidence = "low"
        errors.append("输入转写为空。")
    elif transcript_len < MIN_CHARS:
        confidence = "low"
        warnings.append(f"输入转写偏短（{transcript_len} chars），模型输出可能不稳定/覆盖不足。建议粘贴更完整内容后再判断。")

    # ----------------------------
    # 1) 基础完整性
    # ----------------------------
    if is_general:
        if not tldr:
            warnings.append("未生成“核心结论”（summary_tldr 为空）。")
        if not action_items and not decisions and not risks and not questions:
            errors.append("输出几乎没有可执行内容（Action Items/Decisions/Risks/Questions 全部为空）。")
    else:
        # 非通用模板：仅检查是否有任意板块有内容
        any_content = any(
            data.get(k) for k in data if isinstance(data.get(k), (list, dict))
            and (len(data.get(k)) if isinstance(data.get(k), (list, dict)) else True)
        )
        if not any_content:
            warnings.append("当前模板下各板块均为空，建议检查转写内容或重试。")

    # ----------------------------
    # 2) 结构覆盖度（Coverage）
    # ----------------------------
    empty_section_keys = []
    if is_general:
        sections_present = (1 if tldr else 0) + (1 if decisions else 0) + (1 if action_items else 0) + (1 if risks else 0) + (1 if questions else 0)
        total_sections = 5
    else:
        try:
            from templates import get_template_sections
            sections = get_template_sections(tid)
            section_keys = [s["key"] for s in sections] if sections else []
        except Exception:
            section_keys = [k for k in (data or {}) if isinstance(data.get(k), (list, dict))]
        total_sections = len(section_keys) or 1
        sections_present = 0
        for k in section_keys:
            val = data.get(k)
            if _section_has_content(val):
                sections_present += 1
            else:
                empty_section_keys.append(k)

    if is_general and sections_present <= 2:
        warnings.append(f"结构覆盖不足：仅覆盖 {sections_present}/5 个板块（结论/决策/待办/风险/问题）。可能导致“看起来有内容但不完整”。")
    if not is_general and total_sections > 0 and sections_present < total_sections:
        if tid == "growth" and empty_section_keys == ["competitor_mentions"]:
            warnings.append("竞品对标点无内容（若会议未涉及竞品可忽略）。")
        else:
            warnings.append(f"结构覆盖不足：当前模板共 {total_sections} 个板块，仅 {sections_present} 个有内容，建议核对是否遗漏。")

    # ----------------------------
    # 2.1) 决策/风险覆盖启发式（仅通用模板、有转写时）
    # ----------------------------
    if is_general and transcript_len >= 800:
        if len(decisions) <= 1 and (decisions or "拍板" in (transcript or "") or "底线" in (transcript or "")):
            warnings.append("决策可能遗漏：长会议或含「拍板/底线」时通常有多项决策，当前仅 1 条或 0 条，建议核对。")
        if len(risks) <= 1 and _transcript_has_risk_hints(transcript or ""):
            warnings.append("风险可能遗漏：转写中提及风险相关表述但当前风险条数较少，建议核对。")

    # ----------------------------
    # 3) Action Items 质量（仅通用模板）
    # ----------------------------
    missing_owner = 0
    missing_due = 0
    vague_due = 0
    vague_task = 0
    missing_evidence = 0

    if is_general:
        for a in action_items:
            task = (a.get("task") or "").strip()
            owner = (a.get("owner") or "").strip()
            due = (a.get("due") or "").strip()
            ev = (a.get("evidence") or "").strip()

            if not task:
                errors.append("存在空的 Action Item task。")
            if not owner or owner == "未明确":
                missing_owner += 1
            if not due:
                missing_due += 1
            else:
                if _is_vague_due_value(due):
                    vague_due += 1
                elif _contains_vague(due) and not _has_due_hint(due):
                    vague_due += 1
            if _contains_vague(task):
                vague_task += 1
            if not ev:
                missing_evidence += 1

    if is_general and action_items:
        if missing_owner > 0:
            warnings.append(f"有 {missing_owner}/{len(action_items)} 条待办缺少或为「未明确」的 Owner（负责人），建议会后再确认。")
        if missing_due > 0:
            warnings.append(f"有 {missing_due}/{len(action_items)} 条待办缺少 Due（截止时间）。")
        if vague_due > 0:
            warnings.append(f"有 {vague_due}/{len(action_items)} 条待办的截止时间表述偏模糊（如「尽快/稍后/下周/待定」）。")
        if vague_task > 0:
            warnings.append(f"有 {vague_task}/{len(action_items)} 条待办描述偏模糊（如「稍后看看/尽快处理」）。")
        if missing_evidence > 0:
            warnings.append(f"有 {missing_evidence}/{len(action_items)} 条待办缺少 evidence（原文引用），可追溯性不足。")

    # ----------------------------
    # 4) Decisions/Risks/Questions evidence（仅通用模板）
    # ----------------------------
    d_miss = _count_missing_ev(decisions) if is_general else 0
    r_miss = _count_missing_ev(risks) if is_general else 0
    q_miss = _count_missing_ev(questions) if is_general else 0

    if is_general and decisions and d_miss > 0:
        warnings.append(f"有 {d_miss}/{len(decisions)} 条 Decisions 缺少 evidence。")
    if is_general and risks and r_miss > 0:
        warnings.append(f"有 {r_miss}/{len(risks)} 条 Risks 缺少 evidence。")
    if is_general and questions and q_miss > 0:
        warnings.append(f"有 {q_miss}/{len(questions)} 条 Open Questions 缺少 evidence。")

    # ----------------------------
    # 5) 评分（更合理：加入 Coverage & Short-input 上限）
    # ----------------------------
    score = 100
    score -= 25 * len(errors)
    score -= 6 * len(warnings)          # warnings 权重稍微提高一点
    score -= 3 * missing_owner
    score -= 3 * missing_due
    score -= 2 * vague_due
    score -= 2 * missing_evidence

    # Coverage 惩罚：覆盖 <=2，额外扣分
    if sections_present <= 2:
        score -= 12

    # 输入太短：直接封顶（避免虚高）
    if confidence == "low":
        score = min(score, 75)

    score = max(0, min(100, score))

    # total_sections / sections_present 已在上面按模板计算
    stats = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_chars": transcript_len,
        "coverage": {
            "sections_present": sections_present,
            "total_sections": total_sections
        },
        "counts": {
            "tldr": len(tldr),
            "decisions": len(decisions),
            "action_items": len(action_items),
            "risks": len(risks),
            "open_questions": len(questions),
        },
        "action_item_quality": {
            "missing_owner": missing_owner,
            "missing_due": missing_due,
            "vague_due": vague_due,
            "vague_task": vague_task,
            "missing_evidence": missing_evidence,
        }
    }

    return {"score": score, "confidence": confidence, "errors": errors, "warnings": warnings, "stats": stats}
