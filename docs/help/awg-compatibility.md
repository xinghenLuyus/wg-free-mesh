# AWG 协议适配说明

配置先选择 **AmneziaWG** 协议，再选择 **1.5、2.0 或 3.1**。版本作用于整个 Mesh，不支持同一配置内混用版本。新建 AWG 配置默认选择 3.1。

## 版本差异

| 版本 | 本系统生成的参数 |
| --- | --- |
| 1.5 | S1/S2、固定 H1–H4、Jc/Jmin/Jmax、I1–I5；可选 J1–J3 和 Itime。S3/S4 不输出。 |
| 2.0 | S1–S4、H1–H4 单值或范围、Jc/Jmin/Jmax、I1–I5。 |
| 3.1 | 2.0 参数，以及 HeaderProtectionKey、ContentPaddingAddition、握手时序参数、RandomTrailers 和 DisableCookies。 |

3.1 的 HeaderProtectionKey 是全 Mesh 共用的 32 字节 Base64 密钥，不是 WireGuard 私钥。启用它时 S1–S4 必须至少为 12。本系统启用 RandomTrailers 时要求 S1–S4 相等，开关在配置层统一设置。新生成的 3.1 参数使用相等的随机 S 和互不重复的随机固定 H；时序、填充参数也随机生成，手动清空后使用工具链默认值。

## 统一随机与手动配置

端点高级配置 → AmneziaWG 本地参数提供“随机”按钮，沿用配置已保存的方向和强度，仅生成当前端点的本地参数草稿，不修改共享 S/H、密钥、机制开关或其他端点。仍需手动保存才生效。3.1 本地扩展字段旁的小问号说明用途、单位、范围写法和注意事项。

配置设置 → 高级设置提供整配置随机入口：选择通用随机、DNS、STUN/WebRTC、RTP/语音 UDP 或 QUIC Initial（实验性），再选择低开销、均衡或较强扰动，一键生成共享参数和全部现有端点的独立参数。生成只修改草稿，保存才应用并触发配置同步。取消不会更改配置；版本切换会清除未保存的端点草稿。

所有适用字段可逐项编辑或清空，端点高级配置也可独立维护。方向不限制手动内容。方向和强度随配置保存，新建端点沿用生成策略；预览、下载和刷新只使用已保存的实际参数，不会重新随机。普通生成保留已设置的包头保护密钥、DisableCookies 和共享 RandomTrailers；密钥重新生成是单独操作。各端点开关不一致时，先明确设置共享 RandomTrailers，再生成。

这些方向只生成握手前的 CPS 签名包，不会把全部隧道流量变成对应协议，也不保证绕过检测。DNS 使用查询结构，STUN 使用 Binding 请求和 SOFTWARE 属性，RTP 使用同一签名链内关联的序号、时间戳和 SSRC。QUIC 按 [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html) 生成带包体加密、包头保护的单个 1200 字节 Initial，但不建立完整 QUIC 会话；该包仅在再次生成时改变，不能随意在密文中插入随机标签。上述方向尚未做实际工具链互通与流量检测验证。

随机建议范围不是手工配置上限。较大包长会增加 MTU 和带宽风险；较短握手时序可能降低弱网络稳定性。ContentPaddingAddition 指定非零填充时会优先于数据包随机尾部填充，二者并非简单叠加。

## 工具链要求

WFM 生成配置并调用工具链，不会安装或升级 AmneziaWG 本身。客户端使用 Linux/macOS 的 `awg`、`awg-quick` 或 Windows 的 `amneziawg.exe`。**WFM 客户端版本不等于 AWG 协议版本。**

切换前确认每个端点实际安装的 AmneziaWG 实现支持目标版本和所选参数。不同实现和版本支持的参数可能不同，不能仅凭命令存在判断兼容性。不兼容时工具链执行会报错，不会静默降级。

参考 [AmneziaWG 官方说明](https://docs.amnezia.org/documentation/amnezia-wg/) 和 [amneziawg-go](https://github.com/amnezia-vpn/amneziawg-go)，按操作系统和具体实现选择对应版本。

## 版本切换

版本切换会由后端转换不兼容的 S/H 参数，界面展示转换后的值，保存后才生效。切到 1.5 会将 H 范围收敛为固定值并停用 S3/S4；切到 3.1 会生成适配的 S/H 和缺失的 HeaderProtectionKey。未用于当前版本的扩展参数保留但不输出，不维护历史版本配置副本。

AWG 版本切换使用 AWG 工具链。动态端点通过配置同步停止运行中的隧道、写入配置，并在此前运行时重新启动；静态端点需重新下载并自行应用配置。全 Mesh 应协调切换，应用期间可能断连，端点工具链不会随之升级。

完整参数规则见 [协议参数](/reference/protocols)。
