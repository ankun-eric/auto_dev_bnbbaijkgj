"""V2: 修复 Gradle settings 后再构建 APK。先上传本地最新 android/settings.gradle、清缓存，再跑 docker 构建。"""
import paramiko
from pathlib import Path

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_APK_DIR = f"{PROJECT_DIR}/static/apk"

LOCAL_SETTINGS = Path(__file__).parent.parent / "flutter_app" / "android" / "settings.gradle"
REMOTE_SETTINGS = f"{PROJECT_DIR}/flutter_app/android/settings.gradle"

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
    'flutter build apk --release --no-tree-shake-icons'
)


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    # 1) 上传本地修复后的 settings.gradle
    sftp = c.open_sftp()
    print(f"uploading {LOCAL_SETTINGS} -> {REMOTE_SETTINGS}")
    sftp.put(str(LOCAL_SETTINGS), REMOTE_SETTINGS)
    sftp.close()

    # 2) 清掉旧 build 目录避免缓存干扰
    _, o, _ = c.exec_command(
        f'rm -rf {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk; '
        f'rm -rf {PROJECT_DIR}/flutter_app/.dart_tool; '
        f'cat {REMOTE_SETTINGS} | head -30',
        timeout=60,
    )
    print(o.read().decode())

    # 3) 跑 docker 构建
    cmd = (
        f"cd {PROJECT_DIR}/flutter_app && "
        f"docker run --rm --network=host "
        f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
        f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
        f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
        f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
        f"-v $PWD:/app -w /app flutter-builder:latest "
        f"bash -c '{inner}' 2>&1 | tee /tmp/flutter_build_v7_sync2.log | tail -120"
    )
    print(f">>> {cmd[:300]}...")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=2400)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print(f"[stderr]\n{err[-3000:]}")
    print(f"[exit {code}]")

    # 4) 找产物
    _, stdout, _ = c.exec_command(
        f'ls -lh {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/ 2>&1', timeout=30
    )
    print(stdout.read().decode())

    if code == 0:
        # 5) 复制到 static/apk
        stamp_cmd = (
            f'mkdir -p {STATIC_APK_DIR} && '
            f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/bini_health.apk && '
            f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/bini_health_bugfix7_v2_$(date +%s).apk && '
            f'ls -lh {STATIC_APK_DIR}/'
        )
        _, stdout, _ = c.exec_command(stamp_cmd, timeout=60)
        print(stdout.read().decode())

    c.close()
    return code == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
