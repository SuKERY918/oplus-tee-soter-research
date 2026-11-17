# 一加 Ace 6 TEE / SOTER 实测

设备：OnePlus Ace 6（PLQ110，SM8750，Android 17，ColorOS 17），Bootloader 解锁，KernelSU。

## 结论

| # | 结论 |
| --- | --- |
| 1 | 工程模式三个红项走三条独立链路：SOTER → QTI `soter64` TA（cryptoeng cmd 57）；Attestation → KeyMint TA + keystore2；RKP → cryptoeng cmd 61 |
| 2 | `KmInstallKeybox` 的 keybox 路线短暂变绿、HAL/TA 重启后丢失；但 `... true rkp`（只写 device ID）走 RKP 远程预配，清掉 app 旧 blob 后 Attestation 持久变绿，重启保持，见 [10](docs/10-rkp-device-id.md) |
| 3 | SOTER 是 TA 侧拒绝：`soter-provision 1/2` 以 uid 0/1000/2000 运行都返回 `-20` |
| 4 | 工程模式 SOTER 绿在 TA 失败时是假绿：HAL 返回空 buffer，`runCryptoCmd` 把空数组读成 0 |
| 5 | 本地软件 SOTER TA 能生成并导出 ASK，但微信 1 秒内 `removeAllAuthKey` + `removeAllUidKey`；ASK 上报后 TAM 不认自签 ATTK（决定性是服务端校验，不是本地链） |
| 6 | `set_device_locked` 返回 `-40`；锁态由 ABL 在 boot 阶段写入 RPMB，Android 侧改不了 |
| 7 | `ro.boot.*` 是模块伪装；`/proc/cmdline` 真实值 `oplusboot.verifiedbootstate=orange`、`oplusboot.secure_type=3` |

补充（2026-11-17）：自签 ATTK 的失败点在 TAM 服务端校验，而不是本地链没拼好。OhMyKeymint 上游只做 KeyMint/keystore，不含 SOTER；SOTER 相关实现见其第三方分支与 Ommega，详见 [09 OhMyKeymint / Ommega 与 ATTK 信任根](docs/09-omk-ommega-attk.md)。

## 文档

- [01 设备与分区](docs/01-device.md)
- [02 工程模式 Key 状态页](docs/02-engineering-mode.md)
- [03 cryptoeng / KeyMint](docs/03-cryptoeng-keymint.md)
- [04 SOTER / ATTK](docs/04-soter-attk.md)
- [05 尝试记录](docs/05-attempts.md)
- [06 引导链](docs/06-fake-relock.md)
- [07 后续计划](docs/07-next-steps.md)
- [08 复现与恢复](docs/08-repro-rollback.md)
- [09 OhMyKeymint / Ommega 与 ATTK 信任根](docs/09-omk-ommega-attk.md)
- [10 RKP device ID 预配：Attestation key 持久恢复](docs/10-rkp-device-id.md)

## 工具

- `tools/fake61.js`：Frida 伪造 cryptoeng cmd 61 返回。
- `tools/agent_soter.js` + `tools/hook_soter.py`：Frida hook `SoterService`，记录 SOTER 调用。
- `tools/start_soterta.sh`：无模块启动 Ommega 本地软件 SOTER TA。
