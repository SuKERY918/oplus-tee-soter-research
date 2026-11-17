# 06 根因与死锁

## 1. 结论先写

```
表头合法（magic 0x53515445 + 0xFF01）
        ↓
count 份副本逐份 AES-GCM 校验，全失败
        ↓
sub_52E8 返回 -20        ← 全 TA 只有两处写 -20，这是其中一处
        ↓
sub_5090（门禁）把 -20 上抛
        ↓
所有 ATTK 命令（257/258/259/260/261）都返回 -20
        ↓
generate 要求"门禁恰好返回 -13"，永远不满足 → 重配入口锁死
```

-20 的第二个出现位置就是 generate 自己（`va 0x674`），它以另一种方式表达了同一句话：**"表不是干净的，我不写。"**

## 2. 死锁的形式化证明

1. 所有 ATTK 命令入口先过 `sub_5090`（10 个调用点，见 [05 §4](05-soter-ta.md)）。
2. `sub_5090` 的返回值只有四种：`-21` / `-13` / `0` / `sub_52E8` 的返回值（`-11`/`-16`/`-20`/读错误）。
3. `generate_attk_key_pair`（0x5B4）**只在 `sub_5090() == -13` 时继续**；否则返回 -20，且不会调到 `store_attk`。
4. 本机 `sub_5090` 返回 -20（来自 `sub_52E8` 的 "Magic matches but attk invalid"）。
5. 要把 -20 变成 -13，必须让表头 magic 或 `0xFF01` 失效。
6. 能改表头的函数只有两个：`sub_54F0`（store_attk，只被 generate 调用，在门禁之后）与 `sub_5278`（写 0 号扇区，只被 `sub_51B4` 调用，而 `sub_51B4` 自身先过门禁、非 0 直接返回 -32）。
7. ∴ **用户态不存在把状态从 -20 迁到 -13 的路径。** 只能从外部改变表内容：RPMB 擦除、工厂工具、或回锁。

这不是"bug 没修"，而是 TA 作者假设了一个在本机**不可达**的状态（"表头有效 ⇔ ATTK 可用"）。generate 的日志原文就是证据：

```
ATTK already provisioned or RPMB not provisioned
```

他的意思是："要么已经预配好了（表头有效），要么 RPMB 根本没起来（-21）。" 而本机是第三种：**表头有效，内容解不开**。

## 3. 载荷为什么解不开：三个假设

`validate_attk_copy` 的输入只有 KDF 派生的 key、IV、TAG、密文、长度。标签是常量，因此失配只能来自：

| # | 假设 | 支持证据 | 反证 / 缺口 | 判断 |
| --- | --- | --- | --- | --- |
| A | **KDF 根随安全启动状态变化**（出厂在安全启动下写入，解锁后派生不同 key） | `sub_2E94` 明确对安全启动走 KDF、非安全启动走 PRNG；`sub_2FCC` 全程围绕 `qsee_get_secure_state`；QTI 的 `qsee_kdf` 常以安全状态选根 | 无法观测 `qsee_kdf` 内部 | **最可能** |
| B | RPMB 内容在解锁时被重预配/改写 | 解锁会重预配 RPMB key（本机 `rpmb_status` = 1）；persist `_Alt` 在 11-17 新建 | 表头 magic 与 `0xFF01` 仍完好，说明最后一次写入已完成 | 次可能 |
| C | 密文损坏（写一半 / 掉电） | 先写 entry 后写头，理论上可留下"头新内容旧" | **每次写都检查返回值**，失败即中止不写头；且 count 份全坏需同一时刻损坏 | 基本排除 |

可以确定的是：**这不是随机失败**。cmd 271 恒成功、ASK 系返回 -5 而非 -20，都说明 TA 在正常工作；`validate` 是确定性的，同样的表 + 同样的根 = 同样的结果。

### 3.1 为什么"表头有效 + 载荷失效"几乎只能是派生根变了

`store_attk` 的写入顺序是**先写全部 entry 扇区，最后写扇区 0 的 `0xFF01`**，并且**每次 `qsee_stor_write_sectors` 都检查返回值**（`store_attk` 行号 252，失败即 `goto` 清理并返回错误，不会继续写头）。

于是可以排除：

1. 写入中途断电 → 扇区 0 仍是旧值。空设备上是全 0 → 表头无效 → 门禁给 `-13`（不是 -20）。
2. 只有**所有 entry 都写完**之后，才会写 `0xFF01` → **"表头有效"本身就证明写入流程完整跑完过**，那些密文是用**写入当时的 KDF 输出**加密的。
3. 现在同一份密文、同一套常量标签，解不开 → **派生 key 在"写入时"与"读取时"不同**。

能造成这一点的只有两类原因：

- **派生根变了**（安全启动 ↔ 非安全启动、设备唯一 ID/SHK 变化、RPMB 重预配导致的 TEE 密钥层变化）；
- **算法/标签变了**（OTA 换了 TA 版本，`qsee_kdf` 实现或输入拼接方式变化）。

两者都是"外部状态变了"，不是"表被写坏"。

## 4. 副本数（count）能确定到什么程度

三条证据都指向 **count = 3**，但没有一条能直接读到值：

