# tools

这些脚本只在研究机上验证过，路径按需要改。

## fake61.js

Frida 脚本，attach 到 `vendor.oplus.hardware.cryptoeng@1.0-service`，替换 dispatcher（模块 base + `0x1415c`），让 cmd 61 返回 8 字节 0。

```sh
adb shell su -c 'setsid /data/local/tmp/test/frida-server -D'
frida -U -p <cryptoeng pid> -l fake61.js -q
```

效果：工程模式页 RKP default 变绿，并写入 `Settings.Global` 的 `rkpdefault_import=1`。只是视觉/缓存，不 provision RKP。

## agent_soter.js / hook_soter.py

Hook `com.tencent.soter.soterserver.SoterService` 的合成方法，记录微信调用 SOTER 时的参数与返回。

构建：

```sh
npm install frida-java-bridge frida-compile
npx frida-compile agent_soter.js -o agent_soter.compiled.js
python hook_soter.py
```

Frida 17 默认不带 Java bridge，所以需要 `frida-java-bridge` + `frida-compile`。Python 读文件时用 `encoding="utf-8"`，否则 Windows 默认 GBK 会报 `UnicodeDecodeError`。

## start_soterta.sh

不起模块，直接启动 Ommega 的本地软件 SOTER TA。

前提：

- `ommega-inject` 在 `/data/local/tmp/test/ommega/`；
- `/data/misc/ommega/config` 有 `soter_inject: 1`、`remote: off`；
- `/data/misc/ommega/soter_attk.pem` 是 RSA-2048 私钥 + 自签证书。

恢复：

```sh
pkill -f 'ommega-inject --soterta-serve'
setprop ctl.start vendor.soter
```

**注意**：没有可用 ASK/RPC 时，微信支付设置会卡 146 秒。实验完务必恢复原厂。
