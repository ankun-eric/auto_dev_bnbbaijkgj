#!/usr/bin/env python3
"""Final check of deployment"""
import paramiko, time, sys

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=30)

def run(cmd, timeout=60):
    print(f'\n[CMD] {cmd[:200]}')
    sys.stdout.flush()
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(f'[OUT] {out.strip()[:800]}')
    if err.strip():
        print(f'[ERR] {err.strip()[:400]}')
    sys.stdout.flush()
    return out, err, code

domain = '6b099ed3-7175-4a78-91f4-44570c84ed27.noob-ai.test.bangbangvip.com'

# Check all containers
print("=" * 60)
print("ALL CONTAINERS STATUS")
print("=" * 60)
run("docker ps --filter name=6b099ed3 --format 'table {{.Names}}\t{{.Status}}'")

# Backend logs
print("\n" + "=" * 60)
print("BACKEND LOGS (last 40)")
print("=" * 60)
run("docker logs 6b099ed3-7175-4a78-91f4-44570c84ed27-backend --tail 40 2>&1")

# Nginx error log
print("\n" + "=" * 60)
print("NGINX ERROR LOG")
print("=" * 60)
run("docker exec gateway-nginx cat /var/log/nginx/error.log 2>/dev/null | tail -20 || echo 'no_error_file'")
run("docker logs gateway-nginx --tail 20 2>&1")

# HTTP from server itself
print("\n" + "=" * 60)
print("HTTP CHECKS (from server)")
print("=" * 60)
run(f"curl -sv https://{domain}/api/health 2>&1 | head -20")
run(f"curl -sk -w '\\nHTTP_CODE:%{{http_code}}\\n' https://{domain}/api/health")
run(f"curl -sk -w '\\nHTTP_CODE:%{{http_code}}\\n' https://{domain}/")
run(f"curl -sk -w '\\nHTTP_CODE:%{{http_code}}\\n' https://{domain}/admin/")

# Check if backend is actually serving
print("\n" + "=" * 60)
print("DIRECT BACKEND CHECK")
print("=" * 60)
run("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend python3 -c \"import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read())\" 2>&1")

# Nginx test with new config
print("\n" + "=" * 60)
print("NGINX CONFIG TEST")
print("=" * 60)
run("docker exec gateway-nginx nginx -t 2>&1")

ssh.close()
print("\nDone!")
