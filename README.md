# 一加 Ace 6 解锁后 TEE / SOTER 与工程模式 Key 状态研究

对 **OnePlus Ace 6（PLQ110，SM8750，ColorOS 17 / Android 17）** 在 Bootloader 解锁并 root 后，工程模式「Key 状态」页、SOTER、Attestation、RKP 以及微信指纹支付的实测记录。

研究的起点是酷安动态 75072367（作者「阿奎亚」，2026-11-15）：一加 Ace 2（PHK110，SM8475）在解锁状态、只装 Tricky Store + Zygisk Next 的情况下，工程模式 14 行全绿、微信指纹支付可用，且未公开方法。本仓库记录我们在一加 Ace 6 上试图复现时的全部分析、实验与结论。

## 结论摘要

1. **工程模式页的三个红项分别走三条独立链路**：SOTER 走 QTI `soter64` TA（cryptoeng cmd 57）；Attestation 走 KeyMint TA + keystore2；RKP 走 cryptoeng cmd 61。三者都不能靠属性伪装修好。
2. **Attestation 可以用 `KmInstallKeybox` 临时写绿**，但写入不持久：KeyMint HAL / TA 重启后 keybox 丢失，页面重新变红。日志为 `While generating without a provided attestation key`，keystore2 回退 RKP 后卡在 `User consent required to communicate with remote provisioning server`。
3. **SOTER 在本机是 TA 侧拒绝**：`vendor.qti.hardware.soter-provision 1/2` 以任意 uid 运行都返回 `-20`；TA 字符串含 `ATTK already provisioned or RPMB not provisioned`、`is_secure_boot_enabled`、`!!! secboot device && rpmb error, BAILING OUT !!!`。工程模式页的「SOTER 成功」在 TA 失败时是**假绿**：HAL 返回空 buffer，`SecurityInterface.runCryptoCmd` 把空数组读成 0。
4. **本地软件 SOTER TA 可以通过工程模式页的 cmd 57**（返回 0），也能为微信生成并导出 ASK，但微信拿到后 1 秒内就 `removeAllAuthKey` + `removeAllUidKey` 清理。用自签 ATTK（`O=Ommega,CN=Ommega Local ATTK`）无法通过微信的证书链校验；没有腾讯 CA 签发的 ATTK，本地伪造走不通。
5. **运行时改锁态不可行**：`KeymasterHalDevice::set_device_locked(this, 1/0)` 返回 **-40**；keystore2 启动时不调用 `AndroidKeyMintDevice::deviceLocked`；HAL 的 `SetRot` / `LegacySetRot` 只在启动初始化阶段被调用。锁态由 ABL 在启动时写入 RPMB，Android 侧改不了。
6. **属性伪装对 TEE 无效**：`/proc/cmdline` 的真实值是 `oplusboot.verifiedbootstate=orange`、`oplusboot.secure_type=3`；`ro.boot.verifiedbootstate=green`、`ro.boot.flash.locked=1` 只是模块改的属性。`/proc/bootconfig` 里 `androidboot.vbmeta.device_state` 仍是 `unlocked`。
7. **Ace 6 没有 efisp 分区**，XBL 会校验 ABL 的 ELF 段，社区公开的 EFISP/GBL 假回锁（gbl-chainload、gbl_root_canoe，面向 SM8850/SM8845）在这台机器上用不了。
8. **作者方案无法确认**：如果他的机器确实解锁且未做假回锁/临时 root，那么最可能是 SM8475 机型本身不受「解锁即 TEE 假死」影响，或者他使用了未公开的引导链/TEE 手段。本仓库不声称复现了作者的方法。

## 文档

- [01 设备与启动状态](docs/01-device.md)
- [02 工程模式 Key 状态页判定逻辑](docs/02-engineering-mode.md)
- [03 cryptoeng / KeyMint 命令链路](docs/03-cryptoeng-keymint.md)
- [04 SOTER、ATTK 与微信指纹](docs/04-soter-attk.md)
- [05 修复尝试与结果](docs/05-attempts.md)
- [06 假回锁与引导链](docs/06-fake-relock.md)
- [07 对作者方案的分析](docs/07-author-analysis.md)
- [08 后续研究计划](docs/08-next-steps.md)
- [09 复现与恢复](docs/09-repro-rollback.md)

## 工具

- `tools/fake61.js`：Frida hook cryptoeng dispatcher，伪造 RKP cmd 61 返回。
- `tools/hook_soter.js`：Frida hook `com.tencent.soter.soterserver.SoterService` 的 SOTER 原语，记录调用与返回。
- `tools/start_soterta.sh`：无模块方式启动 Ommega 本地软件 SOTER TA。

## 边界

本仓库只记录技术事实与实验数据，不包含任何泄漏的 keybox、私钥、厂商签名材料或绕过付费/授权的工具。所有实验均在作者本人持有的设备上进行。

## 参考

- 酷安动态 75072367（作者「阿奎亚」）
- [SoterFixer](https://github.com/xiaohuangbo/SoterFixer)
- [SoterChecker](https://github.com/Andrea-lyz/SoterChecker)
- [MobileModels issue #93：解锁后 TEE 屏蔽](https://github.com/KHwang9883/MobileModels/issues/93)
- [一加社区：解锁后微信指纹不可用](https://bbs.oneplus.com/thread/2244182264294408193)
- [TEE 损坏修复教程](https://imagebuilder1837.github.io/2025/02/07/tee-repair/)
