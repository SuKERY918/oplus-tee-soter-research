# 09 OhMyKeymint / Ommega 与 ATTK 信任根

本文补充 04/05：为什么软件 TA 的自签 ATTK 过不了微信，服务器方案为什么能过但会封号，
"本地实现"缺的是什么，以及真 ATTK 一般从哪里来。

## 1. 项目关系

| 项目 | 定位 | 与 SOTER 的关系 |
| --- | --- | --- |
| qwq233/OhMyKeymint（上游） | KeyMint / keystore 欺骗 | 不含 SOTER；FAQ 明确 SOTER 是独立框架 |
| ITxiao6666/OhMyKeymint | 第三方分支 | 加本地 SOTER 随机身份、本机 RKP Keybox 签发；文档说明本地随机身份 `finishSign` 返回 -26，不能完成指纹支付签名 |
| jun430/OhMyKeymint | 再分支 | 只改配置，默认本地软件 SOTER TA、关闭远程 relay；未新增真 ATTK，README 的"微信指纹支付可用"需要真机支付流程验证 |
| syh0119/OhMyKeymint | 再分支 | fail-closed SOTER relay；relay 是支付场景的生产路径 |
| jiyin004-jpg/ommega | A/B/服务端三端 | A 端 `soter_local.rs` 自签兜底、`soter_relay.rs` 转 B；服务端 `soter_mint.rs` 有 keybox/attk/self_signed 三层，ATTK 库存 RSA 私钥 + cpu_id |

结论：上游 OMK 管不到 SOTER。能在微信支付里跑通的实现，要么把请求转给一台真机（B 端），
要么用一把 TAM 备案过的真 ATTK 私钥在本地铸料；单纯"软件 TA + 自签"只能骗本地探测。

## 2. 校验位置

| 层 | 生成位置 | 谁签名 | 谁校验 |
| --- | --- | --- | --- |
| ATTK | 产线 TEE，一机一密 | 厂商把公钥登记到腾讯 TAM | TAM |
| ASK | 设备 TEE（或软件 TA） | ATTK 私钥 | 应用服务器把签名交给 TAM 验 |
| AuthKey | 设备 TEE（或软件 TA） | ASK 私钥 | 应用服务器用 ASK 公钥验 |

- TAM 用产线登记的 ATTK 公钥验 ASK 的签名；自签不在备案里，必拒。
- 工程模式绿、cmd 57=0、客户端暂时不报错，都不是微信接受的证据。
- ASK 与 AuthKey 必须同源；混用真机和本地自签会导致自删自建或卡死。
- SOTER 的 blob 是 `[u32 LE JSON 长度][JSON][RSA-PSS 签名]`，不是 X.509 证书链；
  用证书自签去模拟，协议层就先偏了。

## 3. 服务器方案：能过，但根是共享的

- `physical`：请求转给 BL 锁定的真 B 机，由原厂 TEE 用真 ATTK 签。
- `server_key` / `attk`：服务端直接用上传的真 ATTK 私钥 + cpu_id 铸 ASK。
- 两种都用了 TAM 认识的根，所以能过。
- 但公开/默认 relay 让许多用户共用同一台 B 或同一把 ATTK：同一个 cpu_id/ATTK 出现在大量
  微信号、不同 IP 和地理位置。腾讯看到的是"一台设备给一堆账号开通/签名"，这是设备农场/
  账号集群信号，风控和封号是迟早的事。
- relay 运营方还能看到 token、IP、调用记录；私钥/身份在别人手里，本身也是风险。
- 所以问题不是"服务器"这个形态，而是"根被共享"。

## 4. 本地路线对照

| 路线 | 用的根 | 能过微信 | 封号风险 | 备注 |
| --- | --- | --- | --- | --- |
| 软件 TA + 自签 ATTK | 自己生成，TAM 无记录 | 否 | 不封，但也没功能 | 本机实测 ASK 被秒清 |
| 本地导入真 ATTK PEM + cpu_id | TAM 备案过的真根 | 是 | 取决于这把根是否只你一人用 | Ommega WebUI 支持 `soter_attk.pem` + `cpu_id:` 行 |
| 自建 relay + 自己的锁态 B 机 | B 机真 TEE 的真 ATTK | 是 | 低（一人一机） | 最稳的"本地"方案，需要一台锁态真机 |
| 假回锁 / 保留 TEE 的 root | 本机原厂 ATTK | 是 | 低（本质是原厂状态） | efisp 方案只覆盖部分机型；Ace 6 待验证 |

注意：本地软件 TA 还需要完成 `finishSign` 的生物认证证据、ASK/AuthKey 同源、blob 形状对齐；
缺一项就会 -26、146 秒卡死或被微信清钥匙。信任根和协议实现是两道独立的关。

