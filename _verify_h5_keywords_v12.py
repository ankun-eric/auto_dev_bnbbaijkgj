"""明确验证 H5 i-guard chunk 中关键词存在性"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# 使用 python 在远端读取文件内容并断言
PROBE = f'''
import sys, glob
files = glob.glob("/app/.next/static/chunks/app/health-profile/i-guard/page-*.js")
files += glob.glob("/app/.next/static/chunks/app/health-profile/page-*.js")
need_in = ["待确认转让", "守护中", "待守护"]
need_out = ["体验全新"]
result = {{}}
for f in files:
    with open(f, "rb") as fp:
        content = fp.read()
    info = {{}}
    for k in need_in + need_out:
        info[k] = content.count(k.encode("utf-8"))
    result[f] = info
for f, info in result.items():
    print(f)
    for k, v in info.items():
        marker = "✓" if (k in need_in and v > 0) or (k in need_out and v == 0) else "✗"
        print(f"  {{marker}} {{k}}: count={{v}}")
'''

CMDS = [
    f"docker exec {TOKEN}-h5 python3 -c \"{PROBE.replace(chr(10), '; ')}\"",
]


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    # 多行 Python 不好走单行 -c，改为先上传脚本到容器内 /tmp
    sftp = cli.open_sftp()
    rf = sftp.open("/tmp/probe_iguard.py", "w")
    rf.write(PROBE)
    rf.close()
    sftp.close()
    cmd = f"docker cp /tmp/probe_iguard.py {TOKEN}-h5:/tmp/probe_iguard.py && docker exec {TOKEN}-h5 python3 /tmp/probe_iguard.py 2>&1 || docker exec {TOKEN}-h5 node -e 'console.log(\"node fallback\")' "
    print("\n==== CMD:", cmd[:200])
    si, so, se = cli.exec_command(cmd, timeout=60)
    print(so.read().decode("utf-8", errors="ignore"))
    print(se.read().decode("utf-8", errors="ignore"))
    cli.close()


if __name__ == "__main__":
    main()
