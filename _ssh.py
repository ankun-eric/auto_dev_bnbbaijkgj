import paramiko, sys, os, time

def get_pwd(a):
    if a.startswith('@'):
        try:
            with open(a[1:],encoding='utf-8') as f:
                for l in f:
                    l=l.strip()
                    if 'SSH_PASS=' in l: return l.split('=',1)[1].strip().strip('"').strip("'")
                    if 'SSH密码=' in l: return l.split('=',1)[1].strip().strip('"').strip("'")
        except: pass
    e = os.environ.get('SSH_PASS', '')
    return e if e else a

def conn(h, p, u, pw):
    for i in range(3):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(h, p, u, pw, timeout=30)
            return c
        except Exception as ex:
            if i == 2: raise
            time.sleep(3)

def do_exec(c, cmd, to):
    _, o, e = c.exec_command(cmd, timeout=to)
    out = o.read().decode('utf-8', 'replace')
    err = e.read().decode('utf-8', 'replace')
    return out, err, o.channel.recv_exit_status()

if __name__ == '__main__':
    if len(sys.argv) < 6:
        print('Usage: python _ssh.py exec|sftp|upload <host> <port> <user> <pwd|@file> <cmd|script|local> [timeout|remote_path]')
        sys.exit(1)
    mode = sys.argv[1]
    h = sys.argv[2]
    p = int(sys.argv[3])
    u = sys.argv[4]
    pw = get_pwd(sys.argv[5])

    if mode == 'exec':
        cmd = sys.argv[6]
        to = int(sys.argv[7]) if len(sys.argv) > 7 else 120
        c = conn(h, p, u, pw)
        out, err, ec = do_exec(c, cmd, to)
        c.close()
        if out: print(out)
        if err: print(err, file=sys.stderr)
        sys.exit(ec)

    elif mode == 'sftp':
        script = sys.argv[6]
        to = int(sys.argv[7]) if len(sys.argv) > 7 else 300
        c = conn(h, p, u, pw)
        rp = f'/tmp/_s_{os.path.basename(script)}'
        s = c.open_sftp()
        s.put(script, rp)
        s.chmod(rp, 0o755)
        s.close()
        ext = os.path.splitext(script)[1]
        runner = 'python3' if ext == '.py' else 'bash'
        out, err, ec = do_exec(c, f'{runner} {rp}; rm -f {rp}', to)
        c.close()
        if out: print(out)
        if err: print(err, file=sys.stderr)
        sys.exit(ec)

    elif mode == 'upload':
        local = sys.argv[6]
        remote = sys.argv[7]
        c = conn(h, p, u, pw)
        s = c.open_sftp()
        rd = os.path.dirname(remote)
        if rd:
            try: s.stat(rd)
            except: s.mkdir(rd)
        s.put(local, remote)
        s.close()
        c.close()
        print(f'OK: {local} -> {remote}')
