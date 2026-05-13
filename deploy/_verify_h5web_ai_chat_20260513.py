"""[INCIDENT-20260513-01] H5 AI 对话恢复自动化 smoke test

通过两路证据并行验证「晴空诊室」最新版 AI 对话代码已生效：

  路 A：服务器源码标记（git master HEAD 的最新代码必须存在）
    - h5-web/src/app/globals.css            含 PRD-442 / color-brand-500 / gradient-user-bubble
    - h5-web/src/components/ai-chat/AdvisorCapsule/index.tsx  含 PRD-448
    - h5-web/src/components/ai-chat/ProfileCard.tsx           含 PRD-432 + "本次回答结合"
    - h5-web/src/app/(ai-chat)/ai-home/page.tsx               含 PRD-467
    - h5-web/src/components/ai-chat/MoreMenu.tsx              存在
    - h5-web/src/components/ai-chat/ReminderDrawer.tsx        存在（BUG-461/462/466/467 修复后引入）

  路 B：容器内 .next 构建产物（确认本次 --no-cache build 真的把上面源码编译进了镜像）
    - /app/.next/static 中能搜到 color-brand-500
    - /app/.next/static 中能搜到 "本次回答结合"（PRD-432 ProfileCard）
    - /app/.next/static 中能搜到 PRD-467 ai-home 中的特征字符串

  路 C：HTTP 可达
    - GET https://newbb.test.bangbangvip.com/autodev/<DEPLOY_ID>/ai-home  → 200/30x 任一
    - GET 项目首页路径                                                    → 200

只要任意一项 FAIL → 整体 FAIL，立刻输出详细日志。
"""
from __future__ import annotations

