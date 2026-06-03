#!/bin/bash
set -euo pipefail

# FPK Build Script for miloco-n0ts (fnOS)
# Usage: ./fpk/build.sh [VERSION]
# Output: fpk/miloco-n0ts_<version>.fpk

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/miloco-n0ts"
APP_NAME="miloco-n0ts"
VERSION="${1:-1.0.0}"
OUTPUT_DIR="$SCRIPT_DIR"
WORK_DIR=$(mktemp -d)

echo "=== Building FPK: ${APP_NAME} v${VERSION} ==="

# Update version in manifest
sed -i "s/^version.*= .*/version               = ${VERSION}/" "$APP_DIR/appinfo"

# Prepare work directory
mkdir -p "$WORK_DIR/${APP_NAME}"

# Copy manifest
cp "$APP_DIR/appinfo" "$WORK_DIR/${APP_NAME}/"

# Copy config
mkdir -p "$WORK_DIR/${APP_NAME}/config"
cp "$APP_DIR/config/privilege" "$WORK_DIR/${APP_NAME}/config/"
cp "$APP_DIR/config/resource" "$WORK_DIR/${APP_NAME}/config/"

# Copy icon (if exists)
if [ -f "$APP_DIR/ICON.PNG" ]; then
    cp "$APP_DIR/ICON.PNG" "$WORK_DIR/${APP_NAME}/"
fi
if [ -f "$APP_DIR/ICON_256.PNG" ]; then
    cp "$APP_DIR/ICON_256.PNG" "$WORK_DIR/${APP_NAME}/"
fi

# Create app.tgz from docker-compose and data dirs
mkdir -p "$WORK_DIR/app_build"
cp "$APP_DIR/docker-compose.yaml" "$WORK_DIR/app_build/"
mkdir -p "$WORK_DIR/app_build/data"
mkdir -p "$WORK_DIR/app_build/log/backend"

cd "$WORK_DIR/app_build"
tar czf "$WORK_DIR/${APP_NAME}/app.tgz" .
cd "$SCRIPT_DIR"

# Calculate checksum (md5 of manifest)
CHECKSUM=$(md5sum "$WORK_DIR/${APP_NAME}/appinfo" | cut -d' ' -f1)
echo "Checksum: ${CHECKSUM}"

# Build FPK (tar.gz of the app directory)
OUTPUT_FILE="${OUTPUT_DIR}/${APP_NAME}_${VERSION}.fpk"
cd "$WORK_DIR"
tar czf "$OUTPUT_FILE" "${APP_NAME}/"
cd "$SCRIPT_DIR"

# Cleanup
rm -rf "$WORK_DIR"

echo "=== FPK built successfully ==="
echo "Output: ${OUTPUT_FILE}"
echo "Size: $(du -h "$OUTPUT_FILE" | cut -f1)"
echo ""
echo "To install on fnOS:"
echo "  1. Open fnOS web UI"
echo "  2. Go to App Store > Local Install"
echo "  3. Select the .fpk file"
