import paramiko, time
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com','22','ubuntu','Newbang888')
for i in range(20):
    _, out, _ = c.exec_command("docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-backend sh -c 'curl -sf http://localhost:8000/api/health || true'")
    s = out.read().decode()
    if s.strip():
        print(f'READY @{i*3}s:', s[:200])
        break
    time.sleep(3)
else:
    print('TIMEOUT')

_, o, _ = c.exec_command("docker logs --tail 200 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | grep -E 'family_self|backfill|report_interpret|migrate' | tail -40")
print('---- migrate logs ----')
print(o.read().decode())

_, o2, _ = c.exec_command("docker logs --tail 60 6b099ed3-7175-4a78-91f4-44570c84ed27-backend 2>&1 | tail -60")
print('---- last logs ----')
print(o2.read().decode())
c.close()
