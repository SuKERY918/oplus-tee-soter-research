# 12 勘误：旧版结论与新版的差异

本仓库的第一版文档（9 个提交之前）有几处结论是错的。这一篇把它们逐条列清楚，避免读者拿旧版当结论引用。每条都给出**旧版原文 → 为什么错 → 现在的结论在哪**。

> 旧版原文都用 `git show <commit>:<path>` 取，行号以旧版文件为准。

## A 类：结论错误，必须改

### A1 「假绿 = HAL 返回空 buffer」

- **旧版**：`docs/02-engineering-mode.md:52`
  > TA 失败时 HAL 返回空 buffer，`runCryptoCmd` 把空数组读成 0 → `verifyAttkKeyPair()` 返回 0 → 页面「SOTER 成功」

  同义表述在 `README.md:29`：「HAL 返回空 buffer，`runCryptoCmd` 把空数组读成 0」。
- **为什么错**：HAL 永远返回 4 字节，不是空 buffer。真正的原因是 cryptoeng HAL 缓存了 ISoter 代理，而 `getSoterAidl()` 在 `linkToDeath` 之后立刻 `AIBinder_DeathRecipient_delete()` 把它反注册了；soter 服务重启后代理 stale，AIDL 调用失败，handler 里 `v13` 保持初值 0，照样写进输出。
- **现在**：[03 §6](03-cryptoeng-hal.md)、[02 §6](02-engineering-mode.md)。

### A2 「cmd 58 返回 -1000 是 TA 的返回」

- **旧版**：`docs/02-engineering-mode.md:31`
  > `| 58 | generateAttkKeyPair + 4 字节 uid | -1000 |`
- **为什么错**：`-1000` 是 HAL 侧 `generateAttkKeyPair` 处理器的**状态变量初值**（`0x1963c`），AIDL 调用失败时没被回填就原样输出。TA 侧的真实返回是 `-20`，工程模式的 `58` 也不会走到 TA（见 A5）。
- **现在**：[03 §7](03-cryptoeng-hal.md)、[04 §4](04-soter-service.md)。

### A3 「支持屏蔽假说：TA 在读 key 之前就退出」

- **旧版**：`docs/04-soter-attk.md:126-129`
  > `is_secure_boot_enabled` 与 `BAILING OUT` 在初始化路径，`/persist/data/soter/`（`open_soter_partition` 的目标）在设备上从未被创建 —— 支持「TA 在读 key 之前就退出」的屏蔽假说…但 `soter-provision 4` 同样 `-20`，用户态无法区分

  同义表述在 `README.md:33`：「SOTER 失败可能不只是 key 销毁，而是 TA 状态/配置门槛」。
- **为什么错**：TA 并没有提前退出。它走到了 `sub_52E8` 的载荷校验：512 B 表头 magic/版本都合法，1~4 份载荷全部 AES-GCM 校验失败 → `-20`；而 `generate` 又要求门禁**恰好**返回 `-13` 才肯重写 → 死锁。另外 `/persist/data/soter/` 是 SFS 备用路径，真正的存储在 RPMB 的 `FTQS` 分区。
- **现在**：[06 §2–§3](06-root-cause.md)、[05 §6](05-soter-ta.md)。

### A4 「拼接后是 74,924 B 的 ELF」

- **旧版**：`docs/04-soter-attk.md:113`
  > `soter64.b00…b08` 拼接后是 74,924 B 的 ELF64（`0x0-0xe7c8` rx + 四个 rw 段）
- **为什么错**：`b01…b08` 的 `p_offset` 之间有一段 0xdc8 的空间，顺序拼接会把代码整体前移 0xdc8。按 `p_offset` 填充后是 **84,575 B**，`va = file − 0x1000`；74,924 B 那份的 `va = file − 0x238`，所有地址都偏了。旧版在 IDA 里看到的 `0xFFFF…` 负地址"日志函数"其实就是 PLT 桩。
- **现在**：[05 §2](05-soter-ta.md)、[11 §3](11-repro.md)。

### A5 「需要锁态基线才能继续」

- **旧版**：`README.md:33`、`README.md:142`、`docs/07-next-steps.md` 的待办 1/2/5/6/9/10。
- **为什么错**：不是必须。门禁代码已经解出，`installKeybox`/`soter-provision`/`ISoter`/TA 四层的命令矩阵都已在解锁态实测，`enable_soter` 也已从 TA 侧确认非 0（否则 `generate` 会先返 `-12`）。锁态基线现在只剩"回锁后是否恢复"这一个附属问题。
- **现在**：[06 §4](06-root-cause.md)、[08 §5](08-bootchain-relock.md)。

### A6 用 OnePlus 6/9 Pro 的 dump 外推本机

- **旧版**：`docs/12-soter-key-state.md:21-23`
  > 5 | `soter64` TA 有 `is_secure_boot_enabled` / `qsee_get_secure_state` / `BAILING OUT` | 本机 TA 字符串；OnePlus 6/9 Pro 公开 dump 同样存在
  > 7 | OnePlus 6 的 TA 含 `soter_attk_migration` / `store_migration_attk`；OnePlus 9 Pro 的 TA 已无这些字符串

- **为什么错**：本机 TA 的字符串已经逐条验证（`strings.py`，偏移见 [05 §7](05-soter-ta.md)），不需要外推；反过来，OnePlus 6 才有的 `soter_attk_migration` 本机也确实没有。旧版把"公开 dump 里有"和"本机有"混在一张表里。
- **现在**：[05 §7](05-soter-ta.md)。

## B 类：表述不准确，建议补充

