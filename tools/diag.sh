#!/usr/bin/env bash
set -euo pipefail

ADB="${ADB:-adb}"
DEV="${DEV:-}"
if [ -n "$DEV" ]; then ADB="$ADB -s $DEV"; fi

UI=0
if [ "${1:-}" = "--ui" ]; then UI=1; fi

echo "=== device ==="
$ADB get-state
$ADB shell 'getprop ro.product.model; getprop ro.build.version.release; getprop ro.build.version.oplusrom'
$ADB shell 'getprop ro.build.fingerprint'

echo
echo "=== boot state (real, from cmdline) ==="
$ADB shell 'grep -o "oplusboot\.[a-z_]*=[^ ]*" /proc/cmdline'

echo
echo "=== root ==="
$ADB shell 'id'

echo
echo "=== soter-provision ==="
$ADB shell 'for i in 1 2 3 4; do printf "  %s: " "$i"; vendor.qti.hardware.soter-provision $i 2>&1 | head -1; done'

echo
echo "=== persist attestation slots ==="
$ADB shell '
P=/mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_
for d in "$P" "$P"_Alt; do
  [ -d "$d" ] || continue
  printf "  %s\n" "$d"
  printf "    files: %s  keyblob(5r5): %s\n" "$(ls "$d" | wc -l)" "$(ls "$d" | grep -c "^5r5" || true)"
  stat -c "    5r5 mtime: %y  size: %s" "$d/5r5LgWqAGkK7pkbwDExz" 2>/dev/null || printf "    no 5r5\n"
done'

echo
echo "=== rpmb_status ==="
$ADB shell 'xxd -l 4 /mnt/vendor/persist/rpmb_status/rpmb_status 2>/dev/null || od -A x -t x1 -N 4 /mnt/vendor/persist/rpmb_status/rpmb_status'

echo
echo "=== keystore / keymint processes ==="
$ADB shell 'ps -A | grep -E "keystore2|keymint|soter|rkpd" | sed "s/^/  /"'

echo
echo "=== keyattestation app data ==="
$ADB shell 'ls -la /data/data/io.github.vvb2060.keyattestation 2>/dev/null | head -5'

if [ "$UI" = "1" ]; then
  echo
  echo "=== engineering mode (ui dump) ==="
  $ADB shell 'am force-stop com.oplus.engineermode'
  $ADB shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity' >/dev/null
  sleep 3
  $ADB shell 'uiautomator dump /sdcard/.diag_ui.xml' >/dev/null 2>&1 || true
  $ADB shell 'cat /sdcard/.diag_ui.xml 2>/dev/null' | tr '>' '\n' | grep -o 'text="[^"]*"' | sed 's/text="//; s/"$//' | paste - - | sed 's/^/  /'
  $ADB shell 'rm -f /sdcard/.diag_ui.xml'
fi
