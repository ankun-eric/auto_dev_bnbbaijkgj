"""V3.1 Bug 诊断 - 实际表名 questionnaire_answer"""
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
    ("DESC questionnaire_answer", "DESC questionnaire_answer;"),
    ("Bug 2 - 最新 5 条 answer 的关键字段", """
SELECT id, IFNULL(ai_status,'') AS ai_status, IFNULL(ai_failed_reason,'') AS ai_failed_reason,
       LENGTH(IFNULL(ai_full_interpretation,'')) AS ai_len,
       LENGTH(IFNULL(home_care_tips_json,''))    AS tips_len,
       LENGTH(IFNULL(red_flag_signals_json,''))  AS red_len,
       IFNULL(subject_kind,'') AS subject_kind,
       IFNULL(subject_member_id,0) AS subject_member_id,
       IFNULL(subject_name,'') AS subject_name,
       IFNULL(subject_relation,'') AS subject_relation,
       created_at
FROM questionnaire_answer
ORDER BY id DESC LIMIT 10;
"""),
]

for title, sql in queries:
    cmd = f"docker exec {DB_CONTAINER} mysql -uroot -pbini_health_2026 -t bini_health -e \"{sql}\" 2>&1 | grep -v 'Using a password'"
    print("\n=== " + title + " ===")
    print(run(cmd))

cli.close()
