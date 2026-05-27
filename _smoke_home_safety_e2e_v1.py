"""[BUGFIX] E2E HTTP 冒烟：注册→登录→绑定→列设备→断言 bound_at 以 Z 结尾"""
import json
import random
import string
import sys
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"


def _req(method: str, path: str, body=None, token: str | None = None):
    url = BASE + path
    data = None
    headers = {"Content-Type": "application/json", "X-Client-Type": "h5-user"}
    if body is not None:
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8", errors="replace")
            return r.status, txt
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", errors="replace")
        return e.code, body_txt


def main():
    rand = "".join(random.choices(string.digits, k=8))
    phone = "138" + rand
    nickname = "ZSmoke" + rand[:4]
    # register
    s, _ = _req("POST", "/api/auth/register", {"phone": phone, "password": "pw123456", "nickname": nickname})
    assert s in (200, 201, 409), f"register failed: {s}"
    s, t = _req("POST", "/api/auth/login", {"phone": phone, "password": "pw123456"})
    assert s == 200, f"login failed: {s} {t}"
    token = json.loads(t)["access_token"]
    print(f"[OK] login phone={phone}")

    # bind
    dev_sn = "Z" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
    gw_sn = "GWZ" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))
    s, t = _req(
        "POST",
        "/api/home_safety/devices/bind",
        {"device_type": 1, "gateway_sn": gw_sn, "device_sn": dev_sn},
        token=token,
    )
    assert s == 200, f"bind failed: {s} {t}"
    print(f"[OK] bind dev_sn={dev_sn}")

    # list
    s, t = _req("GET", "/api/home_safety/devices", token=token)
    assert s == 200, f"list failed: {s} {t}"
    j = json.loads(t)
    print(f"[DEBUG] response top-level keys: {list(j.keys())}")
    em = next(g for g in j["groups"] if g["device_type"] == 1)
    print(f"[DEBUG] emergency group count={em['count']}, first item bound_at={em['items'][0]['bound_at'] if em['items'] else None}")
    target = next((it for it in em["items"] if it["device_sn"] == dev_sn), None)
    assert target is not None, f"未找到绑定记录 {dev_sn}"
    assert target["bound_at"].endswith("Z"), f"bound_at 应带 Z 后缀: {target['bound_at']}"
    print(f"[OK] bound_at 带 Z: {target['bound_at']}")

    print("\n=== E2E 冒烟全部通过 ===")


if __name__ == "__main__":
    main()
