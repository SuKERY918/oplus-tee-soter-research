# 07 尝试记录

按时间顺序，把"试过什么、结果如何、为什么失败"记全。**失败原因写清楚比结果更重要**——后面的人可以据此跳过。

## 1. 总表

| 目标 | 办法 | 结果 | 结论 |
| --- | --- | --- | --- |
| SOTER key | 杀 teesim、`soter-provision 1..4` | 一律 -20 | 与 teesim 无关 |
| SOTER key | 本地软件 SOTER TA（Ommega） | 页面绿、ASK 能导出，微信 1 秒内删 key | TAM 不认自签 ATTK |
| Attestation key | `KmInstallKeybox` 写 keybox | 短暂绿，重启丢失 | 不持久 |
| Attestation / RKP | `KmInstallKeybox … true rkp` | **持久绿** | 唯一成功的修复，见 [09](09-rkp-attestation.md) |
| RKP default | Frida 伪造 cmd 61 返回 | 页面绿（缓存假绿） | 只骗 UI |
| Attestation | Tricky Store hook 证书链 | 可解 Attestation | 碰不到 SOTER |
| SOTER key | bind mount 替换 TA 读 RPMB | 改 1 字节即 `Error 12` | TEE 完整性校验，封死 |

## 2. 判断标准（写给后续实验）

- 工程模式绿、`cmd 57` 返回 0：**只说明本地 HAL 调用成功**，不能说明 TAM 或微信接受。
- 真实进展看：`soter-provision 1/2`、微信侧 `generateAskKeyPair` 的返回、`soter_status.xml` 的 `WechatASK`、是否出现 `removeAllAuthKey`/`removeAllUidKey`。
- 软件 TA 返回 ASK 后被秒清：优先怀疑 TAM 不认这把 ATTK（自签、未备案、与 `cpu_id` 不匹配），其次才是 JSON 字段、盐长、键序。
- ASK 与 AuthKey 必须同源；一半真机一半自签会出现自删自建或卡死。

## 3. KmInstallKeybox

```sh
LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox <keybox.xml> <DeviceID> <true|false> [rkp]
```

- argc 只接受 4/5/7/8；第 5 个参数为 `rkp` 时**不读 keybox 文件**，只做 device ID 预配（[10](10-kminstallkeybox.md)）。
- teesim 自带的 `keybox.xml` 直接喂 → `InstallKeybox::ParseFile+9668` 触发 `ubsan: sub-overflow` + SIGABRT。
- 自签 keybox → TA 返回 `KeyMasterInstallKeybox error-32`，rc=48。
- 规范化（PKCS8 私钥、PEM 证书、`DeviceID PLQ110`、补 `NumberOfCertificates`）后**能写入成功**：

```
KeyMaster Attestation Key Provisioning success for KeyIDPLQ110
TEE done
InstallKeybox is done!
```

Attestation 短暂变绿，但 HAL/TA 重启后又红，重装仍打印成功。日志：

```
security_level.rs:809: While generating without a provided attestation key
User consent required to communicate with remote provisioning server
```

- 只写 ID（`... <DeviceID> true rkp`）：不读文件也输出 `TEE done`，persist `_Alt` 重建为 14 文件对；`pm clear` 掉旧 blob 后 RKP 证书链持久生效 → 这是唯一成功的路径。

## 4. teesim

- `libteesim_keymint.so` 注入 **keystore2**（PID 1235），不注入 KeyMint HAL、不碰 cryptoeng / soter；
- 杀掉 teesim + 重启 keystore2 后 `soter-provision 1` 仍 `fail -20` → **不是 SOTER 失败原因**。

## 5. 本地软件 SOTER TA（Ommega）

```sh
setprop ctl.stop vendor.soter
OMMEGA_MODDIR=/data/adb/ommega \
OMMEGA_CONF_PATH=/data/misc/ommega/config \
OMMEGA_SOTER_SERVICE=vendor.qti.hardware.soter.ISoter/default \
  /data/local/tmp/test/ommega/ommega-inject --soterta-serve
```

现象：

- 服务注册成功，`cmd 57` 返回 0，页面 SOTER 绿；
- `soter-provision 2/3/4` 返回 0；
- 没有 ASK/RPC 时微信挂 146 秒；
- 补自签 ATTK 后能导出 805 字节的 ASK，**微信 1 秒内 `removeAllUidKey`**；
- `soter_asks.json` 反复出现 `"gone": {"ask:10405": "1"}`。

