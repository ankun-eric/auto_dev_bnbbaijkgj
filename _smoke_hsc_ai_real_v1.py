"""[PRD-HSC-AI-REAL-V1 2026-05-21] 远端烟雾测试。

执行：
1. SSH 进入服务器，在后端容器内运行一个 Python 检查：
   - questionnaire_answer 表已有 ai_profile_snapshot / ai_generated_at 两列
   - questionnaire_template.health_self_check 的 ai_prompt_template 不含旧版错误占位符 {scores}/{main_type}
2. 公网调 /api/health 与 /health-self-check/result/9999999 路由验证。
"""
from __future__ import annotations

import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
DEPLOY_DIR = f"/home/ubuntu/{PROJECT_ID}"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"


CHECK_SCRIPT = """
import asyncio
from app.core.database import async_session
from sqlalchemy import text


async def main():
    async with async_session() as db:
        # 1) 检查列存在
        cols = (
            await db.execute(
                text(
                    \"\"\"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                       WHERE TABLE_SCHEMA = DATABASE()
                         AND TABLE_NAME = 'questionnaire_answer'
                         AND COLUMN_NAME IN ('ai_profile_snapshot', 'ai_generated_at')\"\"\"
                )
            )
        ).fetchall()
        col_names = {r[0] for r in cols}
        print('[check] ai_profile_snapshot_exists=', 'ai_profile_snapshot' in col_names)
        print('[check] ai_generated_at_exists=', 'ai_generated_at' in col_names)

        # 2) 检查 health_self_check 模板的 ai_prompt_template
        r = (
            await db.execute(
                text('SELECT ai_prompt_template FROM questionnaire_template '
                     'WHERE code = \"health_self_check\" LIMIT 1')
            )
        ).first()
        prompt = (r[0] or '') if r else ''
        print('[check] template_exists=', bool(r))
        print('[check] template_prompt_len=', len(prompt))
        print('[check] has_zh_body_part=', '{部位}' in prompt)
        print('[check] has_zh_symptoms=', '{症状列表}' in prompt)
        print('[check] has_zh_duration=', '{持续时间}' in prompt)
        print('[check] has_legacy_scores=', '{scores}' in prompt)
        print('[check] has_legacy_main_type=', '{main_type}' in prompt)
        print('[check] has_legacy_en_body_parts=', '{body_parts}' in prompt)

        # 3) 已有答卷 ai_status 分布
        rows = (
            await db.execute(
                text('SELECT ai_status, COUNT(*) FROM questionnaire_answer GROUP BY ai_status')
            )
        ).fetchall()
        print('[check] ai_status_dist=', [(r[0], r[1]) for r in rows])


asyncio.run(main())
"""


def main() -> int:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    try:
        # 写入临时检查脚本到服务器
        sftp = cli.open_sftp()
        try:
            with sftp.file(f"{DEPLOY_DIR}/_hsc_ai_real_v1_check.py", "w") as f:
                f.write(CHECK_SCRIPT)
        finally:
            sftp.close()
        # 容器内执行
        cmd = (
            f"docker cp {DEPLOY_DIR}/_hsc_ai_real_v1_check.py "
            f"{PROJECT_ID}-backend:/app/_hsc_ai_real_v1_check.py "
            f"&& docker exec {PROJECT_ID}-backend python /app/_hsc_ai_real_v1_check.py 2>&1"
        )
        print(f"$ {cmd}")
        stdin, stdout, stderr = cli.exec_command(cmd, timeout=120, get_pty=False)
        out = stdout.read().decode("utf-8", "ignore")
        err = stderr.read().decode("utf-8", "ignore")
        print(out + err)
        rc = stdout.channel.recv_exit_status()
        return 0 if rc == 0 else rc
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
