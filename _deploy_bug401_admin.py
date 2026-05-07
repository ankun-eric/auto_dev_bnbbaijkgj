"""
Bug401 admin-web 修复部署脚本：
1. SSH 到服务器
2. cd 到部署目录(基于 DEPLOY_ID)
3. git pull 拉最新代码
4. 重新构建并重启 admin-web 容器
5. 验证页面可访问
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[SSH] connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PWD, timeout=30)

    def run(cmd, timeout=600, hide_long=False):
        print(f"\n[CMD] {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
        out = stdout.read().decode("utf-8", errors="ignore")
        err = stderr.read().decode("utf-8", errors="ignore")
        rc = stdout.channel.recv_exit_status()
        if hide_long and len(out) > 4000:
            print(out[:1500])
            print(f"... [omitted {len(out) - 3000} chars] ...")
            print(out[-1500:])
        else:
            print(out)
        if err:
            print("[STDERR]", err[-2000:])
        print(f"[RC] {rc}")
        return rc, out, err

    # Step 1: 找到部署目录
    rc, out, _ = run(
        f"ls -la /home/ubuntu/ 2>/dev/null | grep -E '{DEPLOY_ID}|autodev' || true"
    )

    # 寻找项目目录
    rc, out, _ = run(f"find /home/ubuntu -maxdepth 3 -type d -name '*{DEPLOY_ID[:8]}*' 2>/dev/null | head -5")
    rc, out, _ = run(f"find /home/ubuntu -maxdepth 4 -type d -name 'admin-web' 2>/dev/null | head -10")

    # 大概率在 /home/ubuntu/projects/{DEPLOY_ID}/ 或类似位置
    rc, out, _ = run(f"docker ps --format '{{{{.Names}}}}' | grep -i {DEPLOY_ID[:8]}")
    print("\n[Containers found above]\n")

    # Step 2: 通过容器找代码挂载位置
    rc, out, _ = run(f"docker inspect {DEPLOY_ID}-admin-web --format '{{{{ .HostConfig.Binds }}}}{{{{ .Mounts }}}}{{{{ .Config.WorkingDir }}}}' 2>/dev/null || true")
    rc, out, _ = run(f"docker inspect {DEPLOY_ID}-admin-web --format '{{{{ json .Mounts }}}}' 2>/dev/null || true")

    client.close()


if __name__ == "__main__":
    main()
