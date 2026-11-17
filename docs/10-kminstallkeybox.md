# 10 KmInstallKeybox 与 persist SFS 槽位

`/vendor/bin/KmInstallKeybox` 是 OEM 预装的 attestation key 烧录工具，同时支持 **keybox 写入** 与 **device ID 预配** 两条路径。本文记录静态分析结论与 persist 侧 SFS 槽位的实际格式。

## 1. 样本

| 项 | 值 |
| --- | --- |
| 路径 | `/vendor/bin/KmInstallKeybox` |
| 大小 | 101,960 B |
| 类型 | ELF64 ARM64 PIE |
| md5 | `c71dac75fb76f458b28192161c239d1d` |
| sha256 | `6395f3c47dbbcbc2261b8164cece51d9a7775a997b011e662d31a4d0470be9f8` |
| BuildID | `dd6a662b0b3269f62574f685f522d951` |
| 函数数 | 263（IDA auto-analysis） |
| imagebase | `0x0`，image_size `0x18420` |

相关文件：

- `/vendor/bin/StoreKeybox`（51,888 B）—— **Widevine** keybox 工具，与本工具无关；
- `/vendor/lib64/hw/` 下的 keymint HAL 库 —— 提供 `KeyMasterInstallKeybox`、`KeyMasterProvisionDeviceId`；
- `/odm/lib64/libqsee_keybox_ca.so` —— QSEE keybox CA。

## 2. main 的控制流

入口 `main = 0x11a90`，CFI 跳板 `main_cfi = 0xde4c`。

```c
if (a1 > 8 || ((1 << a1) & 0x1B0) == 0)   // argc 只接受 4/5/7/8
```

参数解析：

- `argc == 5` → 检查 `argv[4]`；`argc == 8` → 检查 `argv[7]`；
- `v17 == 27506 && v18 == 112`：`27506 = 0x6B72`（小端 `'r','k'`）、`112 = 'p'` → 字符串 `rkp`；
- 这个字符串**不在二进制 strings 里**，是内联逐字节比较。

分支：

```c
ParseFile(this, rkp);
if (v28 == 0 && (rkp || ValidateProvisionedKeys() == 0)) { ... }
```

`rkp == true` 时短路，跳过 `ValidateProvisionedKeys()` —— 这就是"没有 keybox 也能成功"的原因。

## 3. InstallKeybox 的构造参数

```c
v10 = (argv[3] != "true");        // 第 4 个参数为 true 时该位为真
InstallKeybox(..., !v10, /*a5=*/ 1);   // a5 固定为 TEE 安全级别
```

调用顺序：

```
ParseFile → KeyMasterInstallKeybox / KeyMasterProvisionDeviceId
          → SetProvisioningKeyboxSuccess / SetProvisioningDeviceIdSuccess
```

字符串证据：

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

`CleanProvisioningState` 与 `allow_reprovision` 说明 HAL 侧存在重置入口，但本工具没暴露对应参数，`soter-provision` 也不涉及 keymaster 槽位。

## 4. ParseFile 的两条分支

`ParseFile = 0xb85c`。

### 4.1 rkp 分支

不读文件，直接采集设备信息：

1. QMI 取 IMEI（双卡两条）；
2. `property_get` 读 `ro.product.brand`、`ro.product.device`、`ro.product.name`、`ro.serialno`、`ro.product.manufacturer`、`ro.product.model`；
3. 打印 `Imei:` / `Brand:` / `Device:` / `Product:` / `SerialNum:` / `Manufacturer:` / `Model:`；
4. `KeyMasterProvisionDeviceId(...)`；
5. `SetProvisioningDeviceIdSuccess()`。

### 4.2 keybox 分支

解析 XML：`NumberOfKeyboxes` / `AndroidAttestation` / `Keybox` / `Key` / `CertificateChain`。