## 5. 真 ATTK 一般从哪里来

先给结论：**"锁定 BL + 临时 root"本身通常拿不到 ATTK。** root 是 Android 用户态权限；
ATTK 私钥在 TEE/RPMB（或 persist 里被 TEE 密钥加密的文件），TEE 不会因为你是 root 就交出私钥。
本机 `oplusboot.rpmb_enabled=1`，正常应在 RPMB/SFS；TA 字符串里的 `/persist/data/soter/`
不能证明 key 在 persist。

常见来源：

1. **不提取，直接把锁态机当 B 端签名机。** ATTK 一直在 TEE 里，只把签名请求送进去。
   这是大多数"能过且不封号"方案的现实做法，也是"临时 root 锁态机"最常见的用途。
2. **产线/售后/内部工具或泄露。** 厂商产线生成并登记 ATTK；工具、备份、内部人员泄露会流出
   极少数真 key/cpu_id。
3. **TEE/TA 漏洞。** 例如 2022 年小米 SOTER TA 的任意读漏洞，可从旧版 MIUI 提取 SOTER 私钥。
   这类漏洞是真实 ATTK 泄露的主要技术来源之一，但依赖具体机型和固件，不是通用方法。
4. **无 RPMB / key 存在 persist 的机型。** 若私钥明文或弱加密，root 可直接读；有 RPMB 的机型不行。
   不同 OEM/平台差异很大，不能拿一台机器的结论套所有机型。
5. **已解锁机型上的原厂 TA。** 如果 ATTK 还在 RPMB，只是 TA 因 secure boot 检查拒绝，那么
   "假回锁/恢复锁态"比提取更现实；如果 ATTK 已被清，才需要备份/导入。
6. **购买的 keybox/key 材料。** 来源复杂，可能被多人共用、被吊销或本身就是蜜罐；
   支付场景不要用。Google keybox / RKP 与 SOTER ATTK 是两套根，不能互换。

所以，"临时 root 锁态机"能做的事主要是：跑 B 端 relay、dump persist 做对比、或在有 TEE
漏洞时配合利用；单独 root 不等于拿到 ATTK。真想走本地，先确认本机 ATTK 是"被挡住"还是
"已被清"，再决定假回锁、自建 B 端，还是导入一把只属于你的真 ATTK。

## 6. 对本项目下一步

1. 锁态基线：`soter-provision 1/2/3`、工程模式 15 行、persist/RPMB/uefivarstore 差异。
   先回答"解锁是屏蔽还是清空 ATTK"。
2. 如果 ATTK 还在：优先评估假回锁/TEE 恢复，让原厂 TA 重新工作；这比任何软件 TA 都干净。
3. 如果 ATTK 已清：评估自己的锁态 B 机 relay；不要用公开默认 B/共享 ATTK 跑支付账号。
4. 如果要继续本地软件 TA：先用一把已知可用的真 ATTK + cpu_id 做对照，把"协议没对齐"和
   "根不被信任"分开；再对齐 805/809 B、`rsa_pss_saltlen`、JSON 键序和 `finishSign` 生物认证证据。
5. 风险：这条路的本质是绕过微信支付的设备可信校验。不要在主账号/大额账户上试验；
   来源不明的 ATTK 既有封号风险，也可能牵扯法律问题。

## 参考

- [Tencent SOTER 密钥体系（ATTK/ASK/AuthKey 与 TAM 验证）](https://cloud.tencent.com/developer/article/1043664)
- [Tencent/soter 官方 Wiki：原理](https://github.com/Tencent/soter/wiki/%E5%8E%9F%E7%90%86)
- [小米 TEE / SOTER 私钥提取漏洞分析](https://www.4hou.com/index.php/posts/50Vv)
- [qwq233/OhMyKeymint（上游，不含 SOTER）](https://github.com/qwq233/OhMyKeymint)
- [ITxiao6666/OhMyKeymint（本地 SOTER 身份与 RKP 分支）](https://github.com/ITxiao6666/OhMyKeymint)
- [jun430/OhMyKeymint（本地软件 SOTER TA 构建）](https://github.com/jun430/OhMyKeymint)
- [syh0119/OhMyKeymint（fail-closed SOTER relay）](https://github.com/syh0119/OhMyKeymint)
- [jiyin004-jpg/ommega（A/B/服务端三端远程 TEE）](https://github.com/jiyin004-jpg/ommega)
- [ommega-relay-server（中继服务端源码）](https://github.com/jiyin004-jpg/ommega-relay-server)
- [一加 15/15T/Ace6T 免解 BL root + 微信指纹（efisp 方案）](http://www.romleyuan.com/lec/read?id=1488)
- [假回锁与 TEE/微信指纹的现状梳理](https://post.smzdm.com/p/al3ldl88)