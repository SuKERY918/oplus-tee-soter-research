# 04 SOTER / ATTK

## 服务

- 进程：`/vendor/bin/hw/vendor.qti.hardware.soter-service`
- 服务名：`vendor.qti.hardware.soter.ISoter/default`（AIDL）
- 实现库：`/vendor/lib64/hw/vendor.qti.hardware.soter-impl.so`
- TA：`soter64`（`/vendor/firmware_mnt/image/soter64.b00…b08`）
- HAL 只是 QSEECom 薄代理

`soter-provision`：

| 命令 | 结果 |
| --- | --- |
| 1 Generate ATTK | `fail -20`，rc=236 |
| 2 Verify ATTK | `fail -20`，rc=236 |
| 3 Export ATTK pubkey | `fail -20`，rc=236 |
| 4 Get device ID | `fail -20`，rc=236 |

uid 0/1000/2000 一致。

```
generateAttkKeyPair called
Generate ATTK send cmd failed
rsp->status: -20
```

## soter64 字符串

```
ATTK already provisioned or RPMB not provisioned
Error: ATTK not provisioned
ATTK status:0x%x, expected:0x%x
SOTER: ATTK not set
Magic matches but attk invalid
is_secure_boot_enabled
!!! secboot device && rpmb error, BAILING OUT !!!
open_soter_partition
Successfully added SOTER partition: %u
/persist/data/soter/
```

`/mnt/vendor/persist/data/soter` 不存在；手工创建（system:system 0700）后仍 `-20`，TA 不写该目录。`/mnt/vendor/persist/data` 下 QSEE SFS 目录是哈希名（`DdHdVQd1…` 等），`vTable` 也只有哈希名，`sha256("SOTER"/"soter"/"ATTK")` 均不匹配。

## 微信调用链

```
钱包 → 支付设置 → 手机指纹识别
  → WalletCheckPwdUI
  → FingerPrintAuthUI
  → 弹窗「系统错误，可删除系统指纹，重新录入后再试」
```

```
I/SoterService: generateAppSecureKey in
start soterService generateAppSecureKey aidl
FgenerateAskKeyPair called
Generate ASK send cmd failed
rsp->status: -20
generateAppSecureKey errcode:-20
```

`hasAskAlready` / `hasAuthKey` / `removeAllAuthKey` 均 `-5`。

`/data/data/com.tencent.mm/shared_prefs/soter_status.xml`：

```xml
<int name="WechatASK" value="0" />
<int name="SoterAuthKeyV2_salt523665d5_scene1" value="0" />
```

## 本地软件 TA

`ommega-inject --soterta-serve` 顶替原厂 `vendor.soter`：

1. cmd 57 返回 0，页面 SOTER 变绿；
2. `soter-provision 2/3/4` 返回 `fail 0`；
3. 无 ASK/RPC 时微信卡 146 秒（`exportAskPublicKey` 等 30 秒后透传）；
4. 补自签 ATTK + ASK 后，导出 805 字节，微信 1 秒内：

```
removeAllAuthKey(uid=10405)
removeAllUidKey(uid=10405)
soter_asks.json: "gone": {"ask:10405": "1"}
```

自签 ATTK：

```
subject/issuer: O=Ommega, CN=Ommega Local ATTK
basicConstraints: CA:TRUE
signature: sha256WithRSA (RSA-2048)
```

## 结论

- TA 对 generate/verify/export 一律 `-20`，与 uid 无关；
- 用户态伪造 ASK/ATTK 会被微信立刻清理；
- 微信在本地校验证书链，自签 ATTK 被拒。
