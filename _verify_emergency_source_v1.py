# -*- coding: utf-8 -*-
"""[紧急呼叫触发源管理 v1.0] 服务端验证脚本

验证：
A. 数据库中 4 条内置触发源中文文案正确（已 UPDATE 修复）
B. GET /api/admin/emergency-sources 返回中文正常
C. 内置触发源 PUT name+desc - 允许
D. 内置触发源 PUT is_enabled=false - 静默忽略，仍为 True
E. 内置触发源 PUT source_code - 静默忽略
F. 内置触发源 DELETE - 返回 403
G. 内置触发源 PATCH toggle - 返回 403
H. 自定义触发源全字段可改 / 可 toggle / 可删除
"""
from __future__ import annotations
import json
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://{HOST}/autodev/{DEPLOY_ID}"


def ssh_run(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30)
    try:
        results = []

        # ===== A. 数据库直查 =====
        rc, out, _ = ssh_run(
            client,
            f"docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 "
            f"--default-character-set=utf8mb4 bini_health -B -e "
            f"\"SELECT source_code, source_name, description, is_enabled, is_builtin "
            f"FROM emergency_call_sources ORDER BY sort_order;\"",
        )
        print("\n[A] DB 直查 emergency_call_sources:")
        print(out)
        expected_names = {
            "health_data_abnormal": "健康数据异常",
            "smoke_alarm": "烟雾报警",
            "water_alarm": "浸水报警",
            "emergency_button": "紧急按钮",
        }
        a_pass = all(name in out for name in expected_names.values())
        results.append(("A. DB 4 条内置文案正确", a_pass))

        # ===== 登录 =====
        # 写一个小的 python 脚本到容器内执行，避免多层 shell 转义
        py_script = (
            "import json, urllib.request as r;"
            "req=r.Request('http://127.0.0.1:8000/api/admin/login',"
            "data=json.dumps({'phone':'13800000000','password':'admin123'}).encode(),"
            "headers={'Content-Type':'application/json'},method='POST');"
            "resp=r.urlopen(req,timeout=10);"
            "print(resp.read().decode())"
        )
        login_cmd = (
            f"docker exec {DEPLOY_ID}-backend python3 -c \"{py_script}\""
        )
        rc, out, _ = ssh_run(client, login_cmd)
        print("\n[login resp]:", out[:500])
        # 去掉 HTTP_CODE 尾部
        json_part = out.split("\nHTTP_CODE=")[0].strip()
        try:
            login = json.loads(json_part)
            token = login.get("token") or login.get("access_token") or login.get("data", {}).get("token")
        except Exception as e:
            print(f"[login parse err] {e}")
            token = None
        results.append(("[login] 取到 token", bool(token)))
        if not token:
            print("无法登录，后续验证跳过。请人工核查 /api/admin/login 行为")
            for label, ok in results:
                print(f"  {'OK ' if ok else 'NG '} {label}")
            return

        import base64 as _b64

        def be_curl(method, path, json_body=None):
            """在 backend 容器内通过 Python 请求接口（避免 shell 转义）。
            返回 (http_code_str, body_text)。"""
            body_json = json.dumps(json_body, ensure_ascii=False) if json_body is not None else ""
            py = (
                "import json, urllib.request as r, urllib.error as e, base64;\n"
                f"method={method!r};\n"
                f"path={path!r};\n"
                f"token={token!r};\n"
                f"body_b64={_b64.b64encode(body_json.encode('utf-8')).decode()!r};\n"
                "body = base64.b64decode(body_b64).decode('utf-8') if body_b64 else None;\n"
                "data = body.encode('utf-8') if body else None;\n"
                "req = r.Request('http://127.0.0.1:8000'+path, data=data,\n"
                "    headers={'Content-Type':'application/json','Authorization':'Bearer '+token}, method=method);\n"
                "try:\n"
                "    resp = r.urlopen(req, timeout=20);\n"
                "    print(resp.status);\n"
                "    print(resp.read().decode('utf-8'));\n"
                "except e.HTTPError as ex:\n"
                "    print(ex.code);\n"
                "    print(ex.read().decode('utf-8'));\n"
            )
            py_b64 = _b64.b64encode(py.encode("utf-8")).decode()
            cmd = (
                f"docker exec {DEPLOY_ID}-backend bash -c "
                f"\"echo {py_b64} | base64 -d | python3\""
            )
            rc, out, _ = ssh_run(client, cmd)
            lines = out.strip().split("\n", 1)
            code = lines[0].strip()
            body = lines[1] if len(lines) > 1 else ""
            return code, body

        # ===== B. GET list =====
        code, body = be_curl("GET", "/api/admin/emergency-sources")
        print(f"\n[B] GET list code={code} body_head={body[:300]}")
        b_pass = code == "200" and "健康数据异常" in body and "烟雾报警" in body \
                 and "浸水报警" in body and "紧急按钮" in body
        results.append(("B. 接口返回 4 条内置中文正确", b_pass))

        # 解析得到 4 条记录的 id
        items = []
        try:
            items = json.loads(body).get("items", [])
        except Exception:
            pass
        idx = {i["source_code"]: i for i in items}
        smoke_id = idx.get("smoke_alarm", {}).get("id")
        water_id = idx.get("water_alarm", {}).get("id")
        eb_id = idx.get("emergency_button", {}).get("id")

        # ===== C. PUT 内置 name+desc allowed =====
        if smoke_id:
            code, body = be_curl(
                "PUT", f"/api/admin/emergency-sources/{smoke_id}",
                json_body={"source_name": "烟雾报警", "description": "当家中烟雾传感器检测到烟雾浓度异常时触发紧急呼叫"},
            )
            print(f"\n[C] PUT 内置 name+desc code={code} body={body[:200]}")
            results.append(("C. PUT 内置 name+desc 200", code == "200"))

        # ===== D. PUT 内置 is_enabled=false 静默忽略 =====
        if smoke_id:
            code, body = be_curl(
                "PUT", f"/api/admin/emergency-sources/{smoke_id}",
                json_body={"is_enabled": False},
            )
            print(f"\n[D-put] PUT is_enabled=false code={code}")
            # 再 GET 验证仍为 True
            code2, body2 = be_curl("GET", "/api/admin/emergency-sources")
            items2 = json.loads(body2).get("items", []) if code2 == "200" else []
            smoke2 = next((i for i in items2 if i["id"] == smoke_id), None)
            still_enabled = bool(smoke2 and smoke2["is_enabled"])
            print(f"[D] 再查 smoke is_enabled={smoke2 and smoke2['is_enabled']}")
            results.append(("D. 内置 PUT is_enabled=false 被忽略，仍为 True", code == "200" and still_enabled))

        # ===== E. PUT 内置 source_code 静默忽略 =====
        if smoke_id:
            code, body = be_curl(
                "PUT", f"/api/admin/emergency-sources/{smoke_id}",
                json_body={"source_code": "hacked_code"},
            )
            print(f"\n[E-put] PUT source_code=hacked code={code}")
            code2, body2 = be_curl("GET", "/api/admin/emergency-sources")
            items2 = json.loads(body2).get("items", []) if code2 == "200" else []
            smoke3 = next((i for i in items2 if i["id"] == smoke_id), None)
            unchanged = bool(smoke3 and smoke3["source_code"] == "smoke_alarm")
            results.append(("E. 内置 PUT source_code 静默忽略", code == "200" and unchanged))

        # ===== F. DELETE 内置 → 403 =====
        if water_id:
            code, body = be_curl("DELETE", f"/api/admin/emergency-sources/{water_id}")
            print(f"\n[F] DELETE 内置 code={code} body={body[:120]}")
            results.append(("F. DELETE 内置 → 403", code == "403"))

        # ===== G. PATCH toggle 内置 → 403 =====
        if eb_id:
            code, body = be_curl("PATCH", f"/api/admin/emergency-sources/{eb_id}/toggle")
            print(f"\n[G] PATCH toggle 内置 code={code} body={body[:120]}")
            results.append(("G. PATCH toggle 内置 → 403", code == "403"))

        # ===== H. 自定义触发源全流程 =====
        # 先清理可能残留
        be_curl("DELETE", "/api/admin/emergency-sources/_nonexistent_")  # noop
        # 创建
        code, body = be_curl(
            "POST", "/api/admin/emergency-sources",
            json_body={
                "source_code": "verify_custom_v1",
                "source_name": "测试自定义触发源",
                "description": "自动化验证用",
                "is_enabled": True,
                "sort_order": 999,
            },
        )
        print(f"\n[H-create] code={code} body={body[:200]}")
        if code != "200":
            # 可能已存在，找出 id
            code2, body2 = be_curl("GET", "/api/admin/emergency-sources")
            items2 = json.loads(body2).get("items", [])
            ex = next((i for i in items2 if i["source_code"] == "verify_custom_v1"), None)
            new_id = ex["id"] if ex else None
        else:
            try:
                new_id = json.loads(body).get("id")
            except Exception:
                new_id = None

        h_create_pass = bool(new_id)
        results.append(("H1. 自定义触发源可创建", h_create_pass))

        if new_id:
            # 全字段编辑
            code, _ = be_curl(
                "PUT", f"/api/admin/emergency-sources/{new_id}",
                json_body={"source_name": "测试自定义改名", "is_enabled": False, "sort_order": 998},
            )
            results.append(("H2. 自定义全字段可改", code == "200"))
            # toggle
            code, body = be_curl("PATCH", f"/api/admin/emergency-sources/{new_id}/toggle")
            results.append(("H3. 自定义可 toggle", code == "200"))
            # delete
            code, body = be_curl("DELETE", f"/api/admin/emergency-sources/{new_id}")
            results.append(("H4. 自定义可删除", code == "200"))

        # ===== 汇总 =====
        print("\n========= 验证结果 =========")
        all_pass = True
        for label, ok in results:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {label}")
            if not ok:
                all_pass = False
        print(f"\n总结：{'全部通过' if all_pass else '存在失败项，需要修复'}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
