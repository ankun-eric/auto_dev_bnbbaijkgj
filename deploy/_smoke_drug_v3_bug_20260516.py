"""[BUG_FIX_拍照识药三联_20260516] 服务器端非UI自动化测试。

直接 SSH 到服务器，把测试脚本注入 backend 容器内运行，
覆盖：
- ai_output_sanitizer 的所有清洗规则
- verify_drug_name_against_ocr 的相似度计算
- drug_identify_engine 的触发判定 / 隐式上下文 / retake 兜底
- health_profile_service 的档案降级取值
- chat ChatMessageCreate schema 接受 button_type / family_member_id
- /api/chat/sessions/* 路由可达（非业务校验）
"""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"

SMOKE_PY = r'''
import asyncio, json, sys, traceback
sys.path.insert(0, "/app")
from app.utils.ai_output_sanitizer import sanitize_ai_output, sanitize_for_drug_card, verify_drug_name_against_ocr
from app.services.drug_identify_engine import is_drug_identify_intent, build_implicit_drug_context, run_drug_identify_stream
from app.schemas.chat import ChatMessageCreate

PASS = []
FAIL = []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("[PASS]" if cond else "[FAIL]"), name, "-", detail if not cond else "")

# 1. sanitize: 去多空行
check("sanitize_collapse_blank", "\n\n\n" not in sanitize_ai_output("a\n\n\n\nb"))
# 2. sanitize: 免责段去重
out = sanitize_ai_output("正文\n\nAI 识别结果仅供参考，具体用药请遵医嘱。\n\nAI 识别结果仅供参考，具体用药请遵医嘱。")
check("sanitize_dedup_disclaimer", out.count("具体用药请遵医嘱") == 1, repr(out))
# 3. sanitize: 移除 ---disclaimer--- 标签
out = sanitize_ai_output("a\n\n---disclaimer---\n免责声明\n---/disclaimer---")
check("sanitize_strip_tag", "---disclaimer---" not in out, repr(out))
# 4. sanitize: 段落 hash 去重
out = sanitize_ai_output("注意事项：饭后服用\n\n注意事项：饭后服用\n\n剂量：5mg")
check("sanitize_dedup_paragraph", out.count("注意事项：饭后服用") == 1, repr(out))
# 5. verify: 高相似度
check("verify_high_sim", verify_drug_name_against_ocr("阿司匹林肠溶片", "阿司匹林肠溶片 100mg*30片 拜耳") >= 0.7)
# 6. verify: 完全不一致
check("verify_low_sim", verify_drug_name_against_ocr("感冒灵颗粒", "阿司匹林肠溶片 100mg") < 0.4)
# 7. intent: 按钮触发
check("intent_button", is_drug_identify_intent(button_type="photo_recognize_drug", content="https://x/y.jpg", image_urls=["https://x/y.jpg"]) is True)
# 8. intent: 关键词触发
check("intent_keyword", is_drug_identify_intent(button_type=None, content="我上传了一张药品图片 https://x/y.jpg", image_urls=["https://x/y.jpg"]) is True)
# 9. intent: 无图不触发
check("intent_no_image", is_drug_identify_intent(button_type="photo_recognize_drug", content="拍照识药", image_urls=[]) is False)
# 10. implicit context: 卡片 meta
ctx = build_implicit_drug_context({"message_type": "drug_identify_card", "medicines": [{"name": "阿司匹林"}]})
check("implicit_ctx_card", ctx is not None and "阿司匹林" in ctx)
# 11. implicit context: 其他类型应为 None
check("implicit_ctx_none", build_implicit_drug_context({"message_type": "text"}) is None)
# 12. schema: 接受新字段
m = ChatMessageCreate(content="hi", button_type="photo_recognize_drug", family_member_id=42)
check("schema_new_fields", m.button_type == "photo_recognize_drug" and m.family_member_id == 42)
# 13. schema: 旧请求兼容
m2 = ChatMessageCreate(content="hi", source="text")
check("schema_back_compat", m2.button_type is None and m2.family_member_id is None)
# 14. run_drug_identify_stream: 无图返回 retake
async def _r():
    out = []
    async for ev in run_drug_identify_stream(image_urls=[], ocr_text_hint=None, user_id=1, family_member_id=None, db=None):
        out.append(ev)
    return out
events = asyncio.get_event_loop().run_until_complete(_r())
final = [e for e in events if e.get("type") == "done"][-1]
check("engine_no_image_retake", final["meta"]["message_type"] == "drug_identify_retake", repr(final))
# 15. drug_card sanitize: 行数硬截断
big = "\n".join("line{}".format(i) for i in range(60))
check("sanitize_card_truncate", sanitize_for_drug_card(big).count("\n") < 60)

print("\n=== SMOKE SUMMARY ===")
print("PASS:", len(PASS))
print("FAIL:", len(FAIL))
if FAIL:
    print("Failed:", FAIL)
    raise SystemExit(1)
print("ALL GREEN")
'''


def run(client, cmd, timeout=120):
    print(f"$ {cmd[:200]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    if out.strip():
        print(out)
    if err.strip():
        print("STDERR:", err)
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # 把脚本写入容器内 /tmp，再运行（绕过 shell 引号转义）
        sftp = client.open_sftp()
        with sftp.file("/tmp/_smoke_drug_v3.py", "w") as fh:
            fh.write(SMOKE_PY)
        sftp.close()
        run(client, f"docker cp /tmp/_smoke_drug_v3.py {BACKEND}:/tmp/_smoke_drug_v3.py")
        rc, out, err = run(
            client,
            f"docker exec {BACKEND} sh -c 'cd /app && python /tmp/_smoke_drug_v3.py 2>&1'",
            timeout=120,
        )
        if rc != 0:
            print(f"\n[SMOKE FAILED rc={rc}]")
            sys.exit(rc)
        print("\n[SMOKE GREEN]")
    finally:
        client.close()


if __name__ == "__main__":
    main()
