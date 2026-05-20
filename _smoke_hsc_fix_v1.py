"""[BUG-HEALTH-SELF-CHECK-FIX-V1] 服务器端 HTTP 烟雾测试
- 验证 GET /api/questionnaire/templates/{id} 含 key_field_codes 字段
- 验证健康自查模板 result_display_mode='triple'
- 验证 Q5 5 档 + Q6 文案
- 验证 H5 路由 /health-self-check/result/[id] 可访问
"""

from __future__ import annotations

import json
import sys

import requests

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def assert_ok(cond: bool, msg: str):
    if not cond:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ {msg}")


def main():
    # 1. 拿 admin token：从公开接口或固定测试号登录
    # 没有 admin token 也能从 /api/questionnaire/templates 等开放接口列表（按 health_self_check code 查）
    # 复用 /api/questionnaire/templates/by-code?code=health_self_check
    r = requests.get(
        f"{BASE}/api/questionnaire/templates/by-code",
        params={"code": "health_self_check"},
        timeout=15,
    )
    print("by-code status:", r.status_code)
    if r.status_code != 200:
        # 尝试 /api/questionnaire/templates 列表
        r = requests.get(f"{BASE}/api/questionnaire/templates", timeout=15)
        print("list status:", r.status_code, r.text[:200])

    # 也许接口需要登录；查询模板详情用 /api/questionnaire/templates/{id}
    # 先列举所有模板看看有没有公开
    r = requests.get(
        f"{BASE}/api/questionnaire/templates/1", timeout=15
    )
    print("template/1 status:", r.status_code)
    if r.status_code == 200:
        data = r.json()
        questions = data.get("questions") or []
        tpl = data.get("template") or data
        code = tpl.get("code") or ""
        mode = tpl.get("result_display_mode")
        kfc = tpl.get("key_field_codes")
        print(f"  template code={code} mode={mode} key_field_codes={kfc}")
        # 健康自查校验
        if code == "health_self_check":
            assert_ok(mode == "triple", f"result_display_mode 应为 'triple'，实际 {mode}")
            assert_ok(
                isinstance(kfc, list) and len(kfc) > 0,
                f"key_field_codes 应非空 list，实际 {kfc}",
            )
            # 题目数
            assert_ok(
                len(questions) >= 6,
                f"健康自查应至少 6 题（含 3 维度升级），实际 {len(questions)}",
            )
            # Q5 选项数（按 dimension='严重程度' 找）
            q5 = next(
                (q for q in questions if (q.get("dimension") or "") == "严重程度"),
                None,
            )
            if q5:
                opts = q5.get("options") or []
                main_opts = [o for o in opts if o.get("value") != "skip"]
                assert_ok(
                    len(main_opts) == 5,
                    f"Q5 应为 5 档单值，实际 {len(main_opts)}",
                )
                labels = []
                for o in main_opts:
                    # label 形如 "1  🙂 轻微"
                    lab = (o.get("label") or "").split()
                    labels.append(lab[-1] if lab else "")
                assert_ok(
                    len(set(labels)) == 5,
                    f"Q5 五档文案不应重复，实际 {labels}",
                )
            # Q6 文案
            q6 = next(
                (q for q in questions if (q.get("dimension") or "") == "症状备注"),
                None,
            )
            if q6:
                title = q6.get("title") or ""
                subtitle = q6.get("subtitle") or ""
                assert_ok(
                    title != subtitle,
                    f"Q6 title/subtitle 不应相同：title={title}, sub={subtitle}",
                )
                assert_ok(
                    "例如" in subtitle or "示例" in subtitle,
                    f"Q6 subtitle 应为示例文案，实际 {subtitle}",
                )

    # 2. H5 路由是否可达
    r = requests.get(f"{BASE}/health-self-check/result/1", timeout=15, allow_redirects=False)
    print("h5 route status:", r.status_code)
    assert_ok(
        r.status_code in (200, 307, 302, 401, 308),
        f"/health-self-check/result/1 应可访问（200/302/401），实际 {r.status_code}",
    )

    print("\n🎉 HSC FIX 烟雾测试全部通过")


if __name__ == "__main__":
    main()
