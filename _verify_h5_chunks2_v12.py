"""验证 H5 i-guard chunk 内容（使用 unicode escape 序列）"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
TOKEN = "6b099ed3-7175-4a78-91f4-44570c84ed27"

# 「待确认转让」: \u5f85 \u786e \u8ba4 \u8f6c \u8ba9
# 「体验全新」: \u4f53 \u9a8c \u5168 \u65b0
# 但是 Next.js JS minified 里中文可能是原文，不是 \uXXXX。让我们用 python 在远端用 grep -P 二进制
CMDS = [
    # 用 LC_ALL=C 直接 grep 字节序列（UTF-8 编码）
    f"docker exec {TOKEN}-h5 sh -c 'LC_ALL=C grep -l \"$(printf \\\"\\xe5\\xbe\\x85\\xe7\\xa1\\xae\\xe8\\xae\\xa4\\\")\" /app/.next/static/chunks/app/health-profile/i-guard/page-*.js 2>/dev/null'",
    # 体验全新
    f"docker exec {TOKEN}-h5 sh -c 'LC_ALL=C grep -l \"$(printf \\\"\\xe4\\xbd\\x93\\xe9\\xaa\\x8c\\xe5\\x85\\xa8\\xe6\\x96\\xb0\\\")\" /app/.next/static/chunks/app/health-profile/i-guard/page-*.js 2>/dev/null; echo END'",
    # 直接 strings 这个 chunk
    f"docker exec {TOKEN}-h5 sh -c 'strings /app/.next/static/chunks/app/health-profile/i-guard/page-77dcc5e9df97fd3e.js 2>/dev/null | head -80 | grep -i \"\\(transfer\\|guardian\\|pend\\|确认\\|转让\\|全新\\|体验\\)\" || echo NOMATCH'",
    # alternatively, just count file size
    f"docker exec {TOKEN}-h5 sh -c 'wc -c /app/.next/static/chunks/app/health-profile/i-guard/page-*.js'",
    # 看 chunk 的实际内容片段
    f"docker exec {TOKEN}-h5 sh -c 'cat /app/.next/static/chunks/app/health-profile/i-guard/page-77dcc5e9df97fd3e.js' | head -c 8000",
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
            print(out[:2500])
        if err.strip():
            print("--stderr--")
            print(err[:300])
    cli.close()


if __name__ == "__main__":
    main()
