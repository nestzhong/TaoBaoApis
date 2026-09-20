# 🎁 TaobaoApis — 淘宝第三方 API 集成库，AI 客服智能体底座

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/node.js-18%2B-green)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

> **在 AI 大模型爆发的时代，每一个淘宝卖家都值得拥有一个 7×24 小时不下线的智能客服。**
> 本项目封装了淘宝平台完整的消息通信能力，为开发者构建 AI 客服智能体提供可靠、稳定的底层 API 支撑。

**⚠️ 严禁用于发布不良信息、违法内容！如有侵权请联系作者删除。**

---

## 为什么需要这个项目？

```
用户私信 ──► [TaobaoApis] ──► 你的 AI Agent（LLM / RAG / 规则引擎）──► 自动回复
               ▲                                                          │
               └──────────────── 发送消息 / 图片 ◄────────────────────────┘
```

淘宝官方没有开放 IM 消息接口。想要接入 GPT、Claude、本地大模型来做智能客服，首先需要能**稳定收发消息**。TaobaoApis 解决的正是这个前置问题：

- 逆向还原了淘宝 WebSocket 私信协议（sign 签名 + base64 + Protobuf）
- 封装全部 HTTP 接口（sign 参数已解密）
- 提供统一的消息收发抽象层，开发者只需关注业务逻辑

**你负责接 AI 大脑，我们负责打通淘宝的神经。**

---

## 已实现功能

### WebSocket 消息通信

| 模块 | 功能 | 状态 |
|------|------|------|
| WebSocket | 私信实时收发（sign + base64 + Protobuf 协议） | ✅ |
| 消息类型 | 文字、图片消息收发 | ✅ |
| 会话管理 | 获取全部历史聊天记录 | ✅ |
| 主动发送 | 主动向指定用户发消息 | ✅ |
| Token 维持 | 自动刷新登录态，常驻进程不掉线 | ✅ |

### 买家端 HTTP API（MTOP 协议）

| 接口 | 功能 | 状态 |
|------|------|------|
| `search_products()` | 商品搜索（含 DinamicX 解析） | ✅ 已验证 |
| `get_cart_list()` | 获取购物车列表 | ✅ 已验证 |
| `add_to_cart()` | 加入购物车 | ✅ |
| `get_order_list()` | 订单列表（含 DinamicX 解析） | ✅ 已验证 |
| `get_order_detail()` | 订单详情（通过订单列表回退查找） | ✅ |
| `get_token()` | 刷新 AccessToken | ✅ 已验证 |
| `get_goods_uid_encrypt_uid()` | 商品详情页解析 | ✅ |
| `upload_media()` | 媒体上传 | ✅ |

### 数据解析工具

| 方法 | 功能 |
|------|------|
| `parse_search_results()` | 从 DinamicX 模板提取商品信息（item_id、标题、价格、店铺名、图片） |
| `parse_order_list_results()` | 从 DinamicX 容器提取订单信息（状态、卖家、商品明细、价格） |

---

## 快速开始

### 环境要求

- Python 3.9+
- Node.js 18+（用于执行签名算法 JS）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 Cookie

