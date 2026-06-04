import paramiko
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=30)

# 看 page.js 是不是包含我们新加的 capture_purpose
cmds = [
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c "capture_purpose" /app/.next/server/app/\\(ai-chat\\)/ai-home/page.js',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c "ai_function_type" /app/.next/server/app/\\(ai-chat\\)/ai-home/page.js',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c "interpret_report" /app/.next/server/app/\\(ai-chat\\)/ai-home/page.js',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c "identify_medicine" /app/.next/server/app/\\(ai-chat\\)/ai-home/page.js',
    'docker exec 6b099ed3-7175-4a78-91f4-44570c84ed27-h5 grep -c "report_understand" /app/.next/server/app/\\(ai-chat\\)/ai-home/page.js',
]
for cmd in cmds:
    print(f"$ {cmd[-100:]}")
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode().strip() or '0')
c.close()
