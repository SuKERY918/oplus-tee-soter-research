# 一加 Ace 6 · 解锁 BL 后 TEE / SOTER 状态实测

[![device](https://img.shields.io/badge/device-OnePlus%20Ace%206%20(PLQ110)-blue?style=flat-square)](#设备与环境)
[![platform](https://img.shields.io/badge/platform-SM8750%20%C2%B7%20Android%2017-success?style=flat-square)](#设备与环境)
[![license](https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square)](LICENSE)

记录 OnePlus Ace 6 在 Bootloader 解锁 + KernelSU 环境下，工程模式「Key 状态」页 15 行的实测结果、三条独立链路的归因，以及一条**已验证、可复现**的 Attestation / RKP 恢复路径。

本仓库只讨论设备侧可观测的行为与边界，不包含 ATTK 私钥导出、TAM 服务端绕过或任何可跨设备复用的密钥材料。

## 设备与环境

| 项 | 值 |
| --- | --- |
| 机型 | OnePlus Ace 6（`PLQ110`，`OP6113L1`） |
| 平台 | SM8750，Android 17 / ColorOS 17.0.0 |
| 构建 | `CP2A.260605.016`，OTA `PLQ110_11.C.14_1140_202610072355` |
| 安全补丁 | 2026-09-01 |
| Root | KernelSU（`u:r:ksu:s0`），SELinux Enforcing |
| BL 状态 | 已解锁；`ro.boot.*` 被模块伪装成 locked，`/proc/cmdline` 的真实值为 `oplusboot.verifiedbootstate=orange` |

## 结论一览

| # | 结论 | 详情 |
| --- | --- | --- |
| 1 | 工程模式三个红项走三条独立链路 | SOTER → QTI `soter64` TA（cryptoeng cmd 57）；Attestation → KeyMint TA + keystore2；RKP → cryptoeng cmd 61 | [03](docs/03-cryptoeng-keymint.md) |
| 2 | `KmInstallKeybox` 的 keybox 路线短暂变绿、重启丢失；`... true rkp`（只写 device ID）走 RKP 远程预配，清掉旧 blob 后持久变绿 | 端到端验证见右侧文档 | [10](docs/10-rkp-device-id.md) |
| 3 | SOTER 是 TA 侧拒绝 | `soter-provision 1/2/3/4` 以 uid 0/1000/2000 运行均返回 `-20` | [04](docs/04-soter-attk.md) |
| 4 | 工程模式的 SOTER 绿在 TA 失败时是假绿 | HAL 返回空 buffer，`runCryptoCmd` 把空数组读成 0 | [02](docs/02-engineering-mode.md) |
| 5 | 本地软件 SOTER TA 能生成并导出 ASK，但微信 1 秒内 `removeAllAuthKey` + `removeAllUidKey` | ASK 上报 TAM 后不认自签 ATTK，决定性是服务端校验 | [09](docs/09-omk-ommega-attk.md) |
| 6 | `set_device_locked` 返回 `-40` | 锁态由 ABL 在 boot 阶段写入 RPMB，Android 侧改不了 | [06](docs/06-fake-relock.md) |
| 7 | `ro.boot.*` 是模块伪装 | `/proc/cmdline` 真实值 `oplusboot.verifiedbootstate=orange`、`oplusboot.secure_type=3` | [01](docs/01-device.md) |
| 8 | SOTER 失败可能不只是 key 销毁，而是 TA 状态/配置门槛 | `soter64` TA 含 `SOTER_CE`/`enable_soter`/`qsee_cfg_getpropval` 与 `get_validated_attk`/`ATTK status`；下一步做锁态/解锁态差集 | [12](docs/12-soter-key-state.md) |

## 三态对照

工程模式 15 行的期望状态。锁态列来自社区资料与 `07` 阶段 A 的待实测项，解锁两列为本机实测。

| 行 | 锁态 | 解锁（裸） | 解锁 + rkp 修复 |
| --- | --- | --- | --- |
| Rpmb key | 成功 | 成功 | 成功 |
| SOTER key | 成功 | 失败（`-20`） | 失败（`-20`） |
| IFAA key | 成功 | 成功 | 成功 |
| Crypto key | 成功 | 成功 | 成功 |
| WidevineL1 key | 成功 | 成功 | 成功 |
| HDCP key | 不支持 | 不支持 | 不支持 |
| Attestation key | 成功 | 失败 | **成功** |
| FIDO key | 成功 | 成功 | 成功 |
| PKI cert | 成功 | 成功 | 成功 |
| PKI Group cert | 成功 | 成功 | 成功 |
| FIDO2 key | 成功 | 成功 | 成功 |
| RKP default | 成功 | 失败 | **成功** |
| RKP widevine | 不支持 | 不支持 | 不支持 |
| StrongBox key | 不支持 | 不支持 | 不支持 |
| DP HDCP V2 key | 不支持 | 不支持 | 不支持 |

红绿差异只集中在 **SOTER key** 一项：Attestation / RKP 已被 `... true rkp` 修复，SOTER 仍是 TA 侧拒绝。

## 快速开始

```sh
# 1. 确认设备与真实锁态
adb shell 'cat /proc/cmdline' | tr ' ' '\n' | grep oplusboot

# 2. 采集当前 15 行状态与 SOTER 返回值
./tools/diag.sh

# 3. 只在需要修复 Attestation / RKP 时执行
./tools/fix-rkp.sh
```

`diag.sh` 只读，不修改设备。`fix-rkp.sh` 会写 persist 与 RPMB，执行前请先读 [08 复现与恢复](docs/08-repro-rollback.md)。

## 目录结构

```
.
├── README.md
├── CHANGELOG.md
├── LICENSE
├── docs/
│   ├── 00-timeline.md        研究时间线
│   ├── 01-device.md          设备、分区、属性
│   ├── 02-engineering-mode.md 工程模式 Key 状态页
│   ├── 03-cryptoeng-keymint.md cryptoeng / KeyMint 链路
│   ├── 04-soter-attk.md      SOTER / ATTK 与 TA 拒绝
│   ├── 05-attempts.md        已尝试路线与失败原因
│   ├── 06-fake-relock.md     引导链、ABL、oplusreserve1
│   ├── 07-next-steps.md      后续实验计划
│   ├── 08-repro-rollback.md  命令级复现与回滚
│   ├── 09-omk-ommega-attk.md OhMyKeymint / Ommega 与信任根
│   ├── 10-rkp-device-id.md   RKP device ID 预配（已验证修复）
│   ├── 11-kminstallkeybox-internals.md  KmInstallKeybox 逆向与 persist 槽位格式
│   └── 12-soter-key-state.md SOTER 状态机、候选真修复路线与验证矩阵
└── tools/
    ├── diag.sh               只读诊断
    ├── fix-rkp.sh            Attestation / RKP 修复
    ├── fake61.js             Frida 伪造 cryptoeng cmd 61
    ├── agent_soter.js        Frida hook SoterService
    ├── hook_soter.py         agent_soter.js 的注入器
    └── start_soterta.sh      启动 Ommega 本地软件 SOTER TA
```

## 文档

建议按 00 → 01 → 02 → 04 → 09 → 12 的顺序读；只想复现 Attestation/RKP 修复的直接看 08 和 10。

| 文档 | 内容 |
| --- | --- |
| [00 时间线](docs/00-timeline.md) | 从 11-16 首次抓页到 11-17 rkp 修复的完整节点 |
| [01 设备与分区](docs/01-device.md) | 属性、分区布局、真实锁态判定 |
| [02 工程模式](docs/02-engineering-mode.md) | 15 行实现、cryptoeng 命令、假绿与缓存 |
| [03 cryptoeng / KeyMint](docs/03-cryptoeng-keymint.md) | cmd 57/58/61、KeyMint TA 报错 |
| [04 SOTER / ATTK](docs/04-soter-attk.md) | 服务、TA 字符串、微信调用链、屏蔽 vs 清空 |
| [05 尝试记录](docs/05-attempts.md) | 每条失败路线的具体现象 |
| [06 引导链](docs/06-fake-relock.md) | xbl/uefi/abl、`set_boot_info_to_rpmb`、oplusreserve1 |
| [07 后续计划](docs/07-next-steps.md) | 锁态基线、差集对比、候选 flag、待答问题 |
| [08 复现与回滚](docs/08-repro-rollback.md) | 可直接粘贴的命令 |
| [09 信任根](docs/09-omk-ommega-attk.md) | ATTK→ASK→AuthKey、TAM 校验位置、三条可行路线 |
| [10 RKP device ID](docs/10-rkp-device-id.md) | 唯一已验证的持久修复路径 |
| [11 KmInstallKeybox 逆向](docs/11-kminstallkeybox-internals.md) | 参数形状、分支逻辑、persist 槽位文件格式 |
| [12 SOTER key 状态机](docs/12-soter-key-state.md) | 真修复候选路线、TA 命令面、一机一文件分类、阶段 F 实验矩阵 |

## 工具

| 工具 | 作用 | 是否修改设备 |
| --- | --- | --- |
| `tools/diag.sh` | 一键采集设备指纹、cmdline、15 行状态、`soter-provision`、persist 槽位 | 否 |
| `tools/fix-rkp.sh` | `KmInstallKeybox ... true rkp` + `pm clear` + 验证 | 是（写 persist / RPMB） |
| `tools/fake61.js` | Frida attach cryptoeng HAL，cmd 61 返回 8 字节 0 | 运行时内存 |
| `tools/agent_soter.js` | Frida hook `SoterService`，打印 SOTER 调用参数 | 运行时内存 |
| `tools/hook_soter.py` | 注入 `agent_soter.js` | 运行时内存 |
| `tools/start_soterta.sh` | 顶替原厂 `vendor.soter`，起动 Ommega 本地软件 TA | 是（临时替换 HAL） |

## 已知边界

- **解锁态拿不到真 ATTK**：私钥在 TEE/RPMB，`soter64` TA 在 `is_secure_boot_enabled` + `BAILING OUT` 路径上就退出，`generate/verify/export/get_device_id` 全部 `-20`，root 不改变这一点。
- **软件 TA / 自签 ATTK 过不了 TAM**：本地链能拼、工程模式能绿，但 ASK 上报后服务端拒绝，微信随即 `removeAllAuthKey` + `removeAllUidKey`，见 [09](docs/09-omk-ommega-attk.md)。
- **`... true rkp` 只修 Attestation / RKP**：与 SOTER 的 `soter64` TA 完全无关，不要指望它让 SOTER key 变绿。
- **RPMB 写入不可回滚**：device ID 记录一旦写入，删 persist 槽位或 dd 回镜像都撤不掉；它写入的是设备真实身份信息，不是密钥，见 [10 §5](docs/10-rkp-device-id.md#5-副作用与回滚)。
- **本机没有 `efisp` 分区**：`06` 里讨论的假回锁路线只覆盖部分机型，本机不可行。
- **SOTER 不只是 key 问题**：`soter64` TA 同时检查 `is_secure_boot_enabled`、`SOTER_CE`/`enable_soter` 配置和 ATTK header/status；`SoterFixer` 的重启偶发有效也说明存在状态性门槛。候选路线和验证方法见 [12](docs/12-soter-key-state.md)，尚未在本机复现。

## 复现与回滚

完整命令、模块安装、keymint/keystore2 急救、回锁前提都在 [08 复现与恢复](docs/08-repro-rollback.md)。

动手前至少确认：

1. `/proc/cmdline` 的 `oplusboot.verifiedbootstate` 是设备的真实状态；
2. 原厂 persist 槽位 `DdHdVQd1…_` 未被修改（`5r5LgWqAGkK7pkbwDExz` 时间戳仍是出厂时间）；
3. 知道回锁会清数据、需要原厂 `init_boot`/`vbmeta`。

## 许可

[MIT](LICENSE)
