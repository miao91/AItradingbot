# AI TradeBot - Discord Bot 闭环测试指南

## 概述

本指南描述了 Discord Bot 与 Clawdbot 的完整闭环测试流程。

---

## 📋 前置要求

### 1. 环境配置

确保 `.env` 文件中已配置以下凭证：

```bash
# Discord Bot 凭证 (请替换为你自己的 Token)
DISCORD_BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN_HERE
DISCORD_CLIENT_ID=YOUR_CLIENT_ID_HERE
DISCORD_CLIENT_SECRET=YOUR_CLIENT_SECRET_HERE

# Clawdbot 配置
CLAWDBOT_USER_ID=975399077120466965

# Discord 频道配置（重要！）
DISCORD_CHANNEL_ID=<你的Discord频道ID>
```

### 2. 获取 Discord Bot Token

1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建新应用或选择现有应用
3. 在 "Bot" 页面获取 Token
4. **重要**: 不要将 Token 提交到公开仓库！

### 3. 获取 Discord Channel ID

1. 在 Discord 中启用开发者模式
   - 设置 → 高级 → 开发者模式
2. 右键点击你的频道 → 复制频道 ID
3. 更新到 `.env` 文件中的 `DISCORD_CHANNEL_ID`

---

## 🚀 启动方式

### 方式一：独立启动 Discord Bot

```bash
python scripts/start_discord_bot.py
```

### 方式二：集成启动（完整系统）

```bash
python run_all.py
```

---

## 🔄 闭环测试流程

### 步骤 1: 在 Discord 输入分析命令

在配置的 Discord 频道中输入：

```
@AItradingBot analyze 600000.SH
```

或使用其他股票代码：
```
@AItradingBot analyze NVDA
@AItradingBot analyze AAPL
```

### 步骤 2: Bot 抓取并转发

Bot 会自动：
1. 检测到 `@AItradingBot analyze` 命令
2. 提取股票代码（如 `600000.SH`）
3. @提及 Clawdbot 并发送分析请求

**请求格式：**
```
@Clawdbot 请分析以下标的：

**分析请求**
```
{
  "action": "analyze",
  "ticker": "600000.SH",
  "request_id": "600000.SH_1234567890_1704067200",
  "timestamp": "2024-01-01T12:00:00",
  "requested_by": "YourUsername"
}
```
```

### 步骤 3: Clawdbot 处理并返回

Clawdbot 收到请求后，会进行深度分析，返回 JSON 格式的估值数据：

**响应格式示例：**
```json
{
  "ticker": "600000.SH",
  "fair_value_range": {
    "min": 100.50,
    "max": 115.20
  },
  "pe_ratio": 15.5,
  "industry_pe": 18.0,
  "growth_expectation": "high",
  "consensus": 75.0,
  "risk_factors": [
    "宏观经济下行风险",
    "行业监管政策变化"
  ],
  "reasoning": "基于当前财务数据和市场环境...",
  "projected_data": {
    "revenue_growth": 0.12,
    "profit_growth": 0.15
  },
  "key_events": [
    "Q4 财报超预期",
    "新业务线启动"
  ]
}
```

### 步骤 4: Bot 解析并格式化输出

Bot 会自动：
1. 检测来自 Clawdbot 的响应
2. 解析 JSON 数据
3. 格式化为 Markdown 输出

**输出格式：**
```markdown
## 📊 600000.SH 分析报告

**💰 合理估值区间**: `100.50 - 115.20`

**📈 PE 比率**: `15.50` (行业: `18.00`, 🔻 `-13.9%`)

**🚀 增长预期**: `高增长`

**🤝 机构共识**: `75%`
🟢 `██████████████░░░░░░░░`

**⚠️ 风险因素**:
  • 宏观经济下行风险
  • 行业监管政策变化

**🎯 关键事件**:
  • Q4 财报超预期
  • 新业务线启动

**🤔 AI 推理**:
> 基于当前财务数据和市场环境，该股票具有...

---
⚠️ *免责声明：以上分析仅供参考，不构成投资建议。投资有风险，决策需谨慎。*
```

### 步骤 5: 同步到 Showcase 前端

Bot 会通过事件总线推送数据到前端，Showcase 页面会实时显示：

