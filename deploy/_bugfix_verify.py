"""从本地 Windows 验证关键链接的可达性与重定向链。"""
import json
import sys
import urllib.request
import urllib.error

BASE = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27"

URLS = [
    ("C 端首页", f"{BASE}/"),
    ("C 端登录页", f"{BASE}/login/"),
    ("商家 PC 版登录页", f"{BASE}/merchant/login/"),
    ("商家 H5 移动版登录页 [核心]", f"{BASE}/merchant/m/login/"),
    ("后端健康检查", f"{BASE}/api/health"),
    ("admin 登录页", f"{BASE}/admin/login/"),
]

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def trace(url: str, ua: str = None, max_hops: int = 10):
    """手工追踪重定向链，返回 list[(status, url)] 以及最终 body。"""
    chain = []
    current = url
    last_body = b""
    last_headers = {}
    for hop in range(max_hops):
        req = urllib.request.Request(current, method="GET")
        if ua:
            req.add_header("User-Agent", ua)
        else:
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0)")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None  # 禁用自动重定向

        opener = urllib.request.build_opener(NoRedirect)
        try:
            resp = opener.open(req, timeout=15)
            status = resp.status
            headers = dict(resp.headers)
            body = resp.read()
            chain.append((status, current, headers.get("Location", "")))
            last_body = body
            last_headers = headers
            if status < 300 or status >= 400:
                break
            loc = headers.get("Location", "")
            if not loc:
                break
            # 解析为绝对 URL
            current = urllib.parse.urljoin(current, loc)
            # 检测循环
            if any(current == prev_url for _, prev_url, _ in chain[:-1]):
                chain.append(("LOOP", current, ""))
                break
        except urllib.error.HTTPError as e:
            chain.append((e.code, current, e.headers.get("Location", "")))
            try:
                last_body = e.read()
            except Exception:
                last_body = b""
            break
        except Exception as e:
            chain.append((f"ERR:{e}", current, ""))
            break
    return chain, last_body


def main():
    import urllib.parse
    results = []
    print("=" * 80)
    print("外部链接可达性验证（默认桌面 UA）")
    print("=" * 80)
    for name, url in URLS:
        chain, body = trace(url)
        final_status, final_url, _ = chain[-1]
        ok = isinstance(final_status, int) and 200 <= final_status < 400
        # 循环？
        loop = any(s == "LOOP" for s, _, _ in chain)
        print(f"\n[{name}] {url}")
        for i, (st, u, loc) in enumerate(chain):
            print(f"  hop{i}: {st}  {u}" + (f"  -> {loc}" if loc else ""))
        print(f"  最终: {final_status}  hops={len(chain)}  loop={loop}")
        results.append({
            "name": name, "url": url,
            "chain": [{"status": str(s), "url": u, "location": l} for s, u, l in chain],
            "final_status": str(final_status), "hops": len(chain),
            "loop": loop, "ok": ok and not loop,
        })

    # 移动 UA 下的核心路径复测
    print("\n" + "=" * 80)
    print("核心路径：移动 UA 下 /merchant/m/login/ 验证")
    print("=" * 80)
    core_url = f"{BASE}/merchant/m/login/"
    chain, body = trace(core_url, ua=MOBILE_UA)
    body_str = body.decode("utf-8", errors="replace") if body else ""
    has_merchant_kw = any(kw in body_str for kw in ["商家", "merchant", "手机号", "登录"])
    print(f"\n[核心/移动UA] {core_url}")
    for i, (st, u, loc) in enumerate(chain):
        print(f"  hop{i}: {st}  {u}" + (f"  -> {loc}" if loc else ""))
    final_status, final_url, _ = chain[-1]
    is_200 = final_status == 200
    # 是否停留在 /merchant/m/login/
    stays_on_m_login = "/merchant/m/login" in final_url
    redirected_to_c = "/login/" in final_url and "/merchant/" not in final_url
    redirected_to_pc = final_url.endswith("/merchant/login/") or final_url.endswith("/merchant/login")
    print(f"\n  最终状态码: {final_status}")
    print(f"  最终 URL: {final_url}")
    print(f"  停留在 /merchant/m/login: {stays_on_m_login}")
    print(f"  被跳到 C 端 /login: {redirected_to_c}")
    print(f"  被跳到 PC 商家 /merchant/login: {redirected_to_pc}")
    print(f"  响应包含商家登录关键词: {has_merchant_kw}")
    print(f"  body length: {len(body_str)}")

    core_ok = is_200 and stays_on_m_login and not redirected_to_c and not redirected_to_pc and has_merchant_kw

    # 汇总
    print("\n" + "=" * 80)
    print("汇总")
    print("=" * 80)
    print(f"{'NAME':<40}{'STATUS':<10}{'HOPS':<6}{'LOOP':<6}{'OK'}")
    for r in results:
        print(f"{r['name']:<40}{r['final_status']:<10}{r['hops']:<6}{str(r['loop']):<6}{r['ok']}")
    print(f"\n核心移动 UA 验证: {'PASS' if core_ok else 'FAIL'}")

    out = {
        "results": results,
        "core_mobile_m_login": {
            "url": core_url,
            "chain": [{"status": str(s), "url": u, "location": l} for s, u, l in chain],
            "final_status": str(final_status),
            "final_url": final_url,
            "stays_on_m_login": stays_on_m_login,
            "redirected_to_c": redirected_to_c,
            "redirected_to_pc": redirected_to_pc,
            "has_merchant_kw": has_merchant_kw,
            "body_len": len(body_str),
            "ok": core_ok,
        },
    }
    with open("deploy/_bugfix_verify_result.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n结果已写入 deploy/_bugfix_verify_result.json")

    # 整体
    all_ok = all(r["ok"] for r in results) and core_ok
    print(f"\n整体结论: {'全部可达 & 核心验证通过' if all_ok else '存在不可达或核心失败（详见上文）'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
