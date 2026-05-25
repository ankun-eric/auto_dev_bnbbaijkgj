# -*- coding: utf-8 -*-
"""[紧急呼叫触发源管理 v1.0] 修复 + 增强部署脚本

流程：
1. 上传后端 + admin-web 改动文件到服务器
2. rebuild backend + admin-web
3. 重启容器并等待 backend 就绪
4. 现网 UPDATE：修复 4 条内置触发源中文乱码
5. HTTP smoke 测试 + 容器内单元测试
"""
from __future__ import annotations
import os
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"
REMOTE_PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
LOCAL_ROOT = os.path.dirname(os.path.abspath(__file__))


def ssh_run(client, cmd, timeout=600, silent=False):
    if not silent:
        print(f"[ssh] $ {cmd[:240]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    combined = out + ("\n[stderr]\n" + err if err.strip() else "")
    if not silent:
        tail = "\n".join(combined.splitlines()[-100:])
        print(tail)
        print(f"[ssh] exit={rc}")
    return rc, combined


def scp_put(sftp, local_path, remote_path):
    print(f"[scp] {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = client.open_sftp()

    try:
        print("\n[1] 上传修改的源码文件")
        files = [
            "backend/app/api/guardian_system_v12.py",
            "backend/app/services/schema_sync.py",
            "backend/tests/test_guardian_system_v12.py",
            "admin-web/src/app/(admin)/emergency-sources/page.tsx",
        ]
        for rel in files:
            local = os.path.join(LOCAL_ROOT, rel.replace("/", os.sep))
            remote = f"{REMOTE_PROJECT_DIR}/{rel}"
            remote_dir = os.path.dirname(remote)
            ssh_run(client, f"mkdir -p '{remote_dir}'", timeout=10, silent=True)
            scp_put(sftp, local, remote)

        print("\n[2] Rebuild backend + admin-web")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose build backend admin-web 2>&1 | tail -20",
            timeout=900,
        )

        print("\n[3] 重启容器")
        ssh_run(
            client,
            f"cd {REMOTE_PROJECT_DIR} && docker compose up -d backend admin-web 2>&1 | tail -10",
            timeout=180,
        )

        print("\n[4] 等待 backend 启动")
        ready = False
        for i in range(60):
            time.sleep(2)
            rc, out = ssh_run(
                client,
                f"docker logs --tail=60 {DEPLOY_ID}-backend 2>&1 | tail -30",
                timeout=20,
                silent=True,
            )
            if "Application startup complete" in out or "Uvicorn running" in out:
                print(f"    backend ready @ {(i + 1) * 2}s")
                ready = True
                break
            if "Traceback" in out and ("Error" in out or "error" in out):
                print("    ⚠️ backend 启动报错")
                ssh_run(client, f"docker logs --tail=120 {DEPLOY_ID}-backend 2>&1 | tail -120", timeout=20)
                break
        if not ready:
            print("    ⚠️ backend 未在 120s 内就绪")

        print("\n[5] 现网 UPDATE - 修复 4 条内置触发源中文乱码 (使用 utf8mb4)")
        # 使用 base64 传输 SQL 内容，规避 shell 引号转义
        import base64
        sql = (
            "SET NAMES utf8mb4;\n"
            "UPDATE emergency_call_sources SET source_name='健康数据异常',"
            " description='当用户的健康数据（如心率、血压、血氧）超出安全阈值时自动触发',"
            " is_enabled=1, updated_at=NOW() WHERE source_code='health_data_abnormal';\n"
            "UPDATE emergency_call_sources SET source_name='烟雾报警',"
            " description='当家中烟雾传感器检测到烟雾浓度异常时触发紧急呼叫',"
            " is_enabled=1, updated_at=NOW() WHERE source_code='smoke_alarm';\n"
            "UPDATE emergency_call_sources SET source_name='浸水报警',"
            " description='当家中浸水传感器检测到漏水或积水时触发紧急呼叫',"
            " is_enabled=1, updated_at=NOW() WHERE source_code='water_alarm';\n"
            "UPDATE emergency_call_sources SET source_name='紧急按钮',"
            " description='当用户按下随身或家中的一键紧急呼叫按钮时立即触发',"
            " is_enabled=1, updated_at=NOW() WHERE source_code='emergency_button';\n"
            "SELECT id, source_code, source_name, LEFT(description, 50) AS desc_preview,"
            " is_enabled, is_builtin FROM emergency_call_sources ORDER BY sort_order;\n"
        )
        b64 = base64.b64encode(sql.encode("utf-8")).decode("ascii")
        ssh_run(
            client,
            f"echo {b64} | base64 -d | "
            f"docker exec -i {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 "
            f"--default-character-set=utf8mb4 bini_health",
            timeout=30,
        )

        print("\n[6] HTTP smoke - 接口可达性")
        smoke_paths = [
            "/api/openapi.json",
            "/api/admin/emergency-sources",
            "/admin/emergency-sources",
        ]
        for path in smoke_paths:
            ssh_run(
                client,
                f"curl -sk -o /tmp/resp.txt -w '{path} -> %{{http_code}}\\n' '{BASE_URL}{path}'",
                timeout=15,
            )

        print("\n[7] 验证管理员接口中文已正常")
        ssh_run(
            client,
            f"TOKEN=$(curl -sk -X POST '{BASE_URL}/api/admin/login' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"phone\":\"13900000000\",\"password\":\"admin123\"}}' "
            f"| python3 -c 'import json,sys;d=json.load(sys.stdin);print(d.get(\"token\") or d.get(\"access_token\") or \"\")'); "
            f"echo \"token_len=$(echo -n $TOKEN | wc -c)\"; "
            f"if [ -n \"$TOKEN\" ]; then "
            f"curl -sk -H \"Authorization: Bearer $TOKEN\" '{BASE_URL}/api/admin/emergency-sources' "
            f"| python3 -c 'import json,sys;d=json.load(sys.stdin);"
            f"items=d.get(\"items\",[]);"
            f"print(\"total\", len(items));"
            f"[print(i[\"source_code\"], i[\"source_name\"], (i.get(\"description\") or \"\")[:30], "
            f"\"builtin=\", i[\"is_builtin\"], \"enabled=\", i[\"is_enabled\"]) for i in items]'; "
            f"fi",
            timeout=30,
        )

        print("\n[8] 容器内单元测试（含新增的 T16-T19）")
        ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-backend bash -c "
            f"'cd /app && python -m pytest tests/test_guardian_system_v12.py "
            f"-v -k \"emergency_source or builtin\" 2>&1 | tail -80'",
            timeout=400,
        )

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        client.close()


if __name__ == "__main__":
    main()
