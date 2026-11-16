# 05 修复尝试与结果

## 总表

| 目标行 | 真实依赖 | 试过的办法 | 结果 |
| --- | --- | --- | --- |
| SOTER key | QTI `soter64` TA（cryptoeng cmd 57） | 杀 teesim、重启 keystore2、`soter-provision`、软件 SOTER TA | 原厂 TA 一律 -20；软件 TA 能骗过页面，但微信拒收自签链 |
| Attestation key | KeyMint TA + keystore2 | `KmInstallKeybox` 写 keybox | 短暂变绿，HAL/TA 重启后丢失 |
| RKP default | cryptoeng cmd 61 | Frida 伪造 cmd 61 返回 | 页面变绿，靠 `Settings.Global` 缓存跨重启 |
| Rpmb / IFAA / Crypto / WidevineL1 / FIDO / PKI | 各自服务 | 未改动 | 一直成功 |
| HDCP / RKP widevine / StrongBox / DP HDCP V2 | 硬件/机型不支持 | — | 一直「不支持」（绿色） |

## 一、KmInstallKeybox

工具：

```
LD_LIBRARY_PATH=/vendor/lib64/hw /vendor/bin/KmInstallKeybox <keybox.xml> <DeviceID> <true|false>
```

第三个参数 `true` = 同时写设备 ID（provision_device_ids），`false` = 只写 KEY。

第一次失败：

- teesim 自带的 `keybox.xml` 直接喂进去，在 `keymasterdevice::InstallKeybox::ParseFile(bool)+9668` 触发 `ubsan: sub-overflow` + SIGABRT；
- 自己用 `cryptography` 生成自签 keybox 能解析，但 TA 返回 `KeyMasterInstallKeybox error-32`（自签链不被 TEE 信任），`InstallKeybox Failed!-2000`，rc=48。

成功的一次：

- 用脚本重新解析 teesim keybox，把私钥统一转 PKCS8、证书重写为 PEM、DeviceID 改 `PLQ110`，再补 `NumberOfCertificates`；
- 输出 `KeyMaster Attestation Key Provisioning success for KeyIDPLQ110` / `TEE done` / `InstallKeybox is done!`，rc=0；
- 工程模式页 Attestation 从「失败」变「成功」。

但随后：

- 反复重启 KeyMint HAL / cryptoeng 后，Attestation 又变红；
- 重新执行 `KmInstallKeybox` 仍然打印成功，但页面还是红；
- 日志：`keystore2: security_level.rs:809: While generating without a provided attestation key`，随后回退 RKP：`User consent required to communicate with remote provisioning server, but no consent has been given.`；
- 说明 TA 实际没有保住 keybox，或者 keybox 只存在易失状态里。

注意：`KmInstallKeybox` 成功一次后，正常流程下该槽位不能重复 provisioning（除非 devcfg 开了 allow_reprovision）。本机能重复执行且每次都打印成功，本身就是「没有真正持久化」的旁证。

## 二、teesim 注入范围

`/data/adb/modules/teesim` 结构：

```
arm64-v8a/inject
libteesim_keymint.so (18.8 MB)
libteesim_keystore.so
classes.dex
daemon
keybox.xml
post-fs-data.sh
service.sh
sepolicy.rule
teeforge.conf
webroot/
```

- `post-fs-data.sh` 只跑 `runtime/teeforge-hide --stage early`；
- `service.sh` 循环起 `daemon`（`app_process -Djava.class.path=classes.dex org.matrix.teesim.App`），boot_completed 后跑 `--stage late`；
- `/proc/1235/maps` 确认 `libteesim_keymint.so` 注入的是 **keystore2**（PID 1235），不是 QTI KeyMint HAL（PID 1201），也不是 soter-service。

实测：`kill` teesim daemon + `stop keystore2; start keystore2`（新 PID 的 maps 里 teesim 计数为 0）后，`soter-provision 1` 仍然 `fail -20`。所以 teesim 不是 SOTER 红的原因。

