"""服务器端后台启动 Flutter APK 构建（nohup），不阻塞本地。

构建产物会写入 PROJECT_DIR/static/apk/bini_health.apk，构建日志在 /tmp/flutter_build.log。
后续可通过 check_apk_done.py 轮询。
"""
import paramiko

DEPLOY_ID = "6b099ed3-7175-4a78-91f4-44570c84ed27"
PROJECT_DIR = f"/home/ubuntu/{DEPLOY_ID}"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('newbb.test.bangbangvip.com', username='ubuntu', password='Newbang888', timeout=60)


def run(cmd):
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode())
    err = e.read().decode()
    if err.strip():
        print('STDERR:', err)


# 写一个服务器侧脚本
build_sh = f'''#!/bin/bash
set -e
cd {PROJECT_DIR}/flutter_app
echo "[$(date)] start" > /tmp/flutter_build.log
docker run --rm --network=host \\
  -e PUB_HOSTED_URL=https://pub.flutter-io.cn \\
  -e FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn \\
  -v $PWD:/app -w /app flutter-builder:latest \\
  bash -c '
    set -e
    export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
    export PUB_HOSTED_URL=https://pub.flutter-io.cn
    echo "sdk.dir=/opt/android-sdk" > android/local.properties
    echo "flutter.sdk=/opt/flutter" >> android/local.properties
    flutter pub get
    for f in $(find /opt/flutter/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do
      sed -i "s/compileSdk *= *flutter.compileSdkVersion/compileSdk = 35/" "$f"
      sed -i "s/compileSdkVersion *= *flutter.compileSdkVersion/compileSdkVersion 35/" "$f"
      sed -i "s/targetSdkVersion *= *flutter.targetSdkVersion/targetSdkVersion 34/" "$f"
      sed -i "s/minSdkVersion *= *flutter.minSdkVersion/minSdkVersion 21/" "$f"
      sed -i "s/minSdk *= *flutter.minSdkVersion/minSdk = 21/" "$f"
    done
    for f in $(find /opt/flutter/.pub-cache -name "build.gradle" -type f 2>/dev/null); do
      if grep -q "com.android.tools.build:gradle:7" "$f" 2>/dev/null; then
        sed -i "s|com.android.tools.build:gradle:7\\.[0-9.]*|com.android.tools.build:gradle:8.4.1|g" "$f"
      fi
    done
    flutter build apk --release --no-tree-shake-icons
  ' >> /tmp/flutter_build.log 2>&1

# 复制产物
APK={PROJECT_DIR}/flutter_app/build/app/outputs/flutter-apk/app-release.apk
if [ -f "$APK" ]; then
  mkdir -p {PROJECT_DIR}/static/apk
  TS=$(date +%s)
  cp "$APK" {PROJECT_DIR}/static/apk/bini_health_v7_${{TS}}.apk
  cp "$APK" {PROJECT_DIR}/static/apk/bini_health.apk
  echo "[$(date)] DONE bini_health_v7_${{TS}}.apk" >> /tmp/flutter_build.log
else
  echo "[$(date)] FAIL no apk" >> /tmp/flutter_build.log
fi
'''

# 写入文件
sftp = c.open_sftp()
with sftp.open('/tmp/build_apk_v7.sh', 'w') as f:
    f.write(build_sh)
sftp.close()
run('chmod +x /tmp/build_apk_v7.sh')

# nohup 后台启动
run('rm -f /tmp/flutter_build.log; nohup /tmp/build_apk_v7.sh > /tmp/flutter_build.nohup 2>&1 < /dev/null &')
import time
time.sleep(2)
run('echo "--- nohup running pid:" $(pgrep -f build_apk_v7.sh) "---"')
run('cat /tmp/flutter_build.log 2>/dev/null | head -3')

print("\n[+] Build started in background. Check via: tail -f /tmp/flutter_build.log on server.")
c.close()
