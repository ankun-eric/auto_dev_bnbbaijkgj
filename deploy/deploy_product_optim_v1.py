"""商品功能优化 v1.0 部署脚本

变更范围：
- backend: models/schemas/api/services 的字段清理 + 新增 marketing_badges
- admin-web: 商品列表删除表单按钮、编辑弹窗移除日期字段、新增营销角标字段
- h5-web: 服务列表卡片重构、详情页头图角标、首页热门推荐（带角标）
- 新增公共组件 h5-web/src/components/MarketingBadge.tsx

部署策略：服务器 git pull 拉最新代码 -> 重启 backend -> rebuild h5-web/admin-web
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssh_helper import create_client, run_cmd  # type: ignore

DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
REMOTE_ROOT = f'/home/ubuntu/{DEPLOY_ID}'

C_BACKEND = f'{DEPLOY_ID}-backend'
C_H5 = f'{DEPLOY_ID}-h5'
C_ADMIN = f'{DEPLOY_ID}-admin'


def main() -> int:
    print('[deploy] connecting to server ...')
    ssh = create_client()
    try:
        # ---- 1. git pull on server ----
        print('\n[deploy] git pull on server ...')
        cmd = (
            f'cd {REMOTE_ROOT} && '
            f'git fetch --all 2>&1 | tail -20 && '
            f'git reset --hard origin/master 2>&1 | tail -10 && '
            f'git log -1 --oneline'
        )
        out, err, code = run_cmd(ssh, cmd, timeout=120)
        print(out)
        if err:
            print('STDERR:', err)
        if code != 0:
            print(f'[deploy] git pull exit code: {code}')
            return code

        # ---- 2. restart backend (schema_sync 会自动建列 + 清理日期列) ----
        print('\n[deploy] restart backend container ...')
        cmd = f'cd {REMOTE_ROOT} && docker compose restart backend 2>&1 | tail -20'
        out, err, code = run_cmd(ssh, cmd, timeout=180)
        print(out)
        if err:
            print('STDERR:', err)
        print('[deploy] sleep 15s for backend to apply schema_sync ...')
        time.sleep(15)

        # ---- 3. rebuild h5-web ----
        print('\n[deploy] rebuild h5-web container ...')
        cmd = f'cd {REMOTE_ROOT} && docker compose build h5-web 2>&1 | tail -40'
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if code != 0:
            print(f'[deploy] h5-web build exit code: {code}')
            return code
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps h5-web 2>&1 | tail -10',
            timeout=180,
        )
        print(out)

        # ---- 4. rebuild admin-web ----
        print('\n[deploy] rebuild admin-web container ...')
        cmd = f'cd {REMOTE_ROOT} && docker compose build admin-web 2>&1 | tail -40'
        out, err, code = run_cmd(ssh, cmd, timeout=1800)
        print(out)
        if code != 0:
            print(f'[deploy] admin-web build exit code: {code}')
            return code
        out, err, code = run_cmd(
            ssh,
            f'cd {REMOTE_ROOT} && docker compose up -d --no-deps admin-web 2>&1 | tail -10',
            timeout=180,
        )
        print(out)

        # ---- 5. wait & status ----
        print('\n[deploy] sleep 20s then check containers ...')
        time.sleep(20)
        out, _, _ = run_cmd(
            ssh,
            f'docker ps --filter name={DEPLOY_ID}- --format "{{{{.Names}}}}\\t{{{{.Status}}}}"',
            timeout=60,
        )
        print(out)

        # ---- 6. verify DB schema ----
        print('\n[deploy] verify products table columns ...')
        out, _, _ = run_cmd(
            ssh,
            f'docker exec {DEPLOY_ID}-db mysql -uroot -pbini_health_2026 bini_health '
            f'-e "SHOW COLUMNS FROM products LIKE \'%_date\'; SHOW COLUMNS FROM products LIKE \'marketing_badges\';" 2>&1 | tail -20',
            timeout=30,
        )
        print(out)

        # ---- 7. backend errors ----
        print('\n[deploy] backend recent errors ...')
        out, _, _ = run_cmd(
            ssh,
            f'docker logs --tail 100 {C_BACKEND} 2>&1 | grep -E "ERROR|Traceback|Exception" | tail -20 || true',
            timeout=30,
        )
        print(out or '(no errors found)')
        return 0
    finally:
        ssh.close()


if __name__ == '__main__':
    sys.exit(main())
