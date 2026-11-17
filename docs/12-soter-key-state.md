# 12 SOTER key 状态机与“真修复”假设

本文把 04/05/09 的结论往前推一步：**解锁态 SOTER 失败，可能不是 ATTK 被销毁，而是 TA 的 secure-state / 配置 / ATTK 状态校验把原 key 拦住了。**

内容分三部分：

1. 已经能确认的事实；
2. 公开 TA 字符串暴露出的状态机；
3. 对所有欧加真骁龙通用方案的可验证假设与实验顺序。

> 本文不提供 ATTK 私钥提取、TA 注入或支付绕过的操作步骤。所有写入类实验只应在备用机上进行。

## 1. 已确认事实

| # | 事实 | 证据等级 |
| --- | --- | --- |
| 1 | TAM 按 `device_id` 查 ATTK 公钥，不是“有厂商根证书就认” | 公开文档：腾讯 SOTER 后台接口错误码 `90005 无法找到所请求 device_id 对应的 attk` |
| 2 | ATTK 私钥在 TEE/RPMB，root 不能直接读出 | 公开资料 + 本机 `soter-provision 1/2/3/4` 全 `-20` |
| 3 | 微信开通时把 ASK 公钥 + `cpu_id` + `uid` 上报；TAM 不认自签 ATTK | 09 实测：自签链 ASK 被秒清 |
| 4 | 一加解锁后 KeyStore 切到第二槽位，原槽位保留；回锁恢复原槽位 | 社区教程 + 本机 persist 行为 |
| 5 | `soter64` TA 有 `is_secure_boot_enabled` / `qsee_get_secure_state` / `BAILING OUT` | 本机 TA 字符串；OnePlus 6/9 Pro 公开 dump 同样存在 |
| 6 | `soter-provision` 只暴露 1–4（Generate/Verify/Export ATTK、GetDeviceId），没有导入/迁移命令 | OnePlus 9 Pro dump 的 `vendor.qti.hardware.soter-provision` 字符串 |
| 7 | OnePlus 6 的 TA 含 `soter_attk_migration` / `store_migration_attk`；OnePlus 9 Pro 的 TA 已无这些字符串 | 公开 dump 对比，不能直接外推到 Ace 6 |
| 8 | 仅重启 `vendor.soter` + 清 `soterserver` 数据，有时能让 SOTER key 恢复 | `SoterFixer` 行为；说明失败至少部分是状态性/缓存性，不是纯密钥销毁 |

## 2. TA 字符串暴露的状态机

从公开的 OnePlus 6 / 9 Pro dump 提取 `soter64` 段并拼接后，能看到三组与“状态”有关的字符串。

### 2.1 QSEE 配置/开关

```text
query_device_id
is_secure_boot_enabled
SOTER_CE
enable_set_bandwidth
qsee_cfg_getpropval
...
enable_soter
get_soter_enable
soter_enable_default %d
```

`enable_soter` / `get_soter_enable` / `soter_enable_default` 紧邻 `qsee_cfg_getpropval`，强烈提示 TA 在启动或处理命令时读取一个 QSEE 配置属性，决定 SOTER 是否启用。`SOTER_CE` 很可能是其中一个配置项。

如果解锁只是把该配置/默认值改成“禁用”，那么：

- ATTK 仍然在 RPMB；
- TA 不是没有 key，而是被配置逻辑拦住；
- 恢复配置/状态即可让原厂 TA 继续使用原 ATTK；
- 不需要提取私钥、不需要 TAM 重新注册；
- 该逻辑在 Qualcomm 平台上共享，天然覆盖所有欧加真骁龙。

### 2.2 ATTK header/status 校验

```text
get_validated_attk
SOTER: Header not validated
magic_num:0x%x, expected:0x%x
ATTK status:0x%x, expected:0x%x
SOTER: ATTK not set
update_soter_rpmb_header
soter_query_update_counter
soter_rpmb_alloc_read
Magic matches but attk invalid
```

