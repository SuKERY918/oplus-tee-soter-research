# 09 RKP device ID 预配：唯一已验证的持久修复

这是整个项目里**唯一一个"改了之后重启仍然有效"的修复**：工程模式的 `Attestation key` 与 `RKP default` 两行由红变绿，且与 SOTER 无关（[04](04-soter-service.md)）。

## 1. 一句话

`KmInstallKeybox <任意路径> <DeviceID> true rkp` —— 第五个参数 `rkp` 走一条**未文档化**的分支：不读 keybox 文件，只把设备身份（IMEI/序列号/型号）写成 RKP device ID。

## 2. 参数形状

```sh
LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox <keybox.xml> <DeviceID> <true|false> [rkp]
```

IDA 反编译 `/vendor/bin/KmInstallKeybox`（101,960 B，263 个函数），`main` @0x11a90 的第一条判断：

```c
if (a1 > 8 || ((1 << a1) & 0x1B0) == 0) { usage(); return 1; }
```

`0x1B0 = 0b110110000` → **argc 只接受 4、5、7、8**。

| argc | 用途 |
| --- | --- |
| 4 | keybox / 只写 ID（无 rkp） |
| 5 | keybox + `rkp` 模式 |
| 7 | Strongbox 单参数 |
| 8 | Strongbox + 第二组参数（`argv[7]` 也可以是 `rkp`） |

`argc == 5` 时检查 `argv[4]`，判定条件是**内联的逐字节比较**：

```c
v17 == 27506 && v18 == 112        // 27506 = 0x6B72，小端 'r','k'；112 = 'p'
```

即字符串 `rkp`。二进制里**没有明文 `rkp`**，`strings` 看不到——这就是这条路径一直没被发现的原因。

## 3. 为什么 rkp 分支能成功

```c
ParseFile(this, rkp);
if (v28 == 0 && (rkp || ValidateProvisionedKeys() == 0)) { ... }
```

`rkp == true` 时短路，**跳过 `ValidateProvisionedKeys()`**。原理解析：

1. `qmi_client_init_instance` / `qmi_client_send_msg_sync` 取 IMEI（双卡两条）；
2. `property_get` 读 `ro.product.brand`、`ro.product.device`、`ro.product.name`、`ro.serialno`、`ro.product.manufacturer`、`ro.product.model`；
3. `KeyMasterProvisionDeviceId(...)` 写入；
4. `SetProvisioningDeviceIdSuccess()` 置标志。

全程**不读 keybox 文件**，所以传一个不存在的路径也能成功。

实测输出（号码已脱敏）：

```
Imei: <imei1>
Imei: <imei2>
Brand: OnePlus
Device: OP6113L1
Product: PLQ110
SerialNum: <serial>
Manufacturer: OnePlus
Model: PLQ110
TEE done
InstallKeybox is done!
```

## 4. 与 keybox 路线的区别

| 路线 | 命令 | 结果 | 持久性 | persist 侧 |
| --- | --- | --- | --- | --- |
| keybox | `<xml> <id> true` | 成功打印 `InstallKeybox is done!` | **不持久**，HAL/TA 重启后丢失 | 写 `5r5LgWqAGkK7pkbwDExz`（自签 key blob） |
| 只写 ID | `<xml> <id> true rkp` | `TEE done` + `InstallKeybox is done!` | **重启保持** | `_Alt` 重建为 14 文件对，**移除 `5r5`** |
| 仅 KEY | `<xml> <id> false` | `KeyMaster Attestation Key Provisioning success for KeyID…` | 见上 | 写 `5r5` + `_Alt` |

persist 侧实测差异（关键证据）：

- 写入前 `_Alt` 只有 2 个文件：`5r5LgWqAGkK7pkbwDExz`（12,696 B，2026-11-16 22:00，即前一天 `... false` 烧进去的自签 key）+ `DdHdVQd1…_Alt`（1,588 B）；
- 写入后 `_Alt` 变成 14 个文件、**`5r5` 计数为 0**，剩下的是 `+Qs4yZ88j…`、`1YG3S3w9Ou…`、`zppz2LHaIf…` 等 device ID / attestation ID 相关文件；
- 原厂槽位 `DdHdVQd1…_` 未被触碰，`5r5` 仍是 12,692 B / 2025-10-30 06:46:51。

也就是说 rkp 模式不是"追加 device ID"，而是**按 RKP 预配重建整个 overlay 槽位**，把自签 key blob 一并清掉。

## 5. 为什么能生效：三步叠加，缺一不可

写入后 KeyAttestation 仍报：

```
KeyStoreException: Invalid key blob
Caused by: security_level.rs:757: While generating with a user-generated attestation key, params: [...]
```

但错误参数里已经出现 `ATTESTATION_ID_BRAND/DEVICE/PRODUCT/MANUFACTURER/MODEL`，没有 `SERIAL`/`IMEI`/`MEID` → device ID 部分已落盘。

完整恢复需要三步：

1. **rkp 重建槽位**：移除 `5r5`，TEE 不再有自签 key 可用；
2. **写入 device ID**：`KeyMasterProvisionDeviceId` + `SetProvisioningDeviceIdSuccess`；
3. **清掉 app 侧旧 blob**：`adb shell pm clear io.github.vvb2060.keyattestation`。

第 3 步单独执行无效（旧 blob 只是缓存，persist 里的自签 key 还在）；第 1、2 步单独执行后 app 仍报错。三步齐备后得到 5 段链：

```
f92009e853b6b045 → e083083c1b64dda92158d939ed8a0fc0 → 9d7b56e9e07377aa2c0474226c7d3c71 → CN=App Attest Key → CN=Android Keystore Key
```

两条叶子同一秒签发 → 新 key 走 RKP 远程预配成功。`CN=Android Keystore Key` 的 notBefore 随每次重签发更新，可作为"本次是否真签发"的判据。

## 6. 验证与持久性

工程模式：

| 行 | 状态 |
| --- | --- |
| Attestation key | 成功 |
| RKP default | 成功 |
| SOTER key | 失败（-20，与本修复无关） |

重启后 `_Alt` 保持那 14 个文件对，KeyAttestation 证书链仍在（叶子时间戳刷新为重启后时间）→ 不是缓存假绿，应用侧独立验证过证书链，且新 boot 里重新签发。

## 7. 副作用与回滚

- 只写 ID **不覆盖**原厂 `DdHdVQd1…_` 槽位，也不改 `rpmb_status`；
- rkp 写入会**移除 `_Alt` 里原有的 `5r5` key blob**，这正是它区别于 keybox 路线的地方；
- 改动落在 SFS/RPMB 层，`dd` 回滚 persist 镜像会与 RPMB 状态不一致，**不要**用备份整盘写回；
- 删除 `_Alt` 目录不能撤销（key 已进 RPMB）；
- 不影响出厂 Attestation key：原厂槽位未动，回锁后仍用原厂链；
- device ID 的值来自设备自身，与产线登记一致，重复登记同一值无实际差异。

## 8. 和 SOTER 的关系

**没有关系。** 这次修复只覆盖 KeyMint/keystore2 这条链（Google RKP）。SOTER 的 ATTK 是独立的 QTI `soter64` TA，解锁后对 `generate/verify/export/get_device_id` 一律 -20，不受本路线影响。

如果有人告诉你"跑一下 `KmInstallKeybox … rkp` 就能修 SOTER"，那是把两条链混为一谈。
