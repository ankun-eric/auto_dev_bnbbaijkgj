import paramiko
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"

def run(cli, cmd):
    print(f"$ {cmd}")
    _, out, err = cli.exec_command(cmd, timeout=60)
    s = out.read().decode("utf-8", errors="replace")
    e = err.read().decode("utf-8", errors="replace")
    print("STDOUT:", s)
    if e:
        print("STDERR:", e[:600])
    return s

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)
run(cli, f"docker exec {DEPLOY_ID}-db env | grep -i mysql")
# 从 backend 的 .env / env 中拿数据库密码
run(cli, f"docker exec {DEPLOY_ID}-backend printenv | grep -iE 'DB_|DATABASE_URL|MYSQL' | head -n 20")
# 直接调 mysql cli with cat heredoc 拿值
mysql = f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health -e"
print("\n=== questionnaire_template ===")
run(cli, f"{mysql} 'SELECT id,code,name,source,LEFT(result_summary_template,80) AS rst FROM questionnaire_template'")
print("\n=== questionnaire_question count by template ===")
run(cli, f"{mysql} 'SELECT template_id, COUNT(*) FROM questionnaire_question GROUP BY template_id'")
print("\n=== chat_function_buttons (questionnaire 类) ===")
run(cli, f"{mysql} 'SELECT id,name,button_type,ai_function_type,questionnaire_template_id,questionnaire_display_form FROM chat_function_buttons WHERE ai_function_type=\"questionnaire\" OR button_type=\"health_self_check\" OR ai_function_type=\"health_self_check\"'")
print("\n=== body_part_dict count ===")
run(cli, f"{mysql} 'SELECT COUNT(*) FROM body_part_dict'")
print("\n=== health_check_templates ===")
run(cli, f"{mysql} 'SHOW TABLES LIKE \"health_check_templates\"'")
run(cli, f"{mysql} 'SELECT id,name,enabled FROM health_check_templates'")
cli.close()
