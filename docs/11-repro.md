# 11 复现手册

所有实验都在这台 OnePlus Ace 6 上跑过。命令按"只读 → 可回滚 → 高风险"排列，**动手前先看每节的"副作用"**。

## 0. 环境

| 项 | 值 |
| --- | --- |
| adb | platform-tools 37.0.1 |
| 设备 | PLQ110，Android 17，KernelSU（`u:r:ksu:s0`） |
| Python | 3.14（只用标准库） |
| 反汇编 | IDA（对本 TA 无符号表，需手工定位） |
| 反编译 | jadx 1.5.6 |

约定：

```powershell
$ADB = 'D:\reverse-tools\platform-tools\adb.exe'
$PY  = 'D:\dev-tools\python-3.14.10\python.exe'
```

## 1. 服务侧验证（不依赖 UI）

### 1.1 服务与 TA 是否活着

```powershell
& $ADB shell 'pidof vendor.qti.hardware.soter-service'
& $ADB shell 'service list | grep -i soter'
& $ADB shell 'service call vendor.qti.hardware.soter.ISoter/default 14 i32 1'
```

期望：有 pid、服务在列、返回 `ffffffec`（-20）。

**副作用**：无，纯读。

### 1.2 ISoter 事务码矩阵

```powershell
foreach ($tx in 1,2,5,6,8,9,12,14) {
  "tx=$tx"
  & $ADB shell "service call vendor.qti.hardware.soter.ISoter/default $tx i32 1"
}
```

期望：`1/9/12 → -5`，`2/5/6/8/14 → -20`。

### 1.3 soter-provision 四条命令

```powershell
foreach ($n in 1,2,3,4) {
  & $ADB shell "logcat -c"
  & $ADB shell "/vendor/bin/vendor.qti.hardware.soter-provision $n"
  & $ADB shell "logcat -d -s vendor.qti.hardware.soter:*" | Select-String 'rsp->status|error'
}
```

期望：四条全 `-20`，`rsp->status: -20`，shell rc=236。

**副作用**：无（TA 侧写操作在门禁之后，进不去）。

## 2. 假绿 A/B

```powershell
# A：制造 stale 代理
& $ADB shell 'stop vendor.soter; sleep 1; start vendor.soter'
& $ADB shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity'
Start-Sleep 3
& $ADB shell 'uiautomator dump /sdcard/ui_a.xml'
& $ADB pull /sdcard/ui_a.xml work/ui_a.xml
& $PY tools\analyze\uiget.py work\ui_a.xml security_status_soter_key
# 期望：成功（假绿），HAL 日志 Failed to VerifyAttkKeyPair, error 0

# B：重启 HAL 恢复真实判定
& $ADB shell 'kill -9 $(pidof vendor.oplus.hardware.cryptoeng@1.0-service)'
Start-Sleep 2
& $ADB shell 'am start -n com.oplus.engineermode/.security.RPMBStatusActivity'
& $ADB shell 'uiautomator dump /sdcard/ui_b.xml'
& $ADB pull /sdcard/ui_b.xml work/ui_b.xml
& $PY tools\analyze\uiget.py work\ui_b.xml security_status_soter_key
# 期望：失败（真实），日志 error -20
```

**副作用**：只重启服务，不改数据。

## 3. 取镜像并重组

```powershell
& $ADB pull /vendor/firmware_mnt/image samples/soter_ta/image
& $PY tools\analyze\build_ta.py samples\soter_ta\image soter64
```

自检：输出 84,575 B（0x14a5f）。`.dynstr` 应以 `\0app_heap_limit\0qsee_SW_AE_FinalData…` 开头。

对照实验：直接 `cat soter64.b00 … b08` 得到 74,924 B，那份的地址全部偏 0xdc8。

## 4. IDA 复现

1. `idb_open` 打开 `samples/soter_ta/image/soter64.bin`（84,575 B 那份）；
2. ImageBase = 0；
3. 等自动分析（约 176 函数）；
4. 直接跳：

| VA | 函数 |
| --- | --- |
| 0x5090 | ATTK 门禁 |
| 0x52E8 | 读表 + 逐份校验 |
| 0x461C | 校验第 i 份 |
| 0x3B3C | KDF |
| 0x2FCC | is_secure_boot_enabled |
| 0x2E94 | query_device_id |
| 0x4F38 | 打开 SOTER 分区 |
| 0x54F0 | store_attk |
| 0x5B4 | generate_attk_key_pair（**不是 0x5AC**） |
| 0x51B4 | update_counter |
| 0x11298 | 命令分派表 |

5. 字符串 xref 只有在这份镜像里才正常。

## 5. 静态交叉验证（不依赖 IDA）

```powershell
# 字符串与偏移
& $PY tools\analyze\strings.py samples\soter_ta\image\soter64.bin 6

# 导入表 → PLT 桩地址
& $PY tools\analyze\pltmap.py samples\soter_ta\image\soter64.bin

# -20 字面量（MOVN W19,#0x13）：应命中 0x5474 与 0x674
& $PY tools\analyze\find20.py samples\soter_ta\image\soter64.bin

# 全目录扫 magic / 关键字
& $PY tools\analyze\scanmagic.py samples\persist
```

## 6. 设备侧取证（只读）

