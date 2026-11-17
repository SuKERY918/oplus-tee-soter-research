# tools

在 OnePlus Ace 6（PLQ110 / SM8750 / ColorOS 17）上实测过的脚本。默认调用 `adb`，可用 `ADB` 覆盖路径、`DEV` 指定序列号。

| 脚本 | 作用 | 是否修改设备 |
| --- | --- | --- |
| [`diag.sh`](#diagsh) | 只读诊断：设备、真实锁态、root、SOTER provision、persist 槽位、进程 | 否（`--ui` 仅切换前台页面） |
| [`fix-rkp.sh`](#fix-rkpsh) | 写入 device ID 走 RKP 预配，修复 Attestation key | 是（persist + RPMB） |
| [`fake61.js`](#fake61js) | Frida 改 cryptoeng dispatcher，让工程模式 `RKP default` 变绿 | 是（仅视觉/缓存） |
| [`agent_soter.js`](#agent_soterjshook_soterpy) / [`hook_soter.py`](#agent_soterjshook_soterpy) | Hook SOTER 服务，记录微信调用参数与返回 | 否 |
| [`start_soterta.sh`](#start_sotertash) | 启动 Ommega 的本地软件 SOTER TA | 是（起进程） |

---

## diag.sh

一次跑完所有只读检查，输出可直接贴进 issue。

```sh
./tools/diag.sh
DEV=3B15AW00WGJ00000 ./tools/diag.sh
```

采集内容：

- `getprop` 的型号、版本、指纹；
- `/proc/cmdline` 里的 `oplusboot.*`（`verifiedbootstate=orange` 是真实锁态，`ro.boot.*` 已被模块改写）；
- `id`（KernelSU 下为 `uid=0(root) context=u:r:ksu:s0`）；
- `vendor.qti.hardware.soter-provision 1..4` 的返回；
- persist 两个 Attestation 槽位的文件数、`5r5` 条数与 mtime；
- `rpmb_status` 前 4 字节；
- keystore2 / keymint / soter / rkpd 进程；
- KeyAttestation 数据目录是否存在。

加 `--ui` 会强制刷新工程模式页并 dump 15 行状态：

```sh
./tools/diag.sh --ui
```

工程模式页有缓存，不 force-stop 会读到旧值；脚本已处理。

## fix-rkp.sh

把 device ID 写进 TEE 并重建 persist 槽位，走 Google RKP 远程预配修复 Attestation key。**不可回滚**，详见 [docs/10](../docs/10-rkp-device-id.md)。

```sh
./tools/fix-rkp.sh
```

四步：

1. preflight：确认 `verifiedbootstate=orange`、原厂槽位 `5r5` 仍是 `2025-10-30` 的 12,692 B（未被动过）；
2. `KmInstallKeybox /data/local/tmp/x PLQ110 true rkp`（argc=5，rkp 模式不读文件）；
3. `pm clear io.github.vvb2060.keyattestation` 清掉旧 key blob；
4. 启动 KeyAttestation，dump 证书链叶子并统计 `_Alt` 里的 `5r5`。

第 2 步前需要人工输入 `y`。完成后按提示重启，再跑 `diag.sh --ui` 复核。

## fake61.js

attach 到 `vendor.oplus.hardware.cryptoeng@1.0-service`，替换 dispatcher（模块 base + `0x1415c`），让 cmd 61 返回 8 字节 0。

```sh
adb shell su -c 'setsid /data/local/tmp/test/frida-server -D'
frida -U -p <cryptoeng pid> -l fake61.js -q
```

效果：工程模式页 `RKP default` 变绿，并写入 `Settings.Global` 的 `rkpdefault_import=1`。只是视觉与缓存，**不 provision RKP**，重启即失效。

## agent_soter.js / hook_soter.py

Hook `com.tencent.soter.soterserver.SoterService` 的合成方法，记录微信调用 SOTER 时的参数与返回。

```sh
npm install frida-java-bridge frida-compile
npx frida-compile agent_soter.js -o agent_soter.compiled.js
python hook_soter.py
```

Frida 17 默认不带 Java bridge，需要 `frida-java-bridge` + `frida-compile`。Python 读文件时用 `encoding="utf-8"`，否则 Windows 默认 GBK 会抛 `UnicodeDecodeError`。

## start_soterta.sh

不装模块，直接启动 Ommega 的本地软件 SOTER TA。

前提：

- `ommega-inject` 在 `/data/local/tmp/test/ommega/`；
- `/data/misc/ommega/config` 有 `soter_inject: 1`、`remote: off`；
- `/data/misc/ommega/soter_attk.pem` 是 RSA-2048 私钥 + 自签证书。

恢复：

```sh
pkill -f 'ommega-inject --soterta-serve'
setprop ctl.start vendor.soter
```

**注意**：没有可用 ASK/RPC 时，微信支付设置会卡 146 秒。实验完务必恢复原厂。自签 ATTK 在 TAM 侧必然验签失败，微信会在 1 秒内 `removeAllAuthKey` + `removeAllUidKey`，不要指望它修好 SOTER。
