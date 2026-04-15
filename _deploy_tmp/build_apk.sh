#!/bin/bash
set -e

BUILD_DIR=/home/ubuntu/flutter-apk-build
DEPLOY_ID="6b099ed3-7175-4a78-91f4-44570c84ed27"
VERSION="android-v20260415-182850-3524"
REPO_URL="https://ankun-eric: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@github.com/ankun-eric/auto_dev_bnbbaijkgj.git"

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Clean previous build
rm -rf repo
echo "=== Cloning repository ==="
git clone --depth 1 "$REPO_URL" repo
cd repo/flutter_app

# Create Dockerfile for Flutter build
cat > Dockerfile.build << 'DOCKERFILE'
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV ANDROID_HOME=/opt/android-sdk
ENV FLUTTER_HOME=/opt/flutter
ENV PATH=$PATH:$FLUTTER_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

RUN apt-get update && apt-get install -y \
    curl git unzip xz-utils zip libglu1-mesa openjdk-17-jdk wget \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $ANDROID_HOME/cmdline-tools && \
    cd $ANDROID_HOME/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O tools.zip && \
    unzip -q tools.zip && \
    mv cmdline-tools latest && \
    rm tools.zip

RUN yes | sdkmanager --licenses > /dev/null 2>&1 || true && \
    sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"

RUN git clone https://github.com/flutter/flutter.git -b stable $FLUTTER_HOME --depth 1 && \
    flutter precache --android && \
    flutter config --no-analytics && \
    dart --disable-analytics

WORKDIR /app
DOCKERFILE

echo "=== Building Docker image (this may take a few minutes on first run) ==="
docker build -t flutter-builder -f Dockerfile.build . 2>&1 | tail -20

echo "=== Running Flutter APK build ==="
docker run --rm \
    -v "$(pwd)":/app \
    -w /app \
    flutter-builder \
    bash -c '
        set -e
        echo "sdk.dir=/opt/android-sdk" > android/local.properties
        echo "flutter.sdk=/opt/flutter" >> android/local.properties
        flutter pub get

        for f in $(find /opt/flutter/.pub-cache -path "*/record_android*/android/build.gradle" -type f 2>/dev/null); do
            echo "Patching: $f"
            sed -i "s/compileSdk\s*=\?\s*flutter\.compileSdkVersion/compileSdk = 35/" "$f"
            sed -i "s/compileSdkVersion\s*=\?\s*flutter\.compileSdkVersion/compileSdkVersion 35/" "$f"
            sed -i "s/targetSdkVersion\s*=\?\s*flutter\.targetSdkVersion/targetSdkVersion 34/" "$f"
            sed -i "s/minSdkVersion\s*=\?\s*flutter\.minSdkVersion/minSdkVersion 21/" "$f"
            sed -i "s/minSdk\s*=\?\s*flutter\.minSdkVersion/minSdk = 21/" "$f"
        done

        for f in $(find /opt/flutter/.pub-cache -name "build.gradle" -type f 2>/dev/null); do
            if grep -q "com.android.tools.build:gradle:7" "$f" 2>/dev/null; then
                echo "Upgrading AGP in: $f"
                sed -i "s|com.android.tools.build:gradle:7\.[0-9.]*|com.android.tools.build:gradle:8.4.1|g" "$f"
            fi
        done

        flutter build apk --release --no-tree-shake-icons
    '

# Find the APK
APK_FILE="$BUILD_DIR/repo/flutter_app/build/app/outputs/flutter-apk/app-release.apk"
if [ ! -f "$APK_FILE" ]; then
    echo "Searching for APK..."
    find "$BUILD_DIR/repo/flutter_app/build" -name "*.apk" -type f 2>/dev/null
    APK_FILE=$(find "$BUILD_DIR/repo/flutter_app/build" -name "*.apk" -type f | head -1)
fi

if [ -z "$APK_FILE" ] || [ ! -f "$APK_FILE" ]; then
    echo "FATAL: No APK found!"
    exit 1
fi

DOWNLOAD_DIR="/home/ubuntu/deployments/$DEPLOY_ID/downloads"
mkdir -p "$DOWNLOAD_DIR"
APK_NAME="bini_health_${VERSION}.apk"
cp "$APK_FILE" "$DOWNLOAD_DIR/$APK_NAME"
echo "=== APK READY: $DOWNLOAD_DIR/$APK_NAME ==="
ls -la "$DOWNLOAD_DIR/$APK_NAME"
echo "=== BUILD SUCCESS ==="
