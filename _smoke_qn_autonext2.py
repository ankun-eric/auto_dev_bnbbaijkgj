"""验证 render-meta 与 BUG-2 后端兜底"""
import paramiko, json

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, username=USER, password=PWD, timeout=30)


def sh(cmd, t=60):
    si, so, se = cli.exec_command(cmd, timeout=t)
    return so.read().decode("utf-8", "replace"), se.read().decode("utf-8", "replace")


# 列出所有模板
o, _ = sh(
    f"docker exec {DEPLOY_ID}-db mysql -N -uroot -pbini_health_2026 bini_health "
    f"-e \"SELECT id, code, name FROM questionnaire_template\" 2>/dev/null"
)
print("=== 问卷模板列表 ===")
print(o)

# 列出所有 questionnaire 按钮的简表（使用 LIMIT + name 引号转换）
o, _ = sh(
    f"docker exec {DEPLOY_ID}-db mysql -N -uroot -pbini_health_2026 bini_health "
    f"-e \"SELECT cfb.id, cfb.questionnaire_template_id, qt.code, "
    f"cfb.presentation_container, cfb.questions_per_page, cfb.auto_next_enabled "
    f"FROM chat_function_buttons cfb LEFT JOIN questionnaire_template qt "
    f"ON cfb.questionnaire_template_id=qt.id "
    f"WHERE cfb.ai_function_type='questionnaire'\" 2>/dev/null"
)
print("\n=== questionnaire 按钮 vs 模板 code ===")
print(o)

# 取首个 TCM 按钮做 render-meta
lines = [ln for ln in o.strip().split("\n") if "tcm_constitution_wangqi_36" in ln]
btn_id = None
if lines:
    btn_id = lines[0].split("\t")[0]
print(f"\nTCM 按钮 id = {btn_id!r}")
if btn_id and btn_id.isdigit():
    out, _ = sh(f"curl -sk '{BASE_URL}/api/questionnaire/buttons/{btn_id}/render-meta'")
    try:
        d = json.loads(out)
        print(json.dumps({
            "display_form": d.get("display_form"),
            "presentation_container": d.get("presentation_container"),
            "questions_per_page": d.get("questions_per_page"),
            "auto_next_enabled": d.get("auto_next_enabled"),
        }, ensure_ascii=False, indent=2))
    except Exception as ex:
        print("parse err:", ex, out[:500])

# 验证 BUG-2 修复：测试 tcm.py 是否包含新的 asyncio.wait_for 代码
o, _ = sh(
    f"docker exec {DEPLOY_ID}-backend grep -n 'asyncio.wait_for' /app/api/tcm.py 2>&1"
)
print("\n=== tcm.py 中的 wait_for 修复 ===")
print(o)

# 验证 BUG-1 校验代码已上线
o, _ = sh(
    f"docker exec {DEPLOY_ID}-backend grep -n 'PRESENTATION_CONTAINERS' /app/api/function_button.py 2>&1"
)
print("\n=== function_button.py 中的呈现配置校验 ===")
print(o)

cli.close()
