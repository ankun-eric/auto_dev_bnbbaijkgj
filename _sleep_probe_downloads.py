#!/usr/bin/env python3
import sys
sys.path.insert(0, 'deploy')
from ssh_helper import get_ssh, run_cmd
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
ssh = get_ssh()
run_cmd(ssh, f'cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>&1 | grep -nE "downloads|location|alias|root|apk" | head -40', 30)
run_cmd(ssh, 'docker exec gateway-nginx ls /data/static/apk/ 2>&1 | tail -10', 30)
ssh.close()
