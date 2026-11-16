# 06 引导链与分区观察

本机（PLQ110，SM8750，平台代号 pakala）的引导链与相关分区实测记录。

## 分区

`/dev/block/by-name` 共 143 项。与引导链相关的：

| 分区 | 设备节点 | 大小 | 内容 |
| --- | --- | --- | --- |
| `xbl_a` | sdb1 | 3,670,016 B | TME 固件字符串（`tmeFwMain`、`TME_FW_NS_DUMP`、`CLICConfig`） |
| `xbl_config_a` | sdb2 | 409,600 B | `pre-ddr-pakala-1.0.dtb`、`post-ddr-pakala-1.0.dtb`、`LinuxLoader`、`ZuefiplatLA.cfg`、PIL 镜像表 |
| `uefi_a` | sde1 | 5,242,880 B | ELF64 AArch64，LK（`arch/arm64/arch.c`、`PSCI`、`TTBR0/TCR/MAIR/SCTLR`） |
| `abl_a` | sde8 | 1,048,576 B | 32-bit ARM ELF，LZMA 压缩的 UEFI FV |
| `uefisecapp_a` | sde17 | 2,097,152 B | ELF |
| `uefivarstore` | sde78 | 524,288 B | 全 0 |

`grep -i efisp /proc/partitions` 为空；`xbl_a`、`xbl_config_a`、`uefi_a`、`abl_a` 中也没有 `efisp` / `GBL` / `VerifiedBoot` / `QCOM_VERIFIEDBOOT` 字符串。

## 引导链结构

从 dump 出来的镜像推断：

```
XBL (sdb1, pakala) → uefi_a (LK) → abl_a (LZMA 压缩的 UEFI FV，内含 LinuxLoader/ABL) → kernel
```

- `abl_a.img`：32-bit ARM ELF `ET_EXEC`，entry `0x9fa00000`，只有一段 PT_LOAD（off=0x1000, filesz=0x42000），载荷熵 7.99；偏移约 0x1020 有 `_FVH`（UEFI Firmware Volume Header），0x1078 起是 LZMA 头，解压得到 815,304 B 的 FV。
- `uefi_a.img`：ELF64 AArch64 `ET_EXEC`，entry `0xa7000000`，PT_LOAD off=0x1000、filesz=0x2a8000，vaddr=0xa7000000，无 section。
- `xbl_a.img`：可见 `boot_elf_auth.c`、`Segments hash check`、`Auth Metadata`、`not authorized`。即 ABL 的 ELF 段由 XBL 校验。

## ABL 里的锁态相关字符串

解压后的 `abl_fv.bin` 有 3,218 条字符串，关键命中：

```
set_boot_info_to_rpmb: secureboot_state:%d lock_state:%d boot_mode:%d tmp_boot_mode:%d
set_boot_info_to_rpmb %d %d %d
set_boot_info_to_rpmb: update boot info to rpmb fail
set_boot_info_to_rpmb: read boot info from rpmb fail
oplusboot.verifiedbootstate=
oplusboot.secure_type=
oplusboot.rpmb_enabled=1
oplusboot.mode=
androidboot.vbmeta.device_state
androidboot.verifiedbootstate=
GetSecureType: oemLcsDevState=(%d)
GetSecureType: fail to find variable L"oemLcsDevState".
if olock secure lock state, Not allow Fastboot.
Flashing is not allowed in Lock State
Erase is not allowed in Lock State
State: Unlocked, AvbSlotVerify returned %a, continue boot
```

即：

1. ABL 把 `secureboot_state`、`lock_state`、`boot_mode` 写进 **RPMB**（`set_boot_info_to_rpmb`）；
2. 它也会读 UEFI 变量 `oemLcsDevState` 来判定 secure type；
3. 解锁状态下 ABL 允许 fastboot 刷写/擦除，并把 unlocked 继续传给内核。

## oplusreserve1

`oplusreserve1`（8 MB，sdf2）实际是**环形引导日志**，不是锁态开关：

```
VB: RWDeviceState: Succeed using rpmb!
Fastboot=0, Recovery:0
km_client_read_rpmb_boot_info: last_bootmode:62
```

里面找不到 `oemLcsDevState` / `UnlockRecord` / `fastboot_unlock_data` 的 ASCII 或 UTF-16LE 形式。解锁记录走的是 RPMB，不是这个分区。

## 用户态为什么改不了 TA 的锁态

- ABL 在 boot 阶段把锁态写进 RPMB；
- KeyMint TA / SOTER TA 在启动时读取该状态；
- Android 启动后，`set_device_locked` 返回 **-40**；
- keystore2 不调用 `deviceLocked`，也没有 `setBootState` 字符串；
- `ro.boot.*` 可以随便改，但那只影响 Android 用户态，TEE 不读属性。
