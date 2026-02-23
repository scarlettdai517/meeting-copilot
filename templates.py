# -*- coding: utf-8 -*-
"""
会议纪要模板：按角色与场景区分，不同模板的「模块/板块」不同，呈现形态不同。
每个模板名、每个模块名均提供中文与英文。
"""

# 模板唯一 id（代码内使用），与展示名（中英文）分离
TEMPLATE_ID_GENERAL = "general"
TEMPLATE_ID_DEV = "dev"
TEMPLATE_ID_GROWTH = "growth"
TEMPLATE_ID_EXEC = "exec"
TEMPLATE_ID_EXTERNAL = "external"

# 展示名：中文 (English)，用于 UI 与历史记录
TEMPLATES = {
    TEMPLATE_ID_GENERAL: {
        "name_zh": "通用纪要",
        "name_en": "General Meeting Notes",
        "desc": "任何人可看，无角色侧重；会议说了什么就总结什么，信息最全。",
        "audience": "任意参会者、需完整留痕的场景",
        "scenario": "各类会议通用，需保留完整结论/决策/待办/风险/待定时",
        "sections": [
            {"key": "summary_tldr", "label_zh": "核心结论", "label_en": "Key Conclusions"},
            {"key": "decisions", "label_zh": "决策", "label_en": "Decisions"},
            {"key": "action_items", "label_zh": "行动项", "label_en": "Action Items"},
            {"key": "risks", "label_zh": "风险", "label_en": "Risks"},
            {"key": "open_questions", "label_zh": "待定问题", "label_en": "Open Questions"},
        ],
        "schema_json": """
{
  "summary_tldr": ["每条为一句完整结论，覆盖会议主要议题、技术/产品/客户约束"],
  "decisions": [{"text": "决策内容", "evidence": "原文短句，必填"}],
  "action_items": [{"task": "具体任务", "owner": "负责人姓名；若原文未指定则填「未明确」", "due": "截止时间；若原文未指定则填「待定」", "priority": "P0|P1|P2", "evidence": "原文短句，必填"}],
  "risks": [{"risk": "风险描述", "mitigation": "缓解措施（若无则空字符串）", "evidence": "原文短句，必填"}],
  "open_questions": [{"question": "待定问题", "owner": "建议跟进人；若仅有人提问无人认领则填「未明确」", "evidence": "原文短句，必填"}]
}
""",
        "prompt_guide": """
通用纪要：不偏重任何角色，会议说了什么就提炼什么。保持客观、完整、可追溯。

【核心结论 summary_tldr】
- 3～7 条，覆盖：会议主要议题、技术/架构结论、产品策略、客户或业务底线、关键约束。
- 示例：端云协同方案、核心场景路由策略、客户要求「无网时家电控制必须能动」等都要体现。

【决策 decisions】——只放「定下来的事」，不放「谁去做某事」
- 仅包含：会上明确拍板的事、客户/领导提出的硬性要求（底线）、大家达成一致的方向或策略。例如：必须集成某功能、无网时某能力必须可用、采用场景路由策略。
- 不包含：带负责人+截止时间的待办（如「Iris 下周三给基准表」「Sarah 梳理场景路径」）→ 这些只放进 action_items，不要重复放进 decisions。
- 每条必有 evidence，引用原文中拍板或表态的短句。

【行动项 action_items】——谁在何时前完成什么
- 包含：会议总结时列出的待办、以及讨论中承诺的交付（如「Iris 下周三给基准表」「Sarah 梳理 10 个核心场景路径」「大刘下周报风险评估」）。每条应有 task/owner/due/evidence。
- owner：若原文说「谁去跟XX对接」但未指名，填「未明确」；due：若只有「尽快」「下周」等如实填写，完全未提则填「待定」。
- 不要把行动项写进 decisions；decisions 只写「定了什么」，action_items 写「谁何时做什么」。
- 每条必有 evidence。

【风险 risks】
- 包含：技术风险（性能、稳定性、资源不足）、进度/交付风险、业务风险。如「过热掉频」「内存不够」「现练来不及」等都要单列。
- mitigation 若原文未提可留空；evidence 必填。

【待定问题 open_questions】
- 尚未拍板、需后续讨论的问题。owner 为建议跟进人；若只是有人提问、无人认领则填「未明确」。

只输出 JSON，禁止解释。evidence 必须为原文中连续短句，可精简不可编造。
""",
    },

    TEMPLATE_ID_DEV: {
        "name_zh": "技术执行模板",
        "name_en": "The Dev-Centric Sync",
        "desc": "屏蔽话术干扰，直达逻辑变更、接口协议与部署链路；便于转 Jira/GitHub。",
        "audience": "架构师、开发者、测试工程师、技术项目经理",
        "scenario": "技术评审、方案对齐、故障复盘、迭代同步",
        "sections": [
            {"key": "architecture_changes", "label_zh": "架构变更说明", "label_en": "Architecture Changes"},
            {"key": "api_protocol_definitions", "label_zh": "API/协议定义", "label_en": "API & Protocol Definitions"},
            {"key": "bug_issue_list", "label_zh": "Bug & Issue 列表", "label_en": "Bug & Issue List"},
            {"key": "env_dependencies", "label_zh": "环境/依赖需求", "label_en": "Environment & Dependencies"},
        ],
        "schema_json": """
{
  "architecture_changes": [{"change": "变更描述（如从纯云变端云协同、某组件替换）", "component": "受影响组件（如 SoC/端侧/云端）", "evidence": "原文短句，必填"}],
  "api_protocol_definitions": [{"item": "协议或接口名（如 Protobuf）", "field_or_behavior": "定义内容或待办（如协议定义待定、需与XX对接）", "evidence": "原文短句，必填"}],
  "bug_issue_list": [{"description": "问题描述", "repro_condition": "复现条件（如运行10分钟后）", "severity": "P0|P1|P2", "evidence": "原文短句，必填"}],
  "env_dependencies": [{"requirement": "需求（硬件/算力/样机/内存/NPU/量化要求等）", "owner_or_deadline": "负责人或截止时间", "evidence": "原文短句，必填"}]
}
""",
        "prompt_guide": """
技术执行视角：工程师需要逻辑变更、接口与部署、可复现问题、环境约束；不写“用户很生气”，要写“内存/过热怎么复现、谁何时交付”。

【架构变更 architecture_changes】
- 每条：变更内容（change）、受影响组件（component）、evidence 必填。
- 需覆盖：从纯云改端云/端云协同、轻量化模型部署位置（如 1.8B 进 SoC）、内存/NPU/算子等约束、新协议需求。会议提到几项就列几项，不要合并成一条笼统描述。

【API/协议 api_protocol_definitions】
- 每条：协议或接口名（item）、当前状态或待办（field_or_behavior，如“定义待定”“需与小李对接”）、evidence 必填。
- 包含：会上提到的 Protobuf、RPC、端云协议等，以及“谁还没发”“谁去对接”等状态。

【Bug & Issue bug_issue_list】
- 每条：问题描述（description）、复现条件（repro_condition）、严重等级 P0/P1/P2、evidence 必填。
- 需覆盖：端侧过热/掉频、内存不足导致无法跑模型、推理时延暴增等；复现条件尽量具体（如“端侧运行 10 分钟后”）。

【环境/依赖 env_dependencies】
- 每条：具体需求（requirement）、负责人或截止时间（owner_or_deadline）、evidence 必填。
- 需覆盖：芯片内存/NPU/算力卡、样机数量与时间、量化精度要求、数据集/训练资源（如 H20）、基准表交付时间等。会议提到几项就列几项。

只输出 JSON，禁止解释。evidence 必须为原文短句。
""",
    },

    TEMPLATE_ID_GROWTH: {
        "name_zh": "业务增长与产品模板",
        "name_en": "The Growth & UX Blueprint",
        "desc": "关注卖点、痛点、排期与竞品；供市场写推文、PM 调 PRD。",
        "audience": "产品经理、市场、运营、增长负责人",
        "scenario": "需求评审、版本规划、用户反馈会、竞品分析会",
        "sections": [
            {"key": "pain_points", "label_zh": "用户痛点洞察", "label_en": "User Pain Points"},
            {"key": "core_selling_points", "label_zh": "核心卖点同步", "label_en": "Core Selling Points"},
            {"key": "launch_countdown", "label_zh": "上线/发版倒计时", "label_en": "Launch Countdown"},
            {"key": "competitor_mentions", "label_zh": "竞品对标点", "label_en": "Competitor Insights"},
        ],
        "schema_json": """
{
  "pain_points": [{"insight": "痛点归纳", "scene_or_quote": "用户/客户原话或场景", "evidence": "原文短句，必填"}],
  "core_selling_points": [{"point": "卖点表述", "version_or_scope": "版本或范围", "evidence": "原文短句，必填"}],
  "launch_countdown": [{"feature_or_milestone": "功能或里程碑", "mvp_status": "进行中/待完成/待评估等", "expected_delivery": "预计交付时间", "evidence": "原文短句，必填"}],
  "competitor_mentions": [{"competitor": "竞品/友商", "dynamic": "对方动态", "response": "我方应对", "evidence": "原文短句"}]
}
""",
        "prompt_guide": """
业务与增长视角：关心“好不好卖”“什么时候能卖”。提取终端用户/客户/代理商的体验反馈、宣传口径、MVP 与交付时间、友商动态。

【用户痛点 pain_points】——只放「用户/客户可感知」的体验与诉求
- 仅包含：终端用户或客户/代理商反馈的问题与吐槽（如慢、离线不能用、像复读机、上下文断、某功能不好用）。insight 归纳痛点，scene_or_quote 可带原话或场景，evidence 必填。
- 不包含：纯技术实现约束（如芯片内存、过热掉频、NPU 算子）→ 后者属于技术模板，不要放进用户痛点。

【核心卖点 core_selling_points】
- 本版/本阶段的宣传口径或产品主张（如隐私不出户、常用秒回复、场景路由、本地优先）。point/version_or_scope/evidence，每条必填。

【上线/发版倒计时 launch_countdown】
- 各功能或里程碑的 MVP 状态及预计交付时间。feature_or_milestone/mvp_status/expected_delivery/evidence。
- mvp_status 可用：进行中、待完成、待评估、已延期等；若存在时间冲突或“可能赶不上”需在 expected_delivery 或描述中体现（如“推介会前（待评估）”）。
- 会议提到几项就列几项，不要合并。

【竞品对标点 competitor_mentions】
- 仅当会议明确提到具体竞品、友商或对标产品时填写；若未提及，输出空数组 []，不要编造。

只输出 JSON，禁止解释。evidence 必须为原文短句。
""",
    },

    TEMPLATE_ID_EXEC: {
        "name_zh": "高管决策简报",
        "name_en": "The Exec TL;DR Brief",
        "desc": "极简：结论、资源/阻碍、风险红绿灯、里程碑置信度；辅助资源配置。",
        "audience": "CEO、部门负责人、投资人",
        "scenario": "经营会、汇报会、投资尽调",
        "sections": [
            {"key": "conclusion", "label_zh": "会议结论", "label_en": "Conclusion"},
            {"key": "resource_blockers", "label_zh": "资源投入/阻碍", "label_en": "Resource & Blockers"},
            {"key": "risk_traffic_light", "label_zh": "重大风险红绿灯", "label_en": "Risk Traffic Light"},
            {"key": "milestone_confidence", "label_zh": "里程碑状态", "label_en": "Milestone Status"},
        ],
        "schema_json": """
{
  "conclusion": ["仅已达成共识的定论或方向，每条一句短句"],
  "resource_blockers": [{"item": "资源或阻碍描述", "type": "resource|blocker", "evidence": "原文短句，必填"}],
  "risk_traffic_light": [{"risk": "风险描述", "level": "red|yellow|green", "evidence": "原文短句，必填"}],
  "milestone_confidence": {"overall": "整体置信度（如高/中/低）", "notes": "关键依赖或压力说明", "evidence": "原文短句，必填"}
}
""",
        "prompt_guide": """
高管视角：极简。只保留已达成共识的定论、需老板协调的资源/阻碍、风险红绿灯、里程碑置信度。每条能追溯原文。

【会议结论 conclusion】——只放「已拍板的事实或方向」，不放「需要做XX」
- 仅包含：会上已达成共识的结论、客户/领导提出的底线、确定的方向（如端云协同、场景路由、方言必须集成）。3～5 条短句。
- 不包含：待办或阻碍（如「需要尽快确定 Protobuf」→ 放进 resource_blockers，不要放进 conclusion）。

【资源投入/阻碍 resource_blockers】
- 需上级协调的资源（resource）或阻碍（blocker）：如算力/H20 申请、芯片或端侧内存约束、协议/定义未到位（如 Protobuf 小李未发）、人力或专项预算、方言数据集与训练资源等。会议提到几项就列几项，每条 type 填 resource 或 blocker，evidence 必填。

【重大风险红绿灯 risk_traffic_light】
- red=致命（如重大延期、现场崩、交付不可达），yellow=需关注（如稳定性风险、时间紧），green=可接受。level 必为 red|yellow|green。
- 需覆盖：技术风险（过热掉频、内存不足）、交付风险（方言赶不上推介会）、稳定性风险等。会议提到几项就列几项，每条 evidence 必填。

【里程碑状态 milestone_confidence】
- 当前关键里程碑（如 2.0/推介会）的整体置信度（overall）、关键依赖或时间压力（notes）、evidence 必填。

只输出 JSON，禁止解释。evidence 必须为原文短句。
""",
    },

    TEMPLATE_ID_EXTERNAL: {
        "name_zh": "外部协作与商务模板",
        "name_en": "The External-Facing Recap",
        "desc": "脱敏与契约化：仅保留交付、责任、商务节点与下次同步；避免内部分歧外泄。",
        "audience": "第三方供应商、代理商、外包团队、大客户",
        "scenario": "对外对接会、验收会、商务周会",
        "sections": [
            {"key": "deliverables", "label_zh": "交付物列表", "label_en": "Deliverables"},
            {"key": "raci_matrix", "label_zh": "双方责任矩阵 (RACI)", "label_en": "RACI Matrix"},
            {"key": "commercial_milestones", "label_zh": "商务节点", "label_en": "Commercial Milestones"},
            {"key": "next_sync_time", "label_zh": "下一次同步时间", "label_en": "Next Sync Time"},
        ],
        "schema_json": """
{
  "deliverables": [{"item": "交付物描述", "owner_side": "我方/对方或具体方（如对方-赵总）", "due": "截止时间", "evidence": "原文短句，必填"}],
  "raci_matrix": [{"task_or_area": "任务或领域", "R": "负责方", "A": "执行方", "C": "咨询方", "I": "知情方", "evidence": "原文短句，必填"}],
  "commercial_milestones": [{"milestone": "节点描述", "criteria_or_payment": "验收标准或付款条件", "due": "时间", "evidence": "原文短句，必填"}],
  "next_sync_time": {"datetime_or_desc": "时间或描述；若会议未约定则填「未明确」", "evidence": "原文短句或「会议未明确约定」"}
}
""",
        "prompt_guide": """
外部协作视角：脱敏。内部争吵、技术细节、自研缺陷不输出；只保留与“合作交付”相关、可对外呈现的内容。每条可追溯原文。

【交付物列表 deliverables】
- 我方或对方/第三方需提供的文档、物料、样机等。item/owner_side（建议标明「我方」或「对方」或具体方如「对方-赵总」）/due/evidence，每条 evidence 必填。

【双方责任矩阵 raci_matrix】——体现「我方 vs 对方/客户」的责任边界
- R=负责、A=执行、C=咨询、I=知情。按任务或领域列出，建议标明责任属于我方还是对方（如「我方-Iris」「对方-赵总」）；若某方未明确可写「我方待定」。
- 不把不在场第三方当作执行方：如「与小李对接」的责任在我方某人，可写 R 或 A 为「我方待定」、C 可写「需对接-小李」或留空。会议提到几项就列几项，每条 evidence 必填。

【商务节点 commercial_milestones】
- 验收、交付、付款或演示等关键节点。milestone/criteria_or_payment/due/evidence，每条 evidence 必填。

【下一次同步时间 next_sync_time】
- 仅当会议**明确约定**下次会议或同步时间时填写具体时间；若未明确约定，datetime_or_desc 填「未明确」，不要用其他日期推断（如不能因「下周三交基准表」就写下次同步为下周三）。evidence 可填原文或「会议未明确约定」。

只输出 JSON，禁止解释。evidence 必须为原文短句或明确说明未约定。
""",
    },
}


