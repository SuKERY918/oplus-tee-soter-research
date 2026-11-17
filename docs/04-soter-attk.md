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

注意协议形状：SOTER 的 ASK/AuthKey blob 是 `[u32 LE JSON 长度][JSON][RSA-PSS 签名]`，不是 X.509 证书链；JSON 字段是 `pub_key`、`cpu_id`、`counter`、`uid`，部分实现还带 `rsa_pss_saltlen`。用自签证书去模拟，协议层就先偏了。本机导出的 ASK 是 805 B，真机抓包是 809 B，字段/盐长/键序值得继续对齐。

## 信任链与校验位置

SOTER 是三级密钥，决定成败的是最后一级校验：

| 层 | 生成位置 | 谁签名 | 谁校验 |
| --- | --- | --- | --- |
| ATTK | 产线 TEE，一机一密 | 厂商把公钥登记到腾讯 TAM | TAM |
| ASK | 设备 TEE（或软件 TA） | ATTK 私钥 | 应用服务器把签名交给 TAM 验 |
| AuthKey | 设备 TEE（或软件 TA） | ASK 私钥 | 应用服务器用 ASK 公钥验 |

- ASK 上报后，应用服务器自己无法验证，必须把 ATTK 签名交给 TAM；TAM 用产线登记的 ATTK 公钥验签，验过了应用服务器才保存 ASK 公钥。
- 自签 ATTK 不在 TAM 备案，所以 ASK 一定过不了；工程模式绿、`runCryptoCmd(57)==0`、甚至客户端暂时不报错，都不能证明微信会接受。
- `removeAllAuthKey`/`removeAllUidKey` 更像是服务端拒绝后的客户端清理，而不是本地链没拼好。

## 屏蔽还是清空

从 TA 固件侧能拿到更多线索。`soter64.b00…b08` 拼接后是 74,924 B 的 ELF64（`0x0-0xe7c8` rx + 四个 rw 段），
除上面已列的字符串外还有：

```
secboot device : %u
get_validated_attk
soter_sfs_check_file / soter_sfs_check_key / soter_sfs_read_file
soter_rpmb_alloc_read / update_soter_rpmb_header
rpmb_init
qsee_stor_device_init error ret: %d
SOTER_GENERATE_ATTK / SOTER_VERIFY_ATTK / SOTER_EXPORT_ATTK_PUBLIC / SOTER_GET_DEVICE_ID / SOTER_GET_VERSION
```

`is_secure_boot_enabled` 与 `BAILING OUT` 在初始化路径，`/persist/data/soter/`（`open_soter_partition` 的目标）
在设备上从未被创建 —— 支持「TA 在读 key 之前就退出」的屏蔽假说，而不是「ATTK 已被删除」。
但 `soter-provision 4`（get device ID，纯读）同样 `-20`，说明 TA 连设备 ID 都不给，用户态无法区分
「被 secboot 挡住」与「ATTK 不存在」。要坐实只能等锁态基线（07 阶段 A）或找到 TA 的补丁点。

## 结论

- TA 对 generate/verify/export 一律 `-20`，与 uid 无关；
- 用户态伪造 ASK/ATTK 会被微信立刻清理；
- 决定性校验在腾讯侧：ASK 上报 TAM 时，自签 ATTK 没有备案，服务端拒绝，客户端随后清 ASK/AuthKey。
