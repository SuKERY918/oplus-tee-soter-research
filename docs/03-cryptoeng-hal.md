# 03 cryptoeng HAL

`vendor.oplus.hardware.cryptoeng@1.0-service` 是 OPLUS 自己的"密码学杂项" HAL：工程模式、产线工具、指纹支付、RKP 都挂在它上面。SOTER 只是它的第 57/58 号命令。

## 1. 样本与服务

| 项 | 值 |
| --- | --- |
| 路径 | `/odm/bin/hw/vendor.oplus.hardware.cryptoeng@1.0-service` |
| 大小 | 168,960 B |
| 符号 | **未 strip**，函数名可直接定位 |
| init | `/odm/etc/init/vendor.oplus.hardware.cryptoeng@1.0-service_FDE.rc` |
| service | `hal_cryptoeng_oplus`，`class hal`，`user system` |
| 接口 | `aidl vendor.oplus.hardware.cryptoeng.ICryptoeng/default` |
| 日志 tag | `cryptoeng_hidl` |

`kill -9` 后 init 立刻拉起（pid 会变），可用作"清缓存"手段——这正是恢复假绿的办法（[02 §4](02-engineering-mode.md)）。

同一份 rc 里有一段 `on property:sys.boot_completed=1 && property:ro.board.platform=canoe` 的 chmod，指向 persist 的 `DdHdVQd1…_` 与 `_Alt`。**本机 `ro.board.platform=sun`，这段不执行**，所以它既不能证明"cryptoeng 正在用这个槽位"，也不能当作归属判据；槽位内容按 tag 判定属于 KeyMint（[10 §5](10-kminstallkeybox.md)）。

## 2. 入口与分发

```
aidl::...::cryptoeng_aidl::cryptoeng_invoke_command   (0x177b4)
    ├─ check_cmd_authtoken(in, uid, pid)      失败 → 日志 sbuf_len = %d, check permission failed.
    └─ malloc(0x5800) → cryptoeng_invoke_command (0x1415c)
           日志：cryptoeng_invoke_command in_len:%d, cmdid = %d
           两张命令表：
             表1 @0x200A8，26 项，func(out, in, in_len, out_len)
             表2 @0x20248，25 项，带 device 参数
```

`check_cmd_authtoken` 说明该 HAL 有按 uid/pid 的命令白名单，但 `service call`（shell uid）实测全部命令都能进到分发器，不做深究。

## 3. 命令表（表1，`work/dumptable.py` 解出）

| cmd | 实现 | 与 SOTER 的关系 |
| --- | --- | --- |
| 53 | `cryptoeng_clean_up` (0x16898) | 否 |
| 54 | `cryptoeng_get_secureType` (0x16954) | 否（但会读 secure state） |
| 55 | `getDeviceId` (0x19c84) | **是**（ISoter getDeviceId） |
| 56 | `exportAttkKeyPair` (0x1993c) | **是** |
| 57 | `verifyAttkKeyPair` (0x197c0) | **是**（工程模式 SOTER 行） |
| 58 | `generateAttkKeyPair` (0x195ec) | **是** |
| 61 | `android_rkp_handle` (0x1a444) | 否（RKP 工厂工具） |
| 90 | `cryptoeng_invoke_engineer_command` (0x152ec) | 否 |
| 91 | `cryptoeng_invoke_read_oplusreserve_command` (0x1511c) | 否 |
| 92 | 0xd4bc | 否 |
| 1001 | `gatekeeper_invoke_commond` (0x15544) | 否 |

几个容易被误解的命令，逐条说清楚：

- **cmd 61** = `android_rkp_handle`：`dlopen("librkp_factory_extraction_tool.so")` → `dlsym("rkp_tool_entry")`，把入参交给它。失败日志 `android_rkp_handle , dlapi run failed! ret = %d`。它能"打死 HAL"是因为调进了不健壮的厂商库，与 SOTER 无关。
- **cmd 90** = `cryptoeng_invoke_engineer_command`：把入参按空格切开，只认 `--engineer_demo`，命中就返回一段 `{"cryptoeng-test": ...}` JSON，其它一律 `not-support`。纯 demo，没有任何工程能力。
- **cmd 91** = 读 `/dev/block/by-name/oplusreserve1`（或 `opporeserve1`）里的 unlock record：legacy 偏移 4,861,952、非 legacy 偏移 4,653,568，读 0x40 字节。
- **cmd 1001** = `gatekeeper_invoke_commond`：只调 `save_security_log()`。

**结论：HAL 里只有 4 个处理器会碰 ISoter（55/56/57/58），没有任何 remove / reset / delete ATTK 的入口。** 这是 xref 级确认，不是"没找到"。

## 4. 四个 SOTER 处理器

### 4.1 `verifyAttkKeyPair` (0x197c0)

