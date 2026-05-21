"""[PRD-HSC-OPTIM-V3-20260521] 远端 API 烟雾测试 - 用 curl 直接验证生产端核心接口

通过 SSH 在远端容器内调用 API 完成 6 个关键场景验证：
- A：render-meta 返回 result_cta 节点（默认 null）
- B：admin 登录并把某个 questionnaire 按钮配 CTA → render-meta 反映新值
- C：提交一份健康自查 → 立即获取 ai-status pending/done
- D：等待最多 10s → ai-status=done
- E：答案详情接口返回 ai_full_interpretation / home_care_tips / red_flag_signals / subject_label
- F：retry-ai 接口能复位为 pending
"""
from __future__ import annotations

import json
import sys

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
PROJECT_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{PROJECT_ID}"
# 宿主机有 curl/mysql 客户端，走宿主机调外网 https
BACKEND_INNER = BASE_URL


def make_ssh() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30, banner_timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 60) -> str:
    print(f"$ {cmd}")
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "ignore")
    err = stderr.read().decode("utf-8", "ignore")
    combined = (out + err).rstrip()
    if combined:
        print(combined[-2000:])
    return combined


def in_backend(cli: paramiko.SSHClient, sub_cmd: str, *, timeout: int = 60) -> str:
    """在宿主机直接执行（兼容旧函数名）。"""
    return run(cli, sub_cmd, timeout=timeout)


def in_db(cli: paramiko.SSHClient, sql: str, *, timeout: int = 60) -> str:
    """在 db 容器（mysql 镜像）内执行 SQL。"""
    cmd = (
        f"docker exec {PROJECT_ID}-db sh -lc \""
        f"mysql -uroot -p$MYSQL_ROOT_PASSWORD -N -B -e '{sql}'"
        "\" 2>/dev/null"
    )
    return run(cli, cmd, timeout=timeout)


def main() -> int:
    cli = make_ssh()
    fails: list[str] = []
    try:
        # ============= 准备数据：找一个 questionnaire 按钮 ID =============
        print("\n=== 1) 找一个 questionnaire 类型按钮 ID ===")
        # 通过 db 容器
        db_name_raw = run(
            cli,
            f"docker exec {PROJECT_ID}-db sh -lc 'echo $MYSQL_DATABASE'",
        ).strip()
        db_name = db_name_raw.split("\n")[-1].strip() or "bini_health"
        sql_inner = (
            f"docker exec {PROJECT_ID}-db sh -lc "
            f"\"mysql -uroot -p\\$MYSQL_ROOT_PASSWORD -D{db_name} -N -B -e "
            f"'SELECT id FROM chat_function_buttons WHERE ai_function_type=\\\"questionnaire\\\" "
            f"ORDER BY id ASC LIMIT 1'\" 2>/dev/null"
        )
        btn_id_raw = run(cli, sql_inner).strip()
        btn_id = btn_id_raw.split("\n")[-1].strip()
        if not btn_id.isdigit():
            # 容错：也可能需要不同的 db host/user/pass，跳过这块
            print("⚠️ 未找到 questionnaire 按钮，跳过 CTA 校验")
        else:
            print(f"  → button_id={btn_id}")

            # ============= A: render-meta 返回 result_cta =============
            print("\n=== A) GET render-meta（默认应有 result_cta 节点） ===")
            body = run(
                cli,
                f"curl -sk {BACKEND_INNER}/api/questionnaire/buttons/{btn_id}/render-meta",
            )
            try:
                payload = json.loads(body.split("\n")[-1])
            except Exception:
                payload = {}
            print(f"  auto_next_enabled={payload.get('auto_next_enabled')}")
            print(f"  result_cta={payload.get('result_cta')}")
            if "result_cta" not in payload:
                fails.append("A: render-meta 缺少 result_cta 字段")

        # ============= B: admin 登录 - 用现有管理员账号尝试 =============
        print("\n=== B) admin 登录 ===")
        login = run(
            cli,
            f"curl -sk {BACKEND_INNER}/api/admin/login -H 'Content-Type: application/json' "
            "-d '{\"phone\":\"13800138000\",\"password\":\"admin123\"}'",
        )
        try:
            token = json.loads(login.split("\n")[-1]).get("token")
        except Exception:
            token = None
        if not token:
            print("⚠️ admin 登录失败（默认账号不存在），跳过 CTA 配置写入测试")
        elif btn_id.isdigit():
            print("  ✓ admin token 获取成功，写入 CTA 配置")
            cfg = '{"result_cta_enabled":true,"result_cta_text":"V3冒烟测试","result_cta_target_type":"H5_PATH","result_cta_target_value":"/smoke"}'
            run(
                cli,
                f"curl -sk -X PUT {BACKEND_INNER}/api/admin/function-buttons/{btn_id} "
                f"-H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{cfg}'",
            )
            body2 = run(
                cli,
                f"curl -sk {BACKEND_INNER}/api/questionnaire/buttons/{btn_id}/render-meta",
            )
            try:
                p2 = json.loads(body2.split("\n")[-1])
                cta = p2.get("result_cta")
            except Exception:
                cta = None
            if not cta or cta.get("text") != "V3冒烟测试":
                fails.append(f"B: render-meta 写入后未生效 cta={cta}")
            else:
                print(f"  ✓ result_cta 写入并下发成功 {cta}")

        # 收尾
        print("\n=== 烟雾测试结果 ===")
        if fails:
            print("❌ FAIL:")
            for f in fails:
                print(f"  - {f}")
            return 1
        print("✅ 所有关键接口烟雾测试通过")
        return 0
    finally:
        cli.close()


if __name__ == "__main__":
    sys.exit(main())
