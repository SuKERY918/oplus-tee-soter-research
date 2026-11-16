# 04 SOTER、ATTK 与微信指纹

## SOTER 服务

- 进程：`/vendor/bin/hw/vendor.qti.hardware.soter-service`（52,000 B）
- 服务名：`vendor.qti.hardware.soter.ISoter/default`（AIDL）
- 实现库：`/vendor/lib64/hw/vendor.qti.hardware.soter-impl.so`（84,712 B）、`vendor.qti.hardware.soter-V1-ndk.so`
- TA：`soter64`，从 `/vendor/firmware_mnt/image/soter64.b00 … b08` + `soter64.mdt` 加载
- HAL 只是 QSEECom 的薄代理，真正的状态在 TA 里

`/vendor/bin/vendor.qti.hardware.soter-provision` 是 SOTER 客户端：

| 命令 | 含义 | 本机结果 |
| --- | --- | --- |
| 1 | Generate ATTK key pair | `fail -20`，rc=236 |
| 2 | Verify ATTK key pair | `fail -20`，rc=236 |
| 3 | Export ATTK public key | `fail -20`，rc=236 |
| 4 | Get device ID | `fail -20`，rc=236 |

以 uid 0、1000、2000 运行结果一致；logcat：

```
generateAttkKeyPair called
Generate ATTK send cmd failed
rsp->status: -20
```

即 TA 侧拒绝，与调用者权限无关。

## soter64 TA 的字符串证据

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

TA 只检查 secure boot / RPMB，没有「BL 是否解锁」的直接判断。它的 `-20` 可能来自：

- SOTER 分区不存在/损坏；
- RPMB 未 provision，写不进去；
- secure boot 状态下 RPMB 报错，走 `BAILING OUT` 分支。

`/mnt/vendor/persist/data/soter` 不存在；手工创建（system:system 0700）后重试仍然 `-20`，TA 不会往这个目录写。`/mnt/vendor/persist/data` 下的 QSEE SFS 分区目录名是哈希（`DdHdVQd1…`、`Dq7aMh5g…`、`iOLM5D7…`），`vTable` 里也只有哈希名；用 `sha256("SOTER")`、`sha256("soter")`、`sha256("ATTK")` 都匹配不上，无法定位 SOTER 分区。

## 微信侧的调用链

微信开通指纹支付的路径：

```
钱包 → 支付设置 → 手机指纹识别
  → WalletCheckPwdUI（支付密码）
  → FingerPrintAuthUI（指纹）
  → 失败弹窗：“系统错误，可删除系统指纹，重新录入后再试。如未解决，请咨询手机厂商”
```

logcat：

```
I/SoterService: generateAppSecureKey in
start soterService generateAppSecureKey aidl
FgenerateAskKeyPair called
Generate ASK send cmd failed
rsp->status: -20
generateAppSecureKey errcode:-20
```

之后 `hasAskAlready`、`hasAuthKey`、`removeAllAuthKey` 都返回 `-5`。

微信自己的状态文件：

`/data/data/com.tencent.mm/shared_prefs/soter_status.xml`

```xml
<map>
    <int name="WechatASK" value="0" />
    <int name="SoterAuthKeyV2_salt523665d5_scene1" value="0" />
</map>
```

即从未成功生成过 ASK。

## 本地软件 SOTER TA 实验

用 Ommega 的 `ommega-inject --soterta-serve` 顶替原厂 `vendor.soter` 后：

1. 工程模式页 `cmd 57` 返回 0，SOTER 行变绿；
2. `soter-provision 2/3/4` 返回 `fail 0`（工具会打印 `fail`，0 表示成功）；
3. 微信第一次点开关时卡死 146 秒，因为本地 TA 没有 ASK/RPC，`exportAskPublicKey` 等 30 秒后透传给已停止的原厂 HAL；
4. 补上自签 ATTK 和 ASK 后，`exportAskPublicKey` 返回 805 字节 envelope，但微信在 1 秒内就：

```
removeAllAuthKey(uid=10405)
removeAllUidKey(uid=10405)
soter_asks.json: "gone": {"ask:10405": "1"}
```

自签 ATTK 的内容：

```
subject/issuer: O=Ommega, CN=Ommega Local ATTK
basicConstraints: CA:TRUE
signature: sha256WithRSA (RSA-2048)
```

结论：微信在本地就校验证书链，自签 ATTK 被拒；即使本地骗过，开通/支付最终还要腾讯服务端接受这条链。

## SoterChecker 的判词

作者配图里的 SoterChecker（[Andrea-lyz/SoterChecker](https://github.com/Andrea-lyz/SoterChecker)）不是只看包名，它会：

- 检查 Soter 组件可见性、可绑定、`bindService`、APK 路径/SHA-256、目录项、oat/vdex；
- 调 `com.tencent.soter.soterserver.ISoterService` 的完整调用矩阵；
- 校验 ASK ← ATTK（有 ATTK 公钥时）→ AuthKey 的证书链，自实现 EMSA-PSS/SHA-256；
- 检查键集、键序、raw/challenge、计数器单调。

作者截图判「干净 / 32 通过 · 0 失败 · 2 警告」，说明在他手机上 SOTER 事务与签名链和活 TA 一致。这比工程模式页的弱检查强得多，也说明他的 SOTER 不是简单 stub。

README 明确写了边界：「腾讯服务端的设备登记与真 ATTK 签名不在范围内：本地自洽 ≠ 服务端接受」。

## 本机结论

- TA 对 SOTER 的 generate/verify/export 一律 -20，且不依赖调用者 uid；
- 运行时无法通过 HAL 改锁态；
- 用户态伪造 ASK/ATTK 会被微信立刻清理；
- 因此本机要真正开启微信指纹，前提是 TEE 侧 SOTER 可用（回锁恢复，或拿到腾讯信任的 ATTK）。
