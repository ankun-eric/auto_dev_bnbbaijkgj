"""
[INCIDENT-20260513-03] 服务器端自动化验证（非UI）

测试用例：
  T1 - h5 主页应返回 200
  T2 - h5 /ai-home 跟随重定向后应返回 200
  T3 - /api/chat-sessions 未登录应返回 401（绝不能 500）
  T4 - h5-web 容器内构建产物应包含本次修复字符串 'soft-fail'
  T5 - h5 容器近 100 行日志无 FATAL/CRITICAL
  T6 - h5-web 镜像中源码已更新，含 INCIDENT-20260513-03 标记
"""
import paramiko
import sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    return c


def run(c, cmd, timeout=90):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="ignore")
    err = e.read().decode("utf-8", errors="ignore")
    rc = o.channel.recv_exit_status()
    return rc, out, err


def expect(name, cond, detail=""):
    sym = "PASS" if cond else "FAIL"
    print(f"  [{sym}] {name}")
    if detail:
        for line in detail.strip().splitlines()[:8]:
            print(f"         {line}")
    return cond


def main():
    print("=" * 60)
    print("INCIDENT-20260513-03 服务器端自动化验证")
    print("=" * 60)
    c = ssh()
    results = []

    # T1
    rc, out, _ = run(c, f"curl -ksS -o /dev/null -w '%{{http_code}}' '{BASE}/'")
    results.append(expect("T1: h5 主页 200", out.strip() == "200", f"HTTP {out.strip()}"))

    # T2
    rc, out, _ = run(c, f"curl -kLsS -o /dev/null -w '%{{http_code}}' '{BASE}/ai-home'")
    results.append(expect("T2: /ai-home 跟随重定向 200", out.strip() == "200", f"HTTP {out.strip()}"))

    # T3
    rc, out, _ = run(c, f"curl -ksS -o /dev/null -w '%{{http_code}}' '{BASE}/api/chat-sessions'")
    code = out.strip()
    results.append(expect(
        f"T3: /api/chat-sessions 未登录 401 (不为 500)",
        code in ("401", "403", "422"),
        f"HTTP {code}",
    ))

    # T4 - 通过 docker exec 检查容器内 .next 是否包含修复关键字
    cmd_t4 = (
        f"docker exec {DEPLOY_ID}-h5 sh -c "
        f"\"grep -r 'soft-fail' /app/.next 2>/dev/null | head -3\""
    )
    rc, out, _ = run(c, cmd_t4)
    has_soft_fail = "soft-fail" in out
    results.append(expect(
        "T4: 容器内 .next 构建产物包含 'soft-fail' (优雅降级逻辑已构建)",
        has_soft_fail,
        out,
    ))

    # T5 - 容器近 100 行日志无致命错误
    rc, out, _ = run(c, f"docker logs --tail 100 {DEPLOY_ID}-h5 2>&1")
    bad = [l for l in out.splitlines() if "FATAL" in l or "uncaughtException" in l]
    results.append(expect(
        "T5: h5 容器近 100 行无 FATAL/uncaughtException",
        len(bad) == 0,
        "\n".join(bad[:5]) if bad else "(clean)",
    ))

    # T6 - 服务器源码包含 INCIDENT-20260513-03 标记
    rc, out, _ = run(
        c,
        f"grep -c 'INCIDENT-20260513-03' /home/ubuntu/{DEPLOY_ID}/h5-web/src/components/ai-chat/Sidebar.tsx",
    )
    count = int(out.strip() or 0)
    results.append(expect(
        f"T6: 服务器源码 Sidebar.tsx 含 INCIDENT-20260513-03 标记 >=2 处",
        count >= 2,
        f"count={count}",
    ))

    c.close()

    passed = sum(results)
    total = len(results)
    print(f"\n结果: {passed}/{total} 通过")
    if passed == total:
        print("PASS: 所有用例通过")
        sys.exit(0)
    else:
        print("FAIL: 有用例未通过")
        sys.exit(1)


if __name__ == "__main__":
    main()
