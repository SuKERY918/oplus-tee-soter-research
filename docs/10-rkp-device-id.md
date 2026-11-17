# 10 RKP device ID 预配：Attestation key 持久恢复

补 05 的 `KmInstallKeybox` 一节。结论：**keybox 路线不持久，但只写 device ID 的 rkp 路线持久**，且能同时点亮工程模式的 `Attestation key` 与 `RKP default` 两行。

## 1. `KmInstallKeybox` 的参数形状

IDA 逆向 `/vendor/bin/KmInstallKeybox`（md5 `c71dac75fb76f458b28192161c239d1d`，263 函数，base 0）得到 main（`0x11a90`）：

```c
if ( a1 > 8 || ((1 << a1) & 0x1B0) == 0 )   // argc 只接受 4/5/7/8
```

- `argc==5` 取 `argv[4]`，`argc==8` 取 `argv[7]`；
- 判定 `v17 == 27506 && v18 == 112`，即小端 `'r','k'` + `'p'`，字符串 `rkp`（二进制里没有明文 `rkp`）；
- `ParseFile(this, a2: rkp)` 之后 `if ( v28 == 0 && (rkp || ValidateProvisionedKeys() == 0) )`，即 rkp 模式跳过密钥校验；
- rkp 分支用 `qmi_client_init_instance`/`qmi_client_send_msg_sync` 取 IMEI，`property_get` 读
  `ro.product.brand/device/name`、`ro.serialno`、`ro.product.manufacturer/model`，再 `KeyMasterProvisionDeviceId` +
  `SetProvisioningDeviceIdSuccess`；
- rkp 模式完全不读 keybox 文件，传不存在的路径也能成功。

实测输出：

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

参数形状的完整逆向见 [11](11-kminstallkeybox-internals.md)。

## 2. 与 keybox 路线的区别

| 路线 | 命令 | 结果 | 持久性 | persist 侧 |
| --- | --- | --- | --- | --- |
| keybox | `<xml> <id> true` | 无文件时 `InstallKeybox Failed!-2000` + `ERROR: Unable to open xml keyfile!` | 成功也不持久，HAL/TA 重启丢失 | 写 `5r5LgWqAGkK7pkbwDExz`（自签 key blob） |
| 只写 ID | `<xml> <id> true rkp` | `TEE done` + `InstallKeybox is done!` | **重启保持** | 重建槽位为 14 文件，**移除 `5r5`** |
| 仅 KEY | `<xml> <id> false` | `KeyMaster Attestation Key Provisioning success for KeyID...` | 见 04/05 | 写 `5r5` + `_Alt` |

persist 侧的实测差异（本次关键证据）：

- 写入前 `_Alt` 只有 2 个文件：`5r5LgWqAGkK7pkbwDExz`（12696 B，2026-11-16 22:00，即 11-16 那次 `... false` 烧入的自签 key）+ `DdHdVQd1…_Alt`（1588 B）；
- 12:24 写入后 `_Alt` 变为 14 个文件，**`5r5LgWqAGkK7pkbwDExz` 计数为 0**，剩下的是 `+Qs4yZ88j…`、`1YG3S3w9Ou…`、`zppz2LHaIf…` 等 device ID / attestation ID 相关文件；
- 原厂槽位 `DdHdVQd1…_` 未被触碰，`5r5LgWqAGkK7pkbwDExz` 仍是 12692 B、2025-10-30 06:46:51。

也就是说 rkp 模式不是"在原有槽位上追加 device ID"，而是**按 RKP 预配重建整个槽位**，把自签 key blob 一并清掉了。

## 3. 为什么能生效：三步叠加

12:24 写入后 KeyAttestation 仍报：

```
KeyStoreException: Invalid key blob
Caused by: security_level.rs:757: While generating with a user-generated attestation key, params: [...]
```

但错误参数里已经出现 `ATTESTATION_ID_BRAND/DEVICE/PRODUCT/MANUFACTURER/MODEL`，没有 `SERIAL`/`IMEI`/`MEID`，说明 device ID 部分已落盘。

完整恢复需要三步叠加，缺一不可：

1. **rkp 重建槽位**（12:24）：移除 `5r5LgWqAGkK7pkbwDExz`，TEE 不再有自签 key 可用；
2. **写入 device ID**（12:24）：`KeyMasterProvisionDeviceId` + `SetProvisioningDeviceIdSuccess`；
3. **清掉 app 侧旧 blob**（12:59）：`pm clear io.github.vvb2060.keyattestation`，否则 KeyAttestation 仍引用旧 key blob。

第 3 步单独执行无效（旧 blob 只是缓存，persist 里的自签 key 还在）；第 1、2 步单独执行后 app 仍报错（12:27 的 TEE 死锁也发生在这一步之后）。三步齐备后再启动，得到 5 段链：

- `f92009e853b6b045` → `e083083c1b64dda92158d939ed8a0fc0` → `9d7b56e9e07377aa2c0474226c7d3c71` → `CN=App Attest Key` → `CN=Android Keystore Key`；
- 两条叶子同一秒签发，说明新 key 走 RKP 远程预配成功。

`CN=Android Keystore Key` 的时间戳随每次重置/重签发更新，可作为「本次是否真签发」的判据。

## 4. 验证

工程模式 `com.oplus.engineermode/.security.RPMBStatusActivity`：

| 行 | 状态 |
| --- | --- |
| Attestation key | 成功（绿） |
| RKP default | 成功（绿） |
| SOTER key | 失败（红，`-20`） |

重启后 `_Alt` 保持 12:24 的 14 文件对，KeyAttestation 证书链仍在（叶子时间戳刷新为重启后时间），确认不是缓存假绿：应用侧独立验证了证书链，且时间戳在新 boot 里重新签发。

13:12 复核：每次点「使用认证密钥」，叶子 `CN=Android Keystore Key` 的 notBefore 都更新为当前时间，说明是当场向 RKP 取证，而不是复用旧链。

## 5. 副作用与回滚

- 只写 ID 不覆盖原厂 `DdHdVQd1…_` 槽位，也不改 `rpmb_status`；
- **rkp 写入会移除 `_Alt` 槽位里原有的 `5r5` key blob**（见 §2），这正是它区别于 keybox 路线的地方；
- 改动落在 RPMB/SFS，`dd` 回滚 persist 镜像会与 RPMB 状态不一致，**不要**用备份整盘写回；
- 删除 `_Alt` 目录不能撤销（key 已进 RPMB），与 wuxianlin 对一加 13 的结论一致；
- 不影响锁态下的出厂 Attestation key：原厂槽位未动，回锁后仍用原厂链；
- device ID 的值来自设备自身（IMEI/serial/型号），与产线登记一致，重新登记同一个值无实际差异。

## 6. 和 SOTER 的关系

这次修复只覆盖 KeyMint/keystore2 这条链（Google RKP）。SOTER 的 ATTK 是独立的 QTI `soter64` TA，解锁态下对 `generate/verify/export/get_device_id` 一律 `-20`，不受本路线影响，详见 04。
