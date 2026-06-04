import paramiko
import sys

def verify_ssh(host, port, username, password, label):
    print(f"\n=== {label} SSH 连通性验证 ===")
    print(f"目标: {username}@{host}:{port}")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=username, password=password, timeout=15)
        stdin, stdout, stderr = client.exec_command("echo 'OK' && hostname && uname -a")
        result = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        print(f"连接成功！")
        print(f"输出: {result}")
        if err:
            print(f"stderr: {err}")
        client.close()
        return True
    except Exception as e:
        print(f"连接失败: {e}")
        return False

if __name__ == "__main__":
    results = {}

    # 测试环境
    results["test"] = verify_ssh(
        "newbb.test.bangbangvip.com", 22, "ubuntu", "Newbang888", "测试环境"
    )

    # 生产环境
    results["prod"] = verify_ssh(
        "chat.benne-ai.com", 22, "ubuntu", "Benne-ai@#", "生产环境"
    )

    print("\n=== 结果汇总 ===")
    for k, v in results.items():
        print(f"  {k}: {'成功' if v else '失败'}")

    all_ok = all(results.values())
    print(f"\n全部通过: {'是' if all_ok else '否'}")
    sys.exit(0 if all_ok else 1)
