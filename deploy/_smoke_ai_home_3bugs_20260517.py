"""[BUG_FIX_AI_HOME_3BUGS_20260517] 服务器侧 smoke：验证 sanitizer 在容器内表现符合预期。"""
import sys
import paramiko

HOST = "newbb.test.bangbangvip.com"
PORT = 22
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BACKEND = f"{DEPLOY_ID}-backend"


SMOKE_PY = r"""# -*- coding: utf-8 -*-
from app.utils.ai_output_sanitizer import sanitize_ai_output

cases = [
    # case 1: 正文末段含'请遵医嘱' → 整段保留
    {
        "name": "case_1 zhengwen_with_zunyizhu",
        "input": "高血压患者可以适量吃西瓜，每次不超过200g。请遵医嘱合理安排饮食。",
        "must_contain": ["高血压患者可以适量吃西瓜", "200g"],
        "must_not_contain": [],
    },
    # case 2: 多段免责整句 → 全部移除
    {
        "name": "case_2 multi_disclaimer",
        "input": "AI 识别结果仅供参考。\n\n西瓜含糖量约5%。\n\n本回答仅供参考，不构成医疗诊断。",
        "must_contain": ["西瓜含糖量约5%"],
        "must_not_contain": ["AI 识别结果仅供参考", "本回答仅供参考"],
    },
    # case 3: 独立段落仅含免责声明 → 整段移除
    {
        "name": "case_3 standalone_disclaimer",
        "input": "西瓜含水量约92%。\n\nAI 识别结果仅供参考",
        "must_contain": ["西瓜含水量约92%"],
        "must_not_contain": ["AI 识别结果仅供参考"],
    },
    # case 4: 零免责段 → 输出与输入实质一致
    {
        "name": "case_4 no_disclaimer",
        "input": "西瓜含水量约92%。\n\n建议餐后两小时再进食。",
        "must_contain": ["西瓜含水量约92%", "建议餐后两小时再进食"],
        "must_not_contain": ["仅供参考", "请遵医嘱"],
    },
    # case 5: 行级清洗 - 段内夹一行免责，其他行保留
    {
        "name": "case_5 inline_disclaimer_line",
        "input": "1. 单次不超过200g\n2. 餐后2小时再吃\nAI 识别结果仅供参考\n3. 冷藏后立即食用可能刺激肠胃",
        "must_contain": ["1. 单次不超过200g", "2. 餐后2小时再吃", "3. 冷藏后立即食用可能刺激肠胃"],
        "must_not_contain": ["AI 识别结果仅供参考"],
    },
]

ok = True
for c in cases:
    out = sanitize_ai_output(c["input"])
    name = c["name"]
    for needle in c["must_contain"]:
        if needle not in out:
            print("[FAIL] %s: missing %r in OUT=%r" % (name, needle, out))
            ok = False
    for needle in c["must_not_contain"]:
        if needle in out:
            print("[FAIL] %s: should NOT contain %r in OUT=%r" % (name, needle, out))
            ok = False
    if ok:
        print("[OK] %s" % name)

if ok:
    print("ALL_SMOKE_PASSED")
    raise SystemExit(0)
else:
    print("SMOKE_FAILED")
    raise SystemExit(1)
"""


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PWD,
                   timeout=30, allow_agent=False, look_for_keys=False)
    try:
        # 把 smoke 脚本写到容器内
        sftp = client.open_sftp()
        # 通过 docker cp 写入需先在 host 写文件
        host_tmp = f"/tmp/smoke_{DEPLOY_ID}.py"
        with sftp.open(host_tmp, "w") as f:
            f.write(SMOKE_PY)
        sftp.close()

        # docker cp 到容器内
        cmd_cp = f"docker cp {host_tmp} {BACKEND}:/app/_smoke_3bugs.py"
        stdin, stdout, stderr = client.exec_command(cmd_cp, timeout=30)
        stdout.channel.recv_exit_status()

        # 容器内执行
        cmd_run = f"docker exec {BACKEND} python /app/_smoke_3bugs.py"
        stdin, stdout, stderr = client.exec_command(cmd_run, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        rc = stdout.channel.recv_exit_status()

        print(out)
        if err.strip():
            print("STDERR:", err)
        print("rc =", rc)
        return rc
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main() or 0)
