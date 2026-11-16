# 06 引导链与分区

## 分区

| 分区 | 节点 | 大小 | 内容 |
| --- | --- | --- | --- |
| `xbl_a` | sdb1 | 3,670,016 B | TME 固件字符串（`tmeFwMain`、`TME_FW_NS_DUMP`、`CLICConfig`） |
| `xbl_config_a` | sdb2 | 409,600 B | `pre-ddr-pakala-1.0.dtb`、`post-ddr-pakala-1.0.dtb`、`LinuxLoader`、`ZuefiplatLA.cfg`、PIL 表 |
| `uefi_a` | sde1 | 5,242,880 B | ELF64，LK（`arch/arm64/arch.c`、`PSCI`、`TTBR0/TCR/MAIR/SCTLR`） |
| `abl_a` | sde8 | 1,048,576 B | 32-bit ARM ELF，LZMA 压缩 UEFI FV |
| `uefisecapp_a` | sde17 | 2,097,152 B | ELF |
| `uefivarstore` | sde78 | 524,288 B | 全 0 |

`grep -i efisp /proc/partitions` 为空；`xbl_a`、`xbl_config_a`、`uefi_a`、`abl_a` 中没有 `efisp` / `GBL` / `VerifiedBoot` / `QCOM_VERIFIEDBOOT` 字符串。

## 引导链

```
XBL (sdb1, pakala) → uefi_a (LK) → abl_a (LZMA UEFI FV，含 LinuxLoader/ABL) → kernel
```

- `abl_a`：`ET_EXEC`，entry `0x9fa00000`，PT_LOAD off=0x1000/filesz=0x42000，载荷熵 7.99；0x1020 有 `_FVH`，0x1078 起 LZMA 头，解压 815,304 B。
- `uefi_a`：`ET_EXEC`，entry `0xa7000000`，PT_LOAD filesz=0x2a8000，无 section。
- `xbl_a`：有 `boot_elf_auth.c`、`Segments hash check`、`Auth Metadata`、`not authorized`（ABL ELF 段由 XBL 校验）。

## ABL 字符串

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

## oplusreserve1

8 MB（sdf2），是环形引导日志：

```
VB: RWDeviceState: Succeed using rpmb!
Fastboot=0, Recovery:0
km_client_read_rpmb_boot_info: last_bootmode:62
```

没有 `oemLcsDevState` / `UnlockRecord` / `fastboot_unlock_data` 的 ASCII 或 UTF-16LE 形式。

## 用户态边界

- ABL 在 boot 阶段把锁态写进 RPMB；
- KeyMint / SOTER TA 启动时读取；
- Android 启动后 `set_device_locked` 返回 `-40`；
- keystore2 不调用 `deviceLocked`，无 `setBootState` 字符串；
- `ro.boot.*` 只影响 Android 用户态，TEE 不读。
