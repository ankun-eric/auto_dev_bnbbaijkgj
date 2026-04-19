"""同步 flutter_app/lib/screens/health/drug_screen.dart 到服务器并构建 APK。"""
import paramiko
import time
import os

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
APK_NAME = f"bini_health_v7_{int(time.time())}.apk"

CHANGED_FLUTTER_FILES = [
    "flutter_app/lib/screens/health/drug_screen.dart",
]


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    # 1) 上传 Flutter 改动文件
    sftp = c.open_sftp()
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in CHANGED_FLUTTER_FILES:
        local = os.path.join(workspace, rel.replace("/", os.sep))
        remote = f"{PROJECT_DIR}/{rel}"
        print(f"upload {rel} ...")
        sftp.put(local, remote)
    sftp.close()

    def run(cmd, timeout=1500, show=True):
        if show:
            print(f"\n>>> {cmd}")
        _, o, e = c.exec_command(cmd, timeout=timeout, get_pty=False)
        out = o.read().decode(errors='ignore')
        err = e.read().decode(errors='ignore')
        if show:
            if out.strip():
                print(out)
            if err.strip():
                print('STDERR:', err)
        return out, err

    # 2) 验证修改已同步
    run(f'grep -n "original_image_url" {PROJECT_DIR}/flutter_app/lib/screens/health/drug_screen.dart | head -3')

    # 2.5) 改 gradle-wrapper 用腾讯镜像；准备持久化缓存目录 + init.gradle
    run(
        f'sed -i "s|services.gradle.org/distributions|mirrors.cloud.tencent.com/gradle|" '
        f'{PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties && '
        f'cat {PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties'
    )
    run('mkdir -p /home/ubuntu/.gradle-cache /home/ubuntu/.pub-cache-host')
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
        "cat > /home/ubuntu/.gradle-cache/init.gradle.kts << 'EOFGRADLE'\n"
        + init_gradle + "EOFGRADLE\n"
        "ls -la /home/ubuntu/.gradle-cache/init.gradle.kts"
    )

    # 3) 用 flutter-builder 容器构建 APK（host 网络 + 国内镜像 + 三方插件 SDK patch + 持久化缓存）
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
    cmd = (
        f"cd {PROJECT_DIR}/flutter_app && "
        f"docker run --rm --network=host "
        f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
        f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
        f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
        f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
        f"-v $PWD:/app -w /app flutter-builder:latest "
        f"bash -c '{inner}' 2>&1 | tail -50"
    )
    out, _ = run(cmd, timeout=2400)

    # 4) 找到产物
    out2, _ = run(f'ls -lh {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/ 2>/dev/null')
    if 'app-release.apk' not in out2:
        print('!!! BUILD FAILED, no app-release.apk found !!!')
        c.close()
        return False

    # 5) 复制到静态目录
    run(
        f'mkdir -p {PROJECT_DIR}/static/apk && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/{APK_NAME} && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/bini_health.apk && '
        f'ls -lh {PROJECT_DIR}/static/apk/'
    )

    print(f"\n==== APK published: bini_health.apk + {APK_NAME} ====")
    c.close()
    return True


if __name__ == '__main__':
    ok = main()
    raise SystemExit(0 if ok else 1)
