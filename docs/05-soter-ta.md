# 05 soter64 TA

本文是整个项目最核心的一篇：`soter64` TA 的镜像、地址、分派表、门禁函数与 ATTK 表格式。

> 地址约定：除非特别说明，本文地址都是**按 program header 重建后的镜像**（84,575 B）里的 VA，满足 `va = file_offset − 0x1000`。

## 1. 取镜像

```sh
adb pull /vendor/firmware_mnt/image  samples/soter_ta/image
```

`/vendor/firmware_mnt` 是个 vfat 的 `modem_a` 分区（`ro`），里面是 1038 个文件、226 MB。SOTER 的就 10 个：

| 文件 | 大小 |
| --- | --- |
| `soter64.b00` | 568 |
| `soter64.b01` | 59,336 |
| `soter64.b02` | 221 |
| `soter64.b03` | 912 |
| `soter64.b04` | 1,736 |
| `soter64.b05` | 304 |
| `soter64.b06` | 6,751 |
| `soter64.b07` | 912 |
| `soter64.b08` | 4,184 |
| `soter64.mdt` | 4,752 |

## 2. 重组镜像（最容易踩的坑）

### 2.1 直接顺序拼接是错的

`soter64.bin = cat b00 b01 … b08` 得到 74,924 B，能反编译、但**所有地址比真实值大 0xdc8**。

原因：`b00` 是 568 B = `Elf64_Ehdr`(64) + 9×`Elf64_Phdr`(56) = 0x238，也就是"ELF 头本身"；`b01` 紧跟着就是代码段。但 program header 里 `b01` 的 `p_offset` 是 `0x1000`、`p_vaddr` 是 `0`，中间那 0xdc8 是隐含的补齐。直接拼接把这个补齐吃掉了。

验证：直接拼接镜像里 `file 0x238` 处正好是 PLT0（`stp x16,x30,[sp,#-0x10]!` / `adrp x16` / `ldr x17,[x16,#0x10]` / `add x16,x16,#0x10` / `br x17`），后面每 16 B 一个桩。所以直接拼接镜像满足 `va = file − 0x238`。

### 2.2 正确做法：按 p_offset 摆放

```sh
python tools/analyze/build_ta.py samples/soter_ta/image soter64
# → samples/soter_ta/image/soter64.bin，84,575 B
```

| 段 | p_offset | vaddr | filesz | 内容 |
| --- | --- | --- | --- | --- |
| b00 | 0x0 | 0x0 | 0x238 | ELF 头 + program header |
| b01 | 0x1000 | 0x0 | 0xe7c8 | 代码（R+X） |
| b02 | 0x10000 | 0xf000 | 0xdd | 数据 |
| b03 | 0x11000 | 0x10000 | 0x390 | `.rodata` 字符串（`KM SOTER UNIQUE ID` 等） |
| b04 | 0x12000 | 0x11000 | 0x6c8 | 数据 |
| b06 | 0x13000 | 0x12000 | 0x1a5f | `.dynamic`/`.dynsym`/`.dynstr`/`.rela` |
| b05 | — | — | 0x130 | 与 b06 前 0x130 字节完全相同，跳过 |
| b07 | — | — | 0x390 | b03 的 RELRO 副本，跳过 |

自检：

```sh
python - <<'PY'
d = open('samples/soter_ta/image/soter64.bin', 'rb').read()
assert len(d) == 84575, len(d)
assert d[0x14500:0x1450f] == b'\x00app_heap_limit', d[0x14500:0x1450f]
assert d.find(b'qsee_stor_read_sectors') == 0x1499e
assert d.find(b'qsee_log') == 0x148f8
print('ok')
PY
```

> 记住 `va = file − 0x1000`：`.dynstr` 的 VA 是 `0x13500`，对应文件偏移 `0x14500`；`qsee_stor_read_sectors` 的 VA 是 `0x1399e`、文件偏移 `0x1499e`。混用两者是本项目早期最容易犯的错。

