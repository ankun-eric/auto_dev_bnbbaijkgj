import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', port=22, username='ubuntu', password='Newbang888', timeout=15)

def run(cmd):
    i, o, e = ssh.exec_command(cmd, timeout=10)
    out = o.read().decode('utf-8', errors='replace').strip()
    err = e.read().decode('utf-8', errors='replace').strip()
    return out, err

lines = []
lines.append("=== MySQL containers ===")
o, e = run('docker ps --format "{{.Names}} {{.Image}}" 2>/dev/null | grep -i mysql || echo NO_MYSQL')
lines.append(f"STDOUT: {o}")
lines.append(f"STDERR: {e}")

lines.append("=== DB inspect ===")
o, e = run('docker inspect db --format "{{.NetworkSettings.Networks}}" 2>/dev/null || echo NO_DB_CONTAINER')
lines.append(f"STDOUT: {o[:500]}")
lines.append(f"STDERR: {e[:200]}")

lines.append("=== DB ping ===")
o, e = run('docker exec db mysqladmin ping -h localhost -uroot -pbini_health_2026 2>/dev/null || echo DB_PING_FAILED')
lines.append(f"STDOUT: {o}")
lines.append(f"STDERR: {e}")

lines.append("=== Existing project containers ===")
o, e = run('docker ps -a --format "{{.Names}} {{.Status}}" 2>/dev/null | grep 6b099ed3 || echo NO_EXISTING')
lines.append(f"STDOUT: {o}")
lines.append(f"STDERR: {e}")

lines.append("=== All docker networks ===")
o, e = run('docker network ls --format "{{.Name}}" 2>/dev/null')
lines.append(f"STDOUT: {o[:500]}")

lines.append("=== Gateway network inspect ===")
o, e = run('docker inspect gateway-nginx --format "{{range .NetworkSettings.Networks}}{{.NetworkID}} {{end}}" 2>/dev/null')
lines.append(f"STDOUT: {o[:500]}")

result = '\n'.join(lines)
with open('deploy/remote_check_result.txt', 'w', encoding='utf-8') as f:
    f.write(result)
print('DONE - written to deploy/remote_check_result.txt')
ssh.close()