1. `soter-provision` 的命令 1 调 `generateAttkKeyPair(3)`（`main_cfi` 0x48EC `MOV W1,#3`）；
2. 工程模式 APK 的 `ATTK_COPY_NUM_DEFAULT = 3`；
3. 计时（各 40 次，含约 9.5 ms 固定开销）：

| 命令 | 平均 |
| --- | --- |
| `hasAskAlready`（-5，不读表） | 9.5 ms |
| `exportAskPublicKey`（-5） | 11.1 ms |
| `verifyAttkKeyPair`（-20） | 16.2 ms |
| `getDeviceId`（-20） | 16.1 ms |

ATTK 路径比 ASK 路径多约 5–6.5 ms，按单次 4 扇区 RPMB 读约 1.5–2 ms 计算，约等于读 3 份。

**为什么不能直接读**：表只存在 RPMB 里，用户态没有任何副本（§5），TA 又被完整性校验封死（[07](07-attempts.md)）。所以本文只写 `count ≈ 3`。

## 5. 取证：ATTK 表在用户态没有副本

| 对象 | 范围 | `ETQS`/`FTQS`/`SOTER`/`soter`/`ATTK` | 结论 |
| --- | --- | --- | --- |
| `/mnt/vendor/persist` | 912 文件，5,152,887 B | 0 命中 | 无副本 |
| `devinfo` | 4,096 B | 0 | 全 0 |
| `secdata` | 28,672 B | 0 | 证书链 |
| `ocdt` | 131,072 B | 0 | — |
| `uefivarstore` | 524,288 B | 0 | 全 0 |
| `misc` / `frp` | 1 MB / 512 KB | 0 | — |
| `oplus_sec_a` | 10 MB | 仅 ASCII `RPMB` @0xa259c | 是 PKI TA 的 JSON 字段名 |

`/mnt/vendor/persist/rpmb_status/rpmb_status` = `01 00 00 00`（RPMB key 已预配 OK），`tam/`、`engineermode/` 空。

`persist` 里的 `DdHdVQd1…_` 与 `_Alt` 是 **KeyMint 的 SFS 槽位**（设备 ID + attestation key），与 ATTK 无关，详见 [10 §5](10-kminstallkeybox.md)。

## 6. 修复路径评估

| 路径 | 可行性 | 代价 / 风险 |
| --- | --- | --- |
| 用户态重配 ATTK | **不可行** | 门禁要求 -13，无写入口 |
| 借 cryptoeng HAL 写 FTQS | **不可行** | HAL 无 SOTER 写入口；cryptoeng TA 只访问 0xFF02/0xFF03 |
| 借 soter TA 的 `store_attk` | **不可行** | 只被 generate 调用，且在门禁之后 |
| 替换 TA 读表 | **已实测不可行** | TEE 加载时按 `.mdt` 哈希 + 签名校验，改 1 字节即 `Error 12`（[07](07-attempts.md)） |
| **`rpmbClient smci -e 1` 全擦 RPMB** | 技术上可行 | 擦除后 FTQS 消失 → 门禁 -13 → generate 可重配。但同时抹掉 RPMB 上**所有**密钥，见下 |
| 回锁 | 不确定 | 若假设 A 成立，回锁后可能重新派生出厂那把 key，表自动可解；但 KSU + 改过 boot 的设备回锁大概率变砖 |
| 官方售后重刷 | 可行 | 恢复出厂 RPMB，清数据，解锁状态可能保留 |

### 6.1 全擦 RPMB 会失去什么

- keystore 全量（所有 App 的 key、`Android Keystore Key` 链）；
- FIDO / Passkey 凭据；
- IFAA；
- SOTER 的 ASK / AK（本来也没生成成功）；
- Widevine L1 keybox —— **不可恢复**，L1 掉到 L3；
- 部分厂商安全状态（`rpmb_status`、`oplus_sec` 相关）。

而且**不可回滚**：persist 备份写回也没有用，因为数据在 RPMB 里，不在那些分区里。

### 6.2 `rpmbClient` 是什么

`/vendor/bin/rpmbClient`（51,744 B）：

```
Usage: rpmbClient <legacy|smci> <-p|-e> <iterations>
  -p  预配/查询 RPMB key（内部还要选 0 生产线 key / 1 测试 key / 2 查询状态）
  -e  擦除整个 RPMB 分区（会要求输入 y 确认）
```

实测只读查询：`echo 2 | rpmbClient smci -p 1` → `RMPB Key status: RPMB_KEY_PROVISIONED_AND_OK (0)`，dmesg 里能看到 `smcinvoke: qtee_release/...rpmbClient`，说明 **smcinvoke 通道从 shell/root 域可用**，`-e` 大概率能执行。本次**没有执行**。

## 7. 未解问题

1. `qsee_kdf` 的根是否随安全启动状态变化——需要 TEE 侧日志或 QTI 文档；
2. 表头 count 实际值（≈3）与 device id 内容——用户态读不到；
3. 出厂时 ATTK 是否真的成功写入过——本机无历史日志；微信 `soter_status.xml` 只有 2026-11-16 的 `WechatASK=0`；
4. 回锁后 KDF 根是否恢复——需真机实验，风险高，未执行。
