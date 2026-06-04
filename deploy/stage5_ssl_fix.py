import paramiko, os

HOST = "chat.benne-ai.com"
PORT = 22
USER = "ubuntu"
PASS = "Benne-ai@#"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
LOCAL_SSL = r"C:\auto_output\bnbbaijkgj\临时任务\chat.benne-ai.com_ssl\chat.benne-ai.com_nginx"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15)

def run(cmd, timeout=30):
    print(f"  CMD: {cmd[:130]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace').strip()
    err = stderr.read().decode(errors='replace').strip()
    code = stdout.channel.recv_exit_status()
    if out and len(out) < 300:
        print(f"  OUT: {out}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:200]}")
    return out, err, code

# Step 1: Upload cert files
print("=== Step 1: 上传SSL证书 ===")
sftp = client.open_sftp()

# Upload key
key_src = os.path.join(LOCAL_SSL, "chat.benne-ai.com.key")
key_dst = "/home/ubuntu/gateway/ssl/chat.benne-ai.com.key"
sftp.put(key_src, key_dst)
print(f"  Uploaded key -> {key_dst}")

# Upload bundle.crt as chat.benne-ai.com.crt
crt_src = os.path.join(LOCAL_SSL, "chat.benne-ai.com_bundle.crt")
crt_dst = "/home/ubuntu/gateway/ssl/chat.benne-ai.com.crt"
sftp.put(crt_src, crt_dst)
print(f"  Uploaded bundle.crt -> {crt_dst}")

sftp.close()

# Step 2: Verify files
print("\n=== Step 2: 验证证书文件 ===")
out, err, code = run("ls -la /home/ubuntu/gateway/ssl/")
print(f"  SSL dir: {out[:500]}")

# Step 3: Verify cert is valid
print("\n=== Step 3: 验证证书有效性 ===")
out, err, code = run("sudo docker exec gateway-nginx openssl x509 -in /etc/nginx/ssl/chat.benne-ai.com.crt -noout -subject -dates 2>&1")
print(f"  Cert info: {out}")

# Step 4: Test nginx config
print("\n=== Step 4: 测试Nginx配置 ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -t 2>&1")
print(f"  Nginx test: {out}")

# Step 5: Reload nginx
print("\n=== Step 5: 重载Nginx ===")
out, err, code = run("sudo docker exec gateway-nginx nginx -s reload 2>&1")
print(f"  Reload: {'OK' if code==0 else f'FAIL: {err}'}")

# Step 6: Test HTTPS
print("\n=== Step 6: 验证HTTPS访问 ===")
import time
time.sleep(2)
out, err, code = run("curl -sI https://chat.benne-ai.com/ 2>&1 | head -10", timeout=20)
print(f"  {out}")

# Also verify SSL certificate
out, err, code = run("curl -svI https://chat.benne-ai.com/ 2>&1 | grep -iE 'SSL|subject|issuer|expire|CN'", timeout=20)
print(f"  SSL details: {out[:500]}")

client.close()
print("\n=== SSL证书部署完成 ===")
