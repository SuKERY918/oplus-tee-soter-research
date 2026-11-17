# 08 复现与恢复

以下命令仅在本机（Ace 6，KernelSU）验证。所有操作默认已 `adb root` 可用。

## 前置检查

```sh
adb shell 'id'
adb shell 'grep -o "oplusboot.verifiedbootstate=[a-z]*" /proc/cmdline'
adb shell 'stat -c "%y %s %n" /mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_/5r5LgWqAGkK7pkbwDExz'
```

第三条必须仍是出厂时间（本机为 `2025-10-30 06:46:51`、12692 B）。若时间已被改过，说明原厂 Attestation 槽位已被写过，不要继续。

## 刷新工程模式页

```sh
adb shell 'am force-stop com.oplus.engineermode'
adb shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity'
```

后台 bring-to-front 不会重新判定，必须 force-stop。

## RKP device ID 预配（Attestation / RKP 修复）

已验证的持久修复路径，详细原理见 [10](10-rkp-device-id.md)。

### 1. 写入 device ID

```sh
adb shell su -c 'LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox \
  /data/local/tmp/x PLQ110 true rkp'
```

`/data/local/tmp/x` 不需要真实存在 —— rkp 分支不读文件。`PLQ110` 是 Device ID 参数，取值不影响结果。

预期输出：

```
Imei: 867485083297890
Imei: 867485083297882
Brand: OnePlus
Device: OP6113L1
Product: PLQ110
SerialNum: 3B15AW00WGJ00000
Manufacturer: OnePlus
Model: PLQ110
TEE done
InstallKeybox is done!
```

### 2. 清掉 app 侧旧 blob

```sh
adb shell 'pm clear io.github.vvb2060.keyattestation'
adb shell 'am start -n io.github.vvb2060.keyattestation/.home.HomeActivity'
```

### 3. 验证

| 检查 | 期望 |
| --- | --- |
| KeyAttestation 证书链 | 5 段，末段 `CN=Android Keystore Key` |
| 叶子时间戳 | 与当前时间一致，且每次点「使用认证密钥」都会更新 |
| 工程模式 `Attestation key` | 成功 |
| 工程模式 `RKP default` | 成功 |
| `_Alt` 槽位 | 14 个文件，`5r5LgWqAGkK7pkbwDExz` 计数为 0 |
| 原厂 `_` 槽位 | `5r5LgWqAGkK7pkbwDExz` 时间戳未变 |
| 重启后 | 以上仍成立 |

一条命令看槽位是否符合预期：

```sh
adb shell 'echo -n "alt 5r5: "; ls /mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_Alt/ | grep -c "^5r5"; echo -n "orig 5r5: "; ls /mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_/ | grep -c "^5r5"'
```

### 4. 失败处理

- 仍报 `Invalid key blob`：再执行一次 `pm clear`，或重启后再试（本机第一次写入后 app 缓存未失效）。
- 设备失去 adb 响应（keystore2 在清理旧 blob 时 TEE 死锁）：长按电源键 10 秒强制重启。USB 层由 kernel 维持，软件侧无法恢复。
- `fail -2000` + `ERROR: Unable to open xml keyfile!`：说明第 5 参数不是 `rkp`，退回了 keybox 分支。

## keybox（失败路线，不要用于修复）

```sh
adb push keybox_norm.xml /data/local/tmp/
adb shell su -c 'LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox \
  /data/local/tmp/keybox_norm.xml PLQ110 false'
```

成功输出：

```
KeyMaster Attestation Key Provisioning success for KeyIDPLQ110
TEE done
InstallKeybox is done!
```

但本机重装仍打印成功、页面不绿，**不持久**：keybox 会写 `5r5LgWqAGkK7pkbwDExz` 到 `_Alt`，HAL/TA 重启后校验失败。这条路线仅用于观察，不要当作修复手段。

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

## 回滚

`... true rkp` 写入的 device ID 在 RPMB，**没有可用的回滚手段**：

- 删 `_Alt` 目录：TA 仍认为已 provision，attestation 依然可用；
- `dd` 回 persist 镜像：与 RPMB 记录不一致，可能触发 TA 清理槽位，比不回滚更糟；
- 原厂 `_` 槽位不受影响，回锁后仍用原厂链。

它不是密钥，是设备真实身份信息（IMEI/serial/型号），重新登记同一个值没有实际差异。详见 [10 §5](10-rkp-device-id.md#5-副作用与回滚)。

## 回锁前提

1. 备份（回锁清数据）；
2. 恢复官方 `init_boot`、`vbmeta`、`boot`、`vendor_boot`；
3. 槽位与固件版本一致；
4. `fastboot flashing lock`；
5. 开机验证 `soter-provision 2` 与微信指纹；
6. 需要 root 时用锁态临时漏洞（内核 build 必须匹配）。
