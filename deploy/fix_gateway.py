"""Fix gateway conf: replace project routes from local gateway-routes.conf,
preserve any extra static location blocks (downloads/, apk/) found in the
current server conf.
"""
import os
import re
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
GATEWAY_CONF = f"/home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf"
LOCAL_CONF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gateway-routes.conf")


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    sftp = c.open_sftp()

    # Read current server conf
    with sftp.file(GATEWAY_CONF, "r") as f:
        current = f.read().decode("utf-8", "replace")
    print(f"Current conf size: {len(current)} bytes")

    # Read local new conf
    with open(LOCAL_CONF, "r", encoding="utf-8") as f:
        new_conf = f.read()
    print(f"New conf size: {len(new_conf)} bytes")

    # Extract preserved location blocks: any location whose path is not /api/, /uploads/, /admin/, /admin/_next/, /, /_next/
    # We use a balanced-brace scan
    def extract_locations(text):
        blocks = []
        i = 0
        while True:
            m = re.search(r"location\s+([^\s{]+)\s*\{", text[i:])
            if not m:
                break
            start = i + m.start()
            path = m.group(1)
            # find matching }
            depth = 0
            j = i + m.end() - 1  # at the '{'
            while j < len(text):
                ch = text[j]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = j + 1
                        blocks.append((path, text[start:end]))
                        i = end
                        break
                j += 1
            else:
                break
        return blocks

    standard_paths = {
        f"/autodev/{DEPLOY_ID}/api/",
        f"/autodev/{DEPLOY_ID}/uploads/",
        f"/autodev/{DEPLOY_ID}/admin/",
        f"/autodev/{DEPLOY_ID}/admin/_next/",
        f"/autodev/{DEPLOY_ID}/",
        f"/autodev/{DEPLOY_ID}/_next/",
        f"= /autodev/{DEPLOY_ID}",
    }

    extras = []
    for path, block in extract_locations(current):
        if path in standard_paths:
            continue
        # exclude exact-match basepath redirect placeholders
        print(f"  preserving extra location: {path}")
        extras.append(block)

    # Compose final
    final = new_conf.rstrip() + "\n"
    if extras:
        final += "\n# ===== Preserved static locations =====\n"
        for b in extras:
            final += b + "\n\n"

    # Backup current
    backup = f"{GATEWAY_CONF}.bak.fix"
    with sftp.file(backup, "w") as f:
        f.write(current.encode("utf-8"))
    print(f"Backed up current to {backup}")

    # Write new
    with sftp.file(GATEWAY_CONF, "w") as f:
        f.write(final.encode("utf-8"))
    print(f"Wrote {len(final)} bytes to {GATEWAY_CONF}")

    sftp.close()

    # nginx -t
    def run(cmd, timeout=60):
        print(f"$ {cmd}")
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", "replace")
        err = stderr.read().decode("utf-8", "replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out)
        if err:
            print(f"[stderr] {err}")
        print(f"[exit {code}]")
        return out, err, code

    out, err, code = run("docker exec gateway nginx -t 2>&1")
    if code != 0:
        print("nginx -t FAILED, restoring backup")
        run(f"cp {backup} {GATEWAY_CONF}")
        run("docker exec gateway nginx -t 2>&1")
        c.close()
        raise SystemExit(1)
    run("docker exec gateway nginx -s reload 2>&1")
    run("sleep 2")
    run(f"docker exec gateway nginx -T 2>/dev/null | grep -E 'ssl_certificate|listen.*443.*ssl' | sort -u")
    run("curl -sI https://newbb.test.bangbangvip.com/ 2>&1 | head -5")

    c.close()
    print("=== gateway fix done ===")


if __name__ == "__main__":
    main()