def template_ids():
    """返回所有模板 id 列表（顺序固定）。"""
    return [
        TEMPLATE_ID_GENERAL,
        TEMPLATE_ID_DEV,
        TEMPLATE_ID_GROWTH,
        TEMPLATE_ID_EXEC,
        TEMPLATE_ID_EXTERNAL,
    ]


def template_names():
    """返回供 UI 使用的展示名列表：中文 (English)。"""
    return [f"{TEMPLATES[tid]['name_zh']}（{TEMPLATES[tid]['name_en']}）" for tid in template_ids()]


def template_id_to_display_name(template_id: str) -> str:
    """由 id 得到展示名。"""
    t = TEMPLATES.get(template_id)
    if not t:
        return template_id
    return f"{t['name_zh']}（{t['name_en']}）"


def display_name_to_template_id(display_name: str) -> str:
    """由展示名反查 id；若为旧版名称或未知则返回 general。"""
    for tid in template_ids():
        if template_id_to_display_name(tid) == display_name:
            return tid
    # 旧版或兼容：若包含部分关键词则映射
    d = (display_name or "").strip()
    if not d:
        return TEMPLATE_ID_GENERAL
    if "通用" in d or "General" in d or "Standard Meeting" in d or "产品/跨职能" in d:
        return TEMPLATE_ID_GENERAL
    if "技术" in d or "Dev" in d or "开发" in d:
        return TEMPLATE_ID_DEV
    if "业务" in d or "Growth" in d or "产品" in d and "跨职能" not in d:
        return TEMPLATE_ID_GROWTH
    if "高管" in d or "Exec" in d:
        return TEMPLATE_ID_EXEC
    if "外部" in d or "External" in d or "商务" in d:
        return TEMPLATE_ID_EXTERNAL
    return TEMPLATE_ID_GENERAL


