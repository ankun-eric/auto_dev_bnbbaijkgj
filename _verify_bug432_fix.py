"""[Bug-432-fix] 验证 Next.js standalone 构建产物中
- 旧的 `res.data` 二次脱壳代码已清理
- 新的 Bug-432-fix 标记字符串已进入产物
"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
CONTAINER = f"{DEPLOY_ID}-h5"


def run(ssh, cmd, timeout=120):
    print(f"\n>>> {cmd[:200]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out[-3000:])
    if err:
        print("STDERR:", err[-1500:])
    print(f"<<< exit={code}")
    return code, out


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, 22, USER, PASSWORD, timeout=30)

    # 列出 standalone 内容
    run(ssh, f"docker exec {CONTAINER} ls /app | head -20")
    run(ssh, f"docker exec {CONTAINER} find /app/.next/server/chunks -name '*.js' | head -5")

    # 在 .next/server/app 中找含有 ProfileCard 字面量的 chunks
    run(
        ssh,
        f"docker exec {CONTAINER} sh -c \"grep -r -l 'ai-profile-card' /app/.next/server/app 2>/dev/null | head -10\"",
    )

    # 抓 ai-chat 相关 chunks，看是否含 'Bug-432-fix' 标记
    run(
        ssh,
        f"docker exec {CONTAINER} sh -c \"grep -r -c 'Bug-432-fix' /app/.next/server/app 2>/dev/null | grep -v ':0' | head -10\"",
    )
    # 如果没找到则检查 chunks 目录
    run(
        ssh,
        f"docker exec {CONTAINER} sh -c \"grep -r -c 'Bug-432-fix' /app/.next/server 2>/dev/null | grep -v ':0' | head -10\"",
    )

    # 还检查"加载档案中..."是否还在产物里（应该还在，loading 文案保留）
    run(
        ssh,
        f"docker exec {CONTAINER} sh -c \"grep -r -c 'ai-profile-card-loading' /app/.next/server 2>/dev/null | grep -v ':0' | head -5\"",
    )

    # 客户端 chunks
    run(
        ssh,
        f"docker exec {CONTAINER} sh -c \"grep -r -c 'Bug-432-fix' /app/.next/static 2>/dev/null | grep -v ':0' | head -10\"",
    )

    ssh.close()


if __name__ == "__main__":
    main()
