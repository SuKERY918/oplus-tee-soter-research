# 09 复现与恢复

以下命令只在本机（Ace 6，KernelSU）验证过。不同版本/机型不要直接套用。

## 刷新工程模式页

```sh
adb shell 'am force-stop com.oplus.engineermode'
adb shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity'
```

注意：Activity 在后台时重新 bring to front 不会重新判定，必须 force-stop 再启动，否则看到的是旧状态。

## 本地软件 SOTER TA（页面 SOTER 绿，微信不可用）

启动：

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
adb shell 'getprop init.svc.vendor.soter'   # 应为 running
```

**警告**：如果软件 TA 没有可用的 ASK/RPC，微信「支付设置 → 手机指纹识别」会卡死 146 秒。出现这种情况先杀 TA、恢复原厂。

## 模块方式（Ommega Local）

构建（在 PC 上）：

1. 复制 Ommega A 端发布包到 `a_local/`；
2. 改 `module.prop`：`id=ommega`、`name=Ommega Local (SOTER)`、`version=1.7.17-local`；
3. 在 `customize.sh` 生成的 `/data/misc/ommega/config` 里加 `soter_inject: 1`、`soter_service: 1`；
4. 重新打包 zip；
5. **必须更新 `customize.sh.sha256` 和 `module.prop.sha256`**，否则 ksud 报 `! Failed to verify customize.sh`；
6. sidecar 必须是纯 LF、UTF-8 无 BOM，PowerShell 的 `Set-Content` 会写 CRLF 导致校验失败。

安装：

```sh
adb push ommega_local.zip /data/local/tmp/test/
adb shell su -c '/data/adb/ksud module install /data/local/tmp/test/ommega_local.zip'
```

安装后模块在 `/data/adb/modules_update/ommega`，**重启后**才进入 `/data/adb/modules/ommega` 并生效。

禁用/恢复：

```sh
adb shell su -c 'touch /data/adb/modules/ommega/disable'
adb shell su -c 'rm -rf /data/adb/modules/ommega /data/adb/modules_update/ommega'
adb reboot
```

KSU 安全模式：开机时按住音量下，模块全部禁用。

## Attestation（keybox）

本机试过 `KmInstallKeybox`，能短暂写绿，但不持久。步骤仅作记录：

```sh
adb push keybox_norm.xml /data/local/tmp/test/
adb shell su -c 'LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox \
  /data/local/tmp/test/keybox_norm.xml PLQ110 false'
```

正常成功输出：

```
KeyMaster Attestation Key Provisioning success for KeyIDPLQ110
TEE done
InstallKeybox is done!
```

注意：

- keybox 必须是未吊销的、格式正确的（`<NumberOfCertificates>` 必须有，私钥统一 PKCS8）；
- 成功一次后正常不能重复 provisioning（除非 devcfg 开了 `allow_reprovision`）；
- 本机重复执行仍打印成功、但页面不绿，说明没有真正持久化；
- 不要使用来源不明的 keybox，不要把它提交到仓库。

## Frida 伪造 RKP（仅视觉）

```sh
adb shell su -c 'setsid /data/local/tmp/test/frida-server -D'
python fake61.py
```

脚本会 attach cryptoeng HAL，替换 `base+0x1415c` 的 dispatcher，cmd 61 直接返回 8 字节 0。页面 RKP default 变绿，并写入 `Settings.Global rkpdefault_import=1`。

## 恢复原厂

```sh
adb shell su -c 'touch /data/adb/modules/ommega/disable'
adb shell su -c 'pkill -f "ommega-inject --soterta-serve"'
adb shell su -c 'setprop ctl.start vendor.soter'
adb shell su -c 'setprop ctl.start vendor.keymint-qti'
adb shell 'getprop init.svc.vendor.soter; getprop init.svc.vendor.keymint-qti'
```

如果 keymint 服务死了：

```sh
adb shell su -c 'setsid /vendor/bin/hw/android.hardware.security.keymint-service-qti &'
```

如果 keystore2 异常：

```sh
adb shell su -c 'stop keystore2; start keystore2'
```

## 回锁（未在本机执行，仅列出必要前提）

1. 备份数据（回锁会清空）；
2. 恢复官方 `init_boot`（去掉 KernelSU patch）、`vbmeta`、`boot`、`vendor_boot`；
3. 确认当前槽位和固件版本一致；
4. `fastboot flashing lock`；
5. 开机后验证 `soter-provision 2` 与微信指纹；
6. 需要 root 时使用锁态临时漏洞（内核 build 必须匹配）。

**不要在没有原厂镜像的情况下回锁**，变砖风险很高。
