import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=20)
keywords = [
    ('本套餐可管理', '6b099ed3-7175-4a78-91f4-44570c84ed27-h5'),
    ('家庭守护成员', '6b099ed3-7175-4a78-91f4-44570c84ed27-h5'),
    ('家庭守护成员总人数', '6b099ed3-7175-4a78-91f4-44570c84ed27-admin'),
    ('填几就是几', '6b099ed3-7175-4a78-91f4-44570c84ed27-admin'),
    ('含本人在内', '6b099ed3-7175-4a78-91f4-44570c84ed27-h5'),  # 应该不出现在权益卡片
]
for kw, cn in keywords:
    cmd = f"docker exec {cn} sh -c 'grep -rl \"{kw}\" /app/.next/static 2>/dev/null | head -3'"
    i, o, e = c.exec_command(cmd, timeout=30)
    out = o.read().decode()
    err = e.read().decode()
    print(f'\n=== "{kw}" in {cn} ===')
    print(out.strip() if out.strip() else '(无匹配)')
    if err.strip():
        print('STDERR:', err)
c.close()
