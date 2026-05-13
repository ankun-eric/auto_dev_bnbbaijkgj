"""探测服务器当前 h5-web 状态：源码内是否有 PRD-442/PRD-448 等关键标记。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJ = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cli, cmd, timeout=60):
    print(f"$ {cmd}")
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print(f"STDERR: {err}")
    print(f"[rc={rc}]")
    return rc, out, err


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    try:
        cmds = [
            f"ls -la {PROJ}/h5-web/ | head -30",
            f"ls {PROJ}/h5-web/src/components/ai-chat/ 2>&1 | head -40",
            f"ls {PROJ}/h5-web/src/components/ai-chat/AdvisorCapsule 2>&1",
            f"ls {PROJ}/h5-web/src/app/'(ai-chat)'/ai-home/ 2>&1",
            f"grep -c 'PRD-442' {PROJ}/h5-web/src/app/globals.css 2>&1",
            f"grep -c 'color-brand-500' {PROJ}/h5-web/src/app/globals.css 2>&1",
            f"grep -c 'PRD-448' {PROJ}/h5-web/src/components/ai-chat/AdvisorCapsule/index.tsx 2>&1 || echo missing",
            f"grep -c 'PRD-467' {PROJ}/h5-web/src/app/'(ai-chat)'/ai-home/page.tsx 2>&1 || echo missing",
            f"sudo docker ps --filter name=6b099ed3-7175-4a78-91f4-44570c84ed27-h5 --format 'table {{{{.Names}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}'",
            f"sudo docker images --filter reference='*h5-web*' --filter reference='*h5*' --format 'table {{{{.Repository}}}}\\t{{{{.Tag}}}}\\t{{{{.CreatedSince}}}}' | head -10",
            f"sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'find /app -maxdepth 3 -name globals.css 2>/dev/null | head' 2>&1 || echo no-container",
            f"sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'ls /app/.next 2>/dev/null | head' 2>&1 || echo no-next",
            f"sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'grep -rc \"color-brand-500\" /app/.next/static 2>/dev/null | grep -v \":0\" | head' 2>&1 || true",
            f"sudo docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 sh -c 'grep -rc \"PRD-448\\|AdvisorCapsule\" /app/.next/static 2>/dev/null | grep -v \":0\" | head' 2>&1 || true",
        ]
        for c in cmds:
            run(cli, c)
            print("---")
    finally:
        cli.close()

if __name__ == "__main__":
    main()
