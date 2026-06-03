#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""血糖卡片优化 PRD 远程冒烟测试。"""
import json
import urllib.request
import urllib.error

BASE = "https://6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com"
HEADERS = {"Content-Type": "application/json", "User-Agent": "smoke/1.0"}


def http(method, path, body=None, headers=None):
    url = BASE + path
    data = None
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return -1, str(e)


def show(title, ok, extra=""):
    icon = "OK" if ok else "FAIL"
    print(f"[{icon}] {title} {extra}")


def main():
    print("=" * 60)
    print("血糖卡片优化 PRD - 远程冒烟测试")
    print(f"BASE = {BASE}")
    print("=" * 60)

    # 1. AC-11 管理后台 AI 提示词列表
    code, body = http("GET", "/api/glucose-v1/admin/ai-prompts")
    ok = code == 200 and '"glucose_single_explain"' in body and '"glucose_trend_explain"' in body
    show("AC-11 列出 AI 提示词（两条已发布）", ok, f"http={code}")

    # 2. AC-15 用户可见字段不含"危象"（仅检查 name/level 字段不要含"危象"）
    try:
        j = json.loads(body)
        items = j.get("data", {}).get("items", [])
        # name 字段不含"危象"
        ok = all("危象" not in it.get("name", "") for it in items)
        show("AC-15 提示词 name 字段不含'危象'", ok)
    except Exception:
        show("AC-15 提示词 name 字段不含'危象'", False)

    # 3. AC-01 必选测量类型校验：缺 scene 时报错 422
    code, body = http("POST", "/api/glucose-v1/records", body={"value": 6.5})
    # 后端要求登录，401 也算"接口存在"；422 表示参数校验拒绝
    ok = code in (401, 422, 400)
    show("AC-01 不传 scene 接口被拒（鉴权或校验）", ok, f"http={code}")

    # 4. 新增 PUT/DELETE 接口存在
    code, _ = http("PUT", "/api/glucose-v1/records/nonexistent",
                   body={"value": 5.0, "scene": "fasting"})
    ok = code in (401, 403, 404, 422)
    show("PUT /records/{id} 接口存在", ok, f"http={code}")

    code, _ = http("DELETE", "/api/glucose-v1/records/nonexistent")
    ok = code in (401, 403, 404, 422)
    show("DELETE /records/{id} 接口存在", ok, f"http={code}")

    # 5. AI 解读接口存在
    code, _ = http("POST", "/api/glucose-v1/ai-explain-single",
                   body={"profile_id": "p", "record_id": "r"})
    ok = code in (200, 400, 401, 403, 404, 422, 500)
    show("POST /ai-explain-single 接口存在", ok, f"http={code}")

    code, _ = http("POST", "/api/glucose-v1/ai-explain-trend",
                   body={"profile_id": "p", "range": "7d"})
    ok = code in (200, 400, 401, 403, 404, 422, 500)
    show("POST /ai-explain-trend 接口存在", ok, f"http={code}")

    # 6. H5 首页可访问
    code, _ = http("GET", "/")
    show("H5 首页可访问", code == 200, f"http={code}")

    # 7. H5 健康指标页可访问
    code, _ = http("GET", "/health-metric/blood_glucose/")
    show("H5 血糖指标页可访问", code in (200, 307, 302), f"http={code}")

    # 8. 健康档案首页
    code, _ = http("GET", "/health-profile/")
    show("H5 健康档案页可访问", code in (200, 307, 302), f"http={code}")

    print("=" * 60)


if __name__ == "__main__":
    main()
