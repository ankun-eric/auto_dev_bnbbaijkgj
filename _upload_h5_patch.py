"""上传 4 个修改的 H5 源文件到远程，然后重建 H5 容器"""
import paramiko, os, sys

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
REMOTE_BASE = "/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27/h5-web"

FILES = [
    "src/app/member-center/page.tsx",
    "src/app/member-center/components/BenefitsCompareTable.tsx",
    "src/app/health-profile/page.tsx",
    "src/app/health-profile/archive-list/page.tsx",
]

def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = cli.open_sftp()
    for f in FILES:
        local = os.path.join("h5-web", f.replace("/", os.sep))
        remote = REMOTE_BASE + "/" + f
        print(f"[upload] {local} -> {remote}")
        sftp.put(local, remote)
    sftp.close()
    cli.close()
    print("upload done")

if __name__ == "__main__":
    main()
