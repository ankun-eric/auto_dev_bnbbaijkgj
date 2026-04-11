import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.bangbangvip.com', username='ubuntu', password='Newbang888')

cmds = [
    'docker exec 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-db mysql -uroot -pbini_health_2026 bini_health -e "ALTER TABLE articles ADD COLUMN summary VARCHAR(500) NULL;"',
    'docker exec 3b7b999d-e51c-4c0d-8f6e-baf90cd26857-db mysql -uroot -pbini_health_2026 bini_health -e "DESCRIBE articles;"',
]

for cmd in cmds:
    print(f"Running: {cmd[:80]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(f"OUT: {out}")
    if err:
        print(f"ERR: {err}")
    print()

ssh.close()
print("Done")
