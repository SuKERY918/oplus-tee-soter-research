# 10 RKP device ID 预配：Attestation key 持久恢复

补 05 的 KmInstallKeybox 一节。结论：**keybox 路线不持久，但只写 device ID 的 rkp 路线持久**，且能同时点亮工程模式的
`Attestation key` 与 `RKP default` 两行。

## 1. KmInstallKeybox 的参数形状

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

## 2. 与 keybox 路线的区别

| 路线 | 命令 | 结果 | 持久性 |
| --- | --- | --- | --- |
| keybox | `<xml> <id> true` | `InstallKeybox Failed!-2000` + `ERROR: Unable to open xml keyfile!`（无文件时） | 成功也不持久，HAL/TA 重启丢失 |
| 只写 ID | `<xml> <id> true rkp` | `TEE done` + `InstallKeybox is done!` | **重启保持** |
| 仅 KEY | `<xml> <id> false` | `KeyMaster Attestation Key Provisioning success for KeyID...` | 见 04/05 |

persist 侧：`/mnt/vendor/persist/data/DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_Alt` 从只有 2 个文件
（`5r5LgWqAGkK7pkbwDExz` 12696 + `DdHdVQd1..._Alt` 1588，2026-11-16 22:00，即此前只烧过 Key）
变为完整 14 个文件对（2026-11-17 12:24），原厂 `DdHdVQd1..._` 槽位不动（仍 2025-10-30）。

## 3. 清掉旧 blob 才能生效

写完 ID 后 KeyAttestation 仍报：

```
KeyStoreException: Invalid key blob
Caused by: security_level.rs:757: While generating with a user-generated attestation key, params: [...]
```

但错误参数里已经出现 `ATTESTATION_ID_BRAND/DEVICE/PRODUCT/MANUFACTURER/MODEL`，没有 `SERIAL`/`IMEI`/`MEID`，
说明 ID 部分已落盘。此时 `pm clear io.github.vvb2060.keyattestation` 再启动：

- 证书链 5 段：`f92009e853b6b045` → `e083083c1b64dda92158d939ed8a0fc0` → `9d7b56e9e07377aa2c0474226c7d3c71`
  → `CN=App Attest Key` → `CN=Android Keystore Key`；
- 两条叶子同一秒签发，说明旧 blob 是唯一障碍，新 key 走 RKP 远程预配成功。

`CN=Android Keystore Key` 一节的时间戳随每次重置/重签发更新，可作为"本次是否真签发"的判据。

## 4. 验证

工程模式 `com.oplus.engineermode/.security.RPMBStatusActivity`：

| 行 | 状态 |
| --- | --- |
| Attestation key | 成功（绿） |
| RKP default | 成功（绿） |
| SOTER key | 失败（红） |

重启后 `persist` 的 `_Alt` 保持 12:24 的 14 文件对，KeyAttestation 证书链仍在（叶子时间戳刷新为重启后时间），
确认不是缓存假绿：应用侧独立验证了证书链，且时间戳在新 boot 里重新签发。

## 5. 副作用与回滚

- 只写 ID 不覆盖原厂 `DdHdVQd1..._` 槽位，也不改 `rpmb_status`；
- 改动落在 RPMB/SFS，`dd` 回滚 persist 镜像会与 RPMB 状态不一致，**不要**用备份整盘写回；
- 删除 `_Alt` 目录不能撤销（key 已进 RPMB），与 wuxianlin 对一加 13 的结论一致；
- 不影响锁态下的出厂 Attestation key：原厂槽位未动，回锁后仍用原厂链。

## 6. 和 SOTER 的关系

这次修复只覆盖 KeyMint/keystore2 这条链（Google RKP）。SOTER 的 ATTK 是独立的 QTI `soter64` TA，
解锁态下对 `generate/verify/export/get_device_id` 一律 `-20`，不受本路线影响，详见 04。
