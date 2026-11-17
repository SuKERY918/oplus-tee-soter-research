# 07 后续计划

基线设备：一台 BL 锁定、TEE 正常、微信指纹可用的一加高通机；临时 root 提权（如 RootNow，要求内核 build 匹配）；保留原厂 `init_boot` / `vbmeta`。

## 待回答

1. 锁态下 `soter-provision 1/2/3` 的返回？
2. 锁态下工程模式 15 行的真实状态？
3. `soter-provision` 从 0 变 -20 的同时，磁盘/分区有什么变化？
4. 回锁后是否 100% 恢复？微信是否需要重开？
5. 解锁是「屏蔽」还是「清空」ATTK？
6. 锁态下的 TA 拒绝是 secure boot 检查，还是 RPMB 里已经没有 key？
7. 如果走本地软件 TA，用哪把真 ATTK + `cpu_id` 做对照？这把根是否只属于本机？

## 本地路线（补充）

- **软件 TA + 自签 ATTK**：只能本机自洽，过不了 TAM；不要把它当作支付可用性的证据。
- **本地导入真 ATTK + `cpu_id`**：可以过 TAM，但必须先确认这把根只属于本机/本人，否则仍会被关联。
- **自建 relay + 自己的锁态 B 机**：ATTK 不离开 TEE，是风险最低的"本地"方案。
- **假回锁 / 保留 TEE 的 root**：让原厂 TA 继续用原厂 ATTK；`efisp` 方案只覆盖部分机型。
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
- `persist` 新增/消失/变化的文件
- `oplusreserve1` 里 `VB: RWDeviceState`、`km_client_read_rpmb_boot_info`
- `soter-provision` 0 → -20 的时间点

## 阶段 C：回锁验证

- `soter-provision` 是否回 0
- 页面 SOTER 是否回绿
- 微信是否要重新开通
- ATTK 是否还在

## 阶段 D：候选 flag

差集重点：`persist` 小文件、`oplusreserve1` 的 boot info、`uefivarstore` 的 `oemLcsDevState`。

若候选 flag 在可写分区，解锁态改回去看 TEE 是否解除屏蔽。

## 阶段 E：引导链（高风险，仅备用机）

- 解包 `abl_a` LZMA FV，定位 `GetSecureType` / `set_boot_info_to_rpmb`
- 研究 `oemLcsDevState` 读取与存储格式
- 评估 EDL/firehose 刷 patched ABL + 绕 XBL 校验
- 找 SM8750 的早期代码执行入口

## 风险

- 解锁/回锁清数据
- 回锁需原厂 `init_boot`/`vbmeta`，不匹配变砖
- 动 `persist`/`uefivarstore`/`abl` 可能不可逆损坏 TEE
