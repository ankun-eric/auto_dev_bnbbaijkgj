"""清理旧的非锁定 constitution 重复标签，保留 9 个 is_locked=1 的新锁定体质"""
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

DB = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"

def execq(sql: str):
    cmd = f'docker exec {DB} mysql -uroot -pbini_health_2026 bini_health -e "{sql}"'
    i, o, e = ssh.exec_command(cmd, timeout=30)
    print(o.read().decode("utf-8", "replace"))
    print(e.read().decode("utf-8", "replace"))


# 删除所有 category='constitution' 且 is_locked=0 的重复标签（保留 is_locked=1 的 9 个）
# 先把 goods_tags 中引用旧 constitution 的 tag_id 重定向到新锁定标签
print("=== 清理 goods_tags 中引用的旧体质标签 ===")
execq(
    "DELETE gt FROM goods_tags gt "
    "JOIN tags t ON gt.tag_id=t.id "
    "WHERE t.category='constitution' AND t.is_locked=0;"
)

print("=== 删除旧体质标签（非锁定） ===")
execq("DELETE FROM tags WHERE category='constitution' AND is_locked=0;")

print("=== 验证：剩余 constitution 标签 ===")
execq("SELECT id, name, status, is_locked, sort_order FROM tags WHERE category='constitution' ORDER BY sort_order;")

print("=== 各类别分布 ===")
execq("SELECT category, COUNT(*) FROM tags GROUP BY category;")

ssh.close()
