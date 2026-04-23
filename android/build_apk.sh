#!/bin/bash
set -e

# Auto-detect JAVA_HOME from SDKMAN or system
if [ -d "/root/.sdkman/candidates/java/current" ]; then
    export JAVA_HOME="/root/.sdkman/candidates/java/current"
elif [ -d "/opt/jdk/jdk-17.0.12" ]; then
    export JAVA_HOME="/opt/jdk/jdk-17.0.12"
else
    export JAVA_HOME="${JAVA_HOME:-$(dirname "$(dirname "$(readlink -f "$(which java)")")")}"
fi

export ANDROID_HOME="/opt/android-sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Starting APK Build ==="
echo "JAVA_HOME=$JAVA_HOME"
echo "ANDROID_HOME=$ANDROID_HOME"
java -version 2>&1

echo "=== Ensuring local.properties ==="
if [ ! -f local.properties ]; then
    echo "sdk.dir=$ANDROID_HOME" > local.properties
fi

echo "=== Cleaning previous build ==="
./gradlew clean --no-daemon 2>&1 || true

echo "=== Running Gradle assembleDebug ==="
./gradlew assembleDebug --no-daemon 2>&1

echo "=== Build Complete ==="
echo "=== APK files ==="
find . -name "*.apk" -type f 2>/dev/null || echo "No APK found"

echo "=== Done ==="
