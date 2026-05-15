#!/usr/bin/env python3
"""[PRD-AICHAT-CAPSULE-V2] 验证服务器迁移结果。"""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DB_PASS = "bini_health_2026"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

    cmds = [
        # 列出全部内置模板
        f"""docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} -e "SELECT id, code, name, is_builtin, prompt_type FROM bini_health.prompt_templates WHERE is_builtin=1 OR code IS NOT NULL ORDER BY id;" 2>/dev/null""",
        # 列出识药按钮及绑定模板
        f"""docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} -e "SELECT b.id, b.name, b.button_type, b.prompt_template_id, p.code AS template_code, p.name AS template_name FROM bini_health.chat_function_buttons b LEFT JOIN bini_health.prompt_templates p ON b.prompt_template_id=p.id WHERE b.button_type IN ('photo_recognize_drug','drug_identify');" 2>/dev/null""",
        # column 仍存在
        f"""docker exec {DEPLOY_ID}-db mysql -uroot -p{DB_PASS} -e "SHOW COLUMNS FROM bini_health.prompt_templates LIKE 'code'; SHOW COLUMNS FROM bini_health.prompt_templates LIKE 'is_builtin';" 2>/dev/null""",
    ]
    for i, cmd in enumerate(cmds, 1):
        print(f"\n==> [{i}]")
        _, o, e = c.exec_command(cmd)
        print(o.read().decode("utf-8", errors="replace"))
        err = e.read().decode("utf-8", errors="replace")
        if err.strip():
            print("ERR:", err[-400:])
    c.close()


if __name__ == "__main__":
    main()
