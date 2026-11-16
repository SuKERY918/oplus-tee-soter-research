# 03 cryptoeng / KeyMint

## cryptoeng

- 进程：`/odm/bin/hw/vendor.oplus.hardware.cryptoeng@1.0-service`
- init：`hal_cryptoeng_oplus`
- 服务：`vendor.oplus.hardware.cryptoeng.ICryptoeng/default`（AIDL），回退 HIDL `@1.0`

`cryptoeng_invoke_command(vector<uint8_t> in, vector<uint8_t>* out)`，输入 = **4 字节小端 cmd + 负载**。

| 输入 | 含义 | 返回 |
| --- | --- | --- |
| `39000000` | cmd 57 verifyAttkKeyPair | `ecffffff` = **-20** |
| `3c000000` | cmd 60 | `00000000` |
| `01000000` | cmd 1 | `00000000` |
| `3b000000` | cmd 59 | `00000000` |
| `19000000` | cmd 25 | `00000000` |
| `1e000000` | cmd 30 | `00000000` |
| `3d00000064656661756c7400` | cmd 61 + `"default\0"` | **进程死亡**，pid 每次都变 |

打开工程模式页触发：57、57、60、1、59、25、30、61。cmd 61 必杀 HAL。

dispatcher：

```
_Z24cryptoeng_invoke_commandP23cryptoeng_device_structPhjS1_Pj   // 偏移 0x1415c
```

先校验 magic `0x000F423F`，再按 cmd 分发。

## KeyMint HAL

- 进程：`android.hardware.security.keymint-service-qti`
- 域：`u:r:vendor_hal_keymint_qti:s0`
- init：`class early_hal`、`user system`、`group system drmrpc`
- `libqtikeymint.so`：设备 286,720 B，pull 下来 290,616 B（不同构建）

符号（`libqtikeymint.so`）：

```
KeymasterHalDevice::SetRot             0x320e8
KeymasterHalDevice::LegacySetRot       0x2e178
KeymasterHalDevice::set_device_locked  0x32290
```

`set_device_locked`：`KeymasterUtils::spu_init()` → `KeymasterUtils::init()` → `KeymasterSerialize::serializeClientSetDeviceLocked(a2 & 1, ...)` → `KeymasterUtils::sendCmd()`；失败打印 `KeyMasterHalDevice set_device_locked ret: %d`。

## 运行时改锁态

hook `keymint_generate_key` 取到 `KeymasterHalDevice* this = 0xb400007855665580`：

```
set_device_locked(this, 1)  -> -40
set_device_locked(this, 0)  -> -40
```

之后 `soter-provision 2` 仍 `fail -20`。TA 在 boot 后拒绝任何 `ClientSetDeviceLocked`。

补充：

- 重启 keystore2 时 `SetRot` / `LegacySetRot` / `set_device_locked` 均未被调用；
- keystore2 二进制无 `deviceLocked|setBootState|boot_state` 字符串；
- `AndroidKeyMintDevice::deviceLocked`（`base+0x1d0f8`）从未被调用。

锁态由 ABL 在 boot 阶段写入 RPMB。

## 手工拉起 HAL

```sh
setprop ctl.stop vendor.keymint-qti
setsid /vendor/bin/hw/android.hardware.security.keymint-service-qti &
```

可注册 `android.hardware.security.keymint.IKeyMintDevice/default`。Frida 17 spawn 默认 resume，hook 必须在脚本加载时同步安装。
