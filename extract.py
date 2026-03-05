import json
from llm import chat_json
from templates import (
    get_template_prompt_guide,
    get_template_schema_json,
    template_id_to_display_name,
    display_name_to_template_id,
    TEMPLATE_ID_GENERAL,
    TEMPLATE_ID_DEV,
    TEMPLATE_ID_GROWTH,
    TEMPLATE_ID_EXEC,
    TEMPLATE_ID_EXTERNAL,
)


# 通用模板 Few-Shot 示例（格式 + 决策与行动项区分 + evidence/未明确）
_GENERAL_FEW_SHOT = """
【输出示例】（格式参考，勿照抄。注意：决策=拍板/底线，行动项=谁何时做什么）
"decisions": [{"text": "采用方案A", "evidence": "张三：那就定方案A吧，大家没意见就按这个做。"}, {"text": "客户要求离线必须能用", "evidence": "客户：离线必须能用，这是底线。"}]
"action_items": [{"task": "与外部对接接口文档", "owner": "未明确", "due": "下周内", "priority": "P1", "evidence": "李四：谁去跟对方对接一下接口？"}, {"task": "下周三前给出性能基准表", "owner": "王五", "due": "下周三", "priority": "P1", "evidence": "王五：基准表我下周三给你。"}]
说明：像「下周三给基准表」这种有负责人+时间的 → 只进 action_items，不进 decisions。
"risks": [{"risk": "工期可能延期", "mitigation": "先出 MVP 再迭代", "evidence": "王五：时间太紧，搞不好要延。"}]
"""

# 技术模板 Few-Shot 示例（格式 + 多条覆盖，勿照抄）
_DEV_FEW_SHOT = """
【输出示例】（技术模板：每类尽量按会议提到的点数逐条列出，勿合并成一条）
"architecture_changes": [{"change": "从纯云改为端云协同", "component": "系统架构", "evidence": "大刘：从纯云变端云协同，需要定义一套新的协议。"}, {"change": "1.8B 模型部署至端侧 SoC", "component": "端侧/SoC", "evidence": "大刘：把 1.8B 小模型直接塞进硬件 SoC 里。"}]
"env_dependencies": [{"requirement": "芯片可用内存至少 1G 用于模型", "owner_or_deadline": "硬件约束", "evidence": "大刘：芯片内存只有 4G，系统占用后剩不到 1G 给模型。"}, {"requirement": "下周三前给出性能基准表", "owner_or_deadline": "Iris / 下周三", "evidence": "Iris：基准表我下周三左右给你吧。"}]
"""

# 业务增长模板 Few-Shot（用户痛点仅放用户可感知的，竞品可空）
_GROWTH_FEW_SHOT = """
【输出示例】（业务增长：用户痛点=用户/客户体验，不放技术实现问题；竞品未提则 []）
"pain_points": [{"insight": "响应慢、离线不可用", "scene_or_quote": "客户说买音箱是当管家的不是当复读机的", "evidence": "赵总：第一慢，第二离线没法用。"}]
"core_selling_points": [{"point": "隐私不出户，常用秒回复", "version_or_scope": "2.0 本地优先", "evidence": "阿强：我们可以宣传隐私不出户，常用秒回复。"}]
"launch_countdown": [{"feature_or_milestone": "核心场景路径", "mvp_status": "进行中", "expected_delivery": "待定", "evidence": "Sarah：梳理 10 个核心场景路径。"}]
"competitor_mentions": []
说明：会议未提具体竞品时 competitor_mentions 输出 []；芯片内存、过热等放技术模板，不进 pain_points。
"""

# 高管决策简报 Few-Shot（结论=定论不含待办，介入事项与风险分离，并强调不漏发布范围策略）
_EXEC_FEW_SHOT = """
【输出示例】（高管模板：结论只放已拍板定论；介入事项写“请管理层做什么”；风险按 red/yellow/green 多条列出）
"conclusion": ["2.0 端云协同方向已定", "客户底线：无网时家电控制必须可用", "短期不做实时能力，先保证会后处理可信", "Beta 先内部与友好客户试点，暂不大规模放出", "AI 仅作为助手，不替代人工决策"]
"management_interventions": [{"item": "Protobuf 协议定义未到位影响联调进度", "request_type": "跨部门协调", "specific_request": "协调中间件团队在本周内确认并下发协议版本", "owner_and_collaborators": "牵头：平台负责人；协同：中间件团队/后端团队", "time_window": "本周内", "evidence": "大刘：小李那边还没把 Protobuf 的定义发我。"}, {"item": "方言训练资源不足可能影响推介会版本", "request_type": "资源调配", "specific_request": "批准追加 H20 训练资源并确认预算", "owner_and_collaborators": "牵头：阿强；协同：财务/算法团队", "time_window": "两周内", "evidence": "阿强：我去跟老板申请专项资金。"}]
"risk_traffic_light": [{"risk": "方言识别可能影响稳定性", "level": "yellow", "mitigation_strategy": "先冻结高风险方言范围，按灰度名单逐批放开并加稳定性回归", "evidence": "大刘：风险极大，为了方言牺牲稳定性现场崩了谁负责？"}, {"risk": "方言可能赶不上推介会", "level": "red", "mitigation_strategy": "将方言目标拆为基础包+增量包，先保障主流程演示可用", "evidence": "Iris：那根本不可能……"}, {"risk": "若强行上实时能力，用户体验和稳定性可能下降", "level": "yellow", "mitigation_strategy": "短期保持会后处理路线，实时链路仅做小流量压测验证", "evidence": "大刘：实时并发一上来就慢，体验会掉。"}]
"milestone_confidence": {"overall": "中等", "notes": "需在两周内完成可追溯与可信能力，依赖标注产能与合规口径明确", "evidence": "赵总：下个月中旬推介会，还没东西出来单子保不住。"}
说明：像「需要尽快确定 Protobuf」这种进 management_interventions；risk_traffic_light 写“风险+缓解策略”，不写管理层介入请求动作。结论中的“不做项”与风险中的“若做会出问题”可同时存在。
"""

