# 11 KmInstallKeybox 逆向与 persist 槽位格式

`/vendor/bin/KmInstallKeybox` 是 OEM 预装的 Attestation Key 烧录工具，一加/OPPO 机型上同时支持 **keybox 写入** 和 **device ID 预配** 两条路径。本文记录静态分析的结论，以及 persist 侧 SFS 槽位的文件格式，作为 [10](10-rkp-device-id.md) 的底层补充。

## 1. 样本信息

| 项 | 值 |
| --- | --- |
| 路径 | `/vendor/bin/KmInstallKeybox` |
| 大小 | 101,960 B |
| 类型 | ELF64 ARM64 PIE |
| md5 | `c71dac75fb76f458b28192161c239d1d` |
| sha256 | `6395f3c47dbbcbc2261b8164cece51d9a7775a997b011e662d31a4d0470be9f8` |
| BuildID | `dd6a662b0b3269f62574f685f522d951` |
| 函数数 | 263（IDA auto-analysis） |
| imagebase | `0x0`，`image_size = 0x18420` |

相关文件：

- `/vendor/bin/StoreKeybox`（51,888 B）— Widevine Key Provisioning Tool，用法 `StoreKeybox /data/keybox.bin`，与本工具无关；
- `/vendor/lib64/hw/` 下的 keymint HAL 库 — 提供 `KeyMasterInstallKeybox`、`KeyMasterProvisionDeviceId` 等实现；
- `/odm/lib64/libqsee_keybox_ca.so` — QSEE keybox CA。

## 2. main 的控制流

入口 `main = 0x11a90`，CFI 跳板 `main_cfi = 0xde4c`。第一条有效判断：

```c
if ( a1 > 8 || ((1 << a1) & 0x1B0) == 0 )
```

`0x1B0 = 0b110110000`，第 4、5、7、8 位为 1 —— **argc 只接受 4、5、7、8**：

| argc | 含义 | 第 4 参（argv[3]） | 第 5 参 | 第 8 参 |
| --- | --- | --- | --- | --- |
| 4 | keybox / 仅 ID（无 rkp） | `true`/`false` | — | — |
| 5 | keybox + `rkp` 模式 | `true`/`false` | `rkp` | — |
| 7 | Strongbox 单参 | — | — | — |
| 8 | Strongbox + 第二组参数 | — | — | `rkp` |

参数解析：

- `argc==5` 时 `v15 = 4`，检查 `argv[4]`；`argc==8` 时 `v15 = 7`，检查 `argv[7]`；
- 判定条件 `v17 == 27506 && v18 == 112`：`27506 = 0x6B72`，小端字节 `'r','k'`；`112 = 'p'`。即字符串 `rkp`；
- 这个字符串**不存在于二进制 strings 中**，是内联的逐字节比较，所以 `strings` 命令看不到它，也是这条路径此前未被发现的原因。

分支：

```c
ParseFile(this, a2: rkp);
if ( v28 == 0 && (rkp || ValidateProvisionedKeys() == 0) )
```

`rkp == true` 时短路，跳过 `ValidateProvisionedKeys()` —— 这正是"没有 keybox 也能成功"的原因。

## 3. InstallKeybox 的构造参数

`main` 后续构造 `InstallKeybox` 实例：

- 第 4 参 = `!v10`，其中 `v10 = (argv[3] != "true")`，即第 4 个命令行参数为 `true` 时该位为真；
- 第 5 参 `a5 = 1`，固定为 TEE 安全级别。

调用顺序：

```
ParseFile → KeyMasterInstallKeybox / KeyMasterProvisionDeviceId → SetProvisioningKeyboxSuccess / SetProvisioningDeviceIdSuccess
```

字符串证据（`strings`）：

```
KeyMasterInstallKeybox
KeyMasterProvisionDeviceId
SetProvisioningKeyboxSuccess
SetProvisioningDeviceIdSuccess
CleanProvisioningState
KM_UNLOCKED_DEVICE_REQUIRED
KeyMaster Attestation Key Provisioning success for KeyID
Provisioning Success
allow_reprovision
```

`CleanProvisioningState` 与 `allow_reprovision` 说明 HAL 侧存在重置入口，但本工具没有暴露对应命令行参数，`soter-provision` 也不涉及 keymaster 槽位。

## 4. ParseFile 的两条分支

`ParseFile = 0xb85c`，`this` 指向工具对象，参数 `rkp: bool`。

### 4.1 rkp 分支（`rkp == true`）

不读文件，直接采集设备信息：

