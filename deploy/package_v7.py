"""打包小程序 ZIP + 启动远程 Flutter APK 构建。"""
import io
import os
import sys
import tarfile
import time
import zipfile

import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_APK_DIR = f"{PROJECT_DIR}/static/apk"
STATIC_DOWNLOADS_DIR = f"{PROJECT_DIR}/static/downloads"

CHANGED_FLUTTER_FILES = [
    "flutter_app/lib/screens/home/home_screen.dart",
    "flutter_app/lib/screens/points/points_screen.dart",
    "flutter_app/lib/screens/ai/ai_home_screen.dart",
]

APK_NAME = f"bini_health_bugfix7_{int(time.time())}.apk"
MP_ZIP_NAME = f"miniprogram_bugfix7_{int(time.time())}.zip"


def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)
    return c


def run(c, cmd, timeout=600, quiet=False):
    if not quiet:
        print(f"\n$ {cmd[:200]}")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if not quiet:
        if out:
            print(out[-2000:])
        if err:
            print(f"[stderr] {err[-1000:]}")
        print(f"[exit {code}]")
    return out, err, code


def build_miniprogram_zip(local_root, out_path):
    mp_dir = os.path.join(local_root, "miniprogram")
    skip = {"node_modules", ".git", "miniprogram_npm"}
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for root, dirs, files in os.walk(mp_dir):
            dirs[:] = [d for d in dirs if d not in skip]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, mp_dir)
                zf.write(full, arcname=f"miniprogram/{rel.replace(os.sep, '/')}")
                count += 1
    print(f"  [miniprogram zip] packed {count} files -> {out_path} ({os.path.getsize(out_path)} bytes)")


def make_tarball(local_root, files):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in files:
            full = os.path.join(local_root, rel.replace("/", os.sep))
            if os.path.exists(full):
                tar.add(full, arcname=rel)
    buf.seek(0)
    return buf.getvalue()


def main():
    local_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c = connect()
    print(f"Connected to {HOST}")

    print("\n=== Step 1: Build miniprogram zip locally ===")
    local_zip = os.path.join(local_root, MP_ZIP_NAME)
    build_miniprogram_zip(local_root, local_zip)

    print("\n=== Step 2: Upload miniprogram zip to server static/downloads ===")
    run(c, f"mkdir -p {STATIC_DOWNLOADS_DIR}")
    sftp = c.open_sftp()
    remote_zip = f"{STATIC_DOWNLOADS_DIR}/{MP_ZIP_NAME}"
    sftp.put(local_zip, remote_zip)
    sftp.put(local_zip, f"{STATIC_DOWNLOADS_DIR}/miniprogram_latest.zip")
    sftp.close()
    print(f"  uploaded {os.path.getsize(local_zip)} bytes -> {remote_zip}")
    run(c, f"ls -lh {STATIC_DOWNLOADS_DIR}/ | head -10")
    os.remove(local_zip)

    print("\n=== Step 3: Sync changed Flutter files via tar ===")
    tar_bytes = make_tarball(local_root, CHANGED_FLUTTER_FILES)
    remote_tar = f"/tmp/{DEPLOY_ID}-flutter7.tar.gz"
    sftp = c.open_sftp()
    with sftp.open(remote_tar, "wb") as f:
        f.write(tar_bytes)
    sftp.close()
    print(f"  uploaded {len(tar_bytes)} bytes")
    run(c, f"cd {PROJECT_DIR} && tar -xzf {remote_tar} && rm -f {remote_tar}")
    run(c, f"grep -n 'width: 40' {PROJECT_DIR}/flutter_app/lib/screens/home/home_screen.dart | head -3")
    run(c, f"grep -n '搜索您想要的健康服务' {PROJECT_DIR}/flutter_app/lib/screens/home/home_screen.dart | head -3")

    print("\n=== Step 4: Start Flutter APK build in background ===")
    # 配置镜像 + 构建 APK
    run(c, f"mkdir -p /home/ubuntu/.gradle-cache /home/ubuntu/.pub-cache-host {STATIC_APK_DIR}")
    init_gradle = (
        "allprojects {\n"
        "  repositories {\n"
        "    maven { url = uri('https://maven.aliyun.com/repository/google') }\n"
        "    maven { url = uri('https://maven.aliyun.com/repository/public') }\n"
        "    maven { url = uri('https://maven.aliyun.com/repository/gradle-plugin') }\n"
        "    maven { url = uri('https://maven.aliyun.com/repository/central') }\n"
        "  }\n"
        "}\n"
    )
    run(
        c,
        "cat > /home/ubuntu/.gradle-cache/init.gradle.kts << 'EOFGRADLE'\n"
        + init_gradle + "EOFGRADLE\n"
    )

    inner = (
        'set -e; '
        'export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn; '
        'export PUB_HOSTED_URL=https://pub.flutter-io.cn; '
        'echo "sdk.dir=/opt/android-sdk" > android/local.properties; '
        'echo "flutter.sdk=/opt/flutter" >> android/local.properties; '
        'flutter pub get; '
        'for f in $(find /opt/flutter/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do '
        '  sed -i "s/compileSdk *= *flutter.compileSdkVersion/compileSdk = 35/" "$f"; '
        '  sed -i "s/compileSdkVersion *= *flutter.compileSdkVersion/compileSdkVersion 35/" "$f"; '
        '  sed -i "s/targetSdkVersion *= *flutter.targetSdkVersion/targetSdkVersion 34/" "$f"; '
        '  sed -i "s/minSdkVersion *= *flutter.minSdkVersion/minSdkVersion 21/" "$f"; '
        '  sed -i "s/minSdk *= *flutter.minSdkVersion/minSdk = 21/" "$f"; '
        'done; '
        'for f in $(find /opt/flutter/.pub-cache -name "build.gradle" -type f 2>/dev/null); do '
        '  if grep -q "com.android.tools.build:gradle:7" "$f" 2>/dev/null; then '
        '    sed -i "s|com.android.tools.build:gradle:7\\.[0-9.]*|com.android.tools.build:gradle:8.4.1|g" "$f"; '
        '  fi; '
        'done; '
        'flutter build apk --release --no-tree-shake-icons; '
        f'cp build/app/outputs/flutter-apk/app-release.apk /static_apk/{APK_NAME}; '
        f'cp build/app/outputs/flutter-apk/app-release.apk /static_apk/bini_health.apk; '
        'echo BUILD_SUCCESS'
    )
    docker_cmd = (
        f"cd {PROJECT_DIR}/flutter_app && "
        f"nohup docker run --rm --network=host "
        f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
        f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
        f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
        f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
        f"-v $PWD:/app -v {STATIC_APK_DIR}:/static_apk -w /app flutter-builder:latest "
        f"bash -c '{inner}' "
        f"> /tmp/flutter_build_v7.log 2>&1 &"
    )
    print("\n>>> launching Flutter build in background...")
    run(c, docker_cmd)
    time.sleep(2)
    run(c, "ps -ef | grep flutter-builder | grep -v grep | head -3")
    print("  Flutter build started. Use deploy/check_apk_done.py to poll status.")

    print("\n=== DONE: miniprogram zip uploaded; Flutter APK building in background ===")
    print(f"  小程序 zip:  https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/miniprogram_latest.zip")
    print(f"  小程序 zip:  https://{DOMAIN}/autodev/{DEPLOY_ID}/downloads/{MP_ZIP_NAME}")
    print(f"  APK (待构建): https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/bini_health.apk")
    print(f"  APK (待构建): https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/{APK_NAME}")

    c.close()
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
