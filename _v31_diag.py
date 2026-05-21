"""V3.1 Bug 诊断脚本：连服务器查 DB 现状"""
import paramiko, sys

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
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    return out, err

queries = [
    ("Bug 1 - chat_function_buttons.auto_next_enabled", """
SELECT id, name, ai_function_type, presentation_container, questions_per_page,
       auto_next_enabled, updated_at
FROM chat_function_buttons
WHERE ai_function_type = 'questionnaire'
ORDER BY updated_at DESC
LIMIT 5;
"""),
    ("Bug 2-A - questionnaire_answers AI status / lengths", """
SELECT id, ai_status, IFNULL(ai_failed_reason, '') AS ai_failed_reason,
       LENGTH(IFNULL(ai_full_interpretation,'')) AS ai_len,
       LENGTH(IFNULL(home_care_tips_json,''))    AS tips_len,
       LENGTH(IFNULL(red_flag_signals_json,''))  AS red_len,
       created_at
FROM questionnaire_answers
ORDER BY id DESC
LIMIT 5;
"""),
    ("Bug 2-B - questionnaire_answers subject_*", """
SELECT id, IFNULL(subject_kind,'') AS subject_kind,
       IFNULL(subject_member_id, 0) AS subject_member_id,
       IFNULL(subject_name,'') AS subject_name,
       IFNULL(subject_relation,'') AS subject_relation,
       created_at
FROM questionnaire_answers
ORDER BY id DESC
LIMIT 10;
"""),
    ("DESC questionnaire_answers", """
DESC questionnaire_answers;
"""),
    ("DESC chat_function_buttons", """
DESC chat_function_buttons;
"""),
]

for title, sql in queries:
    sql_one = sql.strip().replace("\n", " ")
    cmd = f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -t bini_health -e \"{sql_one}\" 2>&1 | grep -v 'Using a password'"
    out, err = run(cmd, timeout=60)
    print("\n=== " + title + " ===")
    print(out)
    if err:
        print("STDERR:", err)

cli.close()
