# Changelog

本仓库按日期记录，格式参考 Keep a Changelog。

## 2026-11-17（第二版：全文重写）

这一版把文档从"边查边记"改成"结论先行 + 证据分级"，并更正了第一版 6 处结论错误。逐条对照见 [docs/12-errata.md](docs/12-errata.md)。

### Changed

- **README 重写**：12 条结论表带证据列（实测/代码/推断）；新增"两把锁"图、15 行实测表、文档索引、工具表、已知边界；序列号与 IMEI 全部脱敏。
- **docs 全量重写为 13 篇**：`00-overview`、`01-device`、`02-engineering-mode`、`03-cryptoeng-hal`、`04-soter-service`、`05-soter-ta`、`06-root-cause`、`07-attempts`、`08-bootchain-relock`、`09-rkp-attestation`、`10-kminstallkeybox`、`11-repro`、`12-errata`。
- **删除旧 10 篇**：`00-timeline`、`03-cryptoeng-keymint`、`04-soter-attk`、`05-attempts`、`06-fake-relock`、`07-next-steps`、`08-repro-rollback`、`09-omk-ommega-attk`、`10-rkp-device-id`、`11-kminstallkeybox-internals`、`12-soter-key-state`（内容并入新文档）。
- `tools/README.md` 增加 `tools/analyze/` 一节；`fix-rkp.sh` 的文档链接改指 `docs/09`。

### Added

- `tools/analyze/`：8 个纯标准库静态分析脚本（`build_ta.py`、`pltmap.py`、`dumptable.py`、`strings.py`、`find20.py`、`scanmagic.py`、`sfs_tags.py`、`uiget.py`），全部参数化、可直接跑。
- `docs/12-errata.md`：A 类 6 条结论错误、B 类 5 条表述问题、C 类 10 条新增结论、D 类 3 条微小订正、旧新文档对照表。

### Fixed（第一版的错误结论）

- **假绿机理**：不是"HAL 返回空 buffer"，而是 cryptoeng HAL 的 ISoter 代理 stale 后把初值 0 当状态返回；根因是 `getSoterAidl` 在 `linkToDeath` 之后立刻 `AIBinder_DeathRecipient_delete` 反注册。
- **`-1000` 的来源**：不是 TA 返回，是 HAL `generateAttkKeyPair` 处理器的状态初值。
- **"屏蔽假说"证伪**：TA 不是在读 key 前退出，而是走到 `sub_52E8` 的载荷校验后返回 `-20`；且 `generate` 只接受 `-13`，构成死锁。
- **TA 镜像大小**：直接拼接的 74,924 B 是错的，按 `p_offset` 重组应为 84,575 B，`va = file − 0x1000`。
- **不再需要锁态基线**：门禁代码、命令矩阵、配置项都已在解锁态坐实。
- **不再用公开 dump 外推**：本机 TA 字符串已逐条验证。

### Added（本轮新增结论，摘要）

- ATTK 表格式（RPMB 逻辑分区 `0x53515446`，512 B 头 + 40 B 描述符 + 2048 B 密文）。
- 死锁证明：`generate` 要求门禁返回 `-13`，实测 `-20`。
- 派生根变化的代码证据：`query_device_id` 在非安全启动下用 PRNG。
- TA 替换被 TEE 完整性校验封死（`.mdt` 里 `b00…b07` 的 SHA-384 表，改 1 字节即 `Error 12`）。
- 工程模式 APK 自带的解锁闸门（`isDeviceOemUnlocked()` → `return 10000`）。
- `rpmbClient smci -e` 是设备上唯一可见的 RPMB 全擦原语（未执行，代价已列）。

## 2026-11-17（前一版）

### Added

- `docs/12-soter-key-state.md`：SOTER 状态机与"真修复"假设。整理 TAM 按 `device_id` 查 ATTK、`soter64` TA 的 `SOTER_CE`/`enable_soter`/`get_validated_attk` 字符串、KeyStore 槽位、候选 A–F 路线、"一机一文件"五种解释、锁态/解锁态与命令授权验证矩阵、阶段 F 实验计划和预测。
- `docs/11-kminstallkeybox-internals.md`：`KmInstallKeybox` 完整逆向（argc 4/5/7/8 分支、`rkp` 内联比较、`InstallKeybox` 构造参数语义）与 persist SFS 槽位文件格式。
- `tools/diag.sh`：只读诊断，输出设备指纹、cmdline、15 行状态、`soter-provision` 返回值、persist 槽位与 keystore2 状态。
- `tools/fix-rkp.sh`：`KmInstallKeybox ... true rkp` + `pm clear` + 验证的完整修复流程。
- `LICENSE`（MIT）、`CHANGELOG.md`。
- README 重构为标准工程结构：设备表、结论表、三态对照、快速开始、目录结构、文档索引、工具表、已知边界。
- `docs/07-next-steps.md`：新增问题 8–11（`SOTER_CE`/`enable_soter`、ATTK header/status、ASK/签名命令授权、一机一文件判定）和阶段 F（SOTER 状态/配置差集）。

### Fixed

- `docs/10-rkp-device-id.md`：修正 `_Alt` 槽位描述。实测 12:24 写入后槽位被**重建为 14 个文件，原先的 `5r5LgWqAGkK7pkbwDExz`（11-16 烧入的自签 Attestation Key blob）被移除**，并非"在原有 2 个文件上追加"。恢复的因果链相应补充为：rkp 重建槽位（移除自签 key）→ 写入 device ID → `pm clear` 清理 app 侧旧 blob，三者叠加。
- `docs/08-repro-rollback.md`：补齐 rkp 复现命令与验证判据，放在 keybox 失败路线之前。
- `docs/00-timeline.md`：补 12:24 写入、12:57 重启保持、12:59 `pm clear` 后 5 段链、13:03 工程模式两行绿；待办勾选 rkp 路线。

## 2026-11-17（首版）

### Added

- `docs/10-rkp-device-id.md`：RKP device ID 预配路线，`Attestation key` 与 `RKP default` 两行持久变绿。

### Changed

- README 结论 2：区分「keybox 短暂变绿」与「`... true rkp` 持久修复」。
- `docs/05-attempts.md`：`KmInstallKeybox` 一节补充 rkp 用法。
- `docs/04-soter-attk.md`：新增「屏蔽还是清空」节。

### Fixed

- 修正 TAM 校验判断：自签 ATTK 的失败点在服务端，不在本地链。