这说明 TA 不是“只认私钥”，还要校验 ATTK 的 header、magic、status 和 RPMB counter。解锁后如果只是 header/status 不匹配，恢复状态 blob 就可能让原 key 重新可用。

### 2.3 命令面

```text
SOTER_GENERATE_ATTK
SOTER_VERIFY_ATTK
SOTER_EXPORT_ATTK_PUBLIC
SOTER_GET_DEVICE_ID
SOTER_GENERATE_ASK
SOTER_EXPORT_ASK_PUBLIC
SOTER_REMOVE_ALL_UID_KEY
SOTER_HAS_ASK_ALREADY
SOTER_GENERATE_AK
SOTER_EXPORT_AK_PUBLIC
SOTER_REMOVE_AK
SOTER_HAS_AK
SOTER_INIT_SIGN
SOTER_FINISH_SIGN
SOTER_GET_VERSION
```

当前只实测了 ATTK 的 1–4 命令。**ASK/AuthKey/initSign/finishSign 是否也被 secure-state 挡住，还没有逐项验证。** 如果 ATTK provisioning 被 gate，但 ASK/签名命令仍可用，那么原厂 TA 可以直接用原 ATTK 走微信，不需要修复 provisioning。

## 3. “所有欧加真骁龙”意味着什么

一个方案能覆盖所有欧加真骁龙，核心必须在它们共有的层：

- Qualcomm QSEE + `soter64` TA；
- Oplus KeyStore 槽位/锁态逻辑；
- Oplus 的 SOTER 配置/provisioning 服务；
- 或者一个通用的 TEE/TA 漏洞。

“每台设备各有一把不同的真 ATTK”不能解释“所有设备通用”：工具可以通用，但每台设备仍需要自己的 key，本质是 key 供应链，不是单一修复方法。

## 4. 候选路线

| 路线 | 用哪把 ATTK | 是否要 TAM 注册 | 是否要 TEE/TA 能力 | 与“一机一文件”的吻合度 | 当前证据 |
| --- | --- | --- | --- | --- | --- |
| A. 恢复 `SOTER_CE` / `enable_soter` / ATTK status | 原机 ATTK | 不需要 | 可能需要写 QSEE 配置/SFS | 高（配置/状态 blob 或 license） | TA 字符串强提示，待锁态/解锁态差集 |
| B. 强制原 KeyStore 槽位/恢复原槽位 key blob | 原机 ATTK | 不需要 | Oplus 槽位逻辑绕过 | 高（设备绑定 blob） | 槽位切换已确认；TA 仍可能 secure-state 拒绝 |
| C. Oplus/WeCooper 重新注册新 ATTK | 新生成 ATTK | 需要 OEM 侧注册 | 需要 TA 能生成 key | 高（注册响应/公钥文件） | 公开资料说支持有限；无公开入口 |
| D. 真 ATTK 私钥导入（本机提取/捐赠机） | 已注册 ATTK | 不需要（已注册） | 需要 TEE/TA 漏洞或 key 来源 | 高（ATTK PEM + cpu_id） | 现代 O+ 无公开通用方法；先例是小米 CVE-2020-14125 |
| E. 本地软件 TA + 随机 ATTK | 随机 | 无法注册 | 不需要 | 低 | 只能过检测器，微信会清钥匙 |
| F. 密码代填 | 不用 ATTK | 不需要 | 不需要 | 中（设备绑定密码库） | 一加 root 圈常见替代方案，但不是 SOTER |

当前优先级：

1. **A**：TA 字符串最直接，且能用原 key，完全符合“修复 SOTER key”；
2. **B**：Oplus 共享逻辑，能用原 key，但 secure-state 仍是关卡；
3. **C**：如果他有 OEM/售后注册通道，能解释“新 key + 所有设备”；
4. **D**：你的原假设，技术上成立，但需要 TEE/TA 0-day 或 key 来源；
5. **E/F**：作为对照，不能证明真 SOTER。

