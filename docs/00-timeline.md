# 00 时间线

记录本次研究的关键节点，便于后来者对照。

| 时间 | 事件 |
| --- | --- |
| 2026-11-16 20:37 | 开始：抓取工程模式页、反编译 `OplusCommercialEngineerMode.apk` |
| 2026-11-16 20:40 | 确认页面 3 红项：SOTER key、Attestation key、RKP default |
| 2026-11-16 20:58 | 首次 `KmInstallKeybox` 成功，Attestation 变绿；SOTER / RKP 仍红 |
| 2026-11-16 21:10 | Frida attach cryptoeng HAL，抓 cmd 57/61 的真实返回 |
| 2026-11-16 21:16 | 确认 cmd 61 会杀死 cryptoeng HAL，页面 RKP 绿来自缓存 |
| 2026-11-16 21:25 | `set_device_locked` 返回 -40，运行时改锁态失败 |
| 2026-11-16 21:43 | 启动 Ommega 本地软件 SOTER TA，页面 SOTER 变绿 |
| 2026-11-16 21:44 | Frida 伪造 cmd 61，RKP 变绿，得到 15 行全绿截图 |
| 2026-11-16 21:51 | 微信「支付设置」卡死 146 秒，定位为软件 TA 的 `exportAskPublicKey` 阻塞 |
| 2026-11-16 22:00 | 回滚原厂 SOTER；keybox 重装后 Attestation 仍红，确认写入不持久 |
| 2026-11-16 22:07 | 微信指纹开关实测：`generateAskKeyPair` 返回 -20，弹「系统错误」 |
| 2026-11-16 22:22 | 构建 Ommega 本地模块并刷入，等用户重启 |
| 2026-11-16 22:24 | 重启后模块生效，但 keymint daemon 因 PID 复用误判单实例退出 |
| 2026-11-16 22:38 | 本地 TA 现场生成 ASK、导出 805 字节，微信立即 `removeAllUidKey` |
| 2026-11-16 22:50 | 确认真实启动状态：`oplusboot.verifiedbootstate=orange`、`secure_type=3` |
| 2026-11-16 22:54 | 禁用 Ommega 模块，恢复原厂 SOTER |
| 2026-11-16 23:02 | 核对 TEE 屏蔽 / 回锁恢复的社区资料，修正「从未 provision」的判断 |
| 2026-11-16 23:07 | 结论：解锁态没有公开可复现的「真全绿 + 微信指纹」方案 |
| 2026-11-16 23:10 | 整理实验记录并发布到本仓库 |

## 待办

- [ ] 用一台锁态 + 临时 root 的一加设备建立基线
- [ ] 对比解锁前后 persist / oplusreserve1 / uefivarstore 差异
- [ ] 评估 `oemLcsDevState` 变量写入路径
- [ ] 评估 SM8750 引导链级锁态伪造的可行性
