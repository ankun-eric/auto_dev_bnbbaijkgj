# -*- coding: utf-8 -*-
"""[H5 下单流程优化 PRD v1.0] 在远程服务器构建最新 APK 并暴露下载链接。"""
import sys
import time
import paramiko

HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_APK_DIR = f"{PROJECT_DIR}/static/apk"

INNER = (
    'set -e; '
    'export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn; '
    'export PUB_HOSTED_URL=https://pub.flutter-io.cn; '
    'echo "sdk.dir=/opt/android-sdk" > android/local.properties; '
    'echo "flutter.sdk=/opt/flutter" >> android/local.properties; '
    'flutter pub get; '
    'flutter build apk --release --no-tree-shake-icons'
)


def run(c, cmd, t=600):
    print(f"\n$ {cmd[:200]}")
    _i, o, e = c.exec_command(cmd, timeout=t)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    rc = o.channel.recv_exit_status()
    if out:
        print(out[-2500:])
    if err.strip():
        print("stderr:", err[-1000:])
    print(f"exit={rc}")
    return rc, out


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    try:
        run(c, f"cd {PROJECT_DIR} && git log -1 --oneline")
        run(c, f"rm -rf {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk")
        cmd = (
            f"cd {PROJECT_DIR}/flutter_app && "
            f"docker run --rm --network=host "
            f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
            f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
            f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
            f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
            f"-v $PWD:/app -w /app flutter-builder:latest "
            f"bash -c '{INNER}' 2>&1 | tee /tmp/flutter_build_h5co.log | tail -80"
        )
        rc, _ = run(c, cmd, t=2700)
        if rc != 0:
            print("BUILD FAILED")
            return rc

        ts = time.strftime("%Y%m%d_%H%M%S")
        apk_name = f"bini_health_h5co_{ts}.apk"
        run(c,
            f"mkdir -p {STATIC_APK_DIR} && "
            f"cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/bini_health.apk && "
            f"cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/{apk_name} && "
            f"ls -lh {STATIC_APK_DIR}/{apk_name}",
            t=120)

        url = f"https://{HOST}/autodev/{DEPLOY_ID}/apk/{apk_name}"
        run(c, f"curl -sk -o /dev/null -w 'apk=%{{http_code}}\\n' '{url}'")
        print(f"\nAPK URL: {url}")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
