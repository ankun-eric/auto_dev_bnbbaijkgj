#!/usr/bin/env python3
"""Inspect h5-web container layout and copy APK into Next.js public/apk/."""
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
APK_NAME = "bini_health_coupon_mall_20260504_130854_91a5.apk"
CONTAINER = f"{DEPLOY_ID}-h5"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=60)


def run(cmd, label=""):
    if label:
        print(f"\n>>> {label}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    print(out)
    if err.strip():
        print("STDERR:", err[:400])
    return out, err


# 1) Inspect mounts of h5-web container
run(
    f"docker inspect {CONTAINER} --format "
    f"'{{{{json .Mounts}}}}' | python3 -m json.tool 2>&1 | head -40",
    "h5-web container Mounts",
)

# 2) Inspect WorkingDir / Cmd
run(
    f"docker inspect {CONTAINER} --format 'WORKDIR={{{{.Config.WorkingDir}}}} CMD={{{{.Config.Cmd}}}}'",
    "h5-web WorkingDir + CMD",
)

# 3) ls public dirs inside container (try common paths)
run(
    f"for p in /app/public /app/public/apk /app/.next/static /app /app/h5-web/public; do "
    f"echo \"--- $p ---\"; docker exec {CONTAINER} ls -la $p 2>&1 | head -10; done",
    "ls inside container",
)

# 4) Copy APK to container's /app/public/apk (Next.js public)
run(
    f"docker exec {CONTAINER} mkdir -p /app/public/apk && "
    f"docker cp /home/ubuntu/{DEPLOY_ID}/h5-web/public/apk/{APK_NAME} {CONTAINER}:/app/public/apk/{APK_NAME} && "
    f"docker exec {CONTAINER} ls -la /app/public/apk/",
    "docker cp APK into container /app/public/apk/",
)

# 5) Verify HTTP again
run(
    f"sleep 2 && curl -sL -o /dev/null -w 'http=%{{http_code}} size=%{{size_download}}\\n' "
    f"'https://newbb.test.bangbangvip.com/autodev/{DEPLOY_ID}/apk/{APK_NAME}'",
    "HTTPS verify",
)

client.close()
