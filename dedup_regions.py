import paramiko
import time

host = "newbb.test.bangbangvip.com"
port = 22
user = "ubuntu"
password = "Newbang888"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(host, port, user, password, timeout=15)
    print("SSH 连接成功")

    # 先去重：用 MySQL 直接执行
    dedup_sql = (
        "DELETE t1 FROM brain_game_regions t1 "
        "INNER JOIN brain_game_regions t2 "
        "WHERE t1.id > t2.id "
        "AND t1.adcode = t2.adcode "
        "AND COALESCE(t1.parent_adcode, '') = COALESCE(t2.parent_adcode, '');"
    )
    count_sql = "SELECT COUNT(*) AS cnt FROM brain_game_regions;"
    dup_sql = (
        "SELECT adcode, COUNT(*) AS cnt FROM brain_game_regions "
        "GROUP BY adcode, COALESCE(parent_adcode, '') "
        "HAVING cnt > 1 LIMIT 5;"
    )

    cmds = [
        # 去重前统计
        f'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "{count_sql}"',
        # 执行去重
        f'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "{dedup_sql}"',
        # 去重后统计
        f'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "{count_sql}"',
        # 检查重复
        f'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 bini_health -e "{dup_sql}"',
    ]

    for cmd in cmds:
        print(f"--- Executing: {cmd[:80]}...")
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print("OUT:", out.strip())
        if err:
            print("ERR:", err.strip())
    stdin, stdout, stderr = client.exec_command(cmd)
    print("STDOUT:", stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("STDERR:", err)

finally:
    client.close()
    print("SSH 连接已关闭")