- 文件不存在或解析失败：`ERROR: Unable to open xml keyfile!`，返回 `-2000`；
- 成功：`KeyMaster Attestation Key Provisioning success for KeyID<id>` + `TEE done` + `InstallKeybox is done!`；
- 之后 `ValidateProvisionedKeys()` 校验刚写入的 key，失败则 `InstallKeybox Failed!`。

### 4.3 输出对照

| 场景 | 输出 |
| --- | --- |
| 无参数 | usage |
| 文件不存在 + 非 rkp | 设备信息 + `InstallKeybox Failed!-2000` + `ERROR: Unable to open xml keyfile!` |
| 文件不存在 + rkp | 设备信息 + `TEE done` + `InstallKeybox is done!` |
| keybox 成功 | `KeyMaster Attestation Key Provisioning success for KeyID…` + `TEE done` + `InstallKeybox is done!` |

## 5. persist SFS 槽位格式

`/mnt/vendor/persist/data/` 下每个目录名是一段 32 字节哈希的 base64url（无填充），代表一个 SFS 存储槽位。本机相关的是：

```
DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_        原厂槽位（34 文件）
DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_Alt     overlay 槽位（28 文件）
```

### 5.1 目录内容

原厂槽位：

- 14 组文件，每组一个数据文件 + 一个 `.bak`；
- `vTable`（593 B）与 `-EPMYqoLBSzsqrGTM4ud`（16,384 B）；
- 其中 `5r5LgWqAGkK7pkbwDExz`（12,692 B）是 attestation key blob，`DdHdVQd1…_`（1,588 B）是槽位索引。

`_Alt` 槽位（rkp 重建后）：

- 14 组文件（数据 + `.bak`），**没有 `5r5`**；
- `DdHdVQd1…_Alt`（1,588 B）指向 device ID 数据。

### 5.2 文件头格式

所有 SFS 文件开头是统一元数据头：

```
[32 B 哈希][文件名 NUL 结尾][tag NUL 结尾][类型/版本 u32]
```

实测 tag 全集（`tools/analyze/sfs_tags.py`）：

```
TEE_DEVICE_ID_PRODUCT / MODEL / BRAND / DEVICE / MANUFACTURER
product / model / brand / device / manufacturer / serial / imei / imei2
attest_key（12,692 B）
gk_sfs_file（16,384 B）
```

数据文件多为 8,192 B + `.bak` 4,096 B。原厂 `5r5` 的类型字段是 `0x28`，11-16 烧入的那份是 `0x05`。

### 5.3 这个槽位到底属于谁

三个容易搞错的点：

1. **不是 cryptoeng 的。** cryptoeng 的 init rc 里确实有一段指向它的 `chmod 0700/0600`，但条件是 `ro.board.platform=canoe`；本机是 `sun`，这段**不会执行**。槽位内容（`TEE_DEVICE_ID_*`、`attest_key`、`gk_sfs_file`）才是判据：它由 KeyMint/keystore 使用。
2. **不是 SOTER 的 ATTK。** ATTK 在 RPMB 的 `FTQS` 分区（[05 §5](05-soter-ta.md)），与这里无关。
3. **`_Alt` 是 overlay 层。** rkp 预配走的是"重建 overlay 槽位"，先清空再按 device ID 写入，所以自签 key blob 被一并移除，而原厂槽位不动。

## 6. 复现

```sh
adb pull /vendor/bin/KmInstallKeybox
adb pull /vendor/bin/StoreKeybox
sha256sum KmInstallKeybox        # 6395f3c4…
```

IDA 步骤：

1. 打开 `KmInstallKeybox`，ImageBase 填 `0`；
2. 等自动分析（263 函数）；
3. 定位 `main`（0x11a90），`find_regex "rkp"` 无结果是正常的；
4. 反编译 `main`、`main_cfi`（0xde4c）、`ParseFile`（0xb85c）；
5. 在 `main` 里搜立即数 `27506` 与 `112`，即可定位 rkp 判定。

本仓库不附二进制样本，只记录哈希与结论。