RPC 问题：`ommega-inject --daemon` 开机时 `keymint-daemon.pid` 里的 pid 被 `vendor.qti.psiclient@1.0-service` 复用，误判 `another instance is running; exiting`，`rpc.sock` 不存在。清 `keymint-daemon.lock`/`keymint-daemon.pid`/`rpc.peers` 可起，**但微信仍拒收自签链**。

为什么这条路本质上走不通：ATTK 的信任根在 TEE + TAM 服务端备案。软件 TA 只能伪造"本地签名成功"，产出的 ASK 上报后服务端一验就退。

## 6. fake61

`Interceptor.replace` cryptoeng 分发器（base + `0x1415c`）：cmd 61 写 8 字节 0、`*outlen = 8`、返回 0，其余透传。页面 RKP 变绿并写入 `rkpdefault_import=1`。**只骗 UI，不改任何真实状态。**

## 7. Tricky Store

hook keystore2 的证书链，可解 Attestation；碰不到 `cmd 57` 与 SOTER TA。

## 8. 微信卡死

```
W/libbinder.Binder(883): Binder transaction to com.tencent.soter.soterserver.ISoterService,
function: UNKNOWN_FUNCTION_NAME, code: 2, took 145983ms.
```

任何半成品软件 SOTER TA 都会让微信支付设置卡死——**这是"本地软件 TA"路线的实际代价**，实验时要有心理准备。

## 9. TA 替换实验（本轮新增，重要负面结论）

### 9.1 动机

如果能把 TA 换成"会帮我们读 RPMB 表"的版本，就能直接读出 count、device id、IV/TAG，从而证明或推翻[派生根假设](06-root-cause.md)。不刷写分区、可完全回滚。

### 9.2 环境事实

- `/vendor` 是 dm-verity 保护的 erofs 只读卷（`/dev/block/dm-20`）；
- `/vendor/firmware_mnt` 是 `modem_a` 分区（`/dev/block/sde6`），vfat `ro`，标签 `u:object_r:firmware_file:s0`；
- KernelSU 下 `mount --bind` 单文件可用；
- `ro.boot.veritymode=enforcing`。

### 9.3 注入通路（成立）

```sh
adb push patched_b01 /data/local/tmp/soter64.b01
adb shell 'chcon u:object_r:firmware_file:s0 /data/local/tmp/soter64.b01; chmod 644 /data/local/tmp/soter64.b01'
adb shell 'mount --bind /data/local/tmp/soter64.b01 /vendor/firmware_mnt/image/soter64.b01'
adb shell 'stop vendor.soter; sleep 1; start vendor.soter'
```

**必须改 SELinux 标签**，否则 HAL（`user system`）打不开：

```
E QSEECOMPAT: read_splitbin_tobuf: fail to open path=/vendor/firmware_mnt/image/soter64.b01
E QSEECOMPAT: QSEECom_start_app: load app failed with ret : -22
```

### 9.4 结果

| 实验 | 结果 |
| --- | --- |
| 放**原样副本** | 正常加载，`tx=14` 仍 `ffffffec`（-20），行为完全不变 → 通路有效 |
| 改 1 个字节（`b01[0x100] ^= 1`） | `E QSEECOMPAT: load_app:name soter64 Error 12` |
| 在 0x5AC 写 `bti c; movz w0,#0x1234; ret` | 同上 `Error 12`；HAL 打 `qseecom or SOTER TA not ready` + `req handle NULL`，`tx=6` 返回 -16 |
| 在真实入口 0x5B4 写同样补丁 | 同上 `Error 12` |

加载失败后构造函数回退到旧名 `soter`：

```
E QSEECOMPAT: read_file_tobuf: fail to open path=/vendor/firmware_mnt/image/soter.b00
E QSEECOMPAT: QSEECom_start_app: load app failed with ret : -22
```

→ HAL 侧表现为 `SoterUtils: qseecom or SOTER TA not ready`、`req handle NULL`、`tx` 返回 -16。

**更正一个曾经的错误判断**：第一轮补丁时看到 -16 就以为"补丁被执行、解锁态不做完整性校验"。实际上那次 -16 是 HAL 的"TA 未就绪"分支，**不是 TA 返回的**。撤回该结论。