def get_template(template_id: str) -> dict:
    """获取模板配置；传入 id 或展示名均可（展示名会转 id）。"""
    tid = display_name_to_template_id(template_id) if template_id in template_names() else template_id
    return TEMPLATES.get(tid, TEMPLATES[TEMPLATE_ID_GENERAL])


def get_template_prompt_guide(template_name_or_id: str) -> str:
    """获取该模板的提炼指引。"""
    t = get_template(template_name_or_id)
    return (t.get("prompt_guide") or "").strip()


def get_template_schema_json(template_name_or_id: str) -> str:
    """获取该模板要求输出的 JSON schema 描述（给 LLM）。"""
    t = get_template(template_name_or_id)
    return (t.get("schema_json") or "").strip()


def get_template_desc(template_name_or_id: str) -> str:
    """供 UI 展示的简短描述（含目标读者、典型场景）。"""
    t = get_template(template_name_or_id)
    if not t:
        return ""
    desc = t.get("desc", "")
    audience = t.get("audience", "")
    scenario = t.get("scenario", "")
    parts = [desc]
    if audience:
        parts.append(f"目标读者：{audience}")
    if scenario:
        parts.append(f"典型场景：{scenario}")
    return " | ".join(parts)


def get_template_sections(template_name_or_id: str) -> list:
    """返回该模板的板块列表，每项为 {"key": ..., "label_zh": ..., "label_en": ...}。"""
    t = get_template(template_name_or_id)
    return list(t.get("sections") or [])


