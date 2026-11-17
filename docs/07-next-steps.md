# 07 后续计划

基线设备：一台 BL 锁定、TEE 正常、微信指纹可用的一加高通机；临时 root 提权（如 RootNow，要求内核 build 匹配）；保留原厂 `init_boot` / `vbmeta`。

## 待回答

状态列：`未开始` / `部分回答` / `已回答`。

| # | 问题 | 状态 | 已有线索 |
| --- | --- | --- | --- |
| 1 | 锁态下 `soter-provision 1/2/3` 的返回？ | 未开始 | 需锁态基线 |
| 2 | 锁态下工程模式 15 行的真实状态？ | 未开始 | 三态表的锁态列待填，见 README |
| 3 | `soter-provision` 从 0 变 -20 的同时，磁盘/分区有什么变化？ | 未开始 | 需解锁前后差集 |
| 4 | 回锁后是否 100% 恢复？微信是否需要重开？ | 未开始 | 社区资料倾向「是」，未实测 |
| 5 | 解锁是「屏蔽」还是「清空」ATTK？ | 部分回答 | [04 屏蔽还是清空](04-soter-attk.md#屏蔽还是清空)：TA 初始化路径即 `is_secure_boot_enabled` + `BAILING OUT`，`/persist/data/soter/` 从未创建，支持屏蔽假说；但 `soter-provision 4`（纯读）也 `-20`，用户态无法区分 |
| 6 | 锁态下的 TA 拒绝是 secure boot 检查，还是 RPMB 里已经没有 key？ | 部分回答 | 同上；要坐实只能等锁态基线或找到 TA 补丁点 |
| 7 | 如果走本地软件 TA，用哪把真 ATTK + `cpu_id` 做对照？这把根是否只属于本机？ | 未开始 | [09](09-omk-ommega-attk.md)：先确认根只属于本机/本人 |
| 8 | 解锁后 `SOTER_CE` / `enable_soter` 配置是否变化？ | 未开始 | TA 字符串显示 `qsee_cfg_getpropval` 读取这些属性，见 [12](12-soter-key-state.md) |
| 9 | 解锁后 ATTK 是消失，还是 header/magic/status 不匹配？ | 未开始 | TA 含 `get_validated_attk`、`ATTK status`、`Header not validated` |
| 10 | ATTK provisioning 被 gate 时，ASK/AuthKey/initSign/finishSign 是否仍可用？ | 未开始 | 当前只实测了 `soter-provision 1..4`，需补命令矩阵 |
| 11 | “一机一文件”是 license、状态 blob、ATTK 还是 TA patch？ | 未开始 | 按文件格式/公钥/`cpu_id`/换机行为判定，见 [12 §5](12-soter-key-state.md#5-一机一文件的五种可能) |

## 本地路线

- **软件 TA + 自签 ATTK**：只能本机自洽，过不了 TAM；不要把它当作支付可用性的证据。
- **本地导入真 ATTK + `cpu_id`**：可以过 TAM，但必须先确认这把根只属于本机/本人，否则仍会被关联。
- **自建 relay + 自己的锁态 B 机**：ATTK 不离开 TEE，是风险最低的「本地」方案。
- **假回锁 / 保留 TEE 的 root**：让原厂 TA 继续用原厂 ATTK；`efisp` 方案只覆盖部分机型，本机无 `efisp`，不可行。
- **SOTER 状态/配置恢复**：不改 key，恢复 `SOTER_CE`/`enable_soter` 或 ATTK header/status，让原厂 TA 继续用原 ATTK；目前是假设，见 [12](12-soter-key-state.md)。
- **RKP device ID 预配**（已实现）：只修 Attestation / RKP，不碰 SOTER，见 [10](10-rkp-device-id.md)。
- 详见 [09 OhMyKeymint / Ommega 与 ATTK 信任根](09-omk-ommega-attk.md)。

## 阶段 A：锁态基线

```sh
getprop | grep -E 'ro.boot|oplusboot'
cat /proc/cmdline
cat /proc/bootconfig
vendor.qti.hardware.soter-provision 1; echo rc=$?
vendor.qti.hardware.soter-provision 2; echo rc=$?
vendor.qti.hardware.soter-provision 3; echo rc=$?
```

dump 并算哈希：

- `persist`（重点 `/mnt/vendor/persist/data`、`.foxs`、`.fsec`、`rpmb_status`、`tam`）
- `secdata`、`oplusreserve1`、`uefivarstore`、`keymaster_a/b`、`abl_a/b`、`uefi_a/b`、`xbl_a/b`
- `/data/misc/keystore`、`/data/vendor/keystore`
- `Settings.Global` 的 key/attestation 项

## 阶段 B：解锁后对比

解锁（清数据，先备份）后重复阶段 A，重点：

- `oplusboot.secure_type`、`oplusboot.verifiedbootstate`
- `persist` 新增/消失/变化的文件（`DdHdVQd1…_` 与 `_Alt` 的差异）
- `oplusreserve1` 里 `VB: RWDeviceState`、`km_client_read_rpmb_boot_info`
- `soter-provision` 0 → -20 的时间点

## 阶段 C：回锁验证

- `soter-provision` 是否回 0
- 页面 SOTER 是否回绿
- 微信是否要重新开通
- ATTK 是否还在

## 阶段 D：候选 flag

差集重点：`persist` 小文件、`oplusreserve1` 的 boot info、`uefivarstore` 的 `oemLcsDevState`、QSEE 配置里的 `SOTER_CE`/`enable_soter`、ATTK header/status。

若候选 flag 在可写分区，解锁态改回去看 TEE 是否解除屏蔽。先做只读 diff，不要直接写 QSEE 配置或 RPMB。

## 阶段 E：引导链（高风险，仅备用机）

- 解包 `abl_a` LZMA FV，定位 `GetSecureType` / `set_boot_info_to_rpmb`
- 研究 `oemLcsDevState` 读取与存储格式
- 评估 EDL/firehose 刷 patched ABL + 绕 XBL 校验
- 找 SM8750 的早期代码执行入口

## 阶段 F：SOTER 状态/配置差集

优先于阶段 E，全部只读：

1. 用 `docs/12 §7 F1` 的只读命令采集锁态/解锁态现场；
2. diff `SOTER_CE`/`enable_soter`、ATTK header/status、`persist` 下 SOTER 文件、KeyStore 槽位；
3. 在公开 `soter64` TA 里定位 `qsee_cfg_getpropval`/`get_validated_attk`，确认配置名和校验路径；
4. 逐项测试 ASK/AuthKey/initSign/finishSign 命令在解锁态的授权；
5. 多机型重复，判断“所有欧加真骁龙”是否成立。

详细矩阵和判据见 [12](12-soter-key-state.md)。

## 风险

- 解锁/回锁清数据
- 回锁需原厂 `init_boot`/`vbmeta`，不匹配变砖
- 动 `persist`/`uefivarstore`/`abl` 可能不可逆损坏 TEE
