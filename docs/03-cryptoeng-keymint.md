# 03 cryptoeng / KeyMint 命令链路

## cryptoeng 服务

- 进程：`/odm/bin/hw/vendor.oplus.hardware.cryptoeng@1.0-service`
- init 名：`hal_cryptoeng_oplus`
- 服务名：`vendor.oplus.hardware.cryptoeng.ICryptoeng/default`（AIDL），旧客户端回退 HIDL `vendor.oplus.hardware.cryptoeng@1.0`
- 加载：`libqsee_keybox_ca.so`、`librpmbengclient.so`、`libolc_vnd.so`、`vendor.oplus.hardware.cryptoeng@1.0.so`、`vendor.oplus.hardware.cryptoeng-V1-ndk.so`、`libkeymasterprovision.so`、`libkeymasterutils.so`、`libkeymasterdeviceutils.so`、`libqtikeymaster4.so`、`android.hardware.keymaster@3.0.so`

AIDL 方法 `cryptoeng_invoke_command(vector<uint8_t> in, vector<uint8_t>* out)` 的输入格式是 **4 字节小端 cmd + 负载**。

## 实测命令与返回

| 输入 | 含义 | 返回 |
| --- | --- | --- |
| `39000000` | cmd 57（SOTER verifyAttkKeyPair） | `ecffffff` = **-20** |
| `3c000000` | cmd 60 | `00000000` |
| `01000000` | cmd 1 | `00000000` |
| `3b000000` | cmd 59 | `00000000` |
| `19000000` | cmd 25 | `00000000` |
| `1e000000` | cmd 30 | `00000000` |
| `3d000000 64656661756c7400` | cmd 61 + `"default\0"`（RKP） | **进程直接死亡**，`onLeave` 不触发，pid 每次翻新 |

打开工程模式页会依次触发：**57（两次）、60、1、59、25、30、61**。cmd 61 会杀死 cryptoeng HAL，这就是每次开页后 cryptoeng pid 变化的原因；页面仍然显示 RKP 成功，是因为读的是 `Settings.Global` 缓存。

底层 dispatcher：

```
_Z24cryptoeng_invoke_commandP23cryptoeng_device_structPhjS1_Pj
```

在服务二进制里的偏移是 `0x1415c`，先校验 4 字节 magic `0x000F423F`，再按 cmd 分发。单缓冲入口是 `_Z25crypto_eng_invoke_commandPvjS_Pj`（`0x5c740fc2b8`，运行时地址）。另有 `cryptoeng_get_secureType`、`cryptoengSetOlockState`、`cryptoeng_engineer_demo`、`keybox_rsp_proc`。

## KeyMint HAL

- 进程：`/vendor/bin/hw/android.hardware.security.keymint-service-qti`，SELinux 域 `u:r:vendor_hal_keymint_qti:s0`
- init：`class early_hal`、`user system`、`group system drmrpc`，无 seclabel
- 模块：`libqtikeymint.so`（设备加载 286,720 B，pull 下来的文件是 290,616 B，不是同一构建）、`libkeymasterdeviceutils.so`、`libkeymaster_messages.so`、`libkeymasterutils.so`、`android.hardware.security.keymint-V3-ndk.so`、`android.hardware.keymaster@4.0/4.1/3.0.so`
- 注意：`libqtikeymaster4.so` 在 cryptoeng 进程里，不在 KeyMint HAL 里。

关键符号（`libqtikeymint.so` 文件偏移）：

```
KeymasterHalDevice::SetRot          0x320e8
KeymasterHalDevice::LegacySetRot    0x2e178
KeymasterHalDevice::set_device_locked 0x32290
```

`set_device_locked` 反编译：先 `KeymasterUtils::spu_init()`，再 `KeymasterUtils::init(...)`（`this+0x30 == 2` 时用 8477，否则 8474），然后 `KeymasterSerialize::serializeClientSetDeviceLocked(a2 & 1, ...)`，最后 `KeymasterUtils::sendCmd()`。失败打印 `KeyMasterHalDevice set_device_locked ret: %d`。

也就是说，HAL 确实有能力把「设备是否锁定」作为一条 client 命令发给 TA。

## 运行时改锁态实验

通过 hook `keymint_generate_key` 拿到 `KeymasterHalDevice* this = 0xb400007855665580`，然后：

- `set_device_locked(this, 1)` → **-40**
- `set_device_locked(this, 0)` → **-40**

logcat：

```
KeyMasterHalDevice: set_device_locked
ret: -40
```

之后 `soter-provision 2` 仍然 `fail -20`。结论：TA 在 boot 之后拒绝任何 `ClientSetDeviceLocked` 变更，-40 表示无效操作。

另外：

- 重启 keystore2（`stop keystore2; start keystore2`）时，`SetRot` / `LegacySetRot` / `set_device_locked` **一次都没有被调用**（Frida hook 无命中）。
- `/apex/com.android.keystore/bin/keystore2` 内 grep `deviceLocked|setBootState|boot_state|verifiedBootState` 无命中。
- `AndroidKeyMintDevice::deviceLocked(bool, optional<TimeStampToken>)`（`base+0x1d0f8`）在 keystore2 重启时也从未被调用。

因此，Android 侧没有「设置 TA boot state」的路径；锁态由 ABL 在启动阶段通过 KeyMint client 命令写入 RPMB。

## 手工拉起 HAL

`setprop ctl.stop vendor.keymint-qti` 后直接从 root shell 执行：

```sh
setsid /vendor/bin/hw/android.hardware.security.keymint-service-qti &
```

可以成功注册 `android.hardware.security.keymint.IKeyMintDevice/default`，说明 ksu 域可以执行并完成域转换。Frida 17 的 spawn 默认 resume，没有 `--no-pause`；用 `frida -U -f <bin> -l hook.js -o log -q -t inf` 时，如果 hook 用 `setTimeout(..., 0)` 就会晚于 main 初始化，必须在脚本加载时同步安装 hook。
