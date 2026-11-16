# 08 后续研究计划

目标：在**一台 BL 锁定、TEE 正常、微信指纹支付可用**的一加设备上建立基线，查清「解锁到底改了什么」，再找在解锁状态下恢复 TEE 的方法。

## 基线设备

- 一加高通机型，BL 锁定；
- 已用临时 root 漏洞提权（例如 RootNow，要求内核 build 完全匹配，重启失效）；
- TEE 正常：工程模式 `soter-provision 2` 返回 0，微信指纹支付可开通；
- 保留原厂固件、`init_boot`、`vbmeta` 的完整备份。

## 需要先回答的问题

1. 锁态下 `soter-provision 1/2/3` 的真实返回是什么？
2. 锁态下工程模式页 15 行的真实状态？哪些「不支持」是硬件缺失，哪些是 TEE 遮蔽？
3. 解锁后 `soter-provision` 从 0 变 -20 的同时，**磁盘上/分区里**有什么变化？
4. 回锁后是否 100% 恢复？恢复需要多久/是否需要重新开通微信？
5. 解锁后 TEE 是「屏蔽」还是「清空」？ATTK 是否还在？

## 实验设计

### 阶段 A：锁态基线（不动分区）

```sh
getprop | grep -E 'ro.boot|oplusboot'
cat /proc/cmdline
cat /proc/bootconfig
vendor.qti.hardware.soter-provision 1; echo rc=$?
vendor.qti.hardware.soter-provision 2; echo rc=$?
vendor.qti.hardware.soter-provision 3; echo rc=$?
# 工程模式页截图
# 微信指纹支付开通流程录屏
```

同时 dump 并计算哈希：

- `persist`（整个分区，重点是 `/mnt/vendor/persist/data`、`.foxs`、`.fsec`、`rpmb_status`、`tam`）；
- `secdata`、`oplusreserve1`、`uefivarstore`、`keymaster_a/b`、`abl_a/b`、`uefi_a/b`、`xbl_a/b`；
- `/data/misc/keystore`、`/data/vendor/keystore`；
- `Settings.Global` 里与 key/attestation 相关的项。

### 阶段 B：解锁后对比

解锁（会清数据，先备份）后重复阶段 A 的采集，重点看：

- `oplusboot.secure_type`、`oplusboot.verifiedbootstate` 的变化；
- `persist` 里哪些文件新增/消失/内容变化；
- `oplusreserve1` 的引导日志里 `VB: RWDeviceState`、`km_client_read_rpmb_boot_info` 的值；
- `soter-provision` 从 0 → -20 的时间点（解锁后第一次开机？还是回锁再解锁后？）。

### 阶段 C：回锁验证可逆性

回锁，重复阶段 A：

- `soter-provision` 是否恢复 0；
- 工程模式 SOTER 是否恢复绿；
- 微信指纹是否需要重新开通；
- ATTK 是否还在（看 ASK 计数器、`soter_status.xml`）。

### 阶段 D：候选 flag 定位

把阶段 A/B 的差异做差集，重点找：

- `persist` 下新增/修改的小文件（几字节到几 KB）；
- `oplusreserve1` 里 boot info 结构的变化；
- `uefivarstore` 是否出现 `oemLcsDevState` 变量。

如果发现候选 flag 落在可写分区（persist/uefivarstore），在解锁态尝试改回去，看 TEE 是否解除屏蔽——这是最理想的「软件假回锁」。

### 阶段 E：引导链级手段（高风险，仅在备用机）

- 解包 `abl_a` 的 LZMA FV，定位 `GetSecureType` / `set_boot_info_to_rpmb` 调用点；
- 研究 `oemLcsDevState` 的读取路径和变量存储格式；
- 评估 EDL/firehose 刷入 patched ABL + 绕过 XBL 校验的可行性；
- 参考 gbl-chainload 的 protocol hook 思路，但 SM8750 没有 efisp，需要另找早期代码执行入口。

## 工具与脚本

- 分区 dump：`dd if=/dev/block/by-name/<name> of=/data/local/tmp/test/<name>.img`
- 字符串/熵：`strings`、`python` 的 `math.log2` 熵计算
- LZMA 解压：`python -c "import lzma; ..."`
- Frida：`frida-server` + `frida-java-bridge`（Frida 17 默认不带 Java bridge）
- SOTER 调用观测：hook `com.tencent.soter.soterserver.SoterService` 的 `y` / `P` / `L` / `M` / `N` / `O` 等合成方法

## 风险

- 解锁/回锁都会清数据；
- 回锁需要原厂 `init_boot`/`vbmeta`，镜像不匹配会变砖；
- 动 `persist` / `uefivarstore` / `abl` 可能造成不可逆的 TEE 损坏；
- 所有破坏性实验只在备用机上进行，主力机不要碰。