## 5. “一机一文件”的五种可能

| 文件形态 | 最可能含义 | 判定要点 |
| --- | --- | --- |
| 几 KB 文本/JSON，含设备 ID、序列号、签名 | 付费 license/授权文件 | 换机失效；删除后功能失效；不含密钥材料 |
| 几 KB PEM/JSON，含 RSA 私钥 + `cpu_id` | 真 ATTK 文件 | 公钥应与 TAM 已注册 ATTK 一致；`cpu_id` 应与设备一致 |
| 几十~几百 KB 二进制 | QSEE/SOTER 状态 blob、KeyStore 槽位备份、TA patch | 设备绑定；可能一次性导入；不含 PEM |
| XML keybox | KeyMint/Attestation keybox | 不是 SOTER ATTK，不能直接修微信 |
| token/服务器配置 | relay | 与“纯本地”矛盾；断网测试可排除 |

注意：**“一机一文件”在付费软件语境里最常见的是 license**，不一定等于“一机一把 SOTER 私钥”。

## 6. 验证矩阵

在备用机上按顺序做，避免在主账号/真实支付环境试验。

### 6.1 锁态 vs 解锁态

| 项目 | 锁态 | 解锁态 | 关注点 |
| --- | --- | --- | --- |
| `/proc/cmdline` | `verifiedbootstate=green` | `orange` | 真实锁态 |
| `soter-provision 1/2/3/4` | 0 | -20 | 是 key 不在，还是状态被拦 |
| `SOTER_CE` / `enable_soter` 配置 | 记录 | 记录 | 是否被改写 |
| `get_validated_attk` 相关状态 | 记录 | 记录 | header/magic/status 是否变化 |
| `/mnt/vendor/persist/data/soter` | 记录 | 记录 | 是否存在/内容变化 |
| KeyStore 槽位 | 槽位 1 | 槽位 2 | 原槽位是否保留 |

### 6.2 命令授权矩阵

在解锁态逐项测试（只读/无副作用优先）：

- `SOTER_GET_DEVICE_ID`
- `SOTER_GENERATE_ASK`
- `SOTER_EXPORT_ASK_PUBLIC`
- `SOTER_GENERATE_AK`
- `SOTER_EXPORT_AK_PUBLIC`
- `SOTER_INIT_SIGN`
- `SOTER_FINISH_SIGN`

记录每项返回码和调用 UID/SELinux 上下文。重点判断：**ATTK provisioning 被 gate 时，ASK/签名命令是否仍然可用。**

### 6.3 微信侧判据

- `soter_status.xml` 的 `WechatASK` 是否稳定为 1；
- 支付时 logcat 是否有 `initSign` / `finishSign`；
- 修改微信支付密码后，指纹支付是否仍可用；
- 清除他提供的 app/文件数据后，是否仍可用；
- 冻结 `com.tencent.soter.soterserver` 后，是否仍可用。

真 SOTER：`WechatASK=1`，有 SOTER 签名，改密码/清数据不影响，冻结 SOTER 会失败。  
密码代填：`WechatASK` 为 0/假，没有 SOTER 签名，改密码/清数据会失效，冻结 SOTER 仍可用。

### 6.4 文件判据

- 文件里是设备 ID + 签名，还是 RSA 私钥/证书/TA blob？
- 同一个文件换一台同型号设备还能用吗？
- 文件是一次性导入，还是每次开机校验？
- 文件里的 ATTK 公钥与 `soter-provision 3` 导出的是否一致？
- 文件里的 `cpu_id` 与 `soter-provision 4` 返回的是否一致？

## 7. 阶段 F：SOTER 状态/配置差集

这是 07 阶段 A–E 之后新增的实验阶段。

### F1. 锁态基线

在 BL 锁定、SOTER 正常的设备上采集：

