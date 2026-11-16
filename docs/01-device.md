# 01 设备与分区

## 设备

| 项 | 值 |
| --- | --- |
| 型号 | OnePlus Ace 6（PLQ110） |
| SoC | SM8750（平台代号 `sun` / `pakala`） |
| 系统 | ColorOS 17 / Android 17（SDK 37） |
| 构建 | `PLQ110_17.0.0.104(CN01)` |
| 内核 | `6.6.118-android15-8-g9bc34d5b0c79-abogki537459655-4k` |
| 安全补丁 | 2026-09-01 |
| Root | KernelSU，uid=0，域 `u:r:ksu:s0` |
| 槽位 | `_a` |

## 模块

`/data/adb/modules`：`Caelifall_SensorDecoy`、`hybrid_mount`、`inte_rmmod_early`、`susfs4ksu`、`teesim`、`tri_exp_caelifall`、`zygisksu`。

`teesim` 只做两件事：

- 早期/晚期属性伪装（`blhide.log`：early `applied=4`，late `applied=0`）；
- `libteesim_keymint.so` 注入 keystore2（PID 1235），不注入 KeyMint HAL，不碰 cryptoeng / soter。

杀掉 teesim 并重启 keystore2 后 `soter-provision 1` 仍 `fail -20`，不是 SOTER 失败原因。

## 真实启动状态

属性（被模块改过）：

```
ro.boot.verifiedbootstate=green
ro.boot.flash.locked=1
ro.boot.vbmeta.device_state=locked
```

`/proc/cmdline`：

```
oplusboot.verifiedbootstate=orange
oplusboot.secure_type=3
oplusboot.rpmb_enabled=1
oplus.avbkeysha256=1799b97e6a3d4daa0e76710d7492aaccc97ea12d9673fc58e72ce7d3ab16d8c6
```

`/proc/bootconfig`：

```
androidboot.verifiedbootstate = "green"
androidboot.vbmeta.device_state = "unlocked"
```

## 分区

| 分区 | 节点 | 大小 | 内容 |
| --- | --- | --- | --- |
| `xbl_a` | sdb1 | 3.5 MB | TME 固件字符串，无 efisp/GBL |
| `xbl_config_a` | sdb2 | 400 KB | `pre-ddr-pakala-1.0.dtb`、`LinuxLoader`、PIL 表 |
| `uefi_a` | sde1 | 5 MB | ELF64，LK（`arch/arm64/arch.c`、`PSCI`） |
| `abl_a` | sde8 | 1 MB | 32-bit ARM ELF，LZMA 压缩 UEFI FV，解压 815,304 B |
| `uefisecapp_a` | sde17 | 2 MB | ELF |
| `uefivarstore` | sde78 | 512 KB | 全 0 |
| `oplusreserve1` | sdf2 | 8 MB | 环形引导日志 + REBOOT_INFO |
| `secdata` | — | 28 KB | OPLUS SM8750 Attestation 证书链（无私钥） |
| `keymaster_a/b` | sde10 等 | 512 KB | 两份相同（sha256 `7b85e58f…`），ELF64 已 strip |

`/dev/block/by-name` 共 143 项，无 `efisp`。

## Root 能做什么

- 能读分区、ptrace/注入 vendor HAL（KeyMint、cryptoeng、soter 均可 attach）。
- 不能改 TEE 的 RPMB/SFS，不能改 ABL 传给 TEE 的锁态，不能伪造腾讯 CA 签名。
- 运行时 `set_device_locked` 返回 `-40`。
