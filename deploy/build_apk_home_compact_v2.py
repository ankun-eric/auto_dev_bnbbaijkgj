"""首页顶部紧凑化 - APK 构建 v2。

v1 卡在 flutter config 触发的 git fetch --tags（github.com 网络问题）。
v2 策略：
- 镜像 flutter SDK origin 到 gitee/gitclone 或直接让 git fetch 指令无操作（禁用 tagOpt=--no-tags，
  且在 /opt/flutter 注入一个假的 tags refs 来欺骗 flutter_tools 跳过 fetch）。
- 增加 GIT_TERMINAL_PROMPT=0 和 git http.timeout 避免长时间挂起。
- 使用 flutter --no-version-check 跳过 flutter_tools 内的版本 git 操作。
"""
import paramiko
import time

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
DOMAIN = "newbb.test.bangbangvip.com"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
APK_NAME = f"bini_health_home_compact_{time.strftime('%Y%m%d-%H%M%S')}.apk"


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

    # 清理残留容器
    run('docker rm -f flutter_home_compact flutter_home_compact_v2 2>/dev/null; echo clean')

    run(
        f'sed -i "s|services.gradle.org/distributions|mirrors.cloud.tencent.com/gradle|" '
        f'{PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties 2>/dev/null; '
        f'head -5 {PROJECT_DIR}/flutter_app/android/gradle/wrapper/gradle-wrapper.properties'
    )
    run('mkdir -p /home/ubuntu/.gradle-cache /home/ubuntu/.pub-cache-host')

    run(
        f'sudo rm -rf {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk 2>/dev/null; '
        f'sudo rm -rf {PROJECT_DIR}/flutter_app/build/app/intermediates/flutter 2>/dev/null; '
        f'echo clean-ok'
    )

    # 关键：直接在宿主机先把 /opt/flutter 的 origin 置空并禁用 tags fetch，避开在容器里等 github 网络
    inner = (
        'set -e; '
        'export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn; '
        'export PUB_HOSTED_URL=https://pub.flutter-io.cn; '
        'export FLUTTER_SUPPRESS_ANALYTICS=true; '
        'export GIT_TERMINAL_PROMPT=0; '
        # 暴力禁用 flutter SDK 的 origin 拉取：指向一个本地空仓库
        'git config --global http.lowSpeedLimit 1000 || true; '
        'git config --global http.lowSpeedTime 10 || true; '
        'git config --global http.postBuffer 524288000 || true; '
        'cd /opt/flutter && '
        '  git config remote.origin.tagOpt --no-tags && '
        '  git config remote.origin.fetch "+refs/heads/stable:refs/remotes/origin/stable" && '
        # 把 origin 远端改成本地路径，让任何 fetch 秒成功（本地空不改动）
        '  git remote set-url origin /opt/flutter/.git 2>/dev/null || true && '
        '  cd /app; '
        'touch /opt/flutter/bin/cache/engine.stamp 2>/dev/null || true; '
        'echo "sdk.dir=/opt/android-sdk" > android/local.properties; '
        'echo "flutter.sdk=/opt/flutter" >> android/local.properties; '
        # 不做 flutter config（会触发 fetch），也不做 flutter doctor
        'flutter pub get --offline || flutter pub get; '
        'for f in $(find /root/.pub-cache /opt/flutter/.pub-cache -path "*image_gallery_saver*ImageGallerySaverPlugin.kt" -type f 2>/dev/null); do '
        '  sed -i "s|^import io.flutter.plugin.common.PluginRegistry.Registrar$|// patched for kotlin1.9|" "$f"; '
        'done; '
        'for f in $(find /opt/flutter/.pub-cache /root/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do '
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
        f"docker run --rm --name flutter_home_compact_v2 --network=host "
        f"-e PUB_HOSTED_URL=https://pub.flutter-io.cn "
        f"-e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn "
        f"-v /home/ubuntu/.gradle-cache:/root/.gradle "
        f"-v /home/ubuntu/.pub-cache-host:/root/.pub-cache "
        f"-v $PWD:/app -w /app flutter-builder:latest "
        f"bash -c '{inner}' 2>&1 | tee /tmp/flutter_build_home_compact_v2.log"
    )
    run(cmd, timeout=3600)

    out, _ = run(f'ls -lh {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/ 2>&1')
    if 'app-release.apk' not in out:
        print('!!! BUILD FAILED, no app-release.apk !!!')
        run('tail -200 /tmp/flutter_build_home_compact_v2.log')
        c.close()
        return False

    run(
        f'mkdir -p {PROJECT_DIR}/static/apk && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/{APK_NAME} && '
        f'cp {PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk '
        f'{PROJECT_DIR}/static/apk/bini_health.apk && '
        f'chmod 644 {PROJECT_DIR}/static/apk/*.apk && '
        f'ls -lh {PROJECT_DIR}/static/apk/ | tail -5'
    )

    print("\n==== APK published ====")
    print(f"  unique: https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/{APK_NAME}")
    print(f"  latest: https://{DOMAIN}/autodev/{DEPLOY_ID}/apk/bini_health.apk")
    c.close()
    return True


if __name__ == '__main__':
    ok = main()
    raise SystemExit(0 if ok else 1)