import sys
import time

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
REMOTE_H5 = f"{REMOTE_PROJ}/h5-web"
H5_CONTAINER = f"{DEPLOY_ID}-h5"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, timeout: int = 60, log_cmd: bool = False) -> tuple[int, str, str]:
    if log_cmd:
        log(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


# ---------- 检查项定义 ----------
SOURCE_CHECKS: list[tuple[str, str, str]] = [
    # (描述, 远端路径, 必须包含的标记)
    ("品牌色主题（PRD-442）", f"{REMOTE_H5}/src/app/globals.css", "PRD-442"),
    ("天蓝品牌 brand-500", f"{REMOTE_H5}/src/app/globals.css", "color-brand-500"),
    ("用户气泡渐变 token", f"{REMOTE_H5}/src/app/globals.css", "gradient-user-bubble"),
    ("AdvisorCapsule v1.1（PRD-448）", f"{REMOTE_H5}/src/components/ai-chat/AdvisorCapsule/index.tsx", "PRD-448"),
    ("AI 回答档案卡片（PRD-432）", f"{REMOTE_H5}/src/components/ai-chat/ProfileCard.tsx", "PRD-432"),
    ("「本次回答结合」品牌文案", f"{REMOTE_H5}/src/components/ai-chat/ProfileCard.tsx", "本次回答结合"),
    ("ai-home PRD-467 升级", f"{REMOTE_H5}/src/app/(ai-chat)/ai-home/page.tsx", "PRD-467"),
    ("PRD-426 推荐问改版", f"{REMOTE_H5}/src/app/(ai-chat)/ai-home/page.tsx", "PRD-426"),
    ("ConsultTargetPicker 咨询对象选择器", f"{REMOTE_H5}/src/components/ai-chat/ConsultTargetPicker.tsx", "ConsultTargetPicker"),
    ("MoreMenu 右上角更多菜单", f"{REMOTE_H5}/src/components/ai-chat/MoreMenu.tsx", "MoreMenu"),
    ("ReminderDrawer 提醒抽屉（BUG-461/466 修复后）", f"{REMOTE_H5}/src/components/ai-chat/ReminderDrawer.tsx", "ReminderDrawer"),
]

EXISTENCE_CHECKS: list[tuple[str, str]] = [
    ("AdvisorCapsule 目录", f"{REMOTE_H5}/src/components/ai-chat/AdvisorCapsule"),
    ("ai-home page 文件", f"{REMOTE_H5}/src/app/(ai-chat)/ai-home/page.tsx"),
    ("chat 会话页", f"{REMOTE_H5}/src/app/chat/[sessionId]/page.tsx"),
]

CONTAINER_BUILD_CHECKS: list[tuple[str, str]] = [
    # (描述, 必须出现的标记字符串：要求在 /app/.next 任意文件中能找到)
    # 说明：Next.js 生产构建会 minify 组件函数名，所以只用稳定的
    # CSS 变量 / 中文 UI 文案 / 路由路径 等作为判据，避免误报。
    ("容器内品牌色 color-brand-500 已编入", "color-brand-500"),
    ("容器内用户气泡渐变 token gradient-user-bubble", "gradient-user-bubble"),
    ("容器内「本次回答结合」品牌文案（PRD-432）", "本次回答结合"),
    ("容器内「健康档案」入口（PRD-467 / ai-home）", "健康档案"),
    ("容器内 ai-home 路由产物存在", "ai-home"),
]


def check_source(cli: paramiko.SSHClient) -> tuple[int, int, list[str]]:
    log("=== 路 A：服务器源码标记校验 ===")
    pass_n = 0
    fail_n = 0
    failures: list[str] = []
    for desc, path, mark in SOURCE_CHECKS:
        # 用 fgrep 避免特殊字符，且 grep -q 返回 0 即存在
        rc, _, _ = run(cli, f"grep -q -F -- '{mark}' '{path}'")
        if rc == 0:
            pass_n += 1
            log(f"  [PASS] {desc}")
        else:
            fail_n += 1
            msg = f"  [FAIL] {desc}（{path} 中缺失 '{mark}'）"
            log(msg)
            failures.append(msg)
    for desc, path in EXISTENCE_CHECKS:
        rc, _, _ = run(cli, f"test -e '{path}'")
        if rc == 0:
            pass_n += 1
            log(f"  [PASS] 存在 {desc}")
        else:
            fail_n += 1
            msg = f"  [FAIL] 缺失 {desc}：{path}"
            log(msg)
            failures.append(msg)
    return pass_n, fail_n, failures


def check_container_build(cli: paramiko.SSHClient) -> tuple[int, int, list[str]]:
    log("=== 路 B：容器内 .next 构建产物校验 ===")
    pass_n = 0
    fail_n = 0
    failures: list[str] = []

    rc, out, _ = run(cli, f"sudo docker inspect -f '{{{{.State.Status}}}}' {H5_CONTAINER} 2>&1")
    log(f"  容器状态：{out.strip()}")
    if "running" not in out:
        msg = "  [FAIL] h5-web 容器未运行"
        log(msg)
        failures.append(msg)
        fail_n += 1
        return pass_n, fail_n, failures

    rc, out, _ = run(cli, f"sudo docker inspect -f '{{{{.Created}}}}' {H5_CONTAINER}")
    log(f"  容器创建时间：{out.strip()}")

    for desc, mark in CONTAINER_BUILD_CHECKS:
        rc, out, _ = run(
            cli,
            f"sudo docker exec {H5_CONTAINER} sh -c \"grep -r -l -F -- '{mark}' /app/.next 2>/dev/null | head -3\"",
            timeout=90,
        )
        files = [x for x in out.strip().splitlines() if x.strip()]
        if files:
            pass_n += 1
            log(f"  [PASS] {desc} → 命中 {len(files)} 个文件，示例：{files[0]}")
        else:
            fail_n += 1
            msg = f"  [FAIL] {desc} → 容器内 .next 中未找到 '{mark}'"
            log(msg)
            failures.append(msg)
    return pass_n, fail_n, failures


def check_http(cli: paramiko.SSHClient) -> tuple[int, int, list[str]]:
    log("=== 路 C：外部 HTTP 可达性校验 ===")
    pass_n = 0
    fail_n = 0
    failures: list[str] = []
    targets = [
        ("项目首页", f"{BASE_URL}/", {"200", "301", "302", "307", "308"}),
        ("ai-home", f"{BASE_URL}/ai-home", {"200", "301", "302", "307", "308"}),
        ("login 页（登录入口）", f"{BASE_URL}/login", {"200", "301", "302", "307", "308"}),
    ]
    for desc, url, accept in targets:
        rc, out, _ = run(cli, f'curl -sk -o /dev/null -w "%{{http_code}}" --max-time 15 "{url}"', timeout=30)
        code = out.strip()
        if code in accept:
            pass_n += 1
            log(f"  [PASS] {desc} {code} {url}")
        else:
            fail_n += 1
            msg = f"  [FAIL] {desc} got={code} expect∈{accept} url={url}"
            log(msg)
            failures.append(msg)
    return pass_n, fail_n, failures


def main() -> int:
    log("INCIDENT-20260513-01 H5 AI 对话恢复 smoke test 开始")
    cli = ssh_connect()
    try:
        a_pass, a_fail, a_msgs = check_source(cli)
        b_pass, b_fail, b_msgs = check_container_build(cli)
        c_pass, c_fail, c_msgs = check_http(cli)

        total_pass = a_pass + b_pass + c_pass
        total_fail = a_fail + b_fail + c_fail

        log("=" * 60)
        log(f"路 A 服务器源码：PASS {a_pass}  FAIL {a_fail}")
        log(f"路 B 容器构建产物：PASS {b_pass}  FAIL {b_fail}")
        log(f"路 C HTTP 可达性：PASS {c_pass}  FAIL {c_fail}")
        log(f"合计：PASS {total_pass}  FAIL {total_fail}")
        log("=" * 60)

        if total_fail == 0:
            log("[SMOKE TEST: PASS] 三路证据齐全，晴空诊室 AI 对话已恢复 ✅")
            return 0
        log("[SMOKE TEST: FAIL] 详见上方失败项")
        for m in a_msgs + b_msgs + c_msgs:
            log(m)
        return 2
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