### 2.3 重建后地址自洽

- PLT0 在 `file 0x1000` = `va 0`；
- `get_validated_attk`（真实入口 `sub_5090`）在 va `0x5090`；
- `SOTER_CE` 字符串在 va `0xbeee`（file `0xceee`）；
- `get_validated_attk` 字面量在 va `0xc760`（file `0xd760`）。

### 2.4 动态链接信息（`tools/analyze/pltmap.py`）

```
DT_HASH   0x12b38     DT_SYMTAB 0x12db0    DT_SYMENT 0x18
DT_STRTAB 0x13500     DT_STRSZ  0x55f      DT_JMPREL 0x126a0
DT_PLTRELSZ 0x498（49 条 JUMP_SLOT）        DT_RELA 0x12130  DT_RELASZ 0x570
BIND_NOW=1            NEEDED=libcmnlib.so
```

49 条导入全部解出。桩地址公式：

```
stub_va = 0x20 + 16 * i,   i = (got_slot - 0x10018) / 8
```

关键导入：

| 桩 | 符号 |
| --- | --- |
| 0x20 | `qsee_log` |
| 0x40 | `qsee_prng_getdata` |
| 0x50 | `qsee_read_jtag_id` |
| 0x60 | `qsee_get_secure_state` |
| 0x128 | `qsee_cfg_getpropval` |
| 0x130 | `qsee_kdf` |
| 0x1b0 | `qsee_stor_device_init` |
| 0x1c0 | `qsee_stor_open_partition` |
| 0x1d0 | `qsee_stor_add_partition` |
| 0x1e0 | `qsee_stor_write_sectors` |
| 0x1f0 | `qsee_stor_read_sectors` |
| — | `qsee_SW_Cipher_*` / `qsee_SW_AE_*` / `qsee_SW_Hash_*` / `qsee_rsa_*` / `qsee_sfs_*` |

> TA 里同时有 `qsee_sfs_*` 与 `qsee_stor_*`：**ATTK 表走 stor（RPMB 分区），不是 SFS 文件**。这就是 `/persist/data/soter/` 不存在、表却能被正常读到的原因。

## 3. 命令分派表（va 0x11298）

IDA 的函数命名在这里会骗人：`sub_5AC` 其实比真实入口早 8 字节（0x5AC/0x5B0 是前一个函数的收尾 `dsb sy; isb`）。真实入口是 **0x5B4**（`bti c; autibsp; sub sp,sp,#0x50`）。

表结构：每项 16 字节 `{u64 cmd_word; u64 handler}`，`cmd_word` 低 16 位是命令号。

| cmd | handler | 命令 |
| --- | --- | --- |
| 0x101 | 0x5B4 | SOTER_GENERATE_ATTK |
| 0x102 | 0x708 | SOTER_VERIFY_ATTK |
| 0x103 | 0x7AC | SOTER_EXPORT_ATTK_PUBLIC |
| 0x104 | 0xB30 | SOTER_GET_DEVICE_ID |
| 0x105 | 0x11C4 | SOTER_GENERATE_ASK |
| 0x106 | 0x135C | SOTER_EXPORT_ASK_PUBLIC |
| 0x107 | 0x16CC | SOTER_REMOVE_ALL_UID_KEY |
| 0x108 | 0x17E0 | SOTER_HAS_ASK_ALREADY |
| 0x109 | 0x18EC | SOTER_GENERATE_AK |
| 0x10A | 0x1B74 | SOTER_EXPORT_AK_PUBLIC |
| 0x10B | 0x201C | SOTER_REMOVE_AK |
| 0x10C | 0x22E4 | SOTER_HAS_AK |
| 0x10D | 0x2560 | SOTER_INIT_SIGN |
| 0x10E | 0x2AB4 | SOTER_FINISH_SIGN |
| 0x10F | 0x2E24 | SOTER_GET_VERSION |

