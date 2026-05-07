"""[PRD-370] 容器内 chunks token 验证（容器名修正版）"""
import paramiko, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONTAINER = f"{DEPLOY_ID}-h5"  # 修正：容器名后缀是 -h5 而不是 -h5-web


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30)

    cmds = [
        # 1. 列出 login chunk
        f"docker exec {CONTAINER} sh -lc 'ls /app/.next/static/chunks/app/login/ 2>/dev/null | head -10'",
        # 2. 主色 #34C759
        f"docker exec {CONTAINER} sh -lc \"grep -l '34C759' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
        # 3. 浅绿渐变起点 #4AD97A
        f"docker exec {CONTAINER} sh -lc \"grep -l '4AD97A' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
        # 4. 青色渐变尾段 #2BD4C4
        f"docker exec {CONTAINER} sh -lc \"grep -l '2BD4C4' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
        # 5. 主标题 宾尼小康（u5BBE u5C3C u5C0F u5EB7）
        f"docker exec {CONTAINER} sh -lc \"grep -l '\\\\u5bbe\\\\u5c3c\\\\u5c0f\\\\u5eb7' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
        # 6. 卡片不再出现 欢迎回来 (u6b22 u8fce u56de u6765)
        f"docker exec {CONTAINER} sh -lc \"grep -l '\\\\u6b22\\\\u8fce\\\\u56de\\\\u6765' /app/.next/static/chunks/app/login/*.js 2>/dev/null && echo FOUND_BAD_TEXT || echo OK_NO_WELCOME\"",
        # 7. 服务协议及隐私保护
        f"docker exec {CONTAINER} sh -lc \"grep -l '\\\\u670d\\\\u52a1\\\\u534f\\\\u8bae\\\\u53ca\\\\u9690\\\\u79c1\\\\u4fdd\\\\u62a4' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
        # 8. 不同意 / 同意（dialog 按钮）
        f"docker exec {CONTAINER} sh -lc \"grep -lc '\\\\u4e0d\\\\u540c\\\\u610f' /app/.next/static/chunks/app/login/*.js 2>/dev/null | head -3\"",
    ]
    for cmd in cmds:
        print(f"\n[$] {cmd[:200]}")
        i, o, e = c.exec_command(cmd, timeout=30)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        if out: print(out.strip())
        if err: print("[err]", err.strip())

    c.close()


if __name__ == "__main__":
    main()