1. `qmi_client_init_instance` / `qmi_client_send_msg_sync` → 取 IMEI（双卡两条）；
2. `property_get` 依次读 `ro.product.brand`、`ro.product.device`、`ro.product.name`、`ro.serialno`、`ro.product.manufacturer`、`ro.product.model`；
3. 输出 `Imei:` / `Brand:` / `Device:` / `Product:` / `SerialNum:` / `Manufacturer:` / `Model:`；
4. `KeyMasterProvisionDeviceId(...)` 写入；
5. `SetProvisioningDeviceIdSuccess()` 置标志。

### 4.2 keybox 分支（`rkp == false`）

解析 XML：`NumberOfKeyboxes` / `AndroidAttestation` / `Keybox` / `Key` / `CertificateChain`。

- 文件不存在或解析失败：`ERROR: Unable to open xml keyfile!`，返回 `-2000`；
- 成功：`KeyMaster Attestation Key Provisioning success for KeyID<id>` + `TEE done` + `InstallKeybox is done!`。

`ValidateProvisionedKeys()` 在此分支之后执行，校验刚写入的 key 是否可用；失败则 `InstallKeybox Failed!`。

### 4.3 公开可见的输出

| 场景 | 输出 |
| --- | --- |
| 无参数 | usage |
| 文件不存在 + 非 rkp | 设备信息 + `InstallKeybox Failed!-2000` + `ERROR: Unable to open xml keyfile!` |
| 文件不存在 + rkp | 设备信息 + `TEE done` + `InstallKeybox is done!` |
| keybox 成功 | `KeyMaster Attestation Key Provisioning success for KeyID…` + `TEE done` + `InstallKeybox is done!` |

## 5. persist SFS 槽位格式

`/mnt/vendor/persist/data/` 下每个目录名是 32 字节哈希的名字（base64url 编码，无填充），代表一个 SFS 存储槽位。以 Attestation 槽位为例：

```
DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_          原厂槽位
DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_Alt        overlay 槽位
```

### 5.1 目录内容

原厂 `_` 槽位（37 项）：

- 14 组文件，每组一个数据文件 + 一个 `.bak`；
- `vTable`（593 B）与 `-EPMYqoLBSzsqrGTM4ud`（16,384 B）；
- 其中 `5r5LgWqAGkK7pkbwDExz`（12,692 B）是 Attestation Key blob，`DdHdVQd1…_`（1,588 B）是槽位索引。

`_Alt` 槽位（12:24 重建后 28 项）：

- 14 组文件（数据 + `.bak`），无 `5r5`；
- `DdHdVQd1…_Alt`（1,588 B）指向 device ID 数据。

### 5.2 文件头格式

所有 SFS 文件开头是统一的元数据头：`32 字节哈希 + 名字（NUL 结尾）+ 标签（NUL 结尾）+ 类型字段`。

| 文件 | 前 32 字节 | 偏移 32 | 名字 | 标签 |
| --- | --- | --- | --- | --- |
| 原厂 `5r5LgWqAGkK7pkbwDExz` | `f1b4 48db …` | `28 00 00 00` | `5r5LgWqAGkK7pkbwDExz` | `attest_key` |
| 原厂 `DdHdVQd1…_` | `e4ea 015a …` | — | `DdHdVQd1…_` | `2a000000 0e000000` + `zppz2LHaIfP8aLFZsea6` |
| 原厂 `vTable` | `8381 a8b5 …` | — | `DdHdVQd1…_` | `0109 0300 0000 0144 …` |

`28 00 00 00` / `05 00 00 00` 这类字段是类型/版本标记：原厂 `5r5` 为 `0x28`，11-16 烧入的版本为 `0x05`，两者不同。

### 5.3 为什么 rkp 会移除 `5r5`

12:24 写入后 `_Alt` 里 `5r5LgWqAGkK7pkbwDExz` 计数为 0，而原厂 `_` 槽位的 `5r5` 仍是 12,692 B / 2025-10-30。这说明：

- rkp 预配走的是"重建 overlay 槽位"路径，先清空再按 device ID 写入；
- 自签 key blob 不在 RKP 预配的写入集合里，因此被一并移除；
- 原厂槽位不受影响，回锁后仍由原厂链使用。

## 6. 复现分析

```sh
adb pull /vendor/bin/KmInstallKeybox
adb pull /vendor/bin/StoreKeybox
sha256sum KmInstallKeybox
```

IDA 步骤：

1. 打开 `KmInstallKeybox`，ImageBase 填 `0`；
2. 等 auto-analysis 完成（263 函数）；
3. 定位 `main`（`0x11a90`），`find_regex "rkp"` 无结果属正常；
4. 反编译 `main`、`main_cfi`（`0xde4c`）、`ParseFile`（`0xb85c`）；
5. 在 `main` 里搜 `27506` 与 `112` 的立即数比较，即可定位 rkp 判定。

本仓库不附二进制样本，只记录哈希与结论。
