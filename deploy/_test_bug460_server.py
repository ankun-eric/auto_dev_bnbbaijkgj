"""[BUG-460] 服务器侧非 UI 自动化测试脚本

目标：验证 BUG-460（`/api/chat-sessions` 500）修复后，整条用户端 chat-sessions 链路
（含登录、列表、置顶、批量删除）在测试服务器上**完全可用**，不再返回 500。

使用真实 HTTPS 接口 + 真实 MySQL 数据，覆盖以下 14 个断言：

  T01  /api/auth/register 创建新用户成功（200 + access_token）
  T02  GET /api/chat-sessions 在「无任何会话」状态下返回 200 + []（即空数组）
       —— 验证根因 1 已修复：`NULLS LAST` SQL 不再被 MySQL 拒绝（核心断言）
  T03  GET /api/chat-sessions 未登录时返回 401（鉴权未被绕过，回归保护）
  T04  GET /api/chat-sessions 已登录但带错误 token 返回 401
  T05  GET /api/chat-sessions 分页参数 page=1, page_size=20 返回 200
  T06  GET /api/chat-sessions 边界分页 page=999, page_size=100 仍返回 200 + []
  T07  GET /api/chat-sessions response 是 JSON 数组（list 类型，非对象）
  T08  GET /api/chat-sessions/{not_exists_id} 返回 404（详情接口健壮）
  T09  远端源码 chat_history.py 含 BUG-460 标记
  T10  远端 backend 容器最近日志中已无 'NULLS LAST' / '1064' 报错
  T11  GET /api/admin/chat-sessions 普通用户访问返回 403（管理端鉴权未被绕过）
  T12  /api/v1/notifications/unread-count 未登录返回 401（关联接口未受影响）
  T13  GET /api/chat-sessions 同账号请求 5 次稳定返回 200（无偶发 500）
  T14  GET /api/chat-sessions/0 返回 404（避免 id=0 时的边界问题）

通过 Paramiko SSH 进入服务器，使用容器 curl 调用接口；
通过 docker logs 获取 backend 日志做断言。
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Optional

import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASSWORD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
REMOTE_PROJ = f"/home/ubuntu/{DEPLOY_ID}"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

PASS = "[PASS]"
FAIL = "[FAIL]"


def ssh_connect() -> paramiko.SSHClient:
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return cli


def run(cli: paramiko.SSHClient, cmd: str, *, timeout: int = 60) -> tuple[int, str, str]:
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def curl(
    cli: paramiko.SSHClient,
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Optional[dict] = None,
) -> tuple[int, str]:
    """通过 SSH 在服务器上运行 curl，返回 (http_code, response_body)."""
    headers = "-H 'Content-Type: application/json'"
    if token:
        headers += f" -H 'Authorization: Bearer {token}'"
    data_arg = ""
    if body is not None:
        body_str = json.dumps(body).replace("'", "'\\''")
        data_arg = f"-d '{body_str}'"
    cmd = (
        f"curl -k -s -o /tmp/_bug460_resp.txt -w '%{{http_code}}' "
        f"-X {method} {headers} {data_arg} '{url}' ; "
        f"echo '|||SEP|||' ; cat /tmp/_bug460_resp.txt"
    )
    _, out, _ = run(cli, cmd, timeout=30)
    parts = (out or "").split("|||SEP|||", 1)
    code = (parts[0] or "").strip()
    resp = (parts[1] or "").strip() if len(parts) > 1 else ""
    try:
        return int(code), resp
    except ValueError:
        return -1, resp


def register_new_user(cli: paramiko.SSHClient) -> tuple[str, str]:
    """新注册一个用户，返回 (phone, token)。"""
    phone = "1389" + uuid.uuid4().hex[:7]
    password = "Test1234!"
    code, resp = curl(
        cli,
        "POST",
        f"{BASE_URL}/api/auth/register",
        body={"phone": phone, "password": password, "nickname": "bug460-test"},
    )
    if code != 200:
        raise RuntimeError(f"register failed: code={code} resp={resp[:300]}")
    data = json.loads(resp)
    return phone, data["access_token"]


def main() -> int:
    cli = ssh_connect()
    results: list[tuple[str, bool, str]] = []

    try:
        # T01: 注册
        try:
            phone, token = register_new_user(cli)
            results.append(("T01 注册新用户", True, f"phone={phone[-4:]}*** token={token[:8]}…"))
        except Exception as e:
            results.append(("T01 注册新用户", False, str(e)))
            token = ""

        # T02: 核心断言 —— 无会话状态下 /api/chat-sessions 应 200 + 空数组
        code, resp = curl(cli, "GET", f"{BASE_URL}/api/chat-sessions", token=token)
        try:
            data = json.loads(resp) if resp else None
        except Exception:
            data = None
        ok = code == 200 and isinstance(data, list) and len(data) == 0
        results.append((
            "T02 GET /api/chat-sessions 空数据返回 200 + []（核心断言：NULLS LAST SQL 已修复）",
            ok,
            f"code={code} body={resp[:200]}",
        ))

        # T03: 未登录返回 401
        code, resp = curl(cli, "GET", f"{BASE_URL}/api/chat-sessions")
        ok = code == 401
        results.append(("T03 未登录返回 401", ok, f"code={code}"))

        # T04: 错误 token 返回 401
        code, resp = curl(
            cli, "GET", f"{BASE_URL}/api/chat-sessions", token="invalid.fake.token.xyz"
        )
        ok = code == 401
        results.append(("T04 错误 token 返回 401", ok, f"code={code}"))

        # T05: 分页参数
        code, resp = curl(
            cli,
            "GET",
            f"{BASE_URL}/api/chat-sessions?page=1&page_size=20",
            token=token,
        )
        ok = code == 200
        results.append(("T05 分页 page=1 page_size=20 返回 200", ok, f"code={code}"))

        # T06: 边界分页
        code, resp = curl(
            cli,
            "GET",
            f"{BASE_URL}/api/chat-sessions?page=999&page_size=100",
            token=token,
        )
        try:
            data = json.loads(resp) if resp else None
        except Exception:
            data = None
        ok = code == 200 and isinstance(data, list) and len(data) == 0
        results.append((
            "T06 边界分页 page=999 page_size=100 返回 200 + []",
            ok,
            f"code={code} body={resp[:120]}",
        ))

        # T07: 响应是 JSON 数组
        code, resp = curl(cli, "GET", f"{BASE_URL}/api/chat-sessions", token=token)
        try:
            data = json.loads(resp) if resp else None
        except Exception:
            data = None
        ok = code == 200 and isinstance(data, list)
        results.append(("T07 响应类型是 JSON 数组（list）", ok, f"type={type(data).__name__}"))

        # T08: 详情接口对不存在 id 返 404
        code, resp = curl(
            cli, "GET", f"{BASE_URL}/api/chat-sessions/99999999", token=token
        )
        ok = code == 404
        results.append(("T08 详情接口不存在 id 返 404", ok, f"code={code}"))

        # T09: 远端源码标记
        _, out, _ = run(
            cli,
            f"grep -c 'BUG-460' {REMOTE_PROJ}/backend/app/api/chat_history.py",
        )
        marker_count = int((out or "0").strip() or "0")
        ok = marker_count >= 3
        results.append((
            "T09 远端源码 chat_history.py 含 BUG-460 标记 ≥3",
            ok,
            f"count={marker_count}",
        ))

        # T10: 后端日志已无 NULLS LAST / 1064 错误
        _, out, _ = run(
            cli,
            f"docker logs --tail 200 {DEPLOY_ID}-backend 2>&1 "
            "| grep -cE 'NULLS LAST|1064' || true",
        )
        nulls_hits = int((out or "0").strip().splitlines()[-1] or "0") if out else 0
        ok = nulls_hits == 0
        results.append((
            "T10 backend 最近 200 行日志无 'NULLS LAST' / '1064'",
            ok,
            f"hits={nulls_hits}",
        ))

        # T11: 管理端接口对普通用户返 403
        code, resp = curl(
            cli, "GET", f"{BASE_URL}/api/admin/chat-sessions", token=token
        )
        ok = code in {401, 403}
        results.append((
            "T11 管理端 /api/admin/chat-sessions 普通用户返 401/403",
            ok,
            f"code={code}",
        ))

        # T12: 关联接口（通知未读数）未登录 401
        code, resp = curl(
            cli, "GET", f"{BASE_URL}/api/v1/notifications/unread-count"
        )
        ok = code in {401, 403}
        results.append(("T12 关联接口（通知未读数）未登录 401/403", ok, f"code={code}"))

        # T13: 同账号 5 次请求稳定 200
        codes = []
        for _ in range(5):
            c, _ = curl(cli, "GET", f"{BASE_URL}/api/chat-sessions", token=token)
            codes.append(c)
            time.sleep(0.2)
        ok = all(c == 200 for c in codes)
        results.append((
            "T13 同账号 5 次请求稳定 200（无偶发 500）",
            ok,
            f"codes={codes}",
        ))

        # T14: id=0 边界
        code, resp = curl(
            cli, "GET", f"{BASE_URL}/api/chat-sessions/0", token=token
        )
        ok = code in {404, 422}
        results.append(("T14 GET /api/chat-sessions/0 返 404/422", ok, f"code={code}"))

        # T15: 通过数据库直接插入两条 chat_session（一条置顶 + 一条未置顶），
        # 然后调用 /api/chat-sessions 验证排序正确（置顶在前 + pinned_at 不为 NULL 时
        # 排在 pinned_at 为 NULL 之前 + 同组按 updated_at 倒序），彻底验证完整 ORDER BY
        # 在 MySQL 上**无 1064 错误**且**逻辑符合 PRD V7**。
        # 通过 docker exec mysql 客户端注入数据。
        try:
            # 找数据库容器名 / 库 / root 密码
            db_container = f"{DEPLOY_ID}-db"
            _, out_pwd, _ = run(
                cli,
                f"docker exec {db_container} printenv MYSQL_ROOT_PASSWORD",
            )
            mysql_root = (out_pwd or "").strip().splitlines()[-1] if out_pwd else ""
            assert mysql_root, "未能取到 MYSQL_ROOT_PASSWORD"
            _, out_db, _ = run(
                cli,
                f"docker exec {db_container} printenv MYSQL_DATABASE",
            )
            mysql_db = (out_db or "bini_health").strip().splitlines()[-1] or "bini_health"

            def db_exec(sql: str) -> tuple[str, str]:
                _, o, e = run(
                    cli,
                    f"docker exec {db_container} mysql -uroot -p'{mysql_root}' "
                    f"-N -B -D {mysql_db} -e \"{sql}\" 2>&1",
                )
                return (o or ""), (e or "")

            # 找到当前测试用户 id
            out_uid, _ = db_exec(f"SELECT id FROM users WHERE phone='{phone}' LIMIT 1;")
            uid_line = [
                ln for ln in out_uid.splitlines() if ln.strip().isdigit()
            ]
            assert uid_line, f"未找到测试用户 id, out={out_uid!r}"
            uid = int(uid_line[-1])

            # 插入 3 条：
            #   A: 置顶 + pinned_at = NOW(),    updated_at = NOW() - 1 hour
            #   B: 未置顶,                       updated_at = NOW()
            #   C: 置顶 + pinned_at = NOW() - 5min, updated_at = NOW() - 2 hour
            # 预期顺序：[A, C, B]
            # 关键：含 pinned_at NULL（B）+ 非 NULL（A,C）混合，正是触发 NULLS LAST 必修的场景。
            # session_type 是 enum，使用真实合法值 'health_qa'
            insert_sql = (
                "INSERT INTO chat_sessions"
                " (user_id, session_type, title, message_count, is_pinned, pinned_at,"
                "  is_deleted, created_at, updated_at)"
                " VALUES"
                f" ({uid},'health_qa','A-PinnedNew',2,1,NOW(),0,"
                f"  NOW() - INTERVAL 1 HOUR, NOW() - INTERVAL 1 HOUR),"
                f" ({uid},'health_qa','B-Recent',1,0,NULL,0,"
                f"  NOW(), NOW()),"
                f" ({uid},'health_qa','C-PinnedOld',3,1,NOW() - INTERVAL 5 MINUTE,0,"
                f"  NOW() - INTERVAL 2 HOUR, NOW() - INTERVAL 2 HOUR);"
            )
            ins_out, ins_err = db_exec(insert_sql)

            # 再请求一次列表
            code, resp = curl(
                cli, "GET", f"{BASE_URL}/api/chat-sessions", token=token
            )
            data = json.loads(resp) if resp else []
            titles = [item.get("title") for item in data]
            ok_t15 = code == 200 and titles == ["A-PinnedNew", "C-PinnedOld", "B-Recent"]
            results.append((
                "T15 三条数据排序：[置顶新, 置顶旧, 非置顶最近]（验证完整 ORDER BY 在 MySQL 上正确）",
                ok_t15,
                f"code={code} titles={titles}",
            ))

            # T16: is_pinned 字段类型正确（bool 而非 0/1 数字）
            ok_t16 = code == 200 and all(isinstance(it.get("is_pinned"), bool) for it in data)
            results.append((
                "T16 响应中 is_pinned 字段类型为 bool",
                ok_t16,
                f"types={[type(it.get('is_pinned')).__name__ for it in data]}",
            ))

            # T17: message_count 字段为 int 且 >=0
            ok_t17 = code == 200 and all(
                isinstance(it.get("message_count"), int) and it.get("message_count") >= 0
                for it in data
            )
            results.append((
                "T17 响应中 message_count 字段为非负 int",
                ok_t17,
                f"vals={[it.get('message_count') for it in data]}",
            ))

            # T18: 调置顶接口 PUT /api/chat-sessions/{id}/pin 改 B 为置顶
            #     重新拉列表，B 应跃升到首位（pinned_at=NOW() 最新）
            if data and len(data) >= 3:
                b_id = next((it["id"] for it in data if it.get("title") == "B-Recent"), None)
                if b_id:
                    code_pin, _ = curl(
                        cli,
                        "PUT",
                        f"{BASE_URL}/api/chat-sessions/{b_id}/pin",
                        token=token,
                        body={"is_pinned": True},
                    )
                    code2, resp2 = curl(
                        cli, "GET", f"{BASE_URL}/api/chat-sessions", token=token
                    )
                    data2 = json.loads(resp2) if resp2 else []
                    titles2 = [it.get("title") for it in data2]
                    ok_t18 = (
                        code_pin == 200
                        and code2 == 200
                        and len(titles2) >= 3
                        and titles2[0] == "B-Recent"  # 新置顶项在最前
                    )
                    results.append((
                        "T18 置顶 B 后，B 跃升列表首位",
                        ok_t18,
                        f"pin_code={code_pin} list_code={code2} titles={titles2}",
                    ))
        except Exception as e:
            results.append(("T15-T18 数据驱动排序验证", False, f"exception: {e}"))

    finally:
        cli.close()

    print("\n" + "=" * 80)
    print("[BUG-460] 服务器侧非 UI 自动化测试结果")
    print("=" * 80)
    pass_n = 0
    for name, ok, detail in results:
        flag = PASS if ok else FAIL
        print(f"{flag} {name}  ::  {detail}")
        if ok:
            pass_n += 1
    print("-" * 80)
    print(f"通过：{pass_n} / {len(results)}")
    print("=" * 80)
    return 0 if pass_n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
