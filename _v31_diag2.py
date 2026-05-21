"""V3.1 Bug 诊断脚本2：找正确表名"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DB_CONTAINER = f"{PROJECT_ID}-db"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)

def run(cmd, timeout=60):
    stdin, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", "ignore") + stderr.read().decode("utf-8", "ignore")

queries = [
    ("All Tables", "SHOW TABLES;"),
    ("Search questionnaire tables", "SHOW TABLES LIKE '%uestionnaire%';"),
    ("Search answer tables", "SHOW TABLES LIKE '%answer%';"),
]

for title, sql in queries:
    cmd = f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -t bini_health -e \"{sql}\" 2>&1 | grep -v 'Using a password'"
    out = run(cmd)
    print("\n=== " + title + " ===")
    print(out)

cli.close()
