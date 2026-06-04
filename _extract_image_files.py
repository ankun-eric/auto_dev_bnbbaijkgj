import paramiko, os
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR=f'/home/ubuntu/{DEPLOY_ID}'
LOCAL_ROOT=os.path.dirname(os.path.abspath(__file__))
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, t=120):
    print('>>>', cmd[:200])
    _,o,e=s.exec_command(cmd, timeout=t)
    out=o.read().decode('utf-8','replace'); err=e.read().decode('utf-8','replace')
    print(out[-2500:])
    if err: print('ERR:', err[-1000:])
    print('exit=', o.channel.recv_exit_status(), '\n')
    return out

# 从 tmp_extract_be (backend image) 拷出 image 中的 main.py 和 __init__.py
run('docker cp tmp_extract_be:/app/app/main.py /tmp/img_main.py')
run('docker cp tmp_extract_be:/app/app/api/__init__.py /tmp/img_api_init.py')
run('wc -l /tmp/img_main.py /tmp/img_api_init.py')
run('head -100 /tmp/img_api_init.py')
run('grep -n "health_profile_self\\|guardian_bugfix" /tmp/img_main.py | head')
# 拉到本地
sftp=s.open_sftp()
sftp.get('/tmp/img_main.py', os.path.join(LOCAL_ROOT, '_img_main.py'))
sftp.get('/tmp/img_api_init.py', os.path.join(LOCAL_ROOT, '_img_api_init.py'))
print('downloaded image files locally')
# 同时把宿主机已经修改后的 main.py 上传过的版本备一下
sftp.get(f'{PROJECT_DIR}/backend/app/main.py', os.path.join(LOCAL_ROOT, '_host_main.py'))
print('downloaded host main.py')
s.close()