1. **Live Pulse**（左上）：显示分析请求
2. **Global Intel**（左下）：显示 Clawdbot 摘要
3. **Reasoning Lab**（中央）：显示完整分析卡片，包括：
   - 估值区间（带可视化条）
   - PE 比率分析
   - 风险因素列表
   - 关键事件
   - AI 推理逻辑

---

## 🛠️ 故障排查

### 问题 1: Bot 无法启动

**症状：** `❌ 错误: DISCORD_BOT_TOKEN 未正确配置`

**解决：**
- 检查 `.env` 文件中的 `DISCORD_BOT_TOKEN`
- 确保格式正确，以 `MTQ3...` 开头

### 问题 2: Bot 无响应

**可能原因：**
1. Bot 缺少必要的权限
2. Clawdbot ID 配置错误
3. Discord 频道 ID 配置错误

**解决：**
1. 在 Discord Developer Portal 检查 Bot 权限：
   - `Server Members Intent` ✅
   - `Message Content Intent` ✅
   - `Read Messages/View Channels` ✅

2. 确保 Clawdbot User ID 正确：`975399077120466965`

3. 确保 Discord Channel ID 已正确配置

### 问题 3: JSON 解析失败

**症状：** 前端显示 "⚠️ 解析错误 - 研报格式异常"

**解决：**
- 检查 Clawdbot 返回的 JSON 格式是否正确
- 确保包含必需字段：`ticker`, `fair_value_range`
- 查看 Bot 日志获取详细的错误信息

### 问题 4: 前端无数据更新

**检查步骤：**
1. 确认 WebSocket 连接正常（右上角连接状态）
2. 打开浏览器开发者工具，查看 Console 日志
3. 检查是否有 JavaScript 错误
4. 确认 FastAPI 后端正在运行（端口 8000）

---

## 📊 事件流图

```
用户 Discord 输入
    ↓
@AItradingBot analyze <TICKER>
    ↓
Bot 检测命令 → 提取股票代码
    ↓
Bot @提及 Clawdbot → 发送 JSON 请求
    ↓
Clawdbot 分析 → 返回 JSON 响应
    ↓
Bot 解析 JSON → 格式化为 Markdown
    ↓
Bot 回复 Discord → 同时推送事件总线
    ↓
前端接收 WebSocket → 更新 Showcase 页面
    ↓
用户查看分析结果 ✅
```

---

## 🔧 开发模式测试

### 本地测试（模拟 Clawdbot 响应）

在测试环境中，你可以手动发送模拟的 Clawdbot 响应：

```json
{
  "ticker": "TEST.SH",
  "fair_value_range": {
    "min": 100.00,
    "max": 120.00
  },
  "pe_ratio": 15.0,
  "industry_pe": 18.0,
  "growth_expectation": "medium",
  "consensus": 65.0,
  "risk_factors": ["测试风险"],
  "reasoning": "这是一个测试响应",
  "projected_data": {},
  "key_events": ["测试事件"]
}
```

在 Discord 频道中直接粘贴上述 JSON，Bot 会自动检测并处理。

---

## 📝 配置检查清单

在启动前，请确认：

- [ ] `.env` 文件已更新 Discord 凭证
- [ ] `DISCORD_CHANNEL_ID` 已设置为你的频道 ID
- [ ] Discord Bot 已添加到你的服务器
- [ ] Bot 有以下权限：
  - [ ] View Channel
  - [ ] Send Messages
  - [ ] Read Message History
  - [ ] Use Slash Commands
- [ ] Clawdbot ID 正确：`975399077120466965`
- [ ] FastAPI 后端正在运行（端口 8000）
- [ ] 前端 WebSocket 连接正常

---

## 🎯 成功标志

当一切正常工作时，你应该看到：

1. Bot 启动成功，显示 "Discord Bot 已启动"
2. 在 Discord 输入命令后，Bot 回复 "🔍 已将 XXXX 转发给 Clawdbot 分析..."
3. Clawdbot 返回数据后，Bot 自动格式化并发送详细分析报告
4. Showcase 前端实时更新显示 Clawdbot 分析卡片
5. 无 JSON 解析错误

---

## 📞 支持与反馈

如有问题，请检查：
1. Bot 日志：`logs/aitradebot.log`
2. AI 调用日志：`logs/ai_calls.log`
3. 浏览器 Console 输出

---

**祝交易顺利！** 📈💰