### 9.5 `Error 12` 的机制：`.mdt` 哈希表 + OEM 签名

对 `soter64.mdt`（4,752 B）做哈希比对：

- 头部是完整 ELF 头（`7f454c46 … e_machine 0xB7 … e_phnum=9`），与 `soter64.b00` 一致；
- **偏移 0x358 起、步长 0x30，依次存 `b00`…`b07` 的 SHA-384**（各 48 B）：

| 偏移 | 覆盖对象 |
| --- | --- |
| 0x358 | b00 |
| 0x388 | b01（被补丁改的就是它） |
| 0x3b8 | b02 |
| 0x3e8 | b03 / b07（内容完全相同，b07 是 b03 的 RELRO 副本） |
| 0x418 | b04 |
| 0x448 | b05 |
| 0x478 | b06 |

- 0x4d8 之后是哈希表自身的摘要与 RSA 签名（0x510 附近可见 DER `3064 0230 42dd66…`），再往后是 OEM 证书链：`Guangdong`/`Shenzhen`、`OPLUS Technologies`、`OPLUS Attestation CA`、有效期 `240326125815Z`–`440321125815Z`（与 `b08` 内嵌链同源）；
- `b08`（4,184 B）**不是哈希表**，是证书/元数据段。

校验顺序：

```
TEE 内置 OEM 根公钥
   → 验 .mdt 的证书链与签名
   → 用 .mdt 里的 SHA-384 逐段比对 b00..b07
```

**改任何一个字节都会在第二关失败。** 要过校验必须重签 `.mdt`，需要 OPLUS/QTI 私钥——这不是"解锁就能绕过"的软件限制，而是密码学封闭。

### 9.6 回滚

```sh
adb shell 'umount /vendor/firmware_mnt/image/soter64.b01'
adb shell 'stop vendor.soter; sleep 1; start vendor.soter'
adb shell 'service call vendor.qti.hardware.soter.ISoter/default 14 i32 1'   # 应恢复 ffffffec
```

实测恢复后 `mount | grep soter64` 为空、`soter64.b01` 仍是 59,336 B / 2026-09-30 05:21 / `system system r--r-----`。

## 10. 厂商侧：解锁状态下 ATTK 写入被硬性拒绝

工程模式 APK 里有一套完整的工厂密钥预配实现（`KeyProvisionCommandHandler`，771 行），入口第一句就是闸门：

```java
private int generateAttkKeyResult() {
    if (SecurityInterface.isDeviceOemUnlocked()
            || !SecurityInterface.isSoterKeySupport()
            || SecurityInterface.verifyAttkKeyPair() == 0) {
        if (SecurityInterface.isDeviceOemUnlocked()) {
            Log.e(TAG, "generateAttkKeyPair: the device is unlocked so we cannot write key to it!!!");
            return 10000;                          // ERROR_CODE_ATTK_WRITE
        }
        Log.d(TAG, "soter key is not supported or already generated");
        return 0;
    }
    int r = SecurityInterface.generateAttkKeyPair(3);   // ATTK_COPY_NUM_DEFAULT = 3
    if (r != 0) { keyStatusLog("write ATTK failed!"); return 10000; }
    keyStatusLog("write ATTK successed!");
    return 0;
}
```

```java
// SecurityInterface.java:275-277
return !"locked".equals(SystemProperties.get("ro.boot.vbmeta.device_state", "unlocked"));
```

本机 `ro.boot.vbmeta.device_state = unlocked` → **直接 return 10000，TA 都不会被调用**。

同一 APK 还有 31 条 `--security_*` 工厂保留命令（`--generate_attk_key_pair`、`--verify_attk_key_pair`、`--export_attk_public_key`、`--get_device_id`、`--enable_rpmb`、`--install_keybox` …），投递链是系统服务 `engineer` → `EngineerShellCommandService`（`android.engineer.IEngineerRemoteService.sendCommand`）。`adb shell cmd engineer` 返回 `No shell command implementation`，普通 adb 无法投递。

**这条闸门是厂商的自证**：OPlus 自己就假定"解锁后不该再写 ATTK"。所以解锁后重建 SOTER 不是"漏掉了某个隐藏入口"，而是**被设计排除**的路径。
