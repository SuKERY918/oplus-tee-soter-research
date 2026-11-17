# 一加 Ace 6 · 解锁 BL 后 TEE / SOTER 状态实测

[![device](https://img.shields.io/badge/device-OnePlus%20Ace%206%20(PLQ110)-blue?style=flat-square)](#设备与环境)
[![platform](https://img.shields.io/badge/platform-SM8750%20%C2%B7%20Android%2017-success?style=flat-square)](#设备与环境)
[![status](https://img.shields.io/badge/SOTER-%E6%AD%BB%E9%94%81%EF%BC%88-20%EF%BC%89-red?style=flat-square)](docs/06-root-cause.md)
[![license](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

一台 OnePlus Ace 6，解锁 BL、装 KernelSU 之后，工程模式「Key 状态」页里的 **SOTER key** 一直是红的。这个仓库把这条红色的链路从头到尾拆开：APK 怎么判、HAL 怎么转发、TA 怎么拒绝、RPMB 里到底存了什么，以及**为什么它修不好**。

第二版相对第一版做了大量更正，主要结论有两条变化：**「屏蔽假说」被证伪**（TA 不是提前退出，而是卡在载荷校验），**「TA 替换」被实测封死**（TEE 会校验 `.mdt` 里的 SHA-384 表）。差异逐条列在 [12 勘误](docs/12-errata.md)。

本仓库只讨论设备侧可观测的行为与边界，**不包含** ATTK 私钥导出、TAM 服务端绕过、可跨设备复用的密钥材料，也不含任何二进制样本（只记录哈希）。

## 设备与环境

| 项 | 值 |
| --- | --- |
| 机型 | OnePlus Ace 6（`PLQ110` / `OP6113L1`） |
| 平台 | SM8750，Android 17 / ColorOS 17.0.0 |
| 构建 | `CP2A.260605.016`，OTA `PLQ110_11.C.14_1140_202610072355` |
| 内核/系统版本 | `PLQ110_17.0.0.104(CN01)` |
| 安全补丁 | 2026-09-01 |
| Root | KernelSU（`u:r:ksu:s0`），SELinux Enforcing |
| BL 真实状态 | **已解锁**：`ro.boot.verifiedbootstate=orange`、`ro.boot.flash.locked=0`、`ro.boot.vbmeta.device_state=unlocked` |

> 早期记录里 `ro.boot.*` 曾被模块伪装成 locked/green；本轮实测是原始值，`/proc/cmdline` 里的 `oplusboot.verifiedbootstate=orange`、`oplusboot.secure_type=3`、`oplusboot.rpmb_enabled=1` 与此一致。

## 结论

证据强度：**实测** = 本机跑过；**代码** = 反编译/反汇编确认；**推断** = 由前两者推出但未直接观测。

| # | 结论 | 证据 | 详情 |
| --- | --- | --- | --- |
| 1 | 工程模式三个红项是三条独立链路：SOTER 走 `soter64` TA，Attestation 走 KeyMint TA + keystore2，RKP 走 cryptoeng cmd 61 | 实测 | [02](docs/02-engineering-mode.md) |
| 2 | SOTER 全链路是 **APK → cryptoeng HAL（cmd 57）→ ISoter → QSEECom → `soter64` TA**，HAL 只转发，真正的拒绝在 TA | 代码 | [03](docs/03-cryptoeng-hal.md) |
| 3 | `soter-provision 1/2/3/4` 全部 `-20`，**包括纯读的 4（getDeviceId）** | 实测 | [04](docs/04-soter-service.md) |
| 4 | `-20` 只有一个来源：`sub_52E8` 判定「表头 magic/版本合法，但每一份 ATTK 载荷都通不过 AES-GCM 校验」 | 代码 | [05](docs/05-soter-ta.md) |
| 5 | 因此形成**死锁**：`generate` 要求门禁返回 `-13` 才肯重写，而门禁现在是 `-20`，永远进不去 | 代码 | [06 §3](docs/06-root-cause.md) |
| 6 | ATTK 表在 RPMB 逻辑分区 `0x53515446`（"FTQS"，20 扇区）：512 B 头 + 每份 40 B 描述符 + 2048 B 密文，最多 4 份 | 代码 | [05 §5](docs/05-soter-ta.md) |
| 7 | 用户态**没有任何副本**：persist 全树、`secdata`/`devinfo`/`ocdt`/`uefivarstore`/`misc`/`frp`/`oplus_sec_a` 扫 `FTQS`/`ETQS`/`SOTER` 均 0 命中 | 实测 | [06 §5](docs/06-root-cause.md) |
| 8 | 「表头有效但载荷失效」只能是**派生根变了**：`store_attk` 先写载荷、最后才写有效表头，且每次写入都检查返回值 | 代码 | [06 §4](docs/06-root-cause.md) |
| 9 | 派生根变化的直接代码证据：`query_device_id` 在非安全启动下用 **PRNG 随机数**，安全启动下用 KDF 派生 | 代码 | [05 §6](docs/05-soter-ta.md) |
| 10 | 工程模式的「假绿」不是 TA 行为：cryptoeng HAL 的 ISoter 代理 stale 后，handler 把初值 0 当状态返回 | 实测+代码 | [03 §6](docs/03-cryptoeng-hal.md) |
| 11 | 替换 TA 读取 RPMB **不可行**：改 1 字节即 `load_app:name soter64 Error 12`，`.mdt` 里有 `b00…b07` 的 SHA-384 表 + OEM 签名 | 实测 | [05 §8](docs/05-soter-ta.md) |
| 12 | 厂商自己在 APK 里也把这条路封了：`isDeviceOemUnlocked()` 命中即 `return 10000`，TA 根本不会被调用 | 代码 | [07 §9](docs/07-attempts.md) |

唯一的**已验证、可持久**修复是另一条链：`KmInstallKeybox … true rkp` 重建 RKP device ID，让 Attestation key 与 RKP default 两行变绿（[09](docs/09-rkp-attestation.md)）。它与 SOTER 无关。

## 两把锁

```
               ┌─────────────────────────┐
   写入 ATTK → │ ROM 层：工程模式闸门     │  ro.boot.vbmeta.device_state != "locked"
               │ KeyProvisionCommandHandler│ → return 10000，不调 TA
               └─────────────────────────┘
                          ↓ 绕过它也没用
               ┌─────────────────────────┐
               │ TA 层：sub_5090 门禁     │  载荷校验 -20，generate 只认 -13
               └─────────────────────────┘
```

- 第一把锁在 Java 层：解锁机不允许写 ATTK，日志明说 `the device is unlocked so we cannot write key to it!!!`；
- 第二把锁在 TEE 里：即使绕过 Java，TA 的 `generate` 也要求门禁**恰好**返回 `-13`，而现在返回 `-20`。

两把锁互为兜底。要同时打开，需要的不是"绕过检测"，而是让 TEE 里的 ATTK 表回到"不存在"状态——即 `rpmbClient smci -e` 全擦 RPMB，代价见 [06 §6](docs/06-root-cause.md)。

## 工程模式 15 行（本机实测）

| 行 | 状态 | 行 | 状态 |
| --- | --- | --- | --- |
| RPMB key | 成功 | FIDO | 成功 |
| **SOTER key** | **失败** | PKI cert | 成功 |
| IFAA | 成功 | PKI Group cert | 成功 |
| Crypto | 成功 | FIDO2 | 成功 |
| WidevineL1 | 成功 | RKP default | 成功 |
| HDCP | 不支持 | RKP widevine | 不支持 |
| Attestation key | 成功 | StrongBox | 不支持 |
| | | DP HDCP V2 | 不支持 |

只剩 SOTER 一行红。Attestation / RKP 的绿是 [09](docs/09-rkp-attestation.md) 修出来的；早期记录的"裸解锁全红"状态已经不存在。

## 快速开始

```bash
# 1) SOTER 到底是不是真失败（不看 UI，直接问服务）
adb shell service call vendor.qti.hardware.soter.ISoter/default 14 i32 1     # 期望 ffffffec = -20
adb shell /vendor/bin/vendor.qti.hardware.soter-provision 1                  # 期望 fail -20, rc=236

# 2) 假绿 A/B：重启 soter 后页面会变绿，重启 cryptoeng HAL 后恢复红
adb shell 'stop vendor.soter; sleep 1; start vendor.soter'

# 3) 取 TA 镜像并重组（84,575 B 才是正确镜像）
adb pull /vendor/firmware_mnt/image samples/soter_ta/image
python tools/analyze/build_ta.py samples/soter_ta/image soter64
```

完整流程见 [11 复现手册](docs/11-repro.md)。

## 文档

| # | 文档 | 内容 |
| --- | --- | --- |
| 00 | [总览](docs/00-overview.md) | 一页读完：结论、导航、证据约定 |
| 01 | [设备](docs/01-device.md) | 设备信息、分区、进程、root 能力边界 |
| 02 | [工程模式](docs/02-engineering-mode.md) | 15 行判定链、假绿的两种来源 |
| 03 | [cryptoeng HAL](docs/03-cryptoeng-hal.md) | 命令表、四个 SOTER 处理器、death recipient bug |
| 04 | [soter 服务](docs/04-soter-service.md) | AIDL 事务码、TA 命令号、请求格式 |
| 05 | [soter TA](docs/05-soter-ta.md) | 镜像重组、导入表、分派表、门禁伪代码、表格式、`.mdt` |
| 06 | [根因](docs/06-root-cause.md) | 死锁证明、三假设、修复路径与代价 |
| 07 | [尝试记录](docs/07-attempts.md) | 每个尝试做了什么、为什么失败 |
| 08 | [引导链与回锁](docs/08-bootchain-relock.md) | 锁态写在哪、回锁的四种代价 |
| 09 | [RKP device ID](docs/09-rkp-attestation.md) | 唯一持久有效的修复 |
| 10 | [KmInstallKeybox](docs/10-kminstallkeybox.md) | 工具逆向、persist SFS 格式 |
| 11 | [复现手册](docs/11-repro.md) | 命令 + 期望输出 + 回滚 |
| 12 | [勘误](docs/12-errata.md) | 旧版 6 处结论错误逐条更正 |

## 工具

`tools/analyze/` 是一组只依赖 Python 标准库的静态分析脚本（详见 [tools/README.md](tools/README.md)）：

| 脚本 | 用途 |
| --- | --- |
| `build_ta.py` | 按 program header 重组 split-bin TA |
| `pltmap.py` | 解 `.dynamic`，输出导入符号 → PLT 桩地址 |
| `dumptable.py` | 解 cryptoeng HAL 的两张命令表 |
| `strings.py` | 带偏移的 ASCII / UTF-16LE 字符串提取 |
| `find20.py` | 扫 `-20` 字面量（`MOVN` 编码） |
| `scanmagic.py` | 扫 `ETQS`/`FTQS`/`SOTER` 等 magic |
| `sfs_tags.py` | 枚举 persist SFS 槽位的逻辑名 tag |
| `uiget.py` | 从 uiautomator dump 里按 resource-id 取文本 |

`tools/` 下还有第一版的 Frida/JS 脚本，保留作参考（部分依赖微信版本，见 [07](docs/07-attempts.md)）。

## 已知边界

- **没做的事**：没执行 `rpmbClient smci -e`（全擦 RPMB）；没尝试回锁；没抓 TEE 内部日志（Android 侧无 tzdbg 节点）。
- **不能做的事**：从用户态读 RPMB 的 `FTQS` 表；重签 `.mdt`（需 OEM 私钥）；在解锁态写入 ATTK。
- **未坐实**：`qsee_kdf` 的派生根到底绑定在哪（RPMB 密钥？secure state？设备唯一 ID 之一），已知只有"非安全启动走 PRNG"这一条直接证据。
- **不适用**：结论只对这台机（`PLQ110` + `CP2A.260605.016`）成立；同平台其它机型 TA 可能不同。

## 安全声明

- 仓库内所有序列号、IMEI 已替换为 `<serial>` / `<imei1>` / `<imei2>`；
- 不提供 TA / HAL / APK 二进制，只提供哈希与地址；
- 文中所有"改写 RPMB/TA"的路径都标注了风险与回滚方式，请自行评估。

## 许可

[MIT](LICENSE)
