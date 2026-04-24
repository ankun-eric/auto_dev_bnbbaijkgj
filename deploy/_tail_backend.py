import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd
ssh = create_client()
try:
    out, err, _ = run_cmd(ssh, "docker logs --tail 150 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1", timeout=30)
    print(out)
    if err:
        print('STDERR:', err)
finally:
    ssh.close()
