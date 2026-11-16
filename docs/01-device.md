# 01 设备与启动状态

## 设备

| 项 | 值 |
| --- | --- |
| 型号 | OnePlus Ace 6（PLQ110） |
| SoC | SM8750（骁龙 8 Elite，平台代号 `sun` / `pakala`） |
| 系统 | ColorOS 17 / Android 17（SDK 37） |
| 构建 | `PLQ110_17.0.0.104(CN01)` |
| 内核 | `6.6.118-android15-8-g9bc34d5b0c79-abogki537459655-4k` |
| 安全补丁 | 2026-09-01 |
| Root | KernelSU，uid=0，SELinux 域 `u:r:ksu:s0` |
| 槽位 | `_a` |

## 已安装模块（研究开始时）

`/data/adb/modules`：`Caelifall_SensorDecoy`、`hybrid_mount`、`inte_rmmod_early`、`susfs4ksu`、`teesim`、`tri_exp_caelifall`、`zygisksu`。

其中 `teesim`（TEE Shield v4.0-merge，TEESimulator 4.0 + TeeForge 0.8.1）只做两件事：

1. 早期/晚期属性伪装（`/data/adb/teeforge/blhide.log` 显示 early 阶段 `applied=4`，late 阶段 `applied=0`）；
2. 把 `libteesim_keymint.so` 注入 **keystore2**（PID 1235），不注入 KeyMint HAL，也不碰 cryptoeng / soter。

`sepolicy.rule` 只给 `keystore` 域 socket/inject 权限。实测杀掉 teesim daemon 并重启 keystore2 后，`soter-provision 1` 仍然 `fail -20`，说明 teesim 不是 SOTER 失败的根因。

## 真实启动状态 vs 属性伪装

`getprop` 看到的是被模块改过的值：

```
ro.boot.verifiedbootstate=green
ro.boot.flash.locked=1
ro.boot.vbmeta.device_state=locked
ro.boot.vbmeta.digest=7e33ccc901ed3be77a1c345256545f5498295a3c58966595d01382bb2f67944c
```

但底层仍是解锁态：

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

`oplusboot.secure_type=3` 与 `verifiedbootstate=orange` 是 ABL 传给内核的真实值，说明 Bootloader 仍处于解锁状态。属性伪装只影响 Android 用户态，不影响 TEE。

## 关键分区

| 分区 | 设备节点 | 大小 | 内容 |
| --- | --- | --- | --- |
| `xbl_a` | `/dev/block/sdb1` | 3.5 MB | 加密/压缩，可见 TME 固件字符串，无 efisp/GBL 字符串 |
| `xbl_config_a` | `/dev/block/sdb2` | 400 KB | `pre-ddr-pakala-1.0.dtb`、`LinuxLoader`、PIL 镜像表；无 efisp |
| `uefi_a` | `/dev/block/sde1` | 5 MB | ELF64，LK（Little Kernel）负载，不是 EDK2/GBL |
| `abl_a` | `/dev/block/sde8` | 1 MB | 32-bit ARM ELF，内含 LZMA 压缩的 UEFI FV（`_FVH` + LZMA 头），解压后 815,304 B |
| `uefisecapp_a` | `/dev/block/sde17` | 2 MB | ELF |
| `uefivarstore` | `/dev/block/sde78` | 512 KB | 全 0 |
| `oplusreserve1` | `/dev/block/sdf2` | 8 MB | 环形引导日志 + REBOOT_INFO，不是锁态开关 |
| `secdata` | — | 28 KB | OPLUS SM8750 Attestation 证书链（仅证书，无私钥） |
| `keymaster_a` / `keymaster_b` | `/dev/block/sde10` 等 | 512 KB | 两份完全相同（sha256 `7b85e58f…`），ELF64，已 strip |

`/dev/block/by-name` 共 143 项，**没有 `efisp` 分区**。

## Root 的能力边界

- 能读 `/data`、`/vendor`、`/odm`、分区镜像，能 ptrace 并注入 vendor HAL（KeyMint、cryptoeng、soter 都可以 attach）。
- 不能改 TEE 内部的 RPMB / SFS 数据，不能改 ABL 传给 TEE 的锁态，不能伪造腾讯 CA 的签名。
- 运行时 `KeymasterHalDevice::set_device_locked` 返回 -40，说明锁态在 boot 阶段已经固定。