# 外部协作与商务 Few-Shot（RACI 区分我方/对方，下次同步未约定填未明确）
_EXTERNAL_FEW_SHOT = """
【输出示例】（外部模板：交付物标我方/对方；RACI 体现双方责任；下次同步未明确约定则填未明确）
"deliverables": [{"item": "50 台样机", "owner_side": "对方-赵总", "due": "下周一", "evidence": "赵总：50 台没问题，我回去协调。"}, {"item": "性能基准表", "owner_side": "我方-Iris", "due": "下周三", "evidence": "Iris：基准表我下周三左右给你吧。"}]
"raci_matrix": [{"task_or_area": "样机提供", "R": "对方-赵总", "A": "对方-赵总", "C": "我方-阿强", "I": "我方-大刘", "evidence": "阿强：需要 50 台样机做实地压测。赵总：50 台没问题。"}]
"commercial_milestones": [{"milestone": "样机到位", "criteria_or_payment": "50 台样机寄达", "due": "下周一", "evidence": "大刘：赵总，样机下周一必须寄到。"}]
"next_sync_time": {"datetime_or_desc": "未明确", "evidence": "会议未明确约定下次同步时间"}
说明：若会议未说「下次会议何时」，next_sync_time 的 datetime_or_desc 填「未明确」，不要用交付物日期推断。
"""


def build_system_prompt(template_name: str) -> str:
    """按所选模板构建 system prompt：提炼指引 + 该模板专属 JSON schema；通用模板追加 Few-Shot。"""
    from templates import TEMPLATES
    tid = template_name if template_name in TEMPLATES else display_name_to_template_id(template_name)
    guide = get_template_prompt_guide(template_name)
    schema = get_template_schema_json(template_name)
    display = template_id_to_display_name(tid)
    base = f"""你是一个专业的会议助手，按所选模板从会议转写中提炼结构化纪要。

【当前模板】{display}

【本模板的提炼重点与要求】
{guide}

【必须严格输出的 JSON 格式】（不要用 markdown 代码块，只输出纯 JSON）
{schema}
"""
    if tid == TEMPLATE_ID_GENERAL:
        base += _GENERAL_FEW_SHOT
    elif tid == TEMPLATE_ID_DEV:
        base += _DEV_FEW_SHOT
    elif tid == TEMPLATE_ID_GROWTH:
        base += _GROWTH_FEW_SHOT
    elif tid == TEMPLATE_ID_EXEC:
        base += _EXEC_FEW_SHOT
    elif tid == TEMPLATE_ID_EXTERNAL:
        base += _EXTERNAL_FEW_SHOT
    base += "\n要求：evidence 必须来自原文短句；只输出 JSON，禁止任何额外解释。"
    return base


def _normalize_general_result(data: dict) -> None:
    """通用模板后处理：空 owner 填「未明确」、空 due 填「待定」，保证可追溯性。"""
    for item in data.get("action_items") or []:
        if not (item.get("owner") or "").strip():
            item["owner"] = "未明确"
        if not (item.get("due") or "").strip():
            item["due"] = "待定"
    for item in data.get("open_questions") or []:
        if not (item.get("owner") or "").strip():
            item["owner"] = "未明确"


def _normalize_exec_result(data: dict) -> None:
    """高管模板后处理：兼容旧字段并补齐介入事项的缺省值。"""
    if "management_interventions" not in data and "resource_blockers" in data:
        data["management_interventions"] = data.get("resource_blockers") or []

    for item in data.get("management_interventions") or []:
        if not isinstance(item, dict):
            continue
        if not (item.get("owner_and_collaborators") or "").strip():
            item["owner_and_collaborators"] = "未明确"
        if not (item.get("time_window") or "").strip():
            item["time_window"] = "未明确"

    for item in data.get("risk_traffic_light") or []:
        if not isinstance(item, dict):
            continue
        if not (item.get("mitigation_strategy") or "").strip():
            item["mitigation_strategy"] = "待补充（会议未明确）"
        # 风险等级归一
        level_raw = (item.get("level") or "").strip().lower()
        level_map = {
            "红": "red",
            "黄": "yellow",
            "绿": "green",
            "high": "red",
            "medium": "yellow",
            "low": "green",
        }
        normalized_level = level_map.get(level_raw, level_raw)
        if normalized_level not in {"red", "yellow", "green"}:
            normalized_level = "yellow"

        # 合规/法律类风险一律强制 red（硬规则）
        risk_text = (item.get("risk") or "").lower()
        evidence_text = (item.get("evidence") or "").lower()
        compliance_keywords = (
            "合规",
            "法律",
            "法务",
            "监管",
            "违规",
            "处罚",
            "隐私",
            "数据泄露",
            "审计",
            "license",
            "compliance",
            "legal",
            "regulat",
        )
        if any(k in risk_text or k in evidence_text for k in compliance_keywords):
            normalized_level = "red"
        item["level"] = normalized_level


