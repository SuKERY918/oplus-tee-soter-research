# Changelog

本仓库按日期记录，格式参考 Keep a Changelog。

## 2026-11-17

### Added

- `docs/12-soter-key-state.md`：SOTER 状态机与“真修复”假设。整理 TAM 按 `device_id` 查 ATTK、`soter64` TA 的 `SOTER_CE`/`enable_soter`/`get_validated_attk` 字符串、KeyStore 槽位、候选 A–F 路线、“一机一文件”五种解释、锁态/解锁态与命令授权验证矩阵、阶段 F 实验计划和预测。
- `docs/11-kminstallkeybox-internals.md`：`KmInstallKeybox` 完整逆向（argc 4/5/7/8 分支、`rkp` 内联比较、`InstallKeybox` 构造参数语义）与 persist SFS 槽位文件格式。
- `tools/diag.sh`：只读诊断，输出设备指纹、cmdline、15 行状态、`soter-provision` 返回值、persist 槽位与 keystore2 状态。
- `tools/fix-rkp.sh`：`KmInstallKeybox ... true rkp` + `pm clear` + 验证的完整修复流程。
- `LICENSE`（MIT）、`CHANGELOG.md`。
- README 重构为标准工程结构：设备表、结论表、三态对照、快速开始、目录结构、文档索引、工具表、已知边界。
- README 结论 8、目录/文档索引、已知边界补充 SOTER 状态/配置门槛与 12 号文档入口。
- `docs/07-next-steps.md`：新增问题 8–11（`SOTER_CE`/`enable_soter`、ATTK header/status、ASK/签名命令授权、一机一文件判定）和阶段 F（SOTER 状态/配置差集）。

### Fixed

- `docs/10-rkp-device-id.md`：修正 `_Alt` 槽位描述。实测 12:24 写入后槽位被**重建为 14 个文件，原先的 `5r5LgWqAGkK7pkbwDExz`（11-16 烧入的自签 Attestation Key blob）被移除**，并非"在原有 2 个文件上追加"。恢复的因果链相应补充为：rkp 重建槽位（移除自签 key）→ 写入 device ID → `pm clear` 清理 app 侧旧 blob，三者叠加。
- `docs/08-repro-rollback.md`：补齐 rkp 复现命令与验证判据，放在 keybox 失败路线之前。
- `docs/00-timeline.md`：补 12:24 写入、12:57 重启保持、12:59 `pm clear` 后 5 段链、13:03 工程模式两行绿；待办勾选 rkp 路线。
- `docs/07-next-steps.md`：问题 5、6 标注「已部分回答，见 04 屏蔽还是清空」。

## 2026-11-17（前一版）

### Added

- `docs/10-rkp-device-id.md`：RKP device ID 预配路线，`Attestation key` 与 `RKP default` 两行持久变绿。

### Changed

- README 结论 2：区分「keybox 短暂变绿」与「`... true rkp` 持久修复」。
- `docs/05-attempts.md`：`KmInstallKeybox` 一节补充 rkp 用法。
- `docs/04-soter-attk.md`：新增「屏蔽还是清空」节，基于 `soter64` TA 字符串与 `/persist/data/soter/` 从未创建的事实。

### Fixed

- 修正 TAM 校验判断：自签 ATTK 的失败点在服务端，不在本地链。

## 2026-11-16

### Added

- 初始版本：设备与分区、工程模式、cryptoeng/KeyMint、SOTER/ATTK、尝试记录、引导链、后续计划、复现与回滚、OhMyKeymint/Ommega 信任根。

### Known issues

- 解锁态 SOTER 无可用方案；`keybox` 路线写入不持久；`cmd 61` 会杀死 cryptoeng HAL。
