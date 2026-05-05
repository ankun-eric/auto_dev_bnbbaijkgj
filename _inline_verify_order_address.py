"""[订单详情页订单地址展示统一 Bug 修复 v1.0] 服务器侧字段在线验证。

不依赖账号；直接 SSH 到服务器 backend 容器内，用 sqlalchemy + asyncio
   query 真实订单 → 走 _build_order_response → 校验 order_address / order_address_type
   按订单类型符合 PRD 期望。
"""
import sys
import time
import paramiko

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PASSWORD = 'Newbang888'
PROJECT_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
PROJECT_DIR = f'/home/ubuntu/{PROJECT_ID}'
BACKEND_CONTAINER = f'{PROJECT_ID}-backend'

INLINE = r"""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import async_session as AsyncSessionLocal
from app.models.models import UnifiedOrder, OrderItem
from app.api.unified_orders import _build_order_response

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(UnifiedOrder)
            .options(
                selectinload(UnifiedOrder.items).selectinload(OrderItem.product),
                selectinload(UnifiedOrder.store),
                selectinload(UnifiedOrder.shipping_address),
            )
            .order_by(UnifiedOrder.created_at.desc())
            .limit(40)
        )
        orders = res.scalars().all()
        print(f'sample_size={len(orders)}')
        type_count = {'store': 0, 'delivery': 0, 'onsite_service': 0, None: 0}
        errs = []
        for o in orders:
            resp = _build_order_response(o)
            t = resp.order_address_type
            type_count[t] = type_count.get(t, 0) + 1
            ft_set = {(it.fulfillment_type.value if hasattr(it.fulfillment_type, 'value') else str(it.fulfillment_type)) for it in (o.items or [])}
            if t == 'store':
                if resp.order_address is not None:
                    errs.append(f'order#{o.id} type=store but order_address!=None')
            elif t == 'delivery':
                # 期望 order_address 含 contact_name/phone/address_text；可能为空时也允许 None
                if resp.order_address is not None:
                    for k in ('address_text', 'contact_name', 'contact_phone'):
                        if k not in resp.order_address:
                            errs.append(f'order#{o.id} delivery missing {k}')
            elif t == 'onsite_service':
                if resp.order_address is not None:
                    for k in ('address_text', 'contact_name', 'contact_phone'):
                        if k not in resp.order_address:
                            errs.append(f'order#{o.id} onsite missing {k}')
            # 一致性：in_store-only 订单 type 应该 = store
            if ft_set == {'in_store'} and t and t != 'store':
                errs.append(f'order#{o.id} fulfillment={ft_set} but type={t}')
            print(f'  - id={o.id} no={o.order_no} ft={ft_set} order_address_type={t} '
                  f'has_addr={bool(resp.order_address)} store_phone={resp.store_phone!r}')
        print('type_distribution=', type_count)
        if errs:
            print('FAIL:', len(errs))
            for e in errs[:20]:
                print('  *', e)
            raise SystemExit(2)
        print('PASS: order_address fields valid for all sampled orders')

asyncio.run(main())
"""

def get_ssh():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return ssh


def run(ssh, cmd, *, timeout=300, ignore_error=False):
    print(f"\n>>> {cmd}", flush=True)
    chan = ssh.get_transport().open_session()
    chan.settimeout(timeout)
    chan.exec_command(cmd)
    out_chunks = []
    while True:
        if chan.recv_ready():
            data = chan.recv(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.recv_stderr_ready():
            data = chan.recv_stderr(8192).decode('utf-8', errors='replace')
            sys.stdout.write(data); sys.stdout.flush()
            out_chunks.append(data)
        if chan.exit_status_ready() and not chan.recv_ready() and not chan.recv_stderr_ready():
            break
        time.sleep(0.05)
    code = chan.recv_exit_status()
    print(f"\n[exit={code}]", flush=True)
    return code, ''.join(out_chunks)


def main():
    ssh = get_ssh()
    try:
        # 把脚本放到 backend 容器里
        # 用 base64 避免 shell 转义问题
        import base64
        b64 = base64.b64encode(INLINE.encode('utf-8')).decode('ascii')
        run(ssh,
            f'docker exec {BACKEND_CONTAINER} sh -c '
            f'"echo {b64} | base64 -d > /tmp/_inline_verify.py"')
        # 执行（PYTHONPATH=/app 让 import app.xxx 生效）
        code, _ = run(ssh,
            f'docker exec -e PYTHONPATH=/app {BACKEND_CONTAINER} sh -c '
            f'"cd /app && python /tmp/_inline_verify.py"',
            timeout=120)
        sys.exit(code)
    finally:
        ssh.close()


if __name__ == '__main__':
    main()
