import paramiko
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)

def mysql(sql):
    cmd = f"docker exec {PROJECT_ID}-db mysql -uroot -pbini_health_2026 -t -e \"{sql}\" bini_health 2>/dev/null"
    _, out, _ = cli.exec_command(cmd, timeout=60)
    return out.read().decode("utf-8", errors="replace")

for t in ["family_management", "family_invitations", "chat_sessions", "checkup_reports",
          "device_user_bindings", "drug_identify_details", "health_alert_notifications",
          "health_reminders", "report_history", "tcm_diagnoses"]:
    print(f"=== 引用 {t} 的外键 ===")
    print(mysql(f"SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA='bini_health' AND REFERENCED_TABLE_NAME='{t}';"))

cli.close()