```sh
getprop | grep -iE 'soter|qsee|secure'
cat /proc/cmdline
ps -A | grep -i soter
vendor.qti.hardware.soter-provision 1; echo rc=$?
vendor.qti.hardware.soter-provision 2; echo rc=$?
vendor.qti.hardware.soter-provision 3; echo rc=$?
vendor.qti.hardware.soter-provision 4; echo rc=$?
find /mnt/vendor/persist -maxdepth 4 -iname '*soter*' 2>/dev/null
ls -la /mnt/vendor/persist/data/soter 2>/dev/null
sha256sum /vendor/firmware_mnt/image/soter64.* 2>/dev/null
```

### F2. 解锁后重复

解锁后重复 F1，重点 diff：

- `SOTER_CE` / `enable_soter` 配置；
- ATTK header/magic/status；
- `persist` 下 SOTER 相关文件；
- KeyStore 槽位；
- TA 版本/哈希（是否随 OTA 变化）。

### F3. 反编译 TA

用公开固件里的 `soter64` 段（`b00…b07` 拼接）：

- 定位 `qsee_cfg_getpropval` 调用点；
- 找 `SOTER_CE` / `enable_soter` 的属性名、默认值、写入路径；
- 找 `get_validated_attk` 的 header/magic/status 校验；
- 找命令 dispatch 表，确认哪些命令受 secure-state 检查。

### F4. 验证恢复

只在备用机上：

- 尝试恢复候选配置/状态，观察 `soter-provision 3` 是否从 `-20` 变 0；
- 观察微信 `WechatASK` 是否变 1；
- 如果配置有签名/校验，记录校验路径，不要盲目写入。

### F5. 多机型对比

在一加 11 / 12 / Ace 2 / Ace 5 等至少两台骁龙 O+ 设备上重复 F1–F2：

- 如果同一配置项/状态文件都成立，支持“平台级通用方法”；
- 如果只在部分机型成立，说明“所有欧加真骁龙”需要更精确的限定。

## 8. 预测与判定

以下是基于现有事实的预测，不是已复现结论。

### 预测 1：核心不是“每台设备一把 ATTK”，而是平台共享的状态/配置门槛

置信度：高。

理由：

- ATTK 一机一密，TAM 按 `device_id` 查公钥；如果每台设备都要一把已注册 ATTK，本质是 key 供应链，不能自然解释“所有欧加真骁龙通用”。
- QSEE/`soter64` TA、`SOTER_CE`/`enable_soter` 配置、KeyStore 槽位逻辑都是平台共享的；一个通用状态/配置方法更符合“覆盖所有设备”。
- `SoterFixer` 仅重启 `vendor.soter` 就能偶发恢复，说明失败有状态性，不是纯密钥销毁。

预期证据：锁态/解锁态的 `SOTER_CE`/`enable_soter` 或 ATTK header/status 有稳定差异；恢复状态后 `soter-provision 3` 从 `-20` 变 0。

### 预测 2：真修复大概率仍使用原机 ATTK，私钥不出 TEE

置信度：中高。

理由：

- 原 ATTK 已在 TAM 注册，不需要重新注册；只要让 TA 重新接受它，就能过微信。
- 这比提取私钥、重新注册或 relay 都更干净，也最符合“修复 SOTER key”。
- “一机一文件”可以是设备绑定的状态 blob、KeyStore 槽位备份、TA patch 或付费 license，而不是 ATTK PEM。

预期证据：文件里没有 RSA 私钥；`soter-provision 3` 导出的公钥与文件中的公钥/设备身份一致；恢复文件后原厂 TA 返回 0。

### 预测 3：如果文件是 RSA 私钥 + `cpu_id`，才是真 ATTK 导入

置信度：中低。

理由：

