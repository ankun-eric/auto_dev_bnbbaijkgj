"""V3: 彻底清理 gradle daemon + 缓存 + 旧 docker，再构建。
重点：先杀掉所有 flutter-builder docker、清缓存，再用 nohup 异步跑构建并 detach SSH，等到完成再轮询产物。
"""
import paramiko
import time
import sys

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
HOST = "newbb.test.bangbangvip.com"
USER = "ubuntu"
PASS = "Newbang888"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"
STATIC_APK_DIR = f"{PROJECT_DIR}/static/apk"
LOG_FILE = "/tmp/flutter_build_v3.log"
BUILD_FLAG_OK = "/tmp/flutter_build_v3.ok"
BUILD_FLAG_FAIL = "/tmp/flutter_build_v3.fail"

# 内层 docker bash
inner_bash = f'''set -e
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
export PUB_HOSTED_URL=https://pub.flutter-io.cn
echo "sdk.dir=/opt/android-sdk" > android/local.properties
echo "flutter.sdk=/opt/flutter" >> android/local.properties
echo "[step] flutter pub get"
flutter pub get
echo "[step] patch record_android"
for f in $(find /opt/flutter/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do
  sed -i "s/compileSdk *= *flutter.compileSdkVersion/compileSdk = 35/" "$f"
  sed -i "s/compileSdkVersion *= *flutter.compileSdkVersion/compileSdkVersion 35/" "$f"
  sed -i "s/targetSdkVersion *= *flutter.targetSdkVersion/targetSdkVersion 34/" "$f"
  sed -i "s/minSdkVersion *= *flutter.minSdkVersion/minSdkVersion 21/" "$f"
  sed -i "s/minSdk *= *flutter.minSdkVersion/minSdk = 21/" "$f"
done
echo "[step] patch AGP versions in pub-cache"
for f in $(find /opt/flutter/.pub-cache -name "build.gradle" -type f 2>/dev/null); do
  if grep -q "com.android.tools.build:gradle:7" "$f" 2>/dev/null; then
    sed -i "s|com.android.tools.build:gradle:7\\\\.[0-9.]*|com.android.tools.build:gradle:8.4.1|g" "$f"
  fi
done
echo "[step] flutter build apk --release"
flutter build apk --release --no-tree-shake-icons
echo "[done] APK at:"
ls -la build/app/outputs/flutter-apk/
'''

# 外层 wrapper：跑 docker，根据退出码写 OK/FAIL flag
outer_wrapper = f'''#!/bin/bash
set -e
cd {PROJECT_DIR}/flutter_app
rm -rf build/app/outputs/flutter-apk 2>/dev/null || true
rm -rf .dart_tool 2>/dev/null || true
# 把内层 bash 写入临时文件，避免引号噩梦
cat > /tmp/flutter_inner_v3.sh << 'INNER_EOF'
{inner_bash}
INNER_EOF
chmod +x /tmp/flutter_inner_v3.sh

docker run --rm --network=host \\
  -e PUB_HOSTED_URL=https://pub.flutter-io.cn \\
  -e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \\
  -v /home/ubuntu/.gradle-cache:/root/.gradle \\
  -v /home/ubuntu/.pub-cache-host:/root/.pub-cache \\
  -v /tmp/flutter_inner_v3.sh:/tmp/inner.sh \\
  -v $PWD:/app -w /app \\
  flutter-builder:latest \\
  bash /tmp/inner.sh
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  cp build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/bini_health.apk
  cp build/app/outputs/flutter-apk/app-release.apk {STATIC_APK_DIR}/bini_health_bugfix7_v3_$(date +%s).apk
  ls -la {STATIC_APK_DIR}/
  touch {BUILD_FLAG_OK}
else
  touch {BUILD_FLAG_FAIL}
fi
exit $EXIT_CODE
'''


def ssh_exec(c, cmd, timeout=120):
    _, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    return code, out, err


def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=60)

    # 1. 上传最新 settings.gradle / build.gradle（已回滚到 master 版本）
    print("[1] uploading settings.gradle and build.gradle ...")
    sftp = c.open_sftp()
    sftp.put("flutter_app/android/settings.gradle", f"{PROJECT_DIR}/flutter_app/android/settings.gradle")
    sftp.put("flutter_app/android/build.gradle", f"{PROJECT_DIR}/flutter_app/android/build.gradle")
    sftp.close()

    # 2. 杀掉所有 flutter-builder 容器 + 清缓存
    print("[2] killing orphan flutter-builder containers ...")
    code, out, _ = ssh_exec(c, "docker ps --filter ancestor=flutter-builder:latest -q | xargs -r docker kill 2>&1")
    print(out)
    print("[2.1] cleanup gradle daemon ...")
    code, out, _ = ssh_exec(c, "rm -rf /home/ubuntu/.gradle-cache/caches/8.* 2>/dev/null; rm -rf /home/ubuntu/.gradle-cache/daemon 2>/dev/null; echo done")
    print(out)

    # 3. 写入 wrapper 到服务器
    print("[3] uploading build wrapper ...")
    sftp = c.open_sftp()
    with sftp.file("/tmp/flutter_build_v3.sh", "w") as f:
        f.write(outer_wrapper)
    sftp.chmod("/tmp/flutter_build_v3.sh", 0o755)
    sftp.close()

    # 4. 清掉旧 flag，启动 nohup 后台构建
    print("[4] starting nohup background build ...")
    ssh_exec(c, f"rm -f {BUILD_FLAG_OK} {BUILD_FLAG_FAIL} {LOG_FILE}")
    ssh_exec(c, f"nohup bash /tmp/flutter_build_v3.sh > {LOG_FILE} 2>&1 &")
    print(f"  log: {LOG_FILE}")

    # 5. 轮询 flag，最长 25 分钟
    max_wait = 25 * 60
    poll = 30
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(poll)
        elapsed += poll
        code, out, _ = ssh_exec(c, f"if [ -f {BUILD_FLAG_OK} ]; then echo OK; elif [ -f {BUILD_FLAG_FAIL} ]; then echo FAIL; else echo RUN; fi")
        status = out.strip()
        # 取日志尾部观察进度
        _, tail, _ = ssh_exec(c, f"tail -20 {LOG_FILE} 2>/dev/null")
        print(f"  [{elapsed}s/{max_wait}s] status={status}; log tail:")
        print("  " + tail.replace("\n", "\n  "))
        if status == "OK":
            # 列产物
            _, ls, _ = ssh_exec(c, f"ls -la {STATIC_APK_DIR}/")
            print(ls)
            c.close()
            return True
        if status == "FAIL":
            _, full, _ = ssh_exec(c, f"tail -150 {LOG_FILE}")
            print("=== full last 150 lines ===")
            print(full)
            c.close()
            return False

    print("=== timeout ===")
    _, full, _ = ssh_exec(c, f"tail -150 {LOG_FILE}")
    print(full)
    c.close()
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
