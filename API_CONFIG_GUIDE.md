# AI TradeBot - API 配置清单

## 📋 需要配置的 API 密钥

### 🔴 必需 (AI 决策核心)

| API | 用途 | 环境变量 | 当前状态 | 获取方式 |
|-----|------|----------|----------|----------|
| **Kimi (Moonshot AI)** | 长文本处理、公告清洗 | `KIMI_API_KEY` | ❌ 占位符 | https://platform.moonshot.cn/ |
| **智谱 GLM-4** | 逻辑推演、退出策略 | `ZHIPU_API_KEY` | ❌ 占位符 | https://open.bigmodel.cn/ |
| **MiniMax** | 结构化指令生成 | `MINIMAX_API_KEY` | ❌ 占位符 | https://api.minimax.chat/ |
| **MiniMax Group ID** | MiniMax 分组ID | `MINIMAX_GROUP_ID` | ❌ 占位符 | 注册后获得 |
| **Tavily** | 实时搜索、背景信息 | `TAVILY_API_KEY` | ❌ 占位符 | https://tavily.com/ |

### 🟡 重要 (数据源)

| API | 用途 | 环境变量 | 当前状态 | 获取方式 |
|-----|------|----------|----------|----------|
| **Tushare Pro** | 历史行情、基本面数据 | `TUSHARE_TOKEN` | ❌ 占位符 | https://tushare.pro/ |

### 🟢 可选

| API | 用途 | 说明 |
|-----|------|------|
| **AkShare** | 实时行情 | ✅ 免费使用，无需密钥 |
| **QMT/xtquant** | 实盘交易 | 模拟模式不需要 |
| **Redis** | 分布式缓存 | 开发环境不需要 |

---

## 🔑 获取 API 密钥指南

### 1. Kimi (Moonshot AI)

**注册地址**: https://platform.moonshot.cn/

**步骤**:
1. 注册/登录账号
2. 进入控制台
3. 创建 API Key
4. 复制密钥

**免费额度**:
- 新用户有免费额度
- 适合测试和开发

**费用参考**:
- moonshot-v1-128k: ¥12/1M tokens

---

### 2. 智谱 GLM-4

**注册地址**: https://open.bigmodel.cn/

**步骤**:
1. 注册/登录账号
2. 实名认证（需要身份证）
3. 进入 API Keys 页面
4. 生成新的 API Key

**免费额度**:
- 新用户赠送 25 元额度
- GLM-4: ¥0.1/1K tokens

**费用参考**:
- glm-4: ¥0.1/1K tokens
- glm-4-air: ¥0.001/1K tokens (更便宜)

---

### 3. MiniMax

**注册地址**: https://api.minimax.chat/

**步骤**:
1. 注册/登录账号
2. 创建应用获取 Group ID
3. 生成 API Key

**免费额度**:
- 新用户有免费调用额度

**费用参考**:
- abab6.5s-chat: ¥0.015/1K tokens

---

### 4. Tavily

**注册地址**: https://tavily.com/

**步骤**:
1. 注册账号（邮箱或Google登录）
2. 进入 API Keys 页面
3. 创建新的 API Key

**免费额度**:
- 免费计划: 1,000次/月
- 适合开发测试

**费用参考**:
- Developer: $20/月 (15,000次)

---

### 5. Tushare Pro

**注册地址**: https://tushare.pro/

**步骤**:
1. 注册账号
2. 实名认证（需要身份证）
3. 获取积分（每日签到或分享文章）
4. 兑换 Token

**免费额度**:
- 普通用户: 120积分/天
- 可用接口有限，但够用

**费用参考**:
- VIP用户: ¥2000/年

---

## ⚙️ 配置步骤

### 方式1: 手动填写 .env 文件

1. 打开 `.env` 文件
2. 替换以下占位符：

```bash
# 替换这些值
KIMI_API_KEY="你的Kimi密钥"
ZHIPU_API_KEY="你的智谱密钥"
MINIMAX_API_KEY="你的MiniMax密钥"
MINIMAX_GROUP_ID="你的GroupID"
TAVILY_API_KEY="你的Tavily密钥"
TUSHARE_TOKEN="你的Tushare Token"
```

### 方式2: 使用脚本配置

运行以下脚本，系统会提示你输入API密钥：

```bash
python scripts/setup_env.py
```

---

## 🧪 验证配置

配置完成后，运行测试脚本验证：

```bash
# 测试AI连接
python scripts/test_decision.py

# 测试完整流程
python scripts/simulate_hot_news.py
```

---

## 💡 最低成本运行方案

如果预算有限，可以按以下优先级配置：

### 第一优先级（必需）
1. **智谱 GLM-4** - 核心决策逻辑
   - 费用: ¥0.1/1K tokens
   - 每月约: ¥10-50

2. **Tushare Pro** - 数据源
   - 费用: 免费（120积分/天）

### 第二优先级（推荐）
3. **Tavily** - 实时搜索
   - 费用: 免费（1,000次/月）

4. **MiniMax** - 结构化输出
   - 费用: ¥0.015/1K tokens
   - 每月约: ¥5-20

### 第三优先级（可选）
5. **Kimi** - 长文本处理
   - 费用: ¥12/1M tokens
   - 每月约: ¥5-30

---

## 📊 成本估算

**轻度使用**（每月100次分析）:
- 智谱 GLM-4: ¥10
- MiniMax: ¥5
- Tavily: 免费
- Kimi: ¥5
- Tushare: 免费
- **总计: 约 ¥20/月**

**中度使用**（每月500次分析）:
- **总计: 约 ¥80-120/月**

**重度使用**（每月2000次分析）:
- **总计: 约 ¥300-500/月**

---

## ⚠️ 注意事项

1. **密钥安全**
   - 不要将 `.env` 文件提交到 Git
   - 定期轮换 API 密钥
   - 设置每月消费限额

2. **API 限流**
   - 注意各平台的 QPS 限制
   - 实现请求队列和重试机制

3. **成本控制**
   - 开发时使用较小的模型（如 glm-4-air）
   - 设置告警阈值
   - 定期检查用量统计

---

## 🆘 常见问题

### Q: 是否可以只用一个AI模型？

A: 可以，但会降低决策质量。建议至少配置智谱GLM-4。

### Q: 免费额度够用吗？

A: 开发测试够用，生产环境建议付费。

### Q: 如何降低成本？

A:
1. 使用更便宜的模型（glm-4-air）
2. 减少不必要的API调用
3. 增加缓存命中率

### Q: API调用失败会怎样？

A: 系统有降级机制，会使用默认值继续运行。

---

**准备好API密钥后，请告诉我，我会帮你更新配置文件！**
