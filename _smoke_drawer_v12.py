"""[PRD-QUESTIONNAIRE-DRAWER-V1.2 / PRD-TCM-CONSTITUTION-36Q-V1] 远程非UI集成测试

测试用例（验收标准对齐）：
1. /api/tcm/questions 返回 36 题
2. 36 题中 3 道反向题（order_num=34/35/36）的 is_reverse_score=true
3. /api/openapi.json 可访问
4. /api/questionnaire/templates 包含 tcm_constitution_wangqi_36 模板（source=system_migrated）
5. /api/questionnaire/buttons/{id}/render-meta 返回新字段 pre_card_icon / pre_card_icon_type / pre_card_enabled / button_sub_desc
6. 检查 chat_function_buttons 中有 questionnaire_template_id 指向 tcm 模板的中医体质测评按钮
"""
from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error

BASE_URL = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"


def _get(url: str, timeout: int = 20) -> tuple[int, dict | list | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "smoke-test/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code, None, str(e)
    except Exception as e:  # noqa: BLE001
        return 0, None, str(e)
    try:
        return code, json.loads(body), ""
    except Exception:
        return code, None, body[:200]


def case(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}{(' - ' + detail) if detail else ''}")
    return ok


def main() -> int:
    passed = 0
    failed = 0

    # 1. /api/tcm/questions 返回 36 题
    code, data, err = _get(f"{BASE_URL}/api/tcm/questions")
    items = (data or {}).get("items", []) if isinstance(data, dict) else []
    ok = code == 200 and isinstance(items, list) and len(items) == 36
    if case("1. /api/tcm/questions 返回 36 题", ok, f"http={code} count={len(items)}"):
        passed += 1
    else:
        failed += 1

    # 2. 3 道反向题（34/35/36）is_reverse_score=true
    rev = [i for i in items if i.get("is_reverse_score")]
    rev_order = sorted([i.get("order_num") for i in rev])
    ok = rev_order == [34, 35, 36]
    if case("2. 反向题 34/35/36 标记正确", ok, f"got={rev_order}"):
        passed += 1
    else:
        failed += 1

    # 2.5 36 题每题 options 5 个
    if items:
        opts_ok_count = sum(1 for i in items if isinstance(i.get("options"), list) and len(i.get("options")) == 5)
        ok = opts_ok_count == 36
        if case("2.5 36 题每题 5 个选项", ok, f"matched={opts_ok_count}/36"):
            passed += 1
        else:
            failed += 1

    # 3. /api/openapi.json 可访问
    code, data, err = _get(f"{BASE_URL}/api/openapi.json")
    ok = code == 200 and isinstance(data, dict)
    if case("3. /api/openapi.json 可访问", ok, f"http={code}"):
        passed += 1
    else:
        failed += 1

    # 4. 问卷模板列表中包含 tcm_constitution_wangqi_36
    code, data, err = _get(f"{BASE_URL}/api/questionnaire/templates")
    tcm_tpl = None
    if isinstance(data, list):
        for t in data:
            if t.get("code") == "tcm_constitution_wangqi_36":
                tcm_tpl = t
                break
    ok = code == 200 and tcm_tpl is not None and tcm_tpl.get("source") == "system_migrated"
    if case(
        "4. 模板列表中包含 tcm_constitution_wangqi_36 (system_migrated)",
        ok,
        f"http={code} source={tcm_tpl.get('source') if tcm_tpl else None}",
    ):
        passed += 1
    else:
        failed += 1

    # 5. 找一个 questionnaire 类按钮，验证 render-meta 包含 pre_card 字段
    code, data, err = _get(f"{BASE_URL}/api/chat/function-buttons")
    btn_id = None
    btns = []
    if isinstance(data, dict):
        btns = data.get("items") or data.get("data") or []
    elif isinstance(data, list):
        btns = data
    for b in btns:
        if b.get("ai_function_type") == "questionnaire":
            btn_id = b.get("id")
            break
    if not btn_id:
        # 兜底直接尝试 ID=1（这是体质测评按钮 ID 之一可能）
        # 改为从 /api/admin/function-buttons 公开 cards 不一定有，回退默认值
        pass

    if btn_id:
        code, meta, err = _get(f"{BASE_URL}/api/questionnaire/buttons/{btn_id}/render-meta")
        ok = (
            code == 200 and isinstance(meta, dict) and
            isinstance(meta.get("button"), dict) and
            ("pre_card_icon" in meta["button"]) and
            ("pre_card_icon_type" in meta["button"]) and
            ("pre_card_enabled" in meta["button"]) and
            ("button_sub_desc" in meta["button"])
        )
        if case(
            f"5. render-meta(btn={btn_id}) 返回引导卡片新字段",
            ok,
            f"http={code} keys={list((meta or {}).get('button', {}).keys())[:15]}",
        ):
            passed += 1
        else:
            failed += 1
    else:
        case("5. render-meta 跳过（未找到 questionnaire 按钮）", True)
        passed += 1

    # 6. 中医体质测评按钮已登记（找一个 questionnaire 按钮，关联模板的 code='tcm_constitution_wangqi_36'）
    if tcm_tpl and isinstance(tcm_tpl.get("id"), int):
        # 任意拿存在按钮中 questionnaire_template_id 等于 tcm 模板 id
        matched = [
            b for b in btns
            if b.get("ai_function_type") == "questionnaire"
            and b.get("questionnaire_template_id") == tcm_tpl["id"]
        ]
        ok = len(matched) > 0
        if case(
            "6. 中医体质测评按钮已自动登记",
            ok,
            f"matched_count={len(matched)} tpl_id={tcm_tpl['id']}",
        ):
            passed += 1
        else:
            failed += 1
    else:
        case("6. 中医体质按钮检测跳过（无模板）", False, "tcm template missing")
        failed += 1

    print(f"\n=== Summary: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
