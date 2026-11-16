# 02 工程模式 Key 状态页判定逻辑

## 页面定位

- Activity：`com.oplus.engineermode/.security.RPMBStatusActivity`
- APK：`/system_ext/app/OplusCommercialEngineerMode/OplusCommercialEngineerMode.apk`
- 反编译：jadx → `em_src/sources/com/oplus/engineermode/security/`

页面共 15 行：

```
Rpmb key
SOTER key
IFAA key
Crypto key
WidevineL1 key
HDCP key
Attestation key
FIDO key
PKI cert
PKI Group cert
FIDO2 key
RKP default
RKP widevine
StrongBox key
DP HDCP V2 key
```

颜色规则：`isSupport && !isKeyImported` 时显示红字 `key_status_fail`；其余情况一律绿字，所以「不支持」也是绿色。所谓「全绿」= 没有红行。

本机（Ace 6）页面是 15 行，`PKI Group cert` 为「成功」，`DP HDCP V2 key` 为「不支持」。

## 三行的真实来源

`KeyInstanceImpl`：

- `SOTERKey.isKeyImported()` → `SecurityInterface.verifyAttkKeyPair() == 0`
- `GoogleKey.isKeyImported()`（Attestation key）→ `SecurityInterface.isGoogleKeyImport()`
- `RkpDefaultKey.isKeyImported()` → `SecurityInterface.isRkpDefaultImported(context)`

`SecurityInterface`：

- `runCryptoCmd(byte cmd)`：把 `[cmd, 0, 0, 0]` 通过 `RpmbChannel.processCmdV2` 发给 `vendor.oplus.hardware.cryptoeng.ICryptoeng/default`（AIDL；失败回退 HIDL `vendor.oplus.hardware.cryptoeng@1.0`），读返回前 4 字节小端整数。
- `verifyAttkKeyPair()` = `runCryptoCmd((byte) 57)`
- `generateAttkKeyPair(int uid)` = cmd 58 + 4 字节 uid
- `isGoogleKeyImport()`：依次 `new KeyAttestationTest().testRsaAttestation()` 和 `testEcAttestation()`，异常即 false。
- `genRkpInfo(String name)`：cmd 61 + UTF-8 字符串（如 `"default\0"`），从返回偏移 4 读状态（0 成功），再从偏移 4 读字符串；成功后写 `Settings.Global` 的 `rkpdefault_import`。

`KeyAttestationTest`：

- RSA：512 bit、purpose 12（ENCRYPT|DECRYPT）、PKCS1、challenge `"challenge"`、带 validity 起止；
- EC：secp224r1、purpose 12；
- 之后 `KeyStore.getCertificateChain("test_key")` 并校验证书链签名，最后 `deleteEntry`。

因为参数组合很旧（512-bit RSA、secp224r1），真实 KeyMint TA 在解锁态下会直接拒绝。日志：

```
KeymasterUtils: IKMHal_sendCmd failed with rsp_header->status: -49
KeyMasterHalDevice keymint_generate_key ret: -49
KeyStoreException -49, Error::Km(r#SECURE_HW_COMMUNICATION_FAILED)
Failed on key size 512 challenge [challenge], purposes 12 and paddings [PKCS1]
```

## 假绿的机制

TA 失败时 cryptoeng HAL 可能返回空 buffer。`runCryptoCmd` 把空数组读成 int 0，于是 `verifyAttkKeyPair()` 返回 0，页面显示「SOTER 成功」——但同一时刻 `soter-provision 2` 仍然 `fail -20`。这是本机见到的「假绿」，说明**页面绿不等于 TA 真的通过**。

要判断真实状态，应同时看：

- `soter-provision 1/2` 的真实返回；
- `soter-provision` 的 logcat（`Generate ATTK send cmd failed` / `rsp->status: -20`）；
- 微信 `soter_status.xml` 的 `WechatASK`。

## RKP 的缓存

`SecurityInterface.isRkpDefaultImported` 在拿到 0 后会写 `Settings.Global rkpdefault_import=1`。之后即使 cryptoeng 又崩了，页面仍然读这个缓存显示「RKP default 成功」。用 Frida 伪造 cmd 61 返回 8 字节 0 就足以点亮这一行，并可跨 HAL 重启保持。

`RKP widevine` 在 Ace 6 上固定「不支持」；`StrongBox key`、`DP HDCP V2 key`、`HDCP key` 也是「不支持」。
