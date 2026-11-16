# 02 工程模式 Key 状态页

- Activity：`com.oplus.engineermode/.security.RPMBStatusActivity`
- APK：`/system_ext/app/OplusCommercialEngineerMode/OplusCommercialEngineerMode.apk`

15 行：

```
Rpmb key / SOTER key / IFAA key / Crypto key / WidevineL1 key / HDCP key
Attestation key / FIDO key / PKI cert / PKI Group cert / FIDO2 key
RKP default / RKP widevine / StrongBox key / DP HDCP V2 key
```

颜色：`isSupport && !isKeyImported` → 红；其余（含「不支持」）绿。「全绿」= 没有红行。

## 三个关键行的实现

| 行 | 调用链 |
| --- | --- |
| SOTER key | `KeyInstanceImpl.SOTERKey.isKeyImported()` → `SecurityInterface.verifyAttkKeyPair()` = `runCryptoCmd(57) == 0` |
| Attestation key | `GoogleKey.isKeyImported()` → `isGoogleKeyImport()` → `KeyAttestationTest.testRsaAttestation()` + `testEcAttestation()` |
| RKP default | `RkpDefaultKey.isKeyImported()` → `isRkpDefaultImported()` → `genRkpInfo("default")`（cmd 61） |

## cryptoeng 命令

`runCryptoCmd(byte cmd)` 把 `[cmd,0,0,0]` 发给 `vendor.oplus.hardware.cryptoeng.ICryptoeng/default`（失败回退 HIDL `@1.0`），读返回前 4 字节小端 int。

| cmd | 用途 | 本机结果 |
| --- | --- | --- |
| 57 | `verifyAttkKeyPair` | TA `-20`（页面假绿时为 0） |
| 58 | `generateAttkKeyPair` + 4 字节 uid | `-1000` |
| 61 | `genRkpInfo` + UTF-8 名字 | 杀死 cryptoeng HAL |

`genRkpInfo` 从返回偏移 4 读状态，成功后写 `Settings.Global rkpdefault_import`。

## KeyAttestationTest

- RSA 512 bit、purpose 12、PKCS1、challenge `"challenge"`；
- EC secp224r1、purpose 12；
- `getCertificateChain("test_key")` 验链后 `deleteEntry`。

TA 在解锁态直接拒绝：

```
IKMHal_sendCmd failed with rsp_header->status: -49
keymint_generate_key ret: -49
KeyStoreException -49, Error::Km(r#SECURE_HW_COMMUNICATION_FAILED)
```

## 假绿

TA 失败时 HAL 返回空 buffer，`runCryptoCmd` 把空数组读成 0 → `verifyAttkKeyPair()` 返回 0 → 页面「SOTER 成功」，同时 `soter-provision 2` 仍是 `fail -20`。

判定真实状态要看 `soter-provision 1/2`、它的 logcat（`rsp->status: -20`）和微信 `soter_status.xml` 的 `WechatASK`。

## 缓存

`rkpdefault_import=1` 写入后，即使 cmd 61 崩溃，页面仍显示「RKP default 成功」。Frida 伪造 cmd 61 返回 8 字节 0 即可点亮，且跨 HAL 重启保持。
