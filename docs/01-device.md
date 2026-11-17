# 01 设备、属性与分区

## 1. 设备

| 项 | 值 |
| --- | --- |
| 型号 | OnePlus Ace 6（`PLQ110`，板级 `OP6113L1`） |
| SoC | SM8750（平台代号 `sun`，`ro.board.platform=sun`；`xbl_config` 里的 dtb 名是 `pakala`） |
| 系统 | ColorOS 17 / Android 17（SDK 37），`ro.build.display.id = PLQ110_17.0.0.104(CN01)` |
| 内核 | `6.6.118-android15-8-g9bc34d5b0c79-abogki537459655-4k` |
| OTA | `PLQ110_11.C.14_1140_202610072355`（`ro.build.version.ota`） |
| 构建标签 | `CP2A.260605.016`（fingerprint 的构建位） |
| 指纹 | `OnePlus/PLQ110/OP6113L1:17/CP2A.260605.016/B.30b7e77-a6bb2c-a8f423:user/release-keys` |
| 安全补丁 | 2026-09-01 |
| Root | KernelSU，`uid=0`，域 `u:r:ksu:s0`，SELinux `Enforcing` |
| 槽位 | `_a` |

> 三个号各不相同：fingerprint 构建位是 `CP2A.260605.016`，`ro.build.display.id` 是 `PLQ110_17.0.0.104(CN01)`，`ro.build.version.ota` 是 `PLQ110_11.C.14_1140_202610072355`。早期文档把前两个混写成一行，容易对不上。

## 2. 真实锁态

本机 `ro.boot.*` 曾被伪装模块改写，判断真实状态**必须以 `/proc/cmdline` 为准**（它是 ABL 直接传给内核的，模块改不到）：

```sh
adb shell 'tr " " "\n" < /proc/cmdline' | grep -E 'oplusboot|avbkeys'
```

本次实测（2026-11-17）：

```
oplusboot.mode=reboot
oplusboot.prjname=24851
oplusboot.serialno=<hex>
oplusboot.rpmb_enabled=1
oplusboot.secure_type=3
oplusboot.sku=7
oplus_region=151
oplusboot.verifiedbootstate=orange
oplus.avbkeysha256=1799b97e6a3d4daa0e76710d7492aaccc97ea12d9673fc58e72ce7d3ab16d8c6
```

同一时刻的 `getprop` 也是真实值（说明本次会话里伪装模块没有生效）：

```
ro.boot.verifiedbootstate=orange
ro.boot.flash.locked=0
ro.boot.vbmeta.device_state=unlocked
```

结论：**设备处于已解锁、AVB 为 orange 的状态**。这一条对后面所有"解锁态行为"的判断都是前提；如果哪天 `getprop` 又变回 `green/locked`，那是模块在起作用，不能当作真实锁态。

## 3. 分区与数据布局

`/dev/block/by-name` 共 143 项，与本主题相关的：

| 分区 | 大小 | 与本主题的关系 |
| --- | --- | --- |
| `persist` | 约 45 MB | KeyMint SFS 槽位（设备 ID、attestation key），**不含 ATTK** |
| `secdata` | 28,672 B | OPLUS SM8750 Attestation 证书链（无私钥） |
| `devinfo` | 4,096 B | 实测全 0 |
| `ocdt` | 131,072 B | 明文无 SOTER 相关字符串 |
| `uefivarstore` | 524,288 B | 实测全 0 |
| `misc` / `frp` | 1 MB / 512 KB | 无相关数据 |
| `oplus_sec_a` | 10 MB | PKI/attestation TA 数据，唯一出现 `RPMB` 字样处（是 JSON 字段名） |
| `oplusreserve1` | 8 MB | 环形引导日志 + REBOOT_INFO，cryptoeng cmd 91 读它 |
| `oplus_sec_b`、`keystore`、`vm-persist` | — | 与 SOTER 无关 |

**没有 `sfs`、`soter` 独立分区，也没有 `efisp`。** SOTER 的 ATTK 表在 TEE 的 RPMB 逻辑分区里（见 [05](05-soter-ta.md)），任何一个越狱可见的分区都不会有它。

## 4. 进程与服务

```
vendor.qti.hardware.soter-service        → ISoter/default
vendor.oplus.hardware.cryptoeng@1.0-service → ICryptoeng/default
android.hardware.security.keymint-service-qti → IKeyMintDevice/default
keystore2                                 → 系统 keystore
com.tencent.soter.soterserver             → 微信侧 SOTER 服务（u0_aXXX）
```

init 定义：

- `/vendor/etc/init/vendor.qti.hardware.soter-service.rc`：`service vendor.soter`，`class late_start`，`user system`，`group system drmrpc`。
- `/odm/etc/init/vendor.oplus.hardware.cryptoeng@1.0-service_FDE.rc`：`service hal_cryptoeng_oplus`，`class hal`，`user system`，`interface aidl …ICryptoeng/default`；同一份 rc 里还有一段 `on property:sys.boot_completed=1 && property:ro.board.platform=canoe` 的 `chmod`，目标是 persist 的 `DdHdVQd1…_` 与 `_Alt` —— 但**本机 `ro.board.platform=sun`，这段不会执行**（见 [10 §5](10-kminstallkeybox.md)）。

两个服务都被 `kill -9` 后由 init 自动拉起，可作为实验里的"重启点"。

## 5. Root 能做什么、不能做什么

能做：

- 读所有块设备、`adb pull` 分区；
- ptrace/注入 vendor HAL（本次实测 soter-service、cryptoeng HAL 都可 `service call` 或杀进程）；
- `mount --bind` 单文件（`/vendor/firmware_mnt` 虽然 `ro`，但 bind mount 可以覆盖单个文件，见 [07](07-attempts.md)）；
- 调 smcinvoke 通道（`rpmbClient` 就是这么读 RPMB 状态的）。

不能做：

- 改 TEE 内的 RPMB 内容或 TA 映像（有完整性校验）；
- 改 ABL 传给 TEE 的锁态（`set_device_locked` 返回 `-40`）；
- 伪造 ATTK 的签发链（`.mdt` 用 OPLUS/QTI 私钥签名）。

## 6. 本机实测的 15 行

见 [02](02-engineering-mode.md)。当前状态：**只有 `SOTER key` 一行红**，`Attestation key` 与 `RKP default` 已经是绿的（那是 [09](09-rkp-attestation.md) 修好的，与 SOTER 无关）。
