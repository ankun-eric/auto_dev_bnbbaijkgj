#!/usr/bin/env python3
"""阶段0：双环境SSH连通性与ACR连通性验证"""

import paramiko
import sys

def test_ssh(host, port, username, password, label):
    """测试SSH连通性"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"[{label}] 正在连接 {host}:{port} ...")
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=20,
            allow_agent=False,
            look_for_keys=False
        )
        stdin, stdout, stderr = client.exec_command("echo 'OK'; hostname; uname -a")
        result = stdout.read().decode().strip()
        print(f"[{label}] 连接成功！结果: {result}")
        return True
    except Exception as e:
        print(f"[{label}] 连接失败: {e}")
        return False
    finally:
        client.close()

def main():
    results = {}
    
    # 测试环境
    results['TEST'] = test_ssh(
        host='newbb.test.bangbangvip.com',
        port=22,
        username='ubuntu',
        password='Newbang888',
        label='测试环境'
    )
    
    # 生产环境
    results['PROD'] = test_ssh(
        host='chat.benne-ai.com',
        port=22,
        username='ubuntu',
        password='Benne-ai@#',
        label='生产环境'
    )
    
    print("\n========== 结果汇总 ==========")
    for env, ok in results.items():
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"{env}: {status}")
    
    if all(results.values()):
        print("全部连通性验证通过！")
        sys.exit(0)
    else:
        print("存在连通性验证失败！")
        sys.exit(1)

if __name__ == '__main__':
    main()