表项的第 2 个 u64 形如 `0x100000101`：低 16 位命令号，bit32 起是标志位（部分项为 0）。

字符串表在 `va 0xd138` 附近，15 个名字以相对偏移的 u32 存放，`sub_6000` 负责 `cmd - 0x101` 的查表。

## 4. 门禁链路

ATTK 类命令（0x101–0x105）在入口都会调 `sub_5090`。调用点（BL 扫描）：

```
0x618 (sub_5B4)   0x744 / 0x7fc / 0xb78 (sub_708)
0x1014 / 0x1218 (sub_C8C)   0x47b0 (sub_4748)
0x508c (sub_4F38) 0x51cc (sub_51B4) 0x6574 (sub_64E4)
```

### 4.1 `sub_5090` — ATTK 门禁（0x5090，0x124）

```c
if (*off_101D0 == 0) return -21;                     // rpmb_init 未完成
v = sub_52E8();                                      // 读表 + 逐份校验
if (v != 0) { qsee_log(8,"%s:%u:%d","get_validated_attk",70,v); return v; }
if (hdr->magic == 0x53515445 && hdr->flag == 0xFF01) {
    if (*(u32*)entry == 0x53515445) return 0;         // 解密后 entry 头有效
    qsee_log(8,"SOTER: ATTK not set");
} else {
    qsee_log(8,"SOTER: Header not validated");
    qsee_log(8,"magic_num:0x%x, expected:0x%x", ...);
    qsee_log(8,"ATTK status:0x%x, expected:0x%x", ...);
}
return -13;
```

返回值集合只有四种：`-21`（未初始化）、`-13`（表头无效）、`0`（通过）、以及 `sub_52E8` 的返回值（`-11`/`-16`/`-20`/stor 读错误）。

### 4.2 `sub_52E8` — 读表并逐份校验（0x52E8，0x1b0）

```c
if (*off_101A8) return 0;                              // 缓存命中
buf = qsee_malloc(2560); *off_101A8 = buf;
if (!buf) return -11;
rc = qsee_stor_read_sectors(&qword_11120, 0, 1, buf); // 0 号扇区 = 512 B 表头
if (rc) { log(138, rc); sub_5498(); return rc; }
*off_101B0 = buf + 512;                                // entry 区
if (*(u64*)buf == 0x53515445 && *(u32*)(buf+0xC) == 0xFF01) {
    count = *(u32*)(buf+0x10);
    if (count > 4) return -16;
    if (count == 0) { log("****Something is wrong, this should never happen****");
                      log("Magic matches but attk invalid"); → -20 }
    for (i = 0; i < count; i++) {
        rc = qsee_stor_read_sectors(&qword_11120, 1+4*i, 4, *off_101B0);  // 2048 B
        if (rc) { log(154, rc); return rc; }
        if (sub_461C(i) == 0) return 0;
        memset(*off_101B0, 0, 2048);
    }
    log("Something is wrong, this should never happen");
    log("Magic matches but attk invalid");
    → return -20
}
return 0;                                              // magic 不符 → 上层给 -13
```

失败路径都会走 `sub_5498`（`memset(buf,0,2560); free; *off_101A8 = *off_101B0 = NULL`），所以 **-20 每次都重新读 RPMB，稳定复现、不会因为调用次数变化**。

### 4.3 `sub_461C` — 校验第 i 份副本（0x461C，0x12c）

```c
if (i > 3) return -16;
u8 key[32] = {0};
rc = sub_3B3C(0, key, 32);                             // KDF type 0
if (rc) { log(511, rc); return rc; }
rc = sub_35F8(1, key, 32,
              hdr + 40*i + 56, 16,                     // IV
              hdr + 40*i + 72, 16,                     // TAG
              entry_buf,                               // 就地解密
              *(u32*)(hdr + 40*i + 52));               // 长度 = payload + 16
if (rc) log(516, rc);
memset(key, 0, 32);
return rc;
```

