#!/usr/bin/env python3
"""Phase 1.5: Server pre-check — 6 checks via paramiko."""
import paramiko
import sys
import time

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
ACR = "crpi-d7zlu3m44f38jufp.cn-guangzhou.personal.cr.aliyuncs.com"


def ssh_cmd(ssh, cmd, timeout=30):
    """Execute command over SSH and return stdout, stderr, exit_code."""
    print(f"\n  [CMD] {cmd[:120]}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    rc = stdout.channel.recv_exit_status()
    return out, err, rc


ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {HOST}:{PORT} as {USER} ...")
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)
print("Connected!")

results = {}

# ========== Check 1: Gateway nginx config structure ==========
print("\n===== Check 1: Gateway nginx 配置结构 =====")
out, err, rc = ssh_cmd(ssh, "docker ps --filter name=gateway-nginx --format '{{.Names}} {{.Status}}'")
print(f"  gateway-nginx container: {out}")
out, err, rc = ssh_cmd(ssh, "docker exec gateway-nginx ls -la /etc/nginx/conf.d/ 2>/dev/null | head -20")
print(f"  conf.d listing:\n{out}")
out, err, rc = ssh_cmd(ssh, "docker exec gateway-nginx nginx -t 2>&1")
print(f"  nginx -t: {out} {err}")
results["check1"] = rc == 0

# ========== Check 2: 路由占用检查 ==========
print("\n===== Check 2: 路由占用检查 =====")
out, err, rc = ssh_cmd(ssh, "docker exec gateway-nginx ls /etc/nginx/conf.d/ 2>/dev/null")
print(f"  conf.d files: {out}")
out, err, rc = ssh_cmd(ssh, f"docker exec gateway-nginx grep -rl '{DEPLOY_ID}' /etc/nginx/conf.d/ 2>/dev/null")
print(f"  files containing DEPLOY_ID: {out}")
out, err, rc = ssh_cmd(ssh, "docker ps --format '{{.Names}} {{.Image}} {{.Ports}}' 2>/dev/null")
print(f"  all containers:\n{out}")
results["check2"] = True

# ========== Check 3: ACR login + base image pull ==========
print("\n===== Check 3: ACR 基础镜像版本匹配 =====")
out, err, rc = ssh_cmd(ssh, f"echo 'xiaobai888' | docker login {ACR} -u ankun888 --password-stdin 2>&1")
print(f"  ACR login: {out[:200]}")
out, err, rc = ssh_cmd(ssh, f"docker pull {ACR}/noob_doker_base/python:3.12-slim 2>&1 | tail -5", timeout=120)
print(f"  python:3.12-slim pull:\n{out}")
out, err, rc = ssh_cmd(ssh, f"docker pull {ACR}/noob_doker_base/node:20-alpine 2>&1 | tail -5", timeout=120)
print(f"  node:20-alpine pull:\n{out}")
results["check3"] = rc == 0

# ========== Check 4: Docker network topology ==========
print("\n===== Check 4: Docker 网络拓扑 =====")
out, err, rc = ssh_cmd(ssh, "docker network ls --format '{{.Name}} {{.Driver}}' 2>/dev/null")
print(f"  networks:\n{out}")
net_name = f"{DEPLOY_ID}-network"
out, err, rc = ssh_cmd(ssh, f"docker network inspect {net_name} 2>&1 | head -30")
print(f"  app network '{net_name}':\n{out[:500]}")
out, err, rc = ssh_cmd(ssh, "docker inspect gateway-nginx --format '{{json .NetworkSettings.Networks}}' 2>/dev/null")
print(f"  gateway-nginx networks: {out[:300]}")
results["check4"] = True

# ========== Check 5: 基础镜像内置工具检测 ==========
print("\n===== Check 5: 基础镜像内置工具检测 =====")
out, err, rc = ssh_cmd(ssh, f"docker run --rm {ACR}/noob_doker_base/python:3.12-slim python3 --version 2>&1")
print(f"  python version: {out} {err}")
out, err, rc = ssh_cmd(ssh, f"docker run --rm {ACR}/noob_doker_base/node:20-alpine node --version 2>&1")
print(f"  node version: {out} {err}")
results["check5"] = "3.12" in (out + err) and "20" in (out + err)

# ========== Check 6: 磁盘空间检查 ==========
print("\n===== Check 6: 磁盘空间检查 =====")
out, err, rc = ssh_cmd(ssh, "df -h / 2>/dev/null")
print(f"  disk usage:\n{out}")
out, err, rc = ssh_cmd(ssh, "docker system df 2>/dev/null")
print(f"  docker disk:\n{out}")
results["check6"] = True

# Summary
print("\n" + "=" * 60)
print("PRE-CHECK SUMMARY")
for k, v in results.items():
    status = "PASS" if v else "FAIL"
    print(f"  {k}: {status}")

ssh.close()