- 真 ATTK 导入技术上成立，但需要 TEE/TA 漏洞或工厂/捐赠 key；现代 O+ 的 RPMB/TEE 不会让 root 直接读出私钥。
- 如果“所有设备通用”指的是提取工具通用，每台设备仍需要自己的 key；这时“一机一文件”是 ATTK 文件，不是 license。
- 若文件里的 `cpu_id` 与设备不一致，则是捐赠身份/借用，不是本机修复。

预期证据：文件含 `BEGIN RSA PRIVATE KEY`/`BEGIN PRIVATE KEY`；公钥与 TAM 已注册 ATTK 一致；换机后 `cpu_id` 不匹配则失效。

### 预测 4：如果 `WechatASK=0` 或改支付密码后失效，实际不是 SOTER

置信度：高（作为排除条件）。

理由：

- 真 SOTER 的 ASK 已注册，改微信支付密码不影响指纹支付；清应用数据后重新开通仍可用；冻结 `soterserver` 会失败。
- 密码代填依赖保存的支付密码，改密码/清数据会失效；冻结 SOTER 仍可用。

预期证据：`soter_status.xml`、logcat、改密码/清数据/冻结 SOTER 四组测试。

### 预测 5：“所有欧加真骁龙”需要至少两台不同平台验证

置信度：中。

理由：

- 同一套 QSEE/TA 配置逻辑可能随 SoC/固件版本变化；只测一台不能证明“所有”。
- 如果 Ace 2（SM8475）和一加 12/13（SM8650/SM8750）都成立，平台级方法的可信度才高。
- 如果只在部分机型成立，该说法应改为“已测试的欧加真骁龙机型”。

### 优先验证顺序

1. **A：状态/配置恢复**——最符合“原 key + 所有设备”，先做锁态/解锁态 diff。
2. **B：KeyStore 槽位/原槽位 key blob**——与 Oplus 已知槽位切换行为直接相关。
3. **C：WeCooper/新 ATTK 注册**——只有发现 OEM/售后入口时才成立。
4. **D：真 ATTK 导入**——看到 PEM + `cpu_id` 再投入，否则不要先假设。
5. **E/F：本地软件 TA/密码代填**——作为对照组，用来排除“假 SOTER”。

## 9. 边界

- 本文的“A/B/C”都是**待验证假设**，不是已复现结论。
- 工程模式 SOTER 绿、`cmd 57=0`、本地检测器通过，都不能证明微信会接受；决定性是 TAM 和微信实际支付流程。
- 不要在主账号/真实支付环境试验；不要买卖或共享 ATTK/keybox；不要在来源不明的文件上执行 root 脚本。
- 写入 QSEE 配置、persist、RPMB、TA 或 KeyStore 槽位都可能不可逆损坏 TEE；只在有恢复镜像的备用机上进行。

## 10. 参考

- [腾讯 SOTER 后台接口（TAM 按 device_id 查 ATTK）](https://github.com/Tencent/soter/wiki/%E5%90%8E%E5%8F%B0%E6%8E%A5%E5%8F%A3%E6%96%87%E6%A1%A3)
- [OnePlus 9 Pro dump（soter64 TA / provision 二进制）](https://github.com/xealea/oneplus_oneplus9pro_dump)
- [OnePlus 6 dump（含 ATTK migration/状态字符串）](https://github.com/Nervnyi1990/oneplus_oneplus6_dump)
- [SoterFixer（重启 vendor.soter，说明状态可被重置）](https://github.com/xiaohuangbo/SoterFixer)
- [一加解锁后 KeyStore 切槽位教程](http://www.romleyuan.com/lec/read?id=1404)
- [MlgmXyysd 关于 SOTER key/WeCooper 的说明](https://t.me/s/MlgmXyysd_bibilailai/2838)
- [Check Point 小米 TEE / SOTER 私钥提取研究](https://research.checkpoint.com/2022/researching-xiaomis-tee/)
- [Ommega 本地 ATTK 导入实现](https://github.com/jiyin004-jpg/ommega)
- 本仓库 [04](04-soter-attk.md)、[09](09-omk-ommega-attk.md)