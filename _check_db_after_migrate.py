import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

DB = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
PW = "bini_health_2026"
DBNAME = "bini_health"


def execq(sql: str) -> str:
    cmd = f'docker exec {DB} mysql -uroot -p{PW} {DBNAME} -e "{sql}"'
    i, o, e = ssh.exec_command(cmd, timeout=30)
    return o.read().decode("utf-8", "replace") + "\nSTDERR:" + e.read().decode("utf-8", "replace")


print("=== products.symptom_tags column exists? ===")
print(execq("SHOW COLUMNS FROM products LIKE 'symptom_tags';"))

print("=== tags columns ===")
print(execq("SHOW COLUMNS FROM tags;"))

print("=== tag categories distribution ===")
print(execq("SELECT category, COUNT(*) AS cnt FROM tags GROUP BY category ORDER BY category;"))

print("=== constitution tags (should be 9, is_locked=1) ===")
print(execq("SELECT id, name, category, status, is_locked, sort_order FROM tags WHERE category='constitution' ORDER BY sort_order;"))

print("=== goods_tags row count ===")
print(execq("SELECT COUNT(*) AS goods_tag_rows FROM goods_tags;"))

ssh.close()