| # | 旧版位置 | 问题 | 现在 |
| --- | --- | --- | --- |
| B1 | `docs/02:30` | 「TA `-20`（页面假绿时为 0）」把假绿说成 TA 行为；实际上假绿只在 HAL 代理 stale 期间出现，重启 HAL 即恢复 | [02 §6](02-engineering-mode.md) |
| B2 | `docs/02:58` | `rkpdefault_import=1` 的缓存让「RKP default 成功」跨 HAL 重启保持 —— 本轮**未复核**，属未验证项，且与 SOTER 无关 | [02 §7](02-engineering-mode.md) |
| B3 | `docs/03:13` | `cmd 57 → ecffffff` 本身没错，但它是 HAL 转发 ISoter 的结果，HAL 自己不产生 `-20` | [03 §5](03-cryptoeng-hal.md) |
| B4 | `README` 结论表 | 实测与假设混排，读者无法区分证据强度 | 新版每行加「证据」列 |
| B5 | `docs/07` 待办 | 1/2/5/6/9/10 已被本轮回答，待办表需要重写 | [08 §6](08-bootchain-relock.md) |

## C 类：本轮新增的结论（旧版没有）

| # | 结论 | 位置 |
| --- | --- | --- |
| C1 | ATTK 表格式：512 B 头（magic `0x53515445`、版本 `0xFF01`、count、计数器、device id）+ 每份 40 B 描述符（扇区/长度/IV/TAG）+ 2048 B 密文；位于 RPMB 逻辑分区 `0x53515446`（"FTQS"），共 20 扇区 | [05 §5](05-soter-ta.md) |
| C2 | 死锁：`generate` 要求门禁返回 `-13`，而实测是 `-20`，且 `-20` 只在"表头有效但载荷无效"时产生 | [06 §3](06-root-cause.md) |
| C3 | `is_secure_boot_enabled` 分支：`query_device_id` 在非安全启动下用 PRNG 随机数，安全启动下用 KDF 派生 —— 解锁后派生根会变 | [05 §6](05-soter-ta.md) |
| C4 | death recipient 反注册 bug：`getSoterAidl` 在 link 之后立刻 `AIBinder_DeathRecipient_delete`，`soter just died` 永不触发 | [03 §6](03-cryptoeng-hal.md) |
| C5 | persist SFS 槽位归属：`DdHdVQd1…` 是 KeyMint/keystore 的 attestation key 存储，`_Alt` 是 RKP overlay；两者都不是 SOTER 的 ATTK | [10 §5](10-kminstallkeybox.md) |
| C6 | `StoreKeybox` 是 Widevine keybox 工具，与 SOTER 无关 | [07 §3](07-attempts.md) |
| C7 | `rpmbClient smci -e` 是设备上唯一可见的 RPMB 全擦原语（未执行） | [06 §6](06-root-cause.md) |
| C8 | `soter64.mdt` 里 0x358 起是 `b00…b07` 的 SHA-384 表，改动任何分片都会被 `load_app Error 12` 拒绝 | [05 §8](05-soter-ta.md) |
| C9 | 真实命令分派表在 va `0x11298`：0x101→0x5B4（generate）、0x104→0xB30（getDeviceId）…… 共 15 条；IDA 的 `sub_5AC` 比真实入口早 8 字节 | [05 §4](05-soter-ta.md) |
| C10 | 工程模式 APK 自带解锁闸门：`isDeviceOemUnlocked()` 命中后 `generateAttkKeyResult()` 直接 `return 10000`，TA 根本不会被调用 | [07 §9](07-attempts.md) |

## D 类：微小订正

1. `docs/06-fake-relock.md` 里 `oemLcsDevState` 全 0 与 `GetSecureType` 变量并存 —— 这些只是 ABL 字符串，不能证明行为；新版 [08](08-bootchain-relock.md) 只把它当线索。
2. `docs/11-kminstallkeybox-internals.md` 的 `5r5` 类型 `0x28`/`0x05` 保留；补充：`0x28` 是原厂那份（2025-10-30），`0x05` 是 11-16 自签烧入的那份。
3. `docs/02:26` 说 `runCryptoCmd` 失败回退 HIDL —— 实际是 `RpmbChannel` 先走 Java 侧 `ICryptoeng$Stub`（反射），失败再走 HIDL，顺序应写清楚。

## 旧文档 → 新文档对照

| 旧版 | 新版 |
| --- | --- |
| `00-timeline.md` | [00-overview.md](00-overview.md)（时间线并入结论表） |
| `01-device.md` | [01-device.md](01-device.md) |
| `02-engineering-mode.md` | [02-engineering-mode.md](02-engineering-mode.md) |
| `03-cryptoeng-keymint.md` | [03-cryptoeng-hal.md](03-cryptoeng-hal.md) + [04-soter-service.md](04-soter-service.md) |
| `04-soter-attk.md` | [05-soter-ta.md](05-soter-ta.md) + [06-root-cause.md](06-root-cause.md) |
| `05-attempts.md` | [07-attempts.md](07-attempts.md) |
| `06-fake-relock.md` | [08-bootchain-relock.md](08-bootchain-relock.md) |
| `07-next-steps.md` | [06 §7](06-root-cause.md) + [08 §6](08-bootchain-relock.md) |
| `08-repro-rollback.md` | [11-repro.md](11-repro.md) |
| `09-omk-ommega-attk.md` | [07 §5](07-attempts.md) |
| `10-rkp-device-id.md` | [09-rkp-attestation.md](09-rkp-attestation.md) |
| `11-kminstallkeybox-internals.md` | [10-kminstallkeybox.md](10-kminstallkeybox.md) |
| `12-soter-key-state.md` | 内容并入 [05](05-soter-ta.md) 与 [06](06-root-cause.md) |
