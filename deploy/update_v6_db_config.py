"""更新 system_config 表的 home_* 配置为 v6 默认值（用 base64 SQL 避免引号转义）。"""
import base64
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"

SQL = (
    "INSERT INTO system_configs (config_key, config_value, description) VALUES "
    "('home_search_placeholder', '想找什么服务/商品？', '首页搜索栏占位文案'),"
    "('home_font_switch_enabled', 'true', '字号开关'),"
    "('home_font_standard_size', '16', '标准字号'),"
    "('home_font_large_size', '19', '大字号'),"
    "('home_font_xlarge_size', '22', '超大字号') "
    "ON DUPLICATE KEY UPDATE config_value=VALUES(config_value); "
    "SELECT config_key, config_value FROM system_configs WHERE config_key LIKE 'home_%';"
)
b64 = base64.b64encode(SQL.encode("utf-8")).decode("ascii")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASS, timeout=30)


def run(cmd, timeout=60):
    print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print("STDOUT:", out)
    if err.strip():
        print("STDERR:", err)
    return out


cmd = (
    f"echo {b64} | base64 -d > /tmp/v6_sql.sql && "
    f"docker cp /tmp/v6_sql.sql {DEPLOY_ID}-db:/tmp/v6_sql.sql && "
    f"docker exec {DEPLOY_ID}-db sh -c "
    f"'mysql -uroot -p\"$MYSQL_ROOT_PASSWORD\" \"$MYSQL_DATABASE\" < /tmp/v6_sql.sql'"
)
run(cmd)
c.close()
