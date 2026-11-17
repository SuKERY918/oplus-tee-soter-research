# 04 soter-service 与 ISoter

SOTER 这一侧从 `vendor.soter` 服务开始，经 QSEECom 直接进 `soter64` TA。**它不经过 cryptoeng HAL**——cryptoeng 只是"上游调用者"。

## 1. 服务

| 项 | 值 |
| --- | --- |
| init | `/vendor/etc/init/vendor.qti.hardware.soter-service.rc` |
| service | `vendor.soter`，`class late_start`，`user system`，`group system drmrpc` |
| 可执行 | `/vendor/bin/hw/vendor.qti.hardware.soter-service` |
| 实现库 | `/vendor/lib64/vendor.qti.hardware.soter-impl.so`（84,712 B） |
| AIDL | `vendor.qti.hardware.soter.ISoter`（`vendor.qti.hardware.soter-V1-ndk.so`） |
| 服务名 | `vendor.qti.hardware.soter.ISoter/default` |

日志 tag 有三个，别混：

- `vendor.qti.hardware.soter` —— HAL/impl 层的业务日志（`generateAttkKeyPair called`、`rsp->status: %d`）；
- `SoterUtils` —— 构造函数里的断言日志；
- `QSEECOMPAT` —— QSEECom 通道的加载日志（tag 名不是 `QSEEComAPI`）。

## 2. 启动：cmd 271 是"TA 活着"的证明

`soterutils::SoterUtils::SoterUtils()`（0xd154）：

```c
while (property_get("vendor.sys.listeners.registered", ...) ...) usleep(100000);
if (QSEECom_start_app(&h, "/vendor/firmware_mnt/image", "soter64", 10240) != 0)
    QSEECom_start_app(&h, "/vendor/firmware_mnt/image", "soter", 10240);   // 兼容旧名
memset(rsp, 0, 0x2800);
*req = 271;                                     // SOTER_GET_VERSION
ret = QSEECom_send_cmd(h, req, 4, rsp, 10236);
if (ret != 0) __android_log_assert("(ret!=SoterErrorCode::SOTER_ERROR_OK)",
                                   "SoterUtils", "QSEECom_send_cmd failed");
if (rsp[0] != 0) __android_log_assert("get_version_rsp->status",
                                      "SoterUtils", "get_version status failed");
```

`__android_log_assert` 会 **abort**。服务启动常驻、多次重启无 tombstone → **cmd 271 恒定返回 0**。

推论（很重要）：TA 整体是健康的，-20 不是"TA 没初始化"，而是 ATTK 相关命令专属的门禁。ASK 系命令返回 -5 而不是 -20 也印证这一点。

QSEECom 侧加载日志（服务每次启动都打）：

```
D/QSEECOMPAT: QSEECom_start_app, 517: load /vendor/firmware_mnt/image soter64, sb_size 10240
D/QSEECOMPAT: load_app b00_fname=/vendor/firmware_mnt/image/soter64.b00
D/QSEECOMPAT: read_splitbin_tobuf offset[1..8] ...
E/QSEECOMPAT: lookupTA(soter64) returned 23      （未安装时的正常提示）
```

`setprop log.tag.QSEECOMPAT V` 也不会打印 `send_cmd` 的返回值，所以**TA 返回码只能从上层 `rsp->status` 日志看**。

## 3. 请求格式

`Soter::generateAttkKeyPair(char uid, SoterErrorCode*)`（0xaee4）：

```c
memset(buf, 0, 0x2800);
req[0] = 257;              // SOTER_GENERATE_ATTK
req[1] = uid;              // 副本数（工程模式传 3）
QSEECom_send_cmd(h, req, 8, rsp, 10232);
status = rsp[0];           // ← TA 写的第一字段
```

- 请求 = `[u32 cmd][u32 arg]`（8 字节）；响应 = 10232 字节，首 4 字节是状态码。
- 失败日志：`Generate ATTK send cmd failed` + `rsp->status: %d` + `Failed to generate attk, error %d`。
- 由于 buffer 先清零、日志值就是 `rsp[0]`，**-20 可以确定是 TA 写进来的**，不是 QSEECom 的返回值。

## 4. ISoter 事务码矩阵（实测）

不需要写 AIDL 客户端，`service call` 就能枚举：

```sh
adb shell service call vendor.qti.hardware.soter.ISoter/default 14 i32 1
```

