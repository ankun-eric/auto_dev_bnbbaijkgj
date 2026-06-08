#!/usr/bin/env python3
"""远程查询数据库 - 正确字段名"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DB_CONTAINER = "6b099ed3-7175-4a78-91f4-44570c84ed27-db"
DB_PWD = "bini_health_2026"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def mysql_query(sql):
    cmd = f"docker exec {DB_CONTAINER} mysql -uroot -p'{DB_PWD}' -h127.0.0.1 bini_health -e \"{sql}\" 2>&1"
    out, err = run(cmd)
    return out

try:
    client.connect(HOST, port=PORT, username=USER, password=PWD, timeout=15,
                   look_for_keys=False, allow_agent=False, banner_timeout=15)
    print("[OK] SSH 连接成功\n")

    # 查询1: user_id=18 AND family_member_id IS NULL
    print("=" * 60)
    print("查询1: user_id=18 AND family_member_id IS NULL")
    print("=" * 60)
    result = mysql_query("SELECT id, user_id, family_member_id, name, gender, birthday FROM health_profiles WHERE user_id = 18 AND family_member_id IS NULL")
    print(result)

    # 查询2: user_id=18 的全部记录
    print("=" * 60)
    print("查询2: user_id=18 的全部记录")
    print("=" * 60)
    result = mysql_query("SELECT id, user_id, family_member_id, name, gender, birthday FROM health_profiles WHERE user_id = 18")
    print(result)

    # 查询3: 邀请信息
    print("=" * 60)
    print("查询3: 邀请码 695e3db0ab80 的邀请信息")
    print("=" * 60)
    result = mysql_query("SELECT id, invite_code, inviter_user_id, member_id, status, expires_at FROM family_invitations WHERE invite_code = '695e3db0ab80'")
    print(result)

    # 查询4: 用户18管理的家庭成员
    print("=" * 60)
    print("查询4: 用户18管理的家庭成员")
    print("=" * 60)
    result = mysql_query("SELECT id, manager_user_id, managed_user_id, managed_member_id, status FROM family_management WHERE manager_user_id = 18")
    print(result)

    # 查询5: 被邀请人=用户18 的所有邀请
    print("=" * 60)
    print("查询5: 被邀请人=用户18 的所有邀请")
    print("=" * 60)
    result = mysql_query("SELECT id, invite_code, inviter_user_id, member_id, status, accepted_by, expires_at FROM family_invitations WHERE accepted_by = 18 OR invite_code IN (SELECT invite_code FROM family_invitations WHERE accepted_by = 18)")
    print(result)

    # 查询6: 看看所有pending状态的邀请
    print("=" * 60)
    print("查询6: 所有pending状态的邀请")
    print("=" * 60)
    result = mysql_query("SELECT id, invite_code, inviter_user_id, member_id, status, accepted_by FROM family_invitations WHERE status = 'pending'")
    print(result)

finally:
    client.close()
    print("[OK] SSH 已断开")
