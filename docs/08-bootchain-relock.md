# 08 引导链、锁态与回锁

这篇讨论一个绕不开的问题：**锁态是谁写的、Android 侧能不能改、回锁能不能救 SOTER。**

## 1. 引导链

```
XBL (xbl_a)  →  uefi_a (LK)  →  abl_a (LZMA 压缩的 UEFI FV，含 LinuxLoader)  →  kernel
```

| 分区 | 节点 | 大小 | 内容 |
| --- | --- | --- | --- |
| `xbl_a` | sdb1 | 3,670,016 B | TME 固件字符串（`tmeFwMain`、`TME_FW_NS_DUMP`、`CLICConfig`） |
| `xbl_config_a` | sdb2 | 409,600 B | `pre-ddr-pakala-1.0.dtb`、`post-ddr-pakala-1.0.dtb`、`LinuxLoader`、`ZuefiplatLA.cfg`、PIL 表 |
| `uefi_a` | sde1 | 5,242,880 B | ELF64，LK（`arch/arm64/arch.c`、`PSCI`、`TTBR0/TCR/MAIR/SCTLR`） |
| `abl_a` | sde8 | 1,048,576 B | 32-bit ARM ELF + LZMA UEFI FV，解压 815,304 B |
| `uefisecapp_a` | sde17 | 2,097,152 B | ELF |
| `uefivarstore` | sde78 | 524,288 B | 实测全 0 |

`grep -i efisp /proc/partitions` 为空；`xbl_a`、`xbl_config_a`、`uefi_a`、`abl_a` 里都没有 `efisp` / `GBL` / `VerifiedBoot` / `QCOM_VERIFIEDBOOT` 字符串。

→ 网上"用 `efisp` 分区做假回锁"的方案**对本机不适用**。

## 2. 锁态是在 boot 阶段写进 RPMB 的

ABL 里的字符串（`abl_a` 解压后）：

```
set_boot_info_to_rpmb: secureboot_state:%d lock_state:%d boot_mode:%d tmp_boot_mode:%d
set_boot_info_to_rpmb %d %d %d
set_boot_info_to_rpmb: update boot info to rpmb fail
set_boot_info_to_rpmb: read boot info from rpmb fail
oplusboot.verifiedbootstate=
oplusboot.secure_type=
oplusboot.rpmb_enabled=1
androidboot.vbmeta.device_state
GetSecureType: oemLcsDevState=(%d)
GetSecureType: fail to find variable L"oemLcsDevState".
if olock secure lock state, Not allow Fastboot.
Flashing is not allowed in Lock State
Erase is not allowed in Lock State
State: Unlocked, AvbSlotVerify returned %a, continue boot
```

流程：

```
ABL 启动
  → 判断 AVB / secure boot / lock state
  → set_boot_info_to_rpmb(secureboot_state, lock_state, boot_mode)
  → 把 oplusboot.* 写进 cmdline 传给内核
  → TEE 侧的 KeyMint / SOTER TA 启动时再读 RPMB 里的锁态
```

`oplusreserve1`（8 MB，sdf2）是环形引导日志，能看到：

```
VB: RWDeviceState: Succeed using rpmb!
Fastboot=0, Recovery:0
km_client_read_rpmb_boot_info: last_bootmode:62
```

里面没有 `oemLcsDevState` / `UnlockRecord` / `fastboot_unlock_data` 的 ASCII 或 UTF-16LE 形式。

## 3. Android 侧改不了

| 尝试 | 结果 |
| --- | --- |
| `set_device_locked` | 返回 `-40` |
| keystore2 调 `deviceLocked` | 没有该调用（无 `setBootState` 字符串） |
| 改 `ro.boot.*` | 只影响 Android 用户态，TEE 不读它 |
| 刷 `uefivarstore` | 全 0，且里面有 `GetSecureType` 读 `oemLcsDevState` 的代码，但变量本身不存在 |

结论：**锁态在 RPMB + ABL 手里，Android 侧只能读（而且读到的是真的、`/proc/cmdline` 那份）。**

## 4. 回锁能不能救 SOTER？

理论上只有一种可能：如果[假设 A](06-root-cause.md)（KDF 根随安全状态变化）成立，回锁后 TEE 重新以"安全启动"派生，**出厂时写入的那把 key 又对上了**，ATTK 表自动可解，SOTER 行自己就绿了。

但实际代价：

1. 回锁会触发 `Erase is not allowed in Lock State` 之外的一系列限制，**大概率清数据**；
2. 本机已装 KernelSU、动过 `init_boot`/`vbmeta`，回锁会做 AVB 校验，**很可能直接变砖**；
3. 即使回锁成功，也没有证据保证 KDF 根真的会切回去——那是 QTI 内部实现；
4. 回锁后如果表**仍然**解不开，你既回不到解锁状态（有些机型允许再解，但会再清一次），也没修好 SOTER。

**建议：不要为了验证一个假设去回锁。** 如果一定要验证，找一台同型号的备用机。

## 5. 那还能做什么

| 手段 | 能改什么 | 能不能改 ATTK 表 |
| --- | --- | --- |
| `fastboot flash` | 分区（boot/vendor 等） | 不能，表在 RPMB |
| 改 `persist` | KeyMint SFS | 不能 |
| 改 `ro.boot.*` | Android 用户态视图 | 不能 |
| `rpmbClient smci -e 1` | RPMB 全擦 | **能，但代价是全部密钥** |
| 工厂工具（产线） | 能写 ATTK | 解锁机被闸门拒绝；且同样写不进"表头有效"的设备 |

## 6. 小结

- 锁态是 ABL 写进 RPMB 的，Android 侧改不了；
- 本机没有 `efisp`，假回锁方案不适用；
- 回锁是**唯一可能让旧 ATTK 重新可解**的手段，但风险远大于收益，且不保证成功；
- 真正"能自助执行"的仍然是 RPMB 全擦（[06 §5-§6](06-root-cause.md)）。
