"""Add missing pinned_at column to chat_sessions table."""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

cmd = (
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db '
    'mysql -u root -pbini_health_2026 bini_health -e '
    '"ALTER TABLE chat_sessions ADD COLUMN pinned_at DATETIME NULL DEFAULT NULL;" 2>&1'
)
print(f"CMD: {cmd}")
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
out = stdout.read().decode("utf-8", errors="replace")
print(f"OUT: {out}")
exit_code = stdout.channel.recv_exit_status()
print(f"EXIT: {exit_code}")

ssh.close()
