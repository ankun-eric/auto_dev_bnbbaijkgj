"""Smoke 自动下一步：通过 paramiko 查 DB + curl render-meta"""
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
    return (so.read().decode("utf-8", "replace"), se.read().decode("utf-8", "replace"))


# 1) 查 DB
sql = (
    "SELECT id, name, ai_function_type, questionnaire_template_id, "
    "presentation_container, questions_per_page, auto_next_enabled, "
    "questionnaire_display_form FROM chat_function_buttons "
    "WHERE ai_function_type='questionnaire' LIMIT 20\\G"
)
o, e = sh(
    f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health "
    f"-e \"{sql}\" 2>&1 | grep -v Warning"
)
print("=== 问卷按钮新字段 ===")
print(o)
if e and "Warning" not in e:
    print("[stderr]", e)

# 2) 拿一个 TCM 按钮 ID
sql2 = (
    "SELECT id FROM chat_function_buttons cfb "
    "INNER JOIN questionnaire_template qt ON cfb.questionnaire_template_id=qt.id "
    "WHERE qt.code='tcm_constitution_wangqi_36' "
    "AND cfb.ai_function_type='questionnaire' LIMIT 1"
)
o, e = sh(
    f"docker exec {DEPLOY_ID}-db mysql -N -uroot -pbini_health_2026 bini_health "
    f"-e \"{sql2}\" 2>/dev/null"
)
btn_id = (o or "").strip()
print(f"\nTCM 按钮 ID = {btn_id!r}")

# 3) 调 render-meta
if btn_id.isdigit():
    o, e = sh(f"curl -sk '{BASE_URL}/api/questionnaire/buttons/{btn_id}/render-meta'")
    try:
        data = json.loads(o)
        print("\n=== render-meta（关键字段） ===")
        print(json.dumps({
            "display_form": data.get("display_form"),
            "presentation_container": data.get("presentation_container"),
            "questions_per_page": data.get("questions_per_page"),
            "auto_next_enabled": data.get("auto_next_enabled"),
            "btn_meta": {
                k: data.get("button", {}).get(k)
                for k in [
                    "id", "name", "ai_function_type",
                    "presentation_container", "questions_per_page",
                    "auto_next_enabled",
                ]
            },
        }, ensure_ascii=False, indent=2))
    except Exception as ex:
        print("render-meta parse error:", ex)
        print(o[:500])

# 4) 尝试触发 BUG-2 修复链路：POST 一组测评看返回是否带 id
# 跳过（需要登录态）

cli.close()
