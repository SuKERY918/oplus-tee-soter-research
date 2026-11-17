# 05 尝试记录

## 总表

| 目标行 | 依赖 | 办法 | 结果 |
| --- | --- | --- | --- |
| SOTER key | `soter64` TA（cmd 57） | 杀 teesim、`soter-provision`、软件 SOTER TA | 原厂一律 -20；软件 TA 骗过页面，但 ASK 上报 TAM 被拒（自签 ATTK 无备案） |
| Attestation key | KeyMint + keystore2 | `KmInstallKeybox` | 短暂变绿，HAL/TA 重启后丢失 |
| RKP default | cryptoeng cmd 61 | Frida 伪造返回 | 页面绿，靠 `rkpdefault_import` 缓存 |

## 判断标准

- 工程模式绿、cmd 57 返回 0：只说明本地 HAL 调用成功，不能说明微信接受。
- 真实进展看：`soter-provision 1/2`、微信 `generateAskKeyPair` 返回、`soter_status.xml` 的 `WechatASK`、是否出现 `removeAllAuthKey`/`removeAllUidKey`。
- 本地软件 TA 返回 ASK 后被秒清：优先怀疑 TAM 不认这把 ATTK（自签、未备案、或与 `cpu_id` 不匹配），其次才是 JSON 字段、盐长和键序。
- ASK 与 AuthKey 必须同源；一半走真机、一半走本地自签，会出现自删自建或卡死。

## KmInstallKeybox

```
LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox <keybox.xml> <DeviceID> <true|false> [rkp]
```

- argc 只接受 4/5/7/8；第 5 个参数为 `rkp` 时只做 device ID 预配，不读 keybox 文件。
- teesim 自带 `keybox.xml` 直接喂：`InstallKeybox::ParseFile+9668` 触发 `ubsan: sub-overflow` + SIGABRT。
- 自签 keybox：TA 返回 `KeyMasterInstallKeybox error-32`，rc=48。
- 规范化 teesim keybox（PKCS8 私钥、PEM 证书、DeviceID `PLQ110`、补 `NumberOfCertificates`）后成功：

```
KeyMaster Attestation Key Provisioning success for KeyIDPLQ110
TEE done
InstallKeybox is done!
```

Attestation 变绿。但 HAL/TA 重启后又红；重装仍打印成功、页面照旧。日志：

```
security_level.rs:809: While generating without a provided attestation key
User consent required to communicate with remote provisioning server
```

- 只写 ID（`... <DeviceID> true rkp`）：不读文件也输出 `TEE done` + `InstallKeybox is done!`，persist 的
  `_Alt` 槽位重建为完整 14 文件对；`pm clear` 掉旧 blob 后 RKP 证书链持久生效、重启保持，工程模式 Attestation key
  与 RKP default 同时变绿，见 [10](10-rkp-device-id.md)。

## teesim

- `libteesim_keymint.so` 注入 **keystore2**（PID 1235），不注入 KeyMint HAL，不碰 soter；
- `kill` teesim + 重启 keystore2 后 `soter-provision 1` 仍 `fail -20`。

## 本地软件 SOTER TA

```sh
setprop ctl.stop vendor.soter
OMMEGA_MODDIR=/data/adb/ommega \
OMMEGA_CONF_PATH=/data/misc/ommega/config \
OMMEGA_SOTER_SERVICE=vendor.qti.hardware.soter.ISoter/default \
  /data/local/tmp/test/ommega/ommega-inject --soterta-serve
```

- 服务注册成功，cmd 57 返回 0，页面 SOTER 绿；
- `soter-provision 2/3/4` 返回 0；
- 无 ASK/RPC 时微信挂 146 秒；
- 补自签 ATTK 后导出 805 字节，微信 1 秒内 `removeAllUidKey`；
- `soter_asks.json` 反复出现 `"gone": {"ask:10405": "1"}`。

RPC 问题：`ommega-inject --daemon` 开机时 `keymint-daemon.pid` 里的 pid 被 `vendor.qti.psiclient@1.0-service` 复用，误判 `another instance is running; exiting`，`rpc.sock` 不存在。清 `keymint-daemon.lock`/`keymint-daemon.pid`/`rpc.peers` 可起，但微信仍拒收自签链。

## fake61

`Interceptor.replace` cryptoeng dispatcher（base + `0x1415c`）：cmd 61 写 8 字节 0、`*outlen=8`、返回 0，其余透传。页面 RKP 变绿并写入 `rkpdefault_import=1`。

## Tricky Store

hook keystore2 证书链，可解决 Attestation；碰不到 cmd 57 / SOTER TA。

## 微信卡死

```
W/libbinder.Binder(883): Binder transaction to com.tencent.soter.soterserver.ISoterService,
function: UNKNOWN_FUNCTION_NAME, code: 2, took 145983ms.
```

任何半成品软件 SOTER TA 都会让微信支付设置卡死。
