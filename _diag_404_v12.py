"""诊断 404：i-guard 路径在新容器内为何 404"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

CMDS = [
    f"docker ps --format '{{{{.Names}}}} {{{{.Status}}}} {{{{.Image}}}}' | grep {TOKEN}-h5",
    # 直接从 host 通过域名访问
    f"curl -k -s -o /tmp/_d1.html -w 'iguard=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{TOKEN}/health-profile/i-guard",
    f"curl -k -s -L -o /tmp/_d1L.html -w 'iguardL=%{{http_code}}\\n' https://newbb.test.bangbangvip.com/autodev/{TOKEN}/health-profile/i-guard",
    f"head -c 500 /tmp/_d1L.html",
    # 直接探 H5 容器内部
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/autodev/{TOKEN}/health-profile/i-guard'",
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/autodev/{TOKEN}/health-profile/i-guard/'",
    f"docker exec gateway sh -c 'curl -s -o /dev/null -w \"%{{http_code}}\\n\" http://{TOKEN}-h5:3001/autodev/{TOKEN}/'",
    # 是否走到 next 的 redirect
    f"docker exec gateway sh -c 'curl -s -I http://{TOKEN}-h5:3001/autodev/{TOKEN}/health-profile/i-guard'",
    # 查看 next.config.js BASE_PATH 设置
    f"docker exec {TOKEN}-h5 sh -c 'env | grep -i base; ls / ; cat /app/server.js 2>/dev/null | head -30'",
    f"docker exec {TOKEN}-h5 sh -c 'ls /app/.next/standalone/.next/server/app 2>/dev/null | head -20; echo ----; ls /app/.next/server/app 2>/dev/null | head -30'",
    f"docker exec {TOKEN}-h5 sh -c 'find /app -name \"*.next\" -prune -o -type d -name \"i-guard\" -print 2>/dev/null'",
    f"docker exec {TOKEN}-h5 sh -c 'ls /app/.next/server/app/health-profile/ 2>/dev/null'",
    f"docker exec {TOKEN}-h5 sh -c 'cat /app/.next/routes-manifest.json 2>/dev/null | head -120 | python3 -c \"import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get(\\\"staticRoutes\\\",[])[:10],ensure_ascii=False,indent=2))\" 2>/dev/null || head -100 /app/.next/routes-manifest.json 2>/dev/null'",
    f"docker logs --tail 50 {TOKEN}-h5 2>&1 | tail -50",
    # H5 src 是否带 basePath next config
    f"cat /home/ubuntu/{TOKEN}/h5-web/next.config.js 2>/dev/null | head -50",
    f"cat /home/ubuntu/{TOKEN}/h5-web/next.config.mjs 2>/dev/null | head -50",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    for c in CMDS:
        print("\n==== CMD:", c[:200])
        si, so, se = cli.exec_command(c, timeout=30)
        out = so.read().decode("utf-8", errors="ignore")
        err = se.read().decode("utf-8", errors="ignore")
        if out.strip():
            print(out)
        if err.strip():
            print("--stderr--")
            print(err)
    cli.close()


if __name__ == "__main__":
    main()
