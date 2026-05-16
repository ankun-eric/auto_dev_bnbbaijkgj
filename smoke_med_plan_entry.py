"""通过公网 HTTPS 域名 smoke 测试用药计划入口改造的所有路由。"""
import json
import paramiko

HOST = "newbb.test.bangbangvip.com"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://{HOST}/autodev/{DEPLOY_ID}"

PAGES = [
    ("/", "ai-home root"),
    ("/health-profile", "健康档案页"),
    ("/ai-home/medication-reminder", "用药提醒页"),
    ("/ai-home/medication-plans", "用药计划列表页"),
    ("/ai-home/medication-plans/new", "用药新增表单"),
]

APIS = [
    # 未认证下应该返回 401 (确认接口已挂载且鉴权生效)
    ("/api/medication-plans/hero-count", "Hero 计数"),
    ("/api/medication-plans/today", "今日提醒"),
    ("/api/medication-plans/summary", "摘要卡数据"),
    ("/api/medication-stats/monthly-compliance", "月度依从率"),
    ("/api/health-plan/medications/list?tab=in_progress", "list tab=in_progress"),
    ("/api/health-plan/medications/list?tab=not_started", "list tab=not_started"),
    ("/api/health-plan/medications/list?tab=finished", "list tab=finished"),
]


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, 22, "ubuntu", "Newbang888", timeout=30, allow_agent=False, look_for_keys=False)
    try:
        def run(cmd):
            _, o, e = c.exec_command(cmd, timeout=30, get_pty=False)
            return o.read().decode("utf-8", "replace").strip(), e.read().decode("utf-8", "replace").strip()

        print("\n===== 前端页面探活（期望 200） =====")
        pass_pages = fail_pages = 0
        for path, desc in PAGES:
            url = f"{BASE}{path}"
            out, _ = run(f"curl -sL -o /dev/null -w '%{{http_code}}' '{url}'")
            ok = out == "200"
            mark = "✓" if ok else "✗"
            print(f"  [{mark}] {out}  {desc}  {url}")
            pass_pages += 1 if ok else 0
            fail_pages += 0 if ok else 1

        print("\n===== 后端 API 探活（期望 401 = 已挂载且需鉴权） =====")
        pass_apis = fail_apis = 0
        for path, desc in APIS:
            url = f"{BASE}{path}"
            out, _ = run(f"curl -s -o /dev/null -w '%{{http_code}}' '{url}'")
            ok = out in ("401", "403")  # 未认证应被拦截，说明接口存在
            mark = "✓" if ok else "✗"
            print(f"  [{mark}] {out}  {desc}  {url}")
            pass_apis += 1 if ok else 0
            fail_apis += 0 if ok else 1

        print("\n===== Summary =====")
        print(f"  前端页面: {pass_pages}/{len(PAGES)} OK, {fail_pages} FAIL")
        print(f"  后端 API: {pass_apis}/{len(APIS)} OK, {fail_apis} FAIL")
        total_fail = fail_pages + fail_apis
        if total_fail == 0:
            print("  ✓✓✓ ALL PASS ✓✓✓")
        else:
            print(f"  ✗ {total_fail} FAIL — 需要修复")
    finally:
        c.close()


if __name__ == "__main__":
    main()