### 4.4 `sub_3B3C` — 派生密钥（0x3B3C，0x104）

```c
if (__ROR8__(len - 8, 3) > 3) return -16;              // len ∈ {8,16,24,32}
type 0: label1 = "KM SOTER UNIQUE ID"           (va 0x11000)
        label2 = "KM SOTER UNIQUE ID FROM SHK"  (va 0x11013)
type 1: label1 = "KM SOTER SN UNIQUE ID"        (va 0x1102f)
        label2 = "KM SOTER SN UNIQUE ID FROM SHK" (va 0x11045)
default: log("%s: Not supported key type","getDerivedKey"); return -15;
rc = qsee_kdf(0, len, label1, strlen(label1), label2, strlen(label2), out, len);
```

标签是**常量**，所以失配不来自标签，只能来自 `qsee_kdf` 的根（见 [06](06-root-cause.md)）。

### 4.5 `sub_2FCC` — is_secure_boot_enabled（0x2FCC，0x16c）

```c
if (qsee_get_secure_state(&st) == 0) return (st & 0x67) == 0x40;
qsee_log(8,"%s:%u:%d","is_secure_boot_enabled",42,rc);
return 0;
```

同一函数里还读 `SOTER_CE` 配置（`sub_3138` → `qsee_cfg_getpropval`），并据此调 `qsee_set_bandwidth(.., secboot ? 3 : 0, ..)`。

### 4.6 `sub_2E94` — query_device_id（**安全状态分支的直接证据**）

```c
memset(out, 0, 16);
out->chip = (qsee_read_jtag_id() << 24) | ...;         // 4 次 jtag id 拼成
if (sub_2FC0() & 1)                                    // is_secure_boot_enabled()
    sub_3B3C(0, &v, 8);                                // 安全启动：KDF 派生的稳定 ID
else
    loc_6E78(&v, 8);                                   // 非安全启动：PRNG 随机 8 字节
out->devid = bswap64(v);
```

这一行 `else` 是"解锁后行为可能不同"的最强代码证据：**同一个 TA，在两种安全状态下设备 ID 的生成方式都不一样**。

### 4.7 `sub_4F38` — 打开/创建 SOTER 分区（0x4F38，0x158）

```c
enabled = 0; sub_34F4(&enabled);                       // 读 TEE 配置 enable_soter
if (enabled) {
    rc = qsee_stor_open_partition(&part, 0x53515446, &handle);
    if (rc || !handle || !part) {
        log("qsee_stor_open_partition() for Soter partition failed, adding the partition");
        rc = qsee_stor_add_partition(&part, 0x53515446, 20);   // 20 扇区 = 10240 B
        if (!rc) log("Successfully added SOTER partition: %u", 0x53515446);
    }
}
return sub_5090();                                     // 打开后立刻校验
```

- 分区 ID `0x53515446` 小端 = `FTQS`；
- 表头 magic `0x53515445` 小端 = `ETQS`；
- `sub_34F4` 读 `qsee_cfg_getpropval("enable_soter", 13, …)`，值取缓冲 +8 处的 u32 并缓存。本机返回 -20 而非 -12，说明 **`enable_soter` 非 0**，SOTER 是启用的。

### 4.8 `sub_54F0` — store_attk（0x54F0，0x348）

