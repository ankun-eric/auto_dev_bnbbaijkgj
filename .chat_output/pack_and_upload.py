import os
import sys
import zipfile
import secrets
import datetime
import json
import io
import paramiko

PROJECT_ROOT = r"C:\auto_output\bnbbaijkgj"
MINI_DIR = os.path.join(PROJECT_ROOT, "miniprogram")
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PWD = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
BASE_URL = f"https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}"

EXCLUDE_DIRS = {"node_modules", ".git", "dist", "unpackage", "__pycache__", ".DS_Store"}
EXCLUDE_EXT = {".log", ".tmp", ".swp"}


def make_zip():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    rand = secrets.token_hex(2)
    fname = f"miniprogram_book_after_pay_{ts}_{rand}.zip"
    out_path = os.path.join(PROJECT_ROOT, fname)
    count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(MINI_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fn in files:
                if fn in EXCLUDE_DIRS:
                    continue
                ext = os.path.splitext(fn)[1].lower()
                if ext in EXCLUDE_EXT:
                    continue
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, MINI_DIR).replace("\\", "/")
                try:
                    zf.write(full, arc)
                    count += 1
                except Exception as e:
                    print(f"skip {full}: {e}", file=sys.stderr)
    size = os.path.getsize(out_path)
    print(f"zipped {count} files, size={size}, path={out_path}", file=sys.stderr)
    return fname, out_path, size


def ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def main():
    fname, local_path, size = make_zip()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PWD, timeout=30, allow_agent=False, look_for_keys=False)

    # Inspect nginx config to find static path
    rc, out, err = ssh_exec(client, f"cat /home/ubuntu/gateway/conf.d/{DEPLOY_ID}.conf 2>/dev/null || true")
    print("nginx conf:\n" + out, file=sys.stderr)

    # Try to find existing zip files & their location to mirror placement
    rc2, out2, _ = ssh_exec(
        client,
        f"ls -la /home/ubuntu/{DEPLOY_ID}/ 2>/dev/null | head -30; echo '---'; "
        f"find /home/ubuntu/{DEPLOY_ID} -maxdepth 3 -name '*.zip' 2>/dev/null | head -20; echo '---'; "
        f"find /home/ubuntu/gateway -maxdepth 4 -name '*.zip' 2>/dev/null | head -20"
    )
    print("existing zip search:\n" + out2, file=sys.stderr)

    # Determine target dir from nginx conf - look for location ~ \.zip alias/root, or default to /home/ubuntu/<id>/
    target_dir = None
    # Heuristic: parse for alias / root pointing to a directory
    lines = out.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("alias ") or s.startswith("root "):
            path = s.split(None, 1)[1].rstrip(";").strip().strip('"')
            target_dir = path
            print(f"found nginx static path: {target_dir}", file=sys.stderr)
            # Pick a zip-related one if multiple
            break

    # Check candidate dirs that match existing zip locations
    candidate_dirs = []
    for line in out2.splitlines():
        line = line.strip()
        if line.endswith(".zip") and line.startswith("/"):
            d = os.path.dirname(line)
            if d not in candidate_dirs:
                candidate_dirs.append(d)
    print(f"candidate dirs from existing zips: {candidate_dirs}", file=sys.stderr)

    # Prefer the location of existing miniprogram_*.zip files
    chosen = None
    for d in candidate_dirs:
        chosen = d
        break
    if chosen is None and target_dir:
        chosen = target_dir
    if chosen is None:
        chosen = f"/home/ubuntu/{DEPLOY_ID}"

    # Test placement: upload to chosen, verify, otherwise fallback
    sftp = client.open_sftp()

    def try_upload(remote_dir):
        ssh_exec(client, f"mkdir -p {remote_dir}")
        remote_path = f"{remote_dir.rstrip('/')}/{fname}"
        sftp.put(local_path, remote_path)
        ssh_exec(client, f"chmod 644 {remote_path}")
        return remote_path

    candidates_to_try = []
    if chosen:
        candidates_to_try.append(chosen)
    for extra in [
        f"/home/ubuntu/{DEPLOY_ID}",
        f"/home/ubuntu/{DEPLOY_ID}/dist",
        f"/home/ubuntu/{DEPLOY_ID}/uploads",
        f"/home/ubuntu/{DEPLOY_ID}/_static",
        f"/home/ubuntu/gateway/static/{DEPLOY_ID}",
    ]:
        if extra not in candidates_to_try:
            candidates_to_try.append(extra)

    url = f"{BASE_URL}/{fname}"
    last_err = None
    success = False
    for cand in candidates_to_try:
        try:
            print(f"trying upload to {cand}", file=sys.stderr)
            remote_path = try_upload(cand)
            rc3, out3, _ = ssh_exec(client, f'curl -skI "{url}" | head -3')
            print(f"verify result for {cand}: {out3.strip()}", file=sys.stderr)
            if "200" in out3.split("\n")[0]:
                success = True
                print(f"SUCCESS at {cand}", file=sys.stderr)
                break
            else:
                # remove failed upload to keep dir clean
                ssh_exec(client, f"rm -f {remote_path}")
        except Exception as e:
            last_err = str(e)
            print(f"upload to {cand} failed: {e}", file=sys.stderr)

    sftp.close()
    client.close()

    if success:
        print(json.dumps({"download_url": url, "filename": fname, "size_bytes": size}, ensure_ascii=False))
    else:
        print(json.dumps({"error": f"upload failed; last_err={last_err}; tried={candidates_to_try}"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
