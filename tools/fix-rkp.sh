#!/usr/bin/env bash
set -euo pipefail

ADB="${ADB:-adb}"
DEV="${DEV:-}"
if [ -n "$DEV" ]; then ADB="$ADB -s $DEV"; fi

P=/mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_

echo "=== [1/4] preflight ==="
$ADB shell 'grep -o "oplusboot.verifiedbootstate=[a-z]*" /proc/cmdline'
$ADB shell "stat -c '  orig 5r5: %y  %s bytes' $P/5r5LgWqAGkK7pkbwDExz"

echo
echo "this writes device ID into persist/RPMB; it cannot be rolled back."
printf "proceed? [y/N] "
read -r ans
if [ "$ans" != "y" ]; then echo "aborted"; exit 1; fi

echo
echo "=== [2/4] write device id ==="
$ADB shell 'LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox /data/local/tmp/x PLQ110 true rkp'

echo
echo "=== [3/4] clear old key blob ==="
$ADB shell 'pm clear io.github.vvb2060.keyattestation'

echo
echo "=== [4/4] verify ==="
$ADB shell 'am start -n io.github.vvb2060.keyattestation/.home.HomeActivity' >/dev/null
sleep 3
$ADB shell 'uiautomator dump /sdcard/.fix_ui.xml' >/dev/null 2>&1 || true
$ADB shell 'cat /sdcard/.fix_ui.xml 2>/dev/null' | tr '>' '\n' | grep -o 'CN=Android Keystore Key[^"]*' | head -1 | sed 's/^/  /' || true
$ADB shell 'rm -f /sdcard/.fix_ui.xml'
$ADB shell "printf '  alt 5r5 count: '; ls $P"_Alt"/ 2>/dev/null | grep -c '^5r5' || true"
$ADB shell "printf '  alt files: '; ls $P"_Alt"/ 2>/dev/null | wc -l"

echo
echo "reboot and re-check that the certificate chain survives:"
echo "  adb reboot && sleep 60 && ./tools/diag.sh --ui"
