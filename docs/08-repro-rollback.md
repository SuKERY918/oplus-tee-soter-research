# 08 复现与恢复

以下命令仅在本机（Ace 6，KernelSU）验证。

## 刷新工程模式页

```sh
adb shell 'am force-stop com.oplus.engineermode'
adb shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity'
```

后台 bring-to-front 不会重新判定，必须 force-stop。

## 本地软件 SOTER TA

```sh
adb shell su -c 'setprop ctl.stop vendor.soter'
adb shell su -c 'OMMEGA_MODDIR=/data/adb/ommega \
  OMMEGA_CONF_PATH=/data/misc/ommega/config \
  OMMEGA_SOTER_SERVICE=vendor.qti.hardware.soter.ISoter/default \
  nohup /data/local/tmp/test/ommega/ommega-inject --soterta-serve >/dev/null 2>&1 &'
```

恢复：

```sh
adb shell su -c 'pkill -f "ommega-inject --soterta-serve"'
adb shell su -c 'setprop ctl.start vendor.soter'
adb shell 'getprop init.svc.vendor.soter'
```

无 ASK/RPC 时微信会卡 146 秒，先杀 TA 再恢复原厂。

## 模块方式

1. 复制 Ommega A 端发布包到 `a_local/`；
2. 改 `module.prop`：`id=ommega`、`name=Ommega Local (SOTER)`、`version=1.7.17-local`；
3. `customize.sh` 的 config 加 `soter_inject: 1`、`soter_service: 1`；
4. 重新打包；
5. 更新 `customize.sh.sha256`、`module.prop.sha256`（纯 LF、UTF-8 无 BOM，否则 ksud 报 `! Failed to verify customize.sh`）。

```sh
adb push ommega_local.zip /data/local/tmp/test/
adb shell su -c '/data/adb/ksud module install /data/local/tmp/test/ommega_local.zip'
```

模块先进 `/data/adb/modules_update/ommega`，重启后生效。

禁用：

```sh
adb shell su -c 'touch /data/adb/modules/ommega/disable'
adb shell su -c 'rm -rf /data/adb/modules/ommega /data/adb/modules_update/ommega'
adb reboot
```

KSU 安全模式：开机按住音量下。

## keybox

```sh
adb push keybox_norm.xml /data/local/tmp/test/
adb shell su -c 'LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox \
  /data/local/tmp/test/keybox_norm.xml PLQ110 false'
```

成功输出：

```
KeyMaster Attestation Key Provisioning success for KeyIDPLQ110
TEE done
InstallKeybox is done!
```

本机重装仍打印成功但页面不绿，未持久化。

## fake61

```sh
adb shell su -c 'setsid /data/local/tmp/test/frida-server -D'
python fake61.py
```

attach cryptoeng HAL，替换 `base+0x1415c`，cmd 61 返回 8 字节 0；页面 RKP 绿并写 `rkpdefault_import=1`。

## 恢复原厂

```sh
adb shell su -c 'touch /data/adb/modules/ommega/disable'
adb shell su -c 'pkill -f "ommega-inject --soterta-serve"'
adb shell su -c 'setprop ctl.start vendor.soter'
adb shell su -c 'setprop ctl.start vendor.keymint-qti'
adb shell 'getprop init.svc.vendor.soter; getprop init.svc.vendor.keymint-qti'
```

keymint 死了：

```sh
adb shell su -c 'setsid /vendor/bin/hw/android.hardware.security.keymint-service-qti &'
```

keystore2 异常：

```sh
adb shell su -c 'stop keystore2; start keystore2'
```

## 回锁前提

1. 备份（回锁清数据）；
2. 恢复官方 `init_boot`、`vbmeta`、`boot`、`vendor_boot`；
3. 槽位与固件版本一致；
4. `fastboot flashing lock`；
5. 开机验证 `soter-provision 2` 与微信指纹；
6. 需要 root 时用锁态临时漏洞（内核 build 必须匹配）。
