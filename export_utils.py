import json
import pandas as pd

def export_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# 各模板用于「列表导出 CSV」的字段（若存在则导出）
TEMPLATE_CSV_KEY = {
    "general": "action_items",
    "dev": "bug_issue_list",
    "growth": "launch_countdown",
    "exec": "conclusion",  # list of str，也可导出
    "external": "deliverables",
}


def action_items_to_csv(data: dict, template_name: str = "") -> str:
    """
    按模板导出可列表化的内容为 CSV。
    通用模板导出 action_items；技术模板导出 bug_issue_list；外部模板导出 deliverables；以此类推。
    若未匹配或该 key 不存在/为空，返回空字符串。
    """
    try:
        from templates import display_name_to_template_id, detect_template_id_from_data
        tid = display_name_to_template_id(template_name) if template_name else detect_template_id_from_data(data)
    except Exception:
        tid = "general"
    key = TEMPLATE_CSV_KEY.get(tid, "action_items")
    items = data.get(key)
    if not items or not isinstance(items, list):
        # 兼容：旧数据只有 action_items
        items = data.get("action_items", [])
    if not items:
        return ""
    # conclusion 可能是 list of str
    if items and isinstance(items[0], str):
        df = pd.DataFrame({"item": items})
    else:
        df = pd.DataFrame(items)
    return df.to_csv(index=False)
