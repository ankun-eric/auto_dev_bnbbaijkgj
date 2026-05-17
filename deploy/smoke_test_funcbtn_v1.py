"""[PRD-AICHAT-FUNCBTN-OPTIM-V1] 部署后冒烟测试 - 检查关键链接 + 后端 API"""
import urllib.request
import urllib.error
import json
import ssl

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    ("admin/function-buttons页面", BASE + "/admin/function-buttons"),
    ("admin登录页", BASE + "/admin/login"),
    ("h5 ai-home页面", BASE + "/ai-home"),
    ("h5 首页", BASE + "/"),
    ("公开按钮接口(grid)", BASE + "/api/function-buttons?position=grid"),
    ("公开按钮接口(capsule)", BASE + "/api/function-buttons?position=capsule"),
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def check(name, url):
    req = urllib.request.Request(url, headers={"User-Agent": "smoke/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            ok = 200 <= resp.status < 400
            sample = ""
            if "/api/" in url:
                try:
                    data = json.loads(body)
                    if isinstance(data, list):
                        sample = f" len={len(data)}"
                        if data:
                            keys = list(data[0].keys())
                            for k in ("grid_sort", "capsule_sort", "ai_function_type", "ai_opening", "pre_card_for_navigate"):
                                if k in keys:
                                    sample += f" hasField:{k}"
                except Exception:
                    pass
            print(f"[{'OK ' if ok else 'BAD'}] {resp.status} {name}: {url}{sample}")
            return ok
    except urllib.error.HTTPError as e:
        print(f"[BAD] {e.code} {name}: {url}")
        return False
    except Exception as e:
        print(f"[ERR] {name}: {url} -> {e}")
        return False


def main():
    print(f"=== Smoke test against {BASE} ===")
    fails = 0
    for n, u in URLS:
        if not check(n, u):
            fails += 1
    print(f"\n=== {len(URLS) - fails}/{len(URLS)} passed ===")


if __name__ == "__main__":
    main()