```c
if ((len - 2033) >= 0xFFFFFFFFFFFFF7FF) return -22;    // 2033 ≤ len ≤ 2048
tmp = qsee_malloc(2048);
key = KDF(0, 32);
entry = *off_101B0;
*(u64*)entry = 0x53515445; *(u32*)(entry+8) = 16; *(u32*)(entry+12) = len;
memcpy(entry+16, blob, len);                           // 明文 entry = [16 B 头][blob]
hdr = *off_101A8;
*(u64*)hdr = 0x53515445; *(u32*)(hdr+8) = 0; *(u64*)(hdr+24) = 0;
sub_2E94(hdr+32);                                      // 16 B device id
*(u32*)(hdr+16) = count;
for (i = 0; i < count; i++) {
    *(u32*)(hdr+40*i+48) = 4*i;                        // 起始扇区
    *(u32*)(hdr+40*i+52) = len + 16;                   // 长度
    memset(tmp, 0, 2048);
    if (i == 0) {
        prng(hdr+56, 16);                              // IV
        memcpy(tmp, entry, len+16);
        sub_35F8(0, key, 32, hdr+56, 16, hdr+72, 16, tmp, len+16);
    } else {
        memcpy(hdr+40*i+56, hdr+56, 16);               // 复制第 0 份的 IV
        memcpy(hdr+40*i+72, hdr+72, 16);               // 复制第 0 份的 TAG
        // tmp 保持全零，不重新加密
    }
    rc = qsee_stor_write_sectors(&qword_11120, 1+4*i, 4, tmp);
    if (rc) { log("store_attk",252,rc); goto cleanup; } // 每次写都检查返回值
}
*(u32*)(hdr+12) = 0xFF01;                              // 最后才写"表头有效"
qsee_stor_write_sectors(&qword_11120, 0, 1, hdr);
```

两个要点：

1. **只有第 0 份真正加密**，第 1..count−1 份写的是全零页 + 复制来的 IV/TAG。所以实际参与校验的只有第 0 份（其余份必然失败，循环会先命中第 0 份就返回）。
2. **表头最后写**，且每次写都检查返回值 → "表头有效"意味着整套写入流程完整跑完过。这一点是 [06](06-root-cause.md) 排除"写一半坏掉"的关键。

### 4.9 `sub_5B4` — generate_attk_key_pair（死锁所在）

```c
v13 = 0; sub_34F4(&v13); if (!v13) return -12;         // enable_soter 必须非 0
if (a2 < 8) return -22;                                // 请求至少 8 字节
if (sub_5090() != -13) {                               // ← 只接受"表头无效"
    qsee_log(8, "ATTK already provisioned or RPMB not provisioned");
    return -20;
}
copies = *(u8*)(req+4);
rsa: bits = 2048, e = 65537;
rc = sub_3C44(&key);                                   // 生成 ATTK 密钥对
if (!rc) rc = sub_54F0(&key, min(copies,4));           // 写表
```

**这是整个问题的根**：重配要求门禁返回 `-13`，而本机是 `-20`。

### 4.10 `sub_51B4` — soter_query_update_counter（另一条被门禁挡住的写路径）

```c
rc = sub_5090();
if (rc) { log("soter_query_update_counter",98,rc); log("SOTER: Update counter failed"); return -32; }
++*(u64*)(hdr+0x18);
sub_5278();                                            // 回写 0 号扇区
qsee_log(8, "COUNTER %llu", ...);
```

连"把计数器加一"都要先过门禁，所以表头里的 counter 在本机永远不变。

## 5. ATTK 表格式（RPMB 分区 `FTQS`，20 扇区 = 10,240 B）

| 偏移 | 长度 | 内容 |
| --- | --- | --- |
| 扇区 0 + 0x00 | 8 | magic `0x53515445`（`ETQS`，字节 `45 54 51 53`） |
| + 0x08 | 4 | 0 |
| + 0x0C | 4 | `0xFF01`（表头有效标志，最后写入） |
| + 0x10 | 4 | count（1..4，本机推断 3） |
| + 0x18 | 8 | 更新计数器 |
| + 0x20 | 16 | `query_device_id` 结果（chip id + devid） |
| + 0x30 + 40·i | 4 | 第 i 份起始扇区 = 4·i |
| + 0x34 + 40·i | 4 | 第 i 份长度 = payload + 16 |
| + 0x38 + 40·i | 16 | IV |
| + 0x48 + 40·i | 16 | GCM TAG |
| 扇区 1 + 4·i | 2048 | 密文 entry：明文 = `[0]=magic`、`[8]=16`、`[12]=len`、`[16..]=ATTK blob` |