```powershell
# persist 全量（约 5 MB；adb pull 会多嵌套一层同名目录）
& $ADB pull /mnt/vendor/persist samples/persist

# 小分区
foreach ($p in 'devinfo','secdata','ocdt','uefivarstore','misc','frp','oplus_sec_a') {
  & $ADB pull "/dev/block/by-name/$p" "samples/part/$p"
}

# persist 槽位结构
& $PY tools\analyze\sfs_tags.py samples\persist\persist\data\DdHdVQd1FIOARksZgXG27GJ1A5UjYCGhP-ZoGvseqsY_
```

期望：`ETQS`/`FTQS`/`SOTER` 在 persist 与上述分区里 **0 命中**（`oplus_sec_a` 里只有一处 JSON 字段名 `RPMB`）。

## 7. RPMB 面（谨慎）

```powershell
# 只读：查 key 状态
& $ADB shell 'echo 2 | /vendor/bin/rpmbClient smci -p 1'
# 期望：RMPB Key status: RPMB_KEY_PROVISIONED_AND_OK (0)
```

**危险，未在本项目执行**：

```sh
/vendor/bin/rpmbClient smci -e 1     # 全擦 RPMB，输入 y 确认
```

擦除后 FTQS 分区消失 → 门禁回 `-13` → `soter-provision 1` 才有可能成功。代价见 [06 §6.1](06-root-cause.md)。

## 8. TA 替换实验（可完全回滚）

```powershell
# 1) 复制原始分片作为基线
Copy-Item samples\soter_ta\image\soter64.b01 work\soter64_patch.b01

# 2) （可选）打补丁：文件偏移 == VA − 0x1000 的逆运算，b01 从 file 0x1000 起
& $PY -c "p=r'work\soter64_patch.b01'; d=bytearray(open(p,'rb').read()); o=0x5B4-0x1000; d[o:o+4]=bytes.fromhex('5f2403d5'); open(p,'wb').write(d)"

# 3) 推入并打标签
& $ADB push work\soter64_patch.b01 /data/local/tmp/soter64.b01
& $ADB shell 'chcon u:object_r:firmware_file:s0 /data/local/tmp/soter64.b01; chmod 644 /data/local/tmp/soter64.b01'

# 4) bind mount 覆盖（单文件）
& $ADB shell 'mount --bind /data/local/tmp/soter64.b01 /vendor/firmware_mnt/image/soter64.b01'
& $ADB shell 'stop vendor.soter; sleep 1; start vendor.soter'
& $ADB shell 'logcat -d -s QSEECOMPAT:*' | Select-String 'Error 12|load app failed'
```

期望：原样副本 → 正常；改 1 字节 → `load_app:name soter64 Error 12`。

回滚：

```powershell
& $ADB shell 'umount /vendor/firmware_mnt/image/soter64.b01'
& $ADB shell 'stop vendor.soter; sleep 1; start vendor.soter'
& $ADB shell 'service call vendor.qti.hardware.soter.ISoter/default 14 i32 1'   # 应恢复 ffffffec
```

## 9. `.mdt` 哈希表自检

```powershell
& $PY -c "
import hashlib
mdt=open(r'samples\soter_ta\image\soter64.mdt','rb').read()
for i in range(8):
    b=open(r'samples\soter_ta\image\soter64.b%02d'%i,'rb').read()
    h=hashlib.sha384(b).digest()
    off=mdt.find(h)
    print('b%02d len=%d sha384@0x%x'%(i,len(b),off) if off>=0 else 'b%02d MISS'%i)
"
```

期望：`b00→0x358`、`b01→0x388`、`b02→0x3b8`、`b03/b07→0x3e8`、`b04→0x418`、`b05→0x448`、`b06→0x478`。

## 10. 复核工程模式的解锁闸门（纯静态）

```powershell
& $ADB shell 'pm path com.oplus.engineermode'
& $ADB pull /system_ext/app/OplusCommercialEngineerMode/OplusCommercialEngineerMode.apk samples\apk\engmode.apk
D:\reverse-tools\jadx-1.5.6\bin\jadx.bat --no-res --no-imports -d work\engmode_apk samples\apk\engmode.apk
```

看两处：

1. `work\engmode_apk\sources\com\oplus\engineermode\security\assistant\KeyProvisionCommandHandler.java:232-249` —— `generateAttkKeyResult()` 第一个分支就是 `isDeviceOemUnlocked()`，命中即 `return 10000`；
2. `…\security\SecurityInterface.java:275-277` —— `isDeviceOemUnlocked()` 的实现是 `!"locked".equals(get("ro.boot.vbmeta.device_state","unlocked"))`。

```powershell
& $ADB shell getprop ro.boot.vbmeta.device_state   # unlocked → 闸门必定命中
```

## 11. 快速核对表

| 观测 | 期望 | 说明 |
| --- | --- | --- |
| `ISoter tx=14` | `ffffffec` | -20，门禁 |
| `ISoter tx=9` | `fffffffb` | -5，ASK 未预配 |
| `soter-provision 1..4` | 全 -20 | 含纯读的 4 |
| 工程模式 SOTER | 失败 | 重启 soter 后会假绿 |
| 工程模式 Attestation / RKP | 成功 | 已由 rkp 修复 |
| `/mnt/vendor/persist` 扫 magic | 0 命中 | 无 ATTK 副本 |
| `soter64.bin` 重建 | 84,575 B | 直接拼接是 74,924 B |
| TA 补丁 | `Error 12` | 完整性校验 |
