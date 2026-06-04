"""容器在 restart loop 但 docker cp 仍可能从镜像读取。
策略：用 git 历史中已部署的 main.py 版本，或使用容器内文件系统拷出。
最快路径：从最近一次成功部署的 main.py 备份中恢复，或直接用 docker create 临时容器复制。
"""
import paramiko
HOST='newbb.test.bangbangvip.com'; USER='ubuntu'; PWD='Newbang888'
DEPLOY_ID='6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR=f'/home/ubuntu/{DEPLOY_ID}'
s=paramiko.SSHClient(); s.set_missing_host_key_policy(paramiko.AutoAddPolicy())
s.connect(HOST, username=USER, password=PWD, timeout=30)


def run(cmd, t=120):
    print('>>>', cmd[:200])
    _,o,e=s.exec_command(cmd, timeout=t)
    out=o.read().decode('utf-8','replace'); err=e.read().decode('utf-8','replace')
    print(out[-3000:])
    if err: print('ERR:', err[-1500:])
    print('exit=', o.channel.recv_exit_status(), '\n')
    return out

# 用 docker create + cp 方式从 image 中提取文件
run(f'docker stop {DEPLOY_ID}-backend 2>&1 || true')
# 用宿主机上的项目目录主仓 main.py 来作为容器 mount-source 不可行，因为容器是 docker compose 起的
# 直接 cp 镜像里的文件出来
run(f'docker create --name tmp_extract_be {DEPLOY_ID}-backend:latest 2>&1 || docker create --name tmp_extract_be 6b099ed3-7175-4a78-91f4-44570c84ed27-backend:latest 2>&1 || true')
run(f'docker create --name tmp_extract_be2 $(docker inspect --format=\'{{{{.Config.Image}}}}\' {DEPLOY_ID}-backend) 2>&1 || true')
run(f'docker images | grep -i 6b099ed3 | head -10')
s.close()