加密参数：

- 算法 AES-256-GCM（`sub_35F8`：`qsee_SW_Cipher_Init` + GCM 模式 3，key 长度 32）；
- key = `qsee_kdf(0, 32, "KM SOTER UNIQUE ID", "KM SOTER UNIQUE ID FROM SHK")`；
- **AAD = IV 本身**；
- 明文长度 = `len + 16`（含 entry 头）。

## 6. 字符串证据（`strings.py` 命中位置，重建镜像的 va = file − 0x1000）

```
0xbec7  query_device_id
0xbed7  is_secure_boot_enabled
0xbeee  SOTER_CE
0xbfdc  enable_soter
0xbfe9  get_soter_enable
0xbffa  soter_enable_default %d
0xc20c  SOTER_Cipher_keyBlob
0xc3d7  soter_rsa_init_key
0xc45e  validate_attk_copy
0xc494  soter_rsa_serialize_key
0xc6ec  rpmb_init
0xc71a  !!! secboot device && rpmb error, BAILING OUT !!!
0xc74c  secboot device : %u
0xc760  get_validated_attk
0xc773  SOTER: Header not validated
0xc78f  magic_num:0x%x, expected:0x%x
0xc7ad  ATTK status:0x%x, expected:0x%x
0xc7cd  SOTER: ATTK not set
0xc7e1  soter_query_update_counter
0xc809  SOTER: Update counter failed
0xc826  update_soter_rpmb_header
0xc83f  soter_rpmb_alloc_read
0xc88a  Magic matches but attk invalid
0xc8a9  store_attk
0xc900  open_soter_partition
0xc915  Successfully added SOTER partition: %u
0xc957  soter_sfs_check_file / 0xca25 soter_sfs_check_key / 0xca44 delete /
        0xca59 write_file / 0xca6e read_file
0xcfa9  SOTER_GENERATE_ATTK … 0xd0be SOTER_GET_VERSION（15 个命令名，间隔 0x12~0x16）
0x11000 KM SOTER UNIQUE ID
0x11013 KM SOTER UNIQUE ID FROM SHK
0x1102f KM SOTER SN UNIQUE ID
0x11045 KM SOTER SN UNIQUE ID FROM SHK
```

> 这组数字是脚本直接跑出来的（`python tools/analyze/strings.py … | grep`），不是手工换算。旧版文档里 `0xc0a7 rpmb_init`、`0xc144 SOTER: Header not validated` 之类的偏移来自**直接拼接镜像**，与本节差 0xdc8，引用时会全部错位。

`b08` 段（va 0x15000，4184 B）不是哈希表，而是证书/元数据段，里面是同一组 X.509 字符串（`Guangdong`/`Shenzhen`、`OPLUS Technologies`、`OPLUS Attestation CA`、`240326125815Z`–`440321125815Z`、`OPLUS SM8750 Attestation`、`General OPLUS Use Key`、`OPLUS ROOT CA 1`）。

## 7. 在 IDA 里复现

1. `idb_open` → `samples/soter_ta/image/soter64.bin`（**重建后的 84,575 B 那份**）；
2. ImageBase 填 `0`，等自动分析（约 176 个函数）；
3. 跳 `0x5090` 看门禁、`0x52E8` 看读表、`0x54F0` 看写表、`0x5B4` 看 generate；
4. 不要相信函数名：`sub_5AC` 是错的，命令表在 `0x11298`；
5. 字符串 xref 在重建镜像里是正常的（直接拼接那份才会乱）。

## 8. 未解

- `qsee_kdf` 的根是否随安全状态变化：用户态不可观测，只能靠 TEE 侧日志或 QTI 文档；
- 表头 count 的实际值、device id 字段的实际内容：TA 替换实验封死后（[07](07-attempts.md)），用户态读不到。