## 三、本地软件 SOTER TA（Ommega）

Ommega A 端发布包里的 `ommega-inject` 支持 `--soterta-serve`：停掉原厂 `vendor.soter`，用同一个服务名注册一个本地软件 TA，用自己的 ASK 应答 SOTER 调用。

本地直接跑：

```sh
setprop ctl.stop vendor.soter
OMMEGA_MODDIR=/data/adb/ommega \
OMMEGA_CONF_PATH=/data/misc/ommega/config \
OMMEGA_SOTER_SERVICE=vendor.qti.hardware.soter.ISoter/default \
/data/local/tmp/test/ommega/ommega-inject --soterta-serve
```

结果：

- 服务注册成功，工程模式 cmd 57 返回 0，SOTER 行变绿；
- `soter-provision 2/3/4` 变成 0；
- 微信开关能走到 `FingerPrintAuthUI`，但第一次因为没有 ASK/RPC 挂 146 秒后弹「系统错误」；
- 补了自签 ATTK（`O=Ommega,CN=Ommega Local ATTK`）和 ASK 之后，`exportAskPublicKey` 返回 805 字节，微信 1 秒内 `removeAllUidKey` 清理；
- `soter_asks.json` 里反复出现 `"gone": {"ask:10405": "1"}`。

关于 RPC：

- 本地模式需要 `/data/misc/keystore/ommega/rpc.sock` 和 `ommega.soter.rpc` abstract socket；
- `ommega-inject --daemon`（软件 KeyMint，负责 ATTK 签名与 RPC）在开机时因 **PID 复用** 误判单实例：`keymint-daemon.pid` 里记的 pid 2430 被 `vendor.qti.psiclient@1.0-service` 复用，daemon 打印 `another instance is running; exiting`，于是 RPC socket 不存在；
- 手工清 `keymint-daemon.lock` / `keymint-daemon.pid` / `rpc.peers` 后重启 TA，守护能起来，微信仍然拒收自签链。

结论：服务顶替这条路能解决「页面 SOTER 绿」，解决不了「微信要真证书链」。

## 四、Frida 伪造 RKP

在 cryptoeng HAL 内 `Interceptor.replace` dispatcher（模块 base + `0x1415c`）：

- cmd 61 时直接往 out 写 8 字节 0，`*outlen = 8`，返回 0；
- 其余 cmd 透传原函数。

页面 RKP default 变成功，且 `Settings.Global` 的 `rkpdefault_import=1` 会缓存，跨 HAL 重启仍显示绿。这只是视觉/缓存效果，不影响真实 RKP provisioning。

## 五、Tricky Store

作者只装了 Tricky Store + Zygisk Next。Tricky Store 的 README：

- Android 12+；
- 可放 `keybox.xml` 到 `/data/adb/tricky_store/keybox.xml`；
- `target.txt` 指定生效包名；
- `spoof_build_vars` 需要 Zygisk；
- 默认 “hack the leaf certificate”，TEE 坏掉的设备可以对包名加 `!` 走 “generate certificate support”。

它能 hook keystore2 的证书链，解决 Attestation / Play Integrity；但它碰不到 cryptoeng cmd 57，也碰不到 SOTER TA。因此它能让 Attestation key 和 RKP default 绿，不能让 SOTER key 绿——这与作者自己说「Tricky Store 让 Attestation 和 RKP 绿」一致。

## 六、微信卡死的根因

软件 TA 在没有本地 ASK/RPC 时，`exportAskPublicKey` 每 30 秒重试一次，binder 调用一直不返回：

```
W/libbinder.Binder(883): Binder transaction to com.tencent.soter.soterserver.ISoterService,
function: UNKNOWN_FUNCTION_NAME, code: 2, took 145983ms.
```

于是微信 ANR。杀掉软件 TA、`setprop ctl.start vendor.soter` 后恢复正常。

**这个坑要注意：任何“半成品”的软件 SOTER TA 都会让微信支付设置卡死，不如不装。**
