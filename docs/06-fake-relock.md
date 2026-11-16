# 06 假回锁与引导链

## 社区“假回锁”是什么

社区里的「假回锁」= 在引导链里插入一段代码，让 ABL 在把 boot state 交给 TEE 之前看到 `locked`，同时 BL 实际仍是解锁状态、fastboot 仍可刷写。

公开实现主要两种：

- [gbl-chainload](https://github.com/NullCode1337/gbl-chainload-myron)：利用 Qualcomm GBL/EFISP 加载机制，把 chainloader 放进 `efisp` 分区，在内存里给当前槽 ABL 打补丁。mode-1 篡改 `QCOM_VERIFIEDBOOT_PROTOCOL`，让 ABL 看到 locked 的 DeviceInfo，并以该视图构造 KeyMint 的 `SET_ROT` / `SET_BOOT_STATE`；mode-0 还会阻止 TZ soft-fuse 前进、吞掉 `oplusreserve1` / `opporeserve1` 写入。
- `gbl_root_canoe`（SuperTurtleDev，已归档）：面向 canoe（SM8850 / 8 Elite Gen5）的 EDK2 实现，`BDS.efi` 刷进 `efisp`。

社区教程的适用条件：

- 需要 `efisp` 分区；
- 主要面向骁龙 8E5 / 8G5（SM8850 / SM8845）；
- 一加金标 ColorOS 还要同时刷 abl；紫标可直接刷 efisp；
- 一加/真来 3 月补丁及以下可用，4 月补丁已修；
- 只能改 boot / init_boot / vendor_boot，不能动 dtbo/recovery，不能关 avb，不能刷官改/类原生，否则会砖。

## Ace 6 有没有 efisp

没有。

- `/dev/block/by-name` 共 143 项，`grep -i efisp /proc/partitions` 为空；
- `xbl_a`（sdb1）、`xbl_config_a`（sdb2）、`uefi_a`（sde1）、`abl_a`（sde8）都检查过，没有任何 `efisp` / `GBL` / `VerifiedBoot` / `QCOM_VERIFIEDBOOT` 明文字符串；
- `xbl_config_a` 里有 `pre-ddr-pakala-1.0.dtb`、`post-ddr-pakala-1.0.dtb`、`LinuxLoader`、`ZuefiplatLA.cfg`、PIL 镜像表，没有 efisp 加载项。

所以公开的 EFISP 假回锁在 Ace 6 上没有落点。

## 引导链结构

从 dump 出来的镜像推断：

```
XBL (sdb1, pakala) → uefi_a (LK) → abl_a (LZMA 压缩的 UEFI FV，内含 LinuxLoader/ABL) → kernel
```

- `abl_a.img`：32-bit ARM ELF `ET_EXEC`，entry `0xfa00000`，只有一段 PT_LOAD（off=0x1000, filesz=0x42000），载荷熵 7.99；偏移约 0x1020 有 `_FVH`（UEFI Firmware Volume Header），0x1078 起是 LZMA 头，解压得到 815,304 B 的 FV。
- `uefi_a.img`：ELF64 AArch64 `ET_EXEC`，entry `0xa7000000`，PT_LOAD off=0x1000、filesz=0x2a8000，vaddr=0xa7000000，无 section；字符串是 LK（`arch/arm64/arch.c`、`PSCI`、`TTBR0/TCR/MAIR/SCTLR`、`DEBUG ASSERT FAILED`），不是 EDK2/GBL。
- `xbl_a.img`：可见 TME 固件字符串（`tmeFwMain`、`TME_FW_NS_DUMP`、`CLICConfig`），有 `boot_elf_auth.c`、`Segments hash check`、`Auth Metadata`、`not authorized`。说明 ABL 的 ELF 段由 XBL 校验，直接把 patched ABL `dd` 进 `abl_a` 不可行。

## ABL 里的锁态路径

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

`oplusreserve1`（8 MB）实际是**环形引导日志**，不是锁态开关：

```
VB: RWDeviceState: Succeed using rpmb!
Fastboot=0, Recovery:0
km_client_read_rpmb_boot_info: last_bootmode:62
```

里面找不到 `oemLcsDevState` / `UnlockRecord` / `fastboot_unlock_data` 的 ASCII 或 UTF-16LE 形式。解锁记录走的是 RPMB，不是这个分区。

## 为什么用户态改不了

组合证据：

- ABL 在 boot 阶段把锁态写进 RPMB；
- KeyMint TA / SOTER TA 在启动时读取该状态；
- Android 启动后，`set_device_locked` 返回 **-40**；
- keystore2 不调用 `deviceLocked`，也没有 `setBootState` 字符串；
- `ro.boot.*` 可以随便改，但那只影响 Android 用户态，TEE 不读属性。

所以「假回锁」必须发生在 ABL 之前或 ABL 之内；Ace 6 没有 efisp，ABL 又由 XBL 校验，公开工具没有落点。

## 可能的未公开路径

如果要做，只有这几类：

1. 找到 XBL/ABL 的签名校验绕过或内存加载入口（类似 GBL，但 SM8750 没有 efisp）；
2. 通过 EDL/firehose 刷入修改过的 ABL，并同时绕过 XBL 校验（高风险，砖机）；
3. 找 TEE 侧漏洞，直接改 SOTER/KeyMint 读到的 boot info（更底层，公开资料极少）；
4. 利用 UEFI 变量 `oemLcsDevState` 的写入路径（如果它落在可写的 `uefivarstore`，而 ABL 又信任它）——这条目前只有字符串线索，未验证。

在拿到可靠的一手资料前，不建议在主力机上尝试。