返回形如 `Result: Parcel(00000000 ffffffec  '........')`，第二段是 int32 小端（`ffffffec` = -20）。

| tx | 方法 | 返回 | 含义 |
| --- | --- | --- | --- |
| 1 | exportAskPublicKey | -5 | ASK 未预配 |
| 2 | exportAttkPublicKey | -20 | ATTK 门禁 |
| 5 | generateAskKeyPair | -20 | ASK 生成要 ATTK 签名，故继承 -20 |
| 6 | generateAttkKeyPair | -20 | 门禁 |
| 8 | getDeviceId | -20 | **纯读也 -20** |
| 9 | hasAskAlready | -5 | ASK 未预配 |
| 12 | removeAllUidKey | -5 | — |
| 14 | verifyAttkKeyPair | -20 | 门禁 |
| 3/4/7/10/11/13 | — | Parcel `0xffffffff80000008` | 参数类型不匹配 |
| 15/16 | — | `Not a data message` | 无此方法 |

规律：**ATTK 系（257–260）全 -20，ASK 系全 -5**。

`getDeviceId` 只是读取，却同样 -20 —— 这一条单独就把"ATTK 私钥被删了所以签名失败"的猜测排除掉了：读操作都不让做，说明失败在门禁，不在密钥本身。

## 5. TA 命令号

TA 侧命令号是 **0x101..0x10F（257..271）**，`sub_6000` 用 `cmd - 0x101 <= 0xE` 做范围检查，真实分派表在 va `0x11298`（[05 §3](05-soter-ta.md)）。

| 号 | 名字 | 是否过门禁 |
| --- | --- | --- |
| 0x101 | SOTER_GENERATE_ATTK | 是 |
| 0x102 | SOTER_VERIFY_ATTK | 是 |
| 0x103 | SOTER_EXPORT_ATTK_PUBLIC | 是 |
| 0x104 | SOTER_GET_DEVICE_ID | 是 |
| 0x105 | SOTER_GENERATE_ASK | 是（ASK 由 ATTK 签名） |
| 0x106 | SOTER_EXPORT_ASK_PUBLIC | 否（-5 = 未预配） |
| 0x107 | SOTER_REMOVE_ALL_UID_KEY | 否 |
| 0x108 | SOTER_HAS_ASK_ALREADY | 否 |
| 0x109 | SOTER_GENERATE_AK | 否 |
| 0x10A | SOTER_EXPORT_AK_PUBLIC | 否 |
| 0x10B | SOTER_REMOVE_AK | 否 |
| 0x10C | SOTER_HAS_AK | 否 |
| 0x10D | SOTER_INIT_SIGN | 否 |
| 0x10E | SOTER_FINISH_SIGN | 否 |
| 0x10F | SOTER_GET_VERSION | **否**（所以恒成功） |

## 6. 预配工具

`/vendor/bin/vendor.qti.hardware.soter-provision`（51,936 B），只暴露 4 条：

```
Usage: soter_client [CMD]
  1: Generate ATTK key pair
  2: Verify ATTK key pair
  3: Export ATTK public key
  4: Get device ID
```

- 命令 1 走 `generateAttkKeyPair(3)`（`main_cfi` 0x48EC 处 `MOV W1,#3`）——**这就是"副本数 3"的来源之一**；
- 命令 2/3/4 分别走 vtable + 0x98 / + 0x38 / + 0x68；
- 非法参数不走 TA，直接打印 usage 并返回 `qsc_run_soter_cmd failed,ret=-1000`、shell rc=24。

本机四条实测：

```
1 → Generate ATTK send cmd failed / rsp->status: -20 / Failed to generate attk, error -20
2 → verify ATTK send cmd failed / rsp->status: -20
3 → export ATTK send cmd failed / rsp->status: -20
4 → get device id send cmd failed / rsp->status: -20
```

## 7. 微信侧

`com.tencent.soter.soterserver` 用自己的进程持有 SOTER 调用，`/data/data/com.tencent.mm/shared_prefs/soter_status.xml` 记录结果。本机（2026-11-16 22:42）只有：

```xml
<long name="WechatASK" value="0" />
<long name="SoterAuthKeyV2_salt…_scene1" value="0" />
```

→ 微信侧从来没有成功过，与 TA 的 -20 一致。
