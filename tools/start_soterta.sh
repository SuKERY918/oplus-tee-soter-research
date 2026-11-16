#!/system/bin/sh
# Start Ommega's local software SOTER TA without installing the module.
#
# prerequisites:
#   - ommega-inject pushed to /data/local/tmp/test/ommega/ommega-inject
#   - /data/misc/ommega/config contains soter_inject: 1 and remote: off
#   - /data/misc/ommega/soter_attk.pem (RSA-2048 key + self-signed cert)
#
# warning: if there is no usable ASK/RPC, WeChat's payment settings will hang
# for ~146 s on exportAskPublicKey. Kill the TA and start vendor.soter again.

set -eu

INJECT=/data/local/tmp/test/ommega/ommega-inject
MODDIR=/data/adb/ommega
CONF=/data/misc/ommega/config
SERVICE=vendor.qti.hardware.soter.ISoter/default

mkdir -p "$MODDIR" /data/misc/ommega
chmod 755 "$INJECT"

setprop ctl.stop vendor.soter || true
sleep 1

OMMEGA_MODDIR="$MODDIR" \
OMMEGA_CONF_PATH="$CONF" \
OMMEGA_SOTER_SERVICE="$SERVICE" \
setsid "$INJECT" --soterta-serve >/data/local/tmp/test/soterta.log 2>&1 &

sleep 2
echo "started, log: /data/local/tmp/test/soterta.log"
echo "restore: pkill -f 'ommega-inject --soterta-serve'; setprop ctl.start vendor.soter"