登录 [taobao.com](https://www.taobao.com) 后，从浏览器开发者工具中复制完整 Cookie 字符串，填入代码对应位置：

```python
# taobao_live.py 底部
cookies_str = r'your_cookie_string_here'
```

> Cookie 必须是**登录后的状态**，否则无法获取消息。


### 直接运行

```bash
python taobao_live.py
```

---

## 项目结构

```
TaobaoApis/
├── taobao_live.py       # 主入口：WebSocket 消息监听 & 回复逻辑（在此接入 AI）
├── taobao_apis.py       # HTTP API 封装（搜索、购物车、订单、登录、Token刷新、媒体上传）
│                       #   - 搜索: search_products + parse_search_results
│                       #   - 购物车: get_cart_list + add_to_cart
│                       #   - 订单: get_order_list / get_order_detail + parse_order_list_results
│                       #   - 认证: get_token / _ensure_token
├── message/
│   ├── types.py         # 消息类型定义（TextContent / ImageContent / AudioContent）
├── utils/
│   └── taobao_utils.py  # 工具函数（sign 签名、Cookie 处理、消息解密、device_id 生成）
├── static/
│   └── taobao_js_*.js   # 逆向 JS（sign 签名核心算法）
├── requirements.txt
└── Dockerfile
```

---

## 接入 AI 智能体

在 `taobao_live.py` 的 `handle_message` 方法中替换回复逻辑即可：

```python
async def handle_message(self, message, websocket):
    # ... 解析 send_user_id, cid, send_message ...

    # 原始 echo 回复（示例）
    # reply = f'{send_user_name} 说了: {send_message}'

    # 接入 AI 大模型（示例）
    reply = await your_ai_agent(send_message)          # GPT / Claude / Qwen / 本地模型

    await self.send_msg(websocket, cid, send_user_id, make_text(reply))
```

---

## 注意事项

## 注意事项

- `taobao_live.py` 是消息收发主入口，所有 AI 回复逻辑在此扩展
- `taobao_apis.py` 包含 HTTP 接口模板，可按需添加其他接口
- Cookie 需包含 `_m_h5_tk`、`_m_h5_tk_enc`、`unb`、`_nk_`、`_tb_token_`、`cookie2`、`cna` 等关键字段
- 买家端 MTOP 接口在 Token 过期时会自动调用 `get_token()` 刷新（通过 `_ensure_token()` 机制）
- 搜索、购物车、订单列表返回的 DinamicX/Weex 容器数据可由对应 `parse_*_results()` 方法解析为结构化数据

---

## 参与贡献

欢迎任何形式的贡献！无论是修复 Bug、新增接口、完善文档还是分享你基于本项目构建的 AI 应用，PR 随时欢迎。

**提交 PR 前请确认：**

- 代码风格与现有代码保持一致
- 新增接口请附上简要说明（接口用途、入参、返回示例）
- 如果改动较大，建议先开 Issue 讨论方案

**你也可以通过 Issue 来：**

- 反馈 Bug 或接口失效
- 提出新功能建议
- 分享使用中遇到的问题

---

## 额外说明

1. 感谢 Star ⭐ 和 Follow，项目会持续更新
2. 作者联系方式在主页，有问题随时联系
3. 欢迎 PR 和 Issue，也欢迎关注作者其他项目
4. 如果此项目对您有帮助，欢迎请作者喝一杯奶茶 ~~

<div align="center">
  <img src="https://github.com/cv-cat/Spider_XHS/blob/master/author/wx_pay.png" width="380px" alt="微信赞赏码">
  <img src="https://github.com/cv-cat/Spider_XHS/blob/master/author/zfb_pay.jpg" width="380px" alt="支付宝收款码">
</div>

---

## 📈 Star 趋势

<a href="https://cvcat.site/star-history/svg?repos=cv-cat/TaoBaoApis&type=Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/TaoBaoApis&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://cvcat.site/star-history/svg?repos=cv-cat/TaoBaoApis&type=Date" />
    <img alt="Star History Chart" src="https://cvcat.site/star-history/svg?repos=cv-cat/TaoBaoApis&type=Date" />
  </picture>
</a>




## 🍔 交流群

如果你对爬虫和 AI Agent 感兴趣，可以加入群聊一起讨论~

ps: 请加群，人满或者过期 issue | wx 提醒 | qq提醒

| group-1 | group-2 | group-3 | group-4 (2000人qq群) |
|:--:|:--:|:--:|:--:|
| <img width="280" alt="group1" src="https://cvcat.site/assets/group1.jpg" /> | <img width="280" alt="group2" src="https://cvcat.site/assets/group2.jpg" /> | <img width="280" alt="group3" src="https://cvcat.site/assets/group3.jpg" /> | <img width="280" alt="group3" src="https://cvcat.site/assets/group4.jpg" /> |