def get_section_label_zh(section: dict) -> str:
    return section.get("label_zh") or section.get("key") or ""


def get_section_label_en(section: dict) -> str:
    return section.get("label_en") or section.get("key") or ""


def get_section_display(section: dict) -> str:
    """板块展示：中文 (English)。"""
    zh = get_section_label_zh(section)
    en = get_section_label_en(section)
    return f"{zh}（{en}）" if en else zh


def detect_template_id_from_data(data: dict) -> str:
    """根据 result_json 的 key 推断模板 id，用于历史数据无 template 信息时。"""
    if not data or not isinstance(data, dict):
        return TEMPLATE_ID_GENERAL
    keys = set(data.keys())
    if "architecture_changes" in keys or "api_protocol_definitions" in keys or "bug_issue_list" in keys:
        return TEMPLATE_ID_DEV
    if "pain_points" in keys or "core_selling_points" in keys or "launch_countdown" in keys:
        return TEMPLATE_ID_GROWTH
    if "conclusion" in keys or "risk_traffic_light" in keys or "milestone_confidence" in keys:
        return TEMPLATE_ID_EXEC
    if "deliverables" in keys or "raci_matrix" in keys or "next_sync_time" in keys:
        return TEMPLATE_ID_EXTERNAL
    return TEMPLATE_ID_GENERAL
