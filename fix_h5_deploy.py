
import paramiko
import time
import sys

host = 'newbb.test.bangbangvip.com'
port = 22
user = 'ubuntu'
pwd = 'Newbang888'
proj_dir = '/home/ubuntu/6b099ed3-7175-4a78-91f4-44570c84ed27'
deploy_dir = f'{proj_dir}/deploy'

def run_cmd(ssh, cmd, timeout=120):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    if out.strip():
        print(out[-2000:])
    if err.strip():
        print('STDERR:', err[-1000:])
    print('---')
    return out, err

try:
    print("Connecting to server...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port, user, pwd, timeout=30)
    print("Connected!")

    # Step 1: Git pull
    run_cmd(ssh, f'cd {proj_dir} && git pull origin master 2>&1')

    # Step 2: Rebuild h5-web only
    run_cmd(ssh, f'cd {deploy_dir} && docker compose -f docker-compose.prod.yml build h5-web 2>&1', timeout=300)

    # Step 3: Restart h5-web
    run_cmd(ssh, f'cd {deploy_dir} && docker compose -f docker-compose.prod.yml up -d h5-web 2>&1')

    # Step 4: Wait and check health
    time.sleep(10)
    run_cmd(ssh, f'cd {deploy_dir} && docker compose -f docker-compose.prod.yml ps 2>&1')

    # Step 5: Verify
    print("Verifying /brain-game...")
    run_cmd(ssh, 'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 wget -qO- http://localhost:3001/brain-game 2>&1 | head -c 500')

    ssh.close()
    print("DONE - All operations completed successfully")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
