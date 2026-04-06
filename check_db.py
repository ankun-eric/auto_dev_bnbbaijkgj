import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Bangbang987"
DEPLOY_ID = "3b7b999d-e51c-4c0d-8f6e-baf90cd26857"
REMOTE_DIR = f"/home/ubuntu/{DEPLOY_ID}"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

cmd = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -T db mysql -uroot -pbini_health_2026 -e 'DESCRIBE bini_health.sms_templates;'"
print(f">>> {cmd}")
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    for line in err.split('\n'):
        if 'Warning' not in line:
            print(line)

cmd2 = f"cd {REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -T db mysql -uroot -pbini_health_2026 -e 'SELECT column_name, data_type FROM information_schema.columns WHERE table_schema=\"bini_health\" AND table_name=\"sms_templates\" ORDER BY ordinal_position;'"
print(f"\n>>> Checking sms_templates columns...")
stdin, stdout, stderr = client.exec_command(cmd2, timeout=30)
print(stdout.read().decode())

client.close()
print("DB check complete.")
