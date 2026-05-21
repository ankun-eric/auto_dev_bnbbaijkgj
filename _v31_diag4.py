import paramiko
cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("newbb.test.bangbangvip.com", username="ubuntu", password="Newbang888", timeout=30)
sql = "SELECT id,user_id,template_id,ai_status,subject_kind,subject_name,subject_relation,LENGTH(IFNULL(ai_full_interpretation,'')) AS ai_len,LENGTH(IFNULL(home_care_tips_json,'')) AS tips_len FROM questionnaire_answer ORDER BY id DESC LIMIT 5;"
stdin,stdout,stderr = cli.exec_command(f"docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-db mysql -uroot -pbini_health_2026 -t bini_health -e \"{sql}\" 2>&1 | grep -v 'Using a password'")
print(stdout.read().decode("utf-8","ignore"))
cli.close()
