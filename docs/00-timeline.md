# 00 时间线

记录本次研究的关键节点，便于后来者对照。

## 2026-11-16：首次实测

| 时间 | 事件 |
| --- | --- |
| 20:37 | 开始：抓取工程模式页、反编译 `OplusCommercialEngineerMode.apk` |
| 20:40 | 确认页面 3 红项：SOTER key、Attestation key、RKP default |
| 20:58 | 首次 `KmInstallKeybox` 成功，Attestation 变绿；SOTER / RKP 仍红 |
| 21:10 | Frida attach cryptoeng HAL，抓 cmd 57/61 的真实返回 |
| 21:16 | 确认 cmd 61 会杀死 cryptoeng HAL，页面 RKP 绿来自缓存 |
| 21:25 | `set_device_locked` 返回 -40，运行时改锁态失败 |
| 21:43 | 启动 Ommega 本地软件 SOTER TA，页面 SOTER 变绿 |
| 21:44 | Frida 伪造 cmd 61，RKP 变绿，得到 15 行全绿截图 |
| 21:51 | 微信「支付设置」卡死 146 秒，定位为软件 TA 的 `exportAskPublicKey` 阻塞 |
| 22:00 | 回滚原厂 SOTER；keybox 重装后 Attestation 仍红，确认写入不持久 |
| 22:07 | 微信指纹开关实测：`generateAskKeyPair` 返回 -20，弹「系统错误」 |
| 22:22 | 构建 Ommega 本地模块并刷入，等用户重启 |
| 22:24 | 重启后模块生效，但 keymint daemon 因 PID 复用误判单实例退出 |
| 22:38 | 本地 TA 现场生成 ASK、导出 805 字节，微信立即 `removeAllUidKey` |
| 22:50 | 确认真实启动状态：`oplusboot.verifiedbootstate=orange`、`secure_type=3` |
| 22:54 | 禁用 Ommega 模块，恢复原厂 SOTER |
| 23:02 | 核对 TEE 屏蔽 / 回锁恢复的社区资料，修正「从未 provision」的判断 |
| 23:07 | 结论：解锁态没有公开可复现的「真全绿 + 微信指纹」方案 |
| 23:10 | 整理实验记录并发布到本仓库 |

## 2026-11-17：TAM 判断修正

| 时间 | 事件 |
| --- | --- |
| — | 修正 TAM 校验判断：自签 ATTK 的失败点在服务端；新增 [09 信任根](09-omk-ommega-attk.md) |

## 2026-11-17：RKP device ID 预配（本次修复）

| 时间 | 事件 |
| --- | --- |
| 11:39 | 确认解锁态 TEE 假死：KeyAttestation 报 `Invalid key blob`，`security_level.rs:757` 在生成阶段拒绝 |
| 12:18 | 逆向 `KmInstallKeybox`，发现未文档化的 `rkp` 模式（argc=5，内联比较 `'r','k','p'`） |
| 12:24 | `KmInstallKeybox /data/local/tmp/x PLQ110 true rkp` 成功；`_Alt` 槽位被重建为 14 个文件，**11-16 烧入的自签 `5r5LgWqAGkK7pkbwDExz` 被移除** |
| 12:27 | keystore2 清理旧 key blob 时 TEE 死锁，adbd 无响应，需长按电源键强制重启 |
| 12:55 | 设备重启完成，`/proc/cmdline` 仍 `orange`，persist `_Alt` 写入保持 |
| 12:57 | RKP 证书链在重启后保持，叶子 `CN=Android Keystore Key` 按新 boot 时间重新签发 |
| 12:59 | `pm clear` 清掉旧 blob 后得到 5 段链：`f92009e8…` → `e083083c…` → `9d7b56e9…` → `CN=App Attest Key` → `CN=Android Keystore Key` |
| 13:03 | 工程模式 `Attestation key`、`RKP default` 变绿；`SOTER key` 仍红（`-20`） |
| 13:12 | 复核：每次点认证叶子时间戳都更新，确认非缓存假绿 |

## 待办

- [x] 验证 `... true rkp` 路线：本机持久，重启保持
- [x] 部分回答「屏蔽还是清空」：TA 初始化路径含 `is_secure_boot_enabled` + `BAILING OUT`，`/persist/data/soter/` 从未被创建
- [ ] 用一台锁态 + 临时 root 的一加设备建立基线（07 阶段 A）
- [ ] 对比解锁前后 persist / oplusreserve1 / uefivarstore 差异
- [ ] 锁态基线：确认 ATTK 是「被 secure boot 挡住」还是「已被清空」
- [ ] 评估自己的锁态 B 机 relay，避免使用共享 ATTK
- [ ] 对齐本地 SOTER blob：805/809 B、`rsa_pss_saltlen`、JSON 键序、`finishSign` 证据
- [ ] 评估 `oemLcsDevState` 变量写入路径
- [ ] 评估 SM8750 引导链级锁态伪造的可行性
