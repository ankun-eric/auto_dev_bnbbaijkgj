"""Add a `/autodev/{DEPLOY_ID}/static/downloads/` alias location into the
project's gateway nginx conf on the host and reload nginx.

Idempotent: if the location already exists, skip.
"""
import base64
import paramiko
import time

HOST = 'newbb.test.bangbangvip.com'
USER = 'ubuntu'
PWD = 'Newbang888'
DEPLOY_ID = '6b099ed3-7175-4a78-91f4-44570c84ed27'
HOST_CONF = f'/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf'
GATEWAY_CONTAINER = 'gateway'


def run(client, cmd, check=True):
    print(f'$ {cmd}')
    i, o, e = client.exec_command(cmd)
    out = o.read().decode('utf-8', 'ignore')
    err = e.read().decode('utf-8', 'ignore')
    rc = o.channel.recv_exit_status()
    if out:
        print(out)
    if err.strip():
        print('STDERR:', err)
    print(f'[exit {rc}]')
    if check and rc != 0:
        raise SystemExit(f'Command failed (rc={rc}): {cmd}')
    return rc, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=15)

    _, conf, _ = run(c, f'cat {HOST_CONF}')

    marker = f'/autodev/{DEPLOY_ID}/static/downloads/'
    if marker in conf:
        print('[skip] static/downloads location already present')
        c.close()
        return

    new_block = f"""

# Preserved: /autodev/{DEPLOY_ID}/static/downloads/ (alias to same files)
location /autodev/{DEPLOY_ID}/static/downloads/ {{
    alias /data/static/downloads/;
    autoindex off;
    add_header Content-Disposition "attachment";
    types {{
        application/zip zip;
        application/octet-stream apk;
    }}
}}
"""
    new_conf = conf.rstrip() + new_block + '\n'

    ts = time.strftime('%Y%m%d%H%M%S')
    run(c, f'cp {HOST_CONF} {HOST_CONF}.bak.staticdl.{ts}')

    b64 = base64.b64encode(new_conf.encode('utf-8')).decode('ascii')
    run(c, f"echo {b64} | base64 -d > {HOST_CONF}")

    run(c, f'docker exec {GATEWAY_CONTAINER} nginx -t')
    run(c, f'docker exec {GATEWAY_CONTAINER} nginx -s reload')

    print('[OK] static/downloads alias added and nginx reloaded')
    c.close()


if __name__ == '__main__':
    main()
