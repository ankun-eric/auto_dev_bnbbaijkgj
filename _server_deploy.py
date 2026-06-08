"""
Server deployment script for medication history feature.
Connects via SSH, updates code, rebuilds containers.
"""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

def ssh_exec(ssh, cmd, timeout=120):
    """Execute command on SSH and return stdout, stderr, exit_code."""
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', 'replace')
    err = stderr.read().decode('utf-8', 'replace')
    exit_code = stdout.channel.recv_exit_status()
    if out:
        print(out[:2000])
    if err:
        print("STDERR:", err[:1000])
    print(f"EXIT: {exit_code}")
    return out, err, exit_code

def main():
    print(f"Connecting to {HOST}:{PORT} as {USER}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    for attempt in range(1, 4):
        try:
            ssh.connect(HOST, PORT, USER, PASSWORD, timeout=30)
            print("Connected!")
            break
        except Exception as e:
            print(f"Connection attempt {attempt} failed: {e}")
            if attempt == 3:
                print("FAILED to connect after 3 attempts")
                sys.exit(1)
            time.sleep(5)
    
    try:
        # Step 1: Update code from git
        print("\n" + "="*60)
        print("STEP 1: Update code from git")
        print("="*60)
        
        cmds = [
            f"cd {PROJECT_DIR} && git fetch --depth 1 origin master 2>&1",
            f"cd {PROJECT_DIR} && git reset --hard origin/master 2>&1",
        ]
        
        for cmd in cmds:
            out, err, ec = ssh_exec(ssh, cmd, timeout=120)
            if ec != 0:
                print(f"WARNING: command failed with exit code {ec}")
                # Try alternative: git clone if fetch fails
                if "fetch" in cmd and ec != 0:
                    print("Fetch failed, trying direct clone approach...")
                    # Check if directory exists
                    ssh_exec(ssh, f"ls -la {PROJECT_DIR}/.git", timeout=10)
        
        # Show current commit
        ssh_exec(ssh, f"cd {PROJECT_DIR} && git log --oneline -3", timeout=30)
        
        # Step 2: Rebuild and restart containers
        print("\n" + "="*60)
        print("STEP 2: Rebuild containers")
        print("="*60)
        
        # Build
        build_cmd = f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml build --pull backend h5-web 2>&1"
        out, err, ec = ssh_exec(ssh, build_cmd, timeout=600)
        if ec != 0:
            print(f"Build failed (ec={ec}), but continuing...")
        
        # Up (restart)
        print("\n--- docker compose up ---")
        up_cmd = f"cd {PROJECT_DIR} && docker compose -f docker-compose.prod.yml up -d backend h5-web 2>&1"
        out, err, ec = ssh_exec(ssh, up_cmd, timeout=300)
        
        # Step 3: Wait for healthy
        print("\n" + "="*60)
        print("STEP 3: Wait for containers healthy")
        print("="*60)
        
        for i in range(30):
            time.sleep(10)
            out, err, ec = ssh_exec(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}'", timeout=15)
            if f"{DEPLOY_ID}-backend" in out and "Up" in out:
                if "unhealthy" not in out.lower():
                    print(f"Containers appear healthy after {(i+1)*10}s")
                    break
            print(f"Waiting... ({(i+1)*10}s)")
        
        # Final status
        print("\n" + "="*60)
        print("FINAL STATUS")
        print("="*60)
        ssh_exec(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", timeout=15)
        
        # Step 4: Verify
        print("\n" + "="*60)
        print("STEP 4: Verification")
        print("="*60)
        
        # Internal API test
        ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend curl -s http://localhost:8000/api/medication/calendar?year=2026\&month=6 2>&1 | head -c 500", timeout=30)
        
        # Health check
        ssh_exec(ssh, f"docker exec {DEPLOY_ID}-backend curl -s http://localhost:8000/api/health 2>&1", timeout=15)
        
        print("\n" + "="*60)
        print("DEPLOYMENT COMPLETE")
        print("="*60)
        
    finally:
        ssh.close()

if __name__ == "__main__":
    main()
