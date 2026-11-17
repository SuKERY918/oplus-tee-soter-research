# 00 结论总览

本文是全仓库的索引与结论汇总。后续各篇给证据，本篇给判断。

## 1. 一句话结论

**SOTER key 红，不是"解锁把 key 删了"，而是：TEE 里 RPMB 的 ATTK 表头完好、载荷无法用当前派生根解开，而 TA 的重配入口又硬性要求表头"无效"。两点叠加成一个用户态无法打破的死锁。**

## 2. 十二节点结论

| # | 结论 | 证据强度 | 详情 |
|---|---|---|---|
| 1 | 工程模式 SOTER 行 = `runCryptoCmd(57)` = `ISoter.verifyAttkKeyPair()`，只判返回值 `== 0` | 代码 | [02](02-engineering-mode.md) |
| 2 | `-20` 由 TA 自己写入响应首字段（HAL 只是转抄），全 TA 只有两处产生它 | 静态 + 日志 | [05](05-soter-ta.md) |
| 3 | `-20` 的真实含义：表头 magic/标志合法，但 count 份副本**全部** AES-GCM 校验失败 | 静态 | [06](06-root-cause.md) |
| 4 | `generate_attk_key_pair` 要求门禁**恰好返回 -13**，故重配永远被拒 → 死锁 | 静态 | [06](06-root-cause.md) |
| 5 | `-13` 只在"表头无效"时出现；能改表头的函数都在门禁之后 | 静态 | [06](06-root-cause.md) |
| 6 | 用户态无 ATTK 表副本：persist 5 MB + 7 个分区全量扫描 0 命中 | 实测 | [06](06-root-cause.md) |
| 7 | 载荷失配的最可能原因是派生根随安全启动状态变化（TA 在 `query_device_id` 里就写了这个分支） | 静态推断 | [06](06-root-cause.md) |
| 8 | "假绿"= HAL 把 death 回调反注册 + 用初始值 0 当结果；与 TA 无关 | 静态 + A/B | [02](02-engineering-mode.md) |
| 9 | `-1000` 是 `generateAttkKeyPair` 处理器的局部变量初值，不是 TA 返回码 | 静态 | [03](03-cryptoeng-hal.md) |
| 10 | cryptoeng HAL 只有 4 个处理器碰 ISoter，**没有任何 reset/删除入口** | 静态 | [03](03-cryptoeng-hal.md) |
| 11 | 替换 TA 读表已被实测封死：TEE 加载时按 `.mdt` 的 SHA-384 + OEM 签名校验，改 1 字节即 `Error 12` | 实测 | [07](07-attempts.md) |
| 12 | 厂商自己在 APK 里设了同一把锁：解锁态直接 `return 10000`，连 TA 都不调 | 代码 | [07](07-attempts.md) |

## 3. 三个"曾经写错、现已更正"的点

早期文档（v1/v2）里这三条是错的，本版已改，逐条对照见 [12-errata](12-errata.md)：

1. **假绿机理**：不是"TA 失败返回空 buffer"，而是 HAL 侧 AIDL 调用失败后把初值 0 写出。触发条件是 **soter 服务重启过**（HAL 缓存代理失效且 death 回调被删，永不清缓存）。
2. **`/persist/data/soter/` 找不到 → 屏蔽**：不成立。ATTK 存在 RPMB 的 stor 逻辑分区（id `0x53515446`），`/persist/data/soter/` 是 TA 里另一套 SFS 代码的路径，本来就与 ATTK 无关。
3. **TA 替身（Ommega 等）能绕过**：只能骗过 UI 或 App 的本地判定；ATTK 的信任根在 TEE，替换 TA 会被 `Error 12` 拒载。

## 4. 三条"看起来该有、其实没有"的路

| 想法 | 为什么不行 |
|---|---|
| 调 `soter-provision` 重新生成 | 工具只暴露 1–4（generate/verify/export/deviceid），generate 被门禁挡死 |
| 借 cryptoeng HAL 写 RPMB | cryptoeng TA 只访问自己的 0xFF02/0xFF03 分区；HAL 无 SOTER 写入口 |
| 改 TA 让它帮忙读表 | 映像完整性校验在 TEE 内，改一字节就拒载（[07](07-attempts.md)） |

## 5. 仍然成立的唯一自助手段

`/vendor/bin/rpmbClient smci -e 1` —— RPMB 全擦。能让表头消失（门禁回到 -13，generate 才有可能成功），代价是 RPMB 上所有密钥一起消失。评估见 [06 §5](06-root-cause.md)。

## 6. 这份仓库现在有什么

```
README.md                项目总览与结论
docs/00-overview.md      本文：结论与索引
docs/01-device.md        设备、属性、分区、真实锁态判定
docs/02-engineering-mode.md  15 行判定链、假绿机理与复现
docs/03-cryptoeng-hal.md cryptoeng HAL 逆向：分发器、命令表、SOTER 处理器
docs/04-soter-service.md soter-service 与 ISoter 事务矩阵、TA 命令号
docs/05-soter-ta.md      soter64 TA 镜像重建、分派表、门禁伪代码、ATTK 表格式
docs/06-root-cause.md    根因、死锁证明、三假设与排除、修复评估
docs/07-attempts.md      历史尝试、TA 注入实验、厂商闸门
docs/08-bootchain-relock.md  引导链、oplusreserve1、回锁边界
docs/09-rkp-attestation.md   RKP device ID 预配（唯一已验证的持久修复）
docs/10-kminstallkeybox.md   KmInstallKeybox 逆向与 persist SFS 槽位格式
docs/11-repro.md         复现手册（设备侧 + 静态侧）
docs/12-errata.md        对旧版文档的逐条勘误
tools/                   诊断/修复脚本 + 静态分析脚本
```

## 7. 证据强度约定

本仓库所有结论标注三档：

- **实测**：在本机跑出来、日志或返回值可复现；
- **代码**：反编译/反汇编可逐行核对；
- **静态推断**：由代码行为推出、但无法在用户态直接观测（会明确写出"无法证实"）。

旧版文档里"读过、猜过、推论过"混在一起写，是这次重写最主要要修的问题。
