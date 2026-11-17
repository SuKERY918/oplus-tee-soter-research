# 02 工程模式「Key 状态」页

页面：`com.oplus.engineermode/.security.RPMBStatusActivity`。15 行状态，每行是一次独立的密钥自检。

## 1. 先看结论：这张表只能看红，不能把绿当证据

判定语义极其粗糙——很多行只看"某个 HAL 返回的 4 字节 int 是不是 0"。链路中间任何一层把错误吞掉、返回 0，页面就是绿的。

本机实测（`uiautomator dump` 按 resource-id 取文本）：

| 行 | resource-id | 状态 |
| --- | --- | --- |
| Rpmb key | `security_status_rpmb_key` | 成功 |
| **SOTER key** | `security_status_soter_key` | **失败** |
| IFAA key | — | 成功 |
| Crypto key | — | 成功 |
| WidevineL1 key | — | 成功 |
| HDCP key | — | 不支持 |
| Attestation key | `security_status_google_key` | 成功 |
| FIDO key | — | 成功 |
| PKI cert | — | 成功 |
| PKI Group cert | — | 成功 |
| FIDO2 key | — | 成功 |
| RKP default | — | 成功 |
| RKP widevine | — | 不支持 |
| StrongBox key | — | 不支持 |
| DP HDCP V2 key | — | 不支持 |

> 早期文档记录的"裸解锁"状态里 Attestation / RKP 是红的，本机现在两行已绿，是 [09](09-rkp-attestation.md) 的 rkp 预配修好的，与 SOTER 无关。

## 2. SOTER 行的判定链（逐层核对过）

```
RPMBStatusActivity.java:21-25
    if (isSupport() && !isKeyImported())  显示"失败"
    else                                  显示"成功"
    （isKeyImported() 被连续调用两次，所以日志里 cmd 57 连打两次）

KeyInstanceImpl.java:212-214
    SOTERKey.isKeyImported() { return SecurityInterface.verifyAttkKeyPair() == 0; }

SecurityInterface.java:576-577
    verifyAttkKeyPair() { return runCryptoCmd((byte) 57); }

SecurityInterface.java:508-515
    runCryptoCmd(b) → 组 [b,0,0,0] → cryptoengInvokeCommand()
    → transferByteListToInt(list, 4)
    list 为 null 或长度 < 4 → 返回 -1
```

继续往下是 HAL 与 TA，见 [03](03-cryptoeng-hal.md)、[05](05-soter-ta.md)。

关键点：**"绿" 等价于 "拿到了 4 字节且值为 0"**，不校验任何"确实验签成功"的旁证。

## 3. `runCryptoCmd` 的三个坑

1. **失败时返回 -1**：list 为 null 或不足 4 字节，一律 -1 → 页面显示红。所以"红"也可能是 HAL 没起来，不一定是 TA 拒绝。
2. **只读前 4 字节**：HAL 返回 4 字节以上也只取第一个 int。
3. **通道有反射兜底**：`RpmbChannel.java:8-61` 先用反射拿 Java AIDL `vendor.oplus.hardware.cryptoeng.ICryptoeng$Stub`，异常一律 `return null`，再走 HIDL `vendor.oplus.hardware.cryptoeng.V1_0.ICryptoeng`。两条通道任一可用即可，且**异常被静默吞掉**。

## 4. 「假绿」的真实机理

### 4.1 现象

同一台机器、TA 一直返回 -20 的情况下，页面可以显示**成功**：

```
HAL 日志：Failed to VerifyAttkKeyPair, error 0      ← 注意是 0，不是 -20
页面：    SOTER key = 成功
同时：    service call … ISoter/default 14 i32 1 → ffffffec（-20），TA 完全正常
```

### 4.2 触发条件

**只要 `vendor.soter` 服务重启过**，此后打开页面就是假绿，直到 cryptoeng HAL 也被重启。

```sh
adb shell 'stop vendor.soter; sleep 1; start vendor.soter'
# 打开工程模式页面 → 假绿
adb shell 'kill -9 $(pidof vendor.oplus.hardware.cryptoeng@1.0-service)'
# 等 init 拉起，再打开页面 → 恢复真实红色
```

### 4.3 代码级根因（两个 bug 叠加）

**HAL 侧**（`vendor.oplus.hardware.cryptoeng@1.0-service`，`getSoterAidl` @0x19270）：

```c
v10 = AIBinder_DeathRecipient_new(serviceDiedAidl);
AIBinder_linkToDeath(binder, v10, serviceDiedAidl);
proxy = ISoter::fromBinder(binder);
xmmword_28180 = proxy;                       // 全局缓存
...
AStatus_delete(v13);
AIBinder_DeathRecipient_delete(v10);         // ← 函数出口无条件执行，等于立刻反注册
```

`AIBinder_DeathRecipient_delete()` 会把它从所有 binder 上解绑，于是：

- 日志里能看到 `soter service linked to death!!`（确实注册过）；
- 但 soter 进程死亡时 `soter just died` **永远不会出现**，缓存 `xmmword_28180` 永远不清零。

**处理器侧**（`verifyAttkKeyPair` @0x197c0）：

```c
int v13 = 0;                                  // 初值 0
if (proxy) { proxy->verifyAttkKeyPair(&v13); }  // 调用失败时不回填 v13
else       { v13 = -10; }
*out = v13; *out_len = 4;                     // 无论如何都写 4 字节
```

失效代理上的 AIDL 调用返回非 ok 的 Status，`v13` 保持 0 → 输出 0 → APK 判 `== 0` → 绿。

### 4.4 同族处理器的初值不同（解释 `-1000`）

| HAL 处理器 | 局部状态初值 | AIDL 失败时输出 | 对应现象 |
| --- | --- | --- | --- |
| `verifyAttkKeyPair` 0x197c0 | `0` | **0** → 假绿 | 页面"成功" |
| `generateAttkKeyPair` 0x195ec | **`-1000`** | **-1000** | 早期文档记录的 "cmd 58 → -1000" |
| `exportAttkKeyPair` 0x1993c | `0` | 0 | — |
| `getDeviceId` 0x19c84 | `0` | 0 | — |

也就是说：**`-1000` 是 HAL 的局部变量初值，不是 TA 的返回码**。这一点旧文档写错了（见 [12](12-errata.md)）。

## 5. cryptoeng 命令与三行关键结果

`runCryptoCmd(byte cmd)` 把 `[cmd,0,0,0]` 发给 `ICryptoeng/default`，读返回前 4 字节小端 int。

| cmd | 实现 | 本机结果 | 说明 |
| --- | --- | --- | --- |
| 57 | `verifyAttkKeyPair` | TA `-20`（假绿时为 0） | SOTER 行 |
| 58 | `generateAttkKeyPair` + 4 字节副本数 | `-1000` | 早期文档记的就是这个初值 |
| 61 | `android_rkp_handle` | 会打死 cryptoeng HAL | RKP 行，与本主题无关 |

完整命令表见 [03](03-cryptoeng-hal.md)。

## 6. 关于 `rkpdefault_import` 缓存

`Settings.Global rkpdefault_import=1` 写入后，即使 cmd 61 崩溃，`RKP default` 行仍显示成功——这是**另一处**假绿，机理与 SOTER 那处不同（它是 App 侧读设置缓存），不要与 §4 混为一谈。

## 7. 复现命令

见 [11 §1-§2](11-repro.md)：服务侧验证、假绿 A/B、以及一次干净序列（新 HAL → 真实 -20 → 重启 soter → 假绿 → 重启 HAL → 真实 -20）。
