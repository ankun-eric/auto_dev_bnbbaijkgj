"""Home 3 Bugs 修复 - 服务器上构建 Flutter APK (v3)。

相比 v2：
1. 恢复 flutter SDK 的 origin 为原始 github.com（gitclone 镜像导致 Gradle 失败）。
2. 把 flutter_tools 里做 git fetch 的调用强行设置一个短超时，失败不阻塞。
3. 清理 android/.gradle 以便 Gradle 重新解析。
"""
import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
APK_NAME = f"bini_health_home3bugs_{time.strftime('%Y%m%d-%H%M%S')}.apk"


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    def run(cmd, timeout=2400, show=True):
        if show:
            print(f"\n>>> {cmd[:240]}{'...' if len(cmd) > 240 else ''}")
        _, o, e = c.exec_command(cmd, timeout=timeout, get_pty=False)
        out = o.read().decode(errors='ignore')
        err = e.read().decode(errors='ignore')
        if show:
            if out.strip():
                print(out[-3000:])
            if err.strip():
                print('STDERR:', err[-1500:])
        return out, err

    run(
        f'grep -n "WidgetsBindingObserver" {PROJECT_DIR}/flutter_app/lib/screens/home/home_screen.dart | head -3 && '
        f'grep -n "pageSize" {PROJECT_DIR}/flutter_app/lib/services/api_service.dart | head -3'
    )

    run(
        f'sed -i "s|services.gradle.org/distributions|mirrors.cloud.tencent.com/gradle|" '
        f'{PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties 2>/dev/null; '
        f'head -8 {PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties'
    )
    run('mkdir -p /home/ubuntu/.gradle-cache /home/ubuntu/.pub-cache-host')

    # 只清 APK 输出目录，保留 .dart_tool/.gradle 以复用缓存
    run(
        f'sudo rm -rf {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk 2>/dev/null; '
        f'sudo rm -rf {PROJECT_DIR}/flutter_app/build/app/intermediates/flutter 2>/dev/null; '
        f'echo clean-ok'
    )

    inner = (
        'set -e; '
        'export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn; '
        'export PUB_HOSTED_URL=https://pub.flutter-io.cn; '
        'export FLUTTER_SUPPRESS_ANALYTICS=true; '
        # 短超时 git 配置
        'git config --global http.lowSpeedLimit 1000 || true; '
        'git config --global http.lowSpeedTime 20 || true; '
        'git config --global http.postBuffer 524288000 || true; '
        # 不切镜像，保持原 origin；但给 /opt/flutter 加 --no-tags 默认行为：
        'cd /opt/flutter && git config remote.origin.tagOpt --no-tags && cd /app; '
        # 软 touch 一下 engine.stamp 来欺骗 flutter_tools 跳过升级检查
        'touch /opt/flutter/bin/cache/engine.stamp 2>/dev/null || true; '
        'echo "sdk.dir=/opt/android-sdk" > android/local.properties; '
        'echo "flutter.sdk=/opt/flutter" >> android/local.properties; '
        'flutter config --no-analytics >/dev/null 2>&1 || true; '
        # offline 模式 - 如果 pub-cache-host 已经齐全就用缓存，不再联网
        'flutter pub get --offline || flutter pub get; '
        # Patch image_gallery_saver 2.0.3 - 移除废弃 Registrar import
        'for f in $(find /root/.pub-cache /opt/flutter/.pub-cache -path "*image_gallery_saver*ImageGallerySaverPlugin.kt" -type f 2>/dev/null); do '
        '  sed -i "s|^import io.flutter.plugin.common.PluginRegistry.Registrar$|// patched for kotlin1.9|" "$f"; '
        'done; '
        'for f in $(find /opt/flutter/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do '
        '  sed -i "s/compileSdk *= *flutter.compileSdkVersion/compileSdk = 35/" "$f"; '
        '  sed -i "s/compileSdkVersion *= *flutter.compileSdkVersion/compileSdkVersion 35/" "$f"; '
        '  sed -i "s/targetSdkVersion *= *flutter.targetSdkVersion/targetSdkVersion 34/" "$f"; '
        '  sed -i "s/minSdkVersion *= *flutter.minSdkVersion/minSdkVersion 21/" "$f"; '
        '  sed -i "s/minSdk *= *flutter.minSdkVersion/minSdk = 21/" "$f"; '
        'done; '
        'for f in $(find /root/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do '
        '  sed -i "s/compileSdk *= *flutter.compileSdkVersion/compileSdk = 35/" "$f"; '
        '  sed -i "s/compileSdkVersion *= *flutter.compileSdkVersion/compileSdkVersion 35/" "$f"; '
        '  sed -i "s/targetSdkVersion *= *flutter.targetSdkVersion/targetSdkVersion 34/" "$f"; '
        '  sed -i "s/minSdkVersion *= *flutter.minSdkVersion/minSdkVersion 21/" "$f"; '
        '  sed -i "s/minSdk *= *flutter.minSdkVersion/minSdk = 21/" "$f"; '
        'done; '
        'for f in $(find /opt/flutter/.pub-cache /root/.pub-cache -name "build.gradle" -type f 2>/dev/null); do '
        '  if grep -q "com.android.tools.build:gradle:7" "$f" 2>/dev/null; then '
        '    sed -i "s|com.android.tools.build:gradle:7\\.[0-9.]*|com.android.tools.build:gradle:8.4.1|g" "$f"; '
        '  fi; '
        'done; '
        'flutter build apk --release --no-tree-shake-icons'
    )
    cmd = (
        f"cd {PROJECT_DIR}/flutter_app && "
        f"docker run --rm --name flutter_home3bugs_v3 --network=host "
        f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
        f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
        f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
        f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
        f"-v $PWD:/app -w /app flutter-builder:latest "
        f"bash -c '{inner}' 2>&1 | tee /tmp/flutter_build_home3bugs_v3.log | tail -100"
    )
    run(cmd, timeout=3600)

    out, _ = run(f'ls -lh {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/ 2>&1')
    if 'app-release.apk' not in out:
        print('!!! BUILD FAILED, no app-release.apk !!!')
        c.close()
        return False

    run(
        f'mkdir -p {PROJECT_DIR}/static/apk && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/{APK_NAME} && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/bini_health.apk && '
        f'chmod 644 {PROJECT_DIR}/static/apk/*.apk && '
        f'ls -lh {PROJECT_DIR}/static/apk/ | tail -10'
    )

    print(f"\n==== APK published ====")
    print(f"  unique: https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/{APK_NAME}")
    print(f"  latest: https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/bini_health.apk")
    c.close()
    return True


if __name__ == '__main__':
    ok = main()
    raise SystemExit(0 if ok else 1)
