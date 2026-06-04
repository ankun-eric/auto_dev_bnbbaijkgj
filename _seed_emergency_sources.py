"""补种 emergency_call_sources 4 条内置数据"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

SQL = """
INSERT IGNORE INTO emergency_call_sources
  (source_code, source_name, description, is_enabled, is_builtin, sort_order, created_at, updated_at)
VALUES
  ('health_data_abnormal','健康数据异常','心率/血压/血氧/体温异常',1,1,1,NOW(),NOW()),
  ('smoke_alarm','烟雾报警器','火灾隐患',1,1,2,NOW(),NOW()),
  ('water_alarm','水位报警器','漏水/水浸',1,1,3,NOW(),NOW()),
  ('emergency_button','紧急呼叫器','一键呼救，含跌倒检测',1,1,4,NOW(),NOW());
"""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=30)
sql_one = " ".join(SQL.split())
cmd = (
    f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health "
    f"-e \"{sql_one}\" && "
    f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health "
    f"-e 'SELECT id, source_code, source_name, is_enabled FROM emergency_call_sources;'"
)
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
print(stdout.read().decode("utf-8", errors="replace"))
print("[err]", stderr.read().decode("utf-8", errors="replace"))
client.close()