```c
int v13 = 0;
log(4, "cryptoeng_hidl", "Trying to connect to service ISoter aidl");
getSoterAidl(&proxy);
if (proxy) {
    log(4, "cryptoeng_hidl", "calling Soter service api : verifyAttkKeyPair()");
    Status st = proxy->verifyAttkKeyPair(&v13);      // vtable + 152
    if (st.ok() && v13 == 0) log(6, "success to VerifyAttkKeyPair");
    else log(6, "Failed to VerifyAttkKeyPair, error %d", v13);
} else {
    log(6, "Failed to get Soter service");
    v13 = -10;
}
*out = v13; *out_len = 4;
```

### 4.2 `generateAttkKeyPair` (0x195ec)

```c
int v16 = -1000;                                      // ← 初值，就是"cmd 58 返回 -1000"的来源
if (in_len <= 0xFFF) { memcpy(s, in + 4, in_len - 4); uid = s[0]; }
... AIDL 调用（vtable + 88），结果写入 v16 ...
*out = v16; *out_len = 4;
```

`in + 4` 就是 `runCryptoCmd` 传的 `[58,0,0,0]` 之后的 4 字节副本数。工程模式 APK 用的常量是 `ATTK_COPY_NUM_DEFAULT = 3`。

### 4.3 `exportAttkKeyPair` (0x1993c) / `getDeviceId` (0x19c84)

两者初值都是 0，分别对应 vtable + 56、+ 104，日志 `PubKeyLen %d` / `Failed to export attk, error %d`、`Failed to get device id, error %d`。`getDeviceId` 的输出是 `%02x` 拼出来的十六进制串。

### 4.4 ISoter 代理的缓存与 death 回调（假绿根源）

`getSoterAidl` (0x19270)：

```c
if (cached_proxy) return cached_proxy;                        // xmmword_28180
binder = AServiceManager_waitForService("…ISoter/default");
if (!binder) { log(6,"cryptoeng_hidl","soter service doesn't exist"); return; }
recipient = AIBinder_DeathRecipient_new(serviceDiedAidl);
if (AIBinder_linkToDeath(binder, recipient, serviceDiedAidl) != OK)
    log(6,"cryptoeng_hidl","linking soter service to death failed: %d: %s", ...);
proxy = ISoter::fromBinder(binder);
cached_proxy = proxy;
log(6,"cryptoeng_hidl","soter service linked to death!!");
...
AIBinder_DeathRecipient_delete(recipient);                    // ← 出口无条件反注册
```

`serviceDiedAidl` (0x191f0) 只有两句：`log(4,"cryptoeng_hidl","soter just died")`、`cached_proxy = 0`。

因为 recipient 被立刻删掉，**soter 重启后回调永不触发**——日志里从来看不到 `soter just died`，缓存代理永久失效，而处理器又把初值 0 当结果。完整推演见 [02 §4](02-engineering-mode.md)。

## 5. cryptoeng 自己的 TA 也碰不到 SOTER

`/odm/firmware/secure_ta/cryptoeng.*`（50 个分片，2,052,088 B，重组后 1,007,879 B）里确实有大量 RPMB 代码：

```
hal_core_read_rpmb / hal_core_write_rpmb / hal_core_aes_rpmb_kits_init
hal_fdph_*_rpmb / hal_redtea_*_rpmb / hal_simlock_init_rpmb
hal_olock_*_rpmb / hal_pki_read_rpmb / hal_finance_init_rpmb
crypto_eng_rpmb_read / crypto_eng_rpmb_write / reset_olock_rpmb_flag
```

但它访问的是**自己固定的两个分区**：

```c
// sub_4C74：分区 ID 硬编码
part_id = a3 ? 65283 : 65282;      // 0xFF03 / 0xFF02
// crypto_eng_rpmb_read：先 device_init，再按分区开
qsee_stor_device_init(3, 0, &h);
```

而且整个 cryptoeng TA 里**没有** `0x53515446`（FTQS）、`0x53515445`（ETQS），也没有 `soter` 字符串。→ **借 cryptoeng 写 SOTER 分区这条路不存在。**

## 6. 顺带确认的两个工具

| 工具 | 真实用途 |
| --- | --- |
| `/vendor/bin/StoreKeybox` | `StoreKeybox: Widevine Key Provisioning Tool`，读 `argv[1]` 的 keybox.bin → `store_root_of_trust`。**与 SOTER 无关**，旧文档把它列在 SOTER 章节是错的 |
| `/vendor/bin/rpmbClient` | RPMB 预配/擦除工具，`smci -e` 是唯一的全擦原语，见 [06 §5](06-root-cause.md) |

## 7. 复现

```sh
# 命令表
python tools/analyze/dumptable.py samples/bin/vendor.oplus.hardware.cryptoeng@1.0-service

# 看 HAL 日志
adb logcat -c; adb shell service call vendor.oplus.hardware.cryptoeng.ICryptoeng/default 57 i32 1 >/dev/null
adb logcat -d | grep -E 'cryptoeng_hidl|VerifyAttk'
```
