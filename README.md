# 一加 Ace 6 解锁后 TEE / SOTER 与工程模式 Key 状态研究

对 **OnePlus Ace 6（PLQ110，SM8750，ColorOS 17 / Android 17）** 在 Bootloader 解锁并 root 后，工程模式「Key 状态」页、SOTER、Attestation、RKP 以及微信指纹支付的实测记录。

记录范围：工程模式页判定逻辑、cryptoeng / KeyMint 命令链路、SOTER / ATTK、锁态写入路径，以及所有尝试的效果与恢复方式。

## 结论摘要

1. **工程模式页的三个红项分别走三条独立链路**：SOTER 走 QTI `soter64` TA（cryptoeng cmd 57）；Attestation 走 KeyMint TA + keystore2；RKP 走 cryptoeng cmd 61。三者都不能靠属性伪装修好。
2. **Attestation 可以用 `KmInstallKeybox` 临时写绿**，但写入不持久：KeyMint HAL / TA 重启后 keybox 丢失，页面重新变红。日志为 `While generating without a provided attestation key`，keystore2 回退 RKP 后卡在 `User consent required to communicate with remote provisioning server`。
3. **SOTER 在本机是 TA 侧拒绝**：`vendor.qti.hardware.soter-provision 1/2` 以任意 uid 运行都返回 `-20`；TA 字符串含 `ATTK already provisioned or RPMB not provisioned`、`is_secure_boot_enabled`、`!!! secboot device && rpmb error, BAILING OUT !!!`。工程模式页的「SOTER 成功」在 TA 失败时是**假绿**：HAL 返回空 buffer，`SecurityInterface.runCryptoCmd` 把空数组读成 0。
4. **本地软件 SOTER TA 可以通过工程模式页的 cmd 57**（返回 0），也能为微信生成并导出 ASK，但微信拿到后 1 秒内就 `removeAllAuthKey` + `removeAllUidKey` 清理。用自签 ATTK（`O=Ommega,CN=Ommega Local ATTK`）无法通过微信的证书链校验；没有腾讯 CA 签发的 ATTK，本地伪造走不通。
5. **运行时改锁态不可行**：`KeymasterHalDevice::set_device_locked(this, 1/0)` 返回 **-40**；keystore2 启动时不调用 `AndroidKeyMintDevice::deviceLocked`；HAL 的 `SetRot` / `LegacySetRot` 只在启动初始化阶段被调用。锁态由 ABL 在启动时写入 RPMB，Android 侧改不了。
6. **属性伪装对 TEE 无效**：`/proc/cmdline` 的真实值是 `oplusboot.verifiedbootstate=orange`、`oplusboot.secure_type=3`；`ro.boot.verifiedbootstate=green`、`ro.boot.flash.locked=1` 只是模块改的属性。`/proc/bootconfig` 里 `androidboot.vbmeta.device_state` 仍是 `unlocked`。

## 文档

- [01 设备与启动状态](docs/01-device.md)
- [02 工程模式 Key 状态页判定逻辑](docs/02-engineering-mode.md)
- [03 cryptoeng / KeyMint 命令链路](docs/03-cryptoeng-keymint.md)
- [04 SOTER、ATTK 与微信指纹](docs/04-soter-attk.md)
- [05 修复尝试与结果](docs/05-attempts.md)
- [06 引导链与分区观察](docs/06-fake-relock.md)
- [07 后续研究计划](docs/07-next-steps.md)
- [08 复现与恢复](docs/08-repro-rollback.md)

## 工具

- `tools/fake61.js`：Frida hook cryptoeng dispatcher，伪造 RKP cmd 61 返回。
- `tools/agent_soter.js` + `tools/hook_soter.py`：Frida hook `com.tencent.soter.soterserver.SoterService` 的 SOTER 原语，记录调用与返回。
- `tools/start_soterta.sh`：无模块方式启动 Ommega 本地软件 SOTER TA。

## 边界

本仓库只记录技术事实与实验数据，不包含任何泄漏的 keybox、私钥、厂商签名材料或绕过付费/授权的工具。所有实验均在研究者本人持有的设备上进行。