def extract_structured(
    template_name: str, transcript: str, provider: str | None = None
) -> dict:
    from templates import TEMPLATES, display_name_to_template_id
    tid = template_name if template_name in TEMPLATES else display_name_to_template_id(template_name)
    system_prompt = build_system_prompt(template_name)

    cot_hint = ""
    if tid == TEMPLATE_ID_GENERAL:
        cot_hint = (
            "请先通读转写，在脑中列出：①主要议题与结论 ②决策（仅拍板/底线/一致方向，不含「谁何时做什么」）"
            "③行动项（谁在何时前完成什么，会议总结里的待办全部进此处）④风险。输出时 decisions 只放决策，action_items 放所有待办，不要混淆。\n\n"
        )
    elif tid == TEMPLATE_ID_DEV:
        cot_hint = (
            "请先通读转写，逐项列出：①架构/组件变更（如端云协同、模型部署位置、内存/NPU/算子约束）"
            "②协议或接口（含待定、需对接的状态）③Bug/Issue（含复现条件与等级）④环境/依赖（芯片、样机、算力、量化要求、交付时间）。每类按会议提到的点数逐条输出，不要合并成一条。\n\n"
        )
    elif tid == TEMPLATE_ID_GROWTH:
        cot_hint = (
            "请先通读转写，逐项列出：①用户/客户痛点（仅终端用户或客户可感知的体验问题，如慢、离线、像复读机、上下文断，不要放芯片/过热等技术实现问题）"
            "②核心卖点与宣传口径 ③各功能或里程碑的 MVP 状态与预计交付时间 ④会议是否提到具体竞品/友商（未提则 competitor_mentions 输出 []）。\n\n"
        )
    elif tid == TEMPLATE_ID_EXEC:
        cot_hint = (
            "请先通读转写，按“先粗召回、后归类”执行：先列出所有候选关键信息，再写 JSON，避免遗漏。"
            "①结论候选池至少检查：方向拍板、范围取舍、短期不做项、发布范围策略（如先内部/友好客户试点）、方法论原则（如 AI 仅辅助）；其中属于定论的都写入 conclusion。"
            "特别保留否定型决策（如不做/先不做/暂不放出），不要被其他正向结论吞并。"
            "②需要管理层介入的事项（至少满足：需要拍板/跨部门协调/授权背书之一）写入 management_interventions，并补全请求动作、牵头协同方、时间窗口；缺失填「未明确」，不要丢项。"
            "③重大风险写 risk_traffic_light（red/yellow/green），每条包含 risk + mitigation_strategy：优先提取当前已在做的缓解动作；若原文未直接给出，可基于附近上下文给出可执行的下一步策略；若仍无依据则写「待补充（会议未明确）」。"
            "management_interventions 写“需要管理层做什么动作”，risk_traffic_light 写“风险如何缓解”，二者不要混写；若存在“暂不做X”与“做X有风险”，二者可并存。"
            "④里程碑整体置信度与关键依赖写 milestone_confidence，其中 notes 尽量包含「目标能力 + 时间窗口 + 关键依赖」，避免泛化。注意：risk_traffic_light 与 management_interventions 结构上必须分离。\n\n"
        )
    elif tid == TEMPLATE_ID_EXTERNAL:
        cot_hint = (
            "请先通读转写，逐项列出：①交付物及归属方（我方/对方）与时间 ②按任务区分的双方责任（RACI 体现我方 vs 对方，未明确写「我方待定」）"
            "③商务节点（验收/交付/演示）④会议是否明确约定下次同步时间（未约定则 next_sync_time 填「未明确」）。不要用交付物日期推断下次会议时间。\n\n"
        )
    user_prompt = f"""会议转写如下（可能有口语、断句、噪声）：
---TRANSCRIPT START---
{transcript}
---TRANSCRIPT END---

{cot_hint}请严格按上述 JSON 格式输出。"""

    raw = chat_json(system_prompt, user_prompt, temperature=0.2, provider=provider)

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON parse failed. Model output:\n{raw}\n\nError: {e}")

    if tid == TEMPLATE_ID_GENERAL:
        _normalize_general_result(data)
    elif tid == TEMPLATE_ID_EXEC:
        _normalize_exec_result(data)
    return data


def call_llm_text(prompt: str, provider: str | None = None) -> str:
    return chat_json(
        system_prompt="You are a helpful assistant.",
        user_prompt=prompt,
        temperature=0.2,
        provider=provider,
    )
