"""快速重部署 + 测试（仅改 alipay_notify.py）"""
import paramiko, time
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu',
            password='Newbang888', timeout=60)
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_DIR = f'/home/ubuntu/{DEPLOY_ID}'
container = f'{DEPLOY_ID}-backend'

# 1) 上传 alipay_notify.py
sftp = cli.open_sftp()
sftp.put('backend/app/api/alipay_notify.py',
         f'{REMOTE_DIR}/backend/app/api/alipay_notify.py')
print("uploaded alipay_notify.py")
sftp.close()

# 2) docker cp 进容器替换源码并重启容器
def run(cmd, t=120):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=t)
    out = stdout.read().decode('utf-8', 'ignore')
    err = stderr.read().decode('utf-8', 'ignore')
    rc = stdout.channel.recv_exit_status()
    print(f">>> {cmd[:120]}\nexit={rc}\n{out[-1500:]}\n{err[-300:]}")
    return rc, out

run(f'docker cp {REMOTE_DIR}/backend/app/api/alipay_notify.py '
    f'{container}:/app/app/api/alipay_notify.py')
run(f'docker restart {container}')
print("waiting 8s ...")
time.sleep(8)

# 3) 重传测试文件 + conftest（容器重启后丢失了之前的复制）
run(f'docker cp {REMOTE_DIR}/backend/tests/conftest.py {container}:/app/tests/conftest.py')
run(f'docker cp {REMOTE_DIR}/backend/tests/test_alipay_h5_real_payment.py '
    f'{container}:/app/tests/test_alipay_h5_real_payment.py')

# 4) 重新跑 pytest（仅本期 9 用例）
rc, out = run(
    f'docker exec -w /app {container} python -m pytest '
    f'tests/test_alipay_h5_real_payment.py -v --tb=short -p no:warnings 2>&1', t=300,
)
with open('_pytest_output2.txt', 'w', encoding='utf-8') as f:
    f.write(out)

# 5) 跑既有支付链路相关回归用例
rc2, out2 = run(
    f'docker exec -w /app {container} python -m pytest '
    f'tests/test_h5_pay_link_bugfix.py tests/test_h5_pay_success_bugfix.py '
    f'tests/test_payment_config_bugfix.py tests/test_payment_config_v1.py '
    f'tests/test_h5_basepath_pay_url_bugfix.py '
    f'-v --tb=short -p no:warnings 2>&1', t=300,
)
with open('_pytest_regress.txt', 'w', encoding='utf-8') as f:
    f.write(out2)

cli.close()
print("\n========== summary ==========")
print(f"main rc={rc}, regress rc={rc2}")
