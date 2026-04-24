"""v1.0 商品功能优化 - 全量链接可达性验证"""
import urllib.request
import urllib.error
import json
import sys

BASE = 'https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27'

URLS = [
    # 用户端 H5
    (f'{BASE}/', 'H5 首页'),
    (f'{BASE}/services', 'H5 服务列表页'),
    (f'{BASE}/home', 'H5 主页'),
    # 管理后台
    (f'{BASE}/admin/', '管理后台根'),
    (f'{BASE}/admin/login', '管理后台登录'),
    # API
    (f'{BASE}/api/products/categories', '商品分类 API'),
    (f'{BASE}/api/products?page=1&page_size=10', '商品列表 API'),
    (f'{BASE}/api/products/hot-recommendations?limit=6', '热门推荐 API'),
]


def check(url, name):
    try:
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'product-optim-v1-verifier')
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(4096)
            status = resp.status
            ctype = resp.headers.get('Content-Type', '')
            short = body[:200].decode('utf-8', errors='replace').replace('\n', ' ')
            print(f'  [{status}] {name}: OK  (ctype={ctype[:40]})  body={short[:120]}')
            return status < 400
    except urllib.error.HTTPError as e:
        body = e.read(200).decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
        print(f'  [HTTP {e.code}] {name}: {e.reason}  body={body}')
        return False
    except Exception as e:  # noqa: BLE001
        print(f'  [ERR] {name}: {e}')
        return False


def main() -> int:
    print(f'\n=== 验证基础 URL: {BASE} ===\n')
    ok_count = 0
    fail = []
    for url, name in URLS:
        if check(url, name):
            ok_count += 1
        else:
            fail.append((url, name))

    # 专项校验：热门推荐 API 返回是否含 marketing_badges 字段
    print('\n=== 专项：热门推荐 API 字段校验 ===')
    try:
        with urllib.request.urlopen(f'{BASE}/api/products/hot-recommendations?limit=3', timeout=20) as resp:
            payload = json.loads(resp.read())
        items = payload.get('items') or []
        if items:
            sample = items[0]
            has_badges = 'marketing_badges' in sample
            has_valid = 'valid_start_date' in sample or 'valid_end_date' in sample
            print(f'  样本字段：marketing_badges={has_badges}  valid_*_date={has_valid}')
            if not has_badges:
                print('  [WARN] 响应未包含 marketing_badges 字段')
            if has_valid:
                print('  [FAIL] 响应仍包含 valid_*_date 字段（应已移除）')
                fail.append(('/api/products/hot-recommendations', 'schema 未清理'))
        else:
            print('  [INFO] 暂无推荐商品，跳过字段校验')
    except Exception as e:  # noqa: BLE001
        print(f'  [ERR] 专项校验失败：{e}')

    print(f'\n通过：{ok_count}/{len(URLS)}，失败：{len(fail)}')
    for u, n in fail:
        print(f'  - {n}: {u}')
    return 0 if not fail else 1


if __name__ == '__main__':
    sys.exit(main())
