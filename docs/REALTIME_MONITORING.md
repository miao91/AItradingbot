# OpenClaw 实时监测系统

## 概述

OpenClaw 实时监测系统是 AI TradeBot 的实时信息采集和处理引擎，能够：

1. **实时抓取**财经新闻（东方财富公告、财联社电报）
2. **智能初筛**使用轻量级 AI 过滤无价值信息
3. **自动触发**完整分析工作流
4. **实时推送**新事件到网站和 WebSocket 客户端

## 架构

```
┌─────────────────┐
│  LiveMonitor    │  ← 持久化浏览器，定时刷新
│  (playwright)   │
└────────┬────────┘
         │ 新消息
         ▼
┌─────────────────┐
│ RealtimeRouter  │  ← 初筛 + 决策路由
│  (GLM-4)        │
└────────┬────────┘
         │ 通过初筛
         ▼
┌─────────────────┐
│  analyze_event  │  ← 完整工作流
│  (Kimi+智谱)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Database      │  ← 存储到 SQLite
│   + WebSocket   │  ← 推送到网站
└─────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
pip install playwright
playwright install chromium
```

### 2. 启动系统

```bash
python run_all.py
```

系统会自动启动：
- FastAPI 后端 (http://localhost:8000)
- Streamlit 看板 (http://localhost:8501)
- **OpenClaw 实时监测** (后台)

### 3. 测试实时监测

```bash
# 模拟突发新闻
python scripts/simulate_hot_news.py

# 使用自定义新闻
python scripts/simulate_hot_news.py --custom "重大利好！600519.SH签订50亿合同" --ticker "600519.SH"
```

预期输出：
```
============================================================
  AI TradeBot - 实时监测全流程模拟测试
============================================================

[14:30:15.123] 步骤 1: 生成模拟新闻
  标题: 重大利好！600519.SH签订50亿元战略合作协议

[14:30:15.234] 步骤 2: 触发实时路由处理
  ✓ 路由完成，耗时: 3.21秒
  ✓ 事件ID: TEV_20260211_143015

[14:30:16.456] 步骤 3: 验证数据库存储
  ✓ 数据库验证成功，总耗时: 4.32秒

[14:30:17.123] 步骤 4: 验证公共 API 接口
  ✓ API 接口验证成功
  总耗时: 5.89秒

[14:30:17.234] 步骤 5: 测试总结
  总耗时: 5.89秒
  目标: 10秒内完成
  ✓ 性能达标！
```

## 配置

### 信息源配置

编辑 `perception/openclaw/live_monitor.py`:

```python
MONITOR_CONFIG = {
    "sources": [
        {
            "name": "eastmoney_announcement",
            "url": "http://data.eastmoney.com/notices/stock.html",
            "refresh_interval": 30,  # 秒
            "enabled": True
        },
        {
            "name": "cls_telegraph",
            "url": "https://www.cls.cn/telegraph",
            "refresh_interval": 20,
            "enabled": True
        }
    ],
    "browser": {
        "headless": True,  # False = 显示浏览器窗口
    }
}
```

### 初筛配置

编辑 `decision/workflows/realtime_router.py`:

```python
ROUTER_CONFIG = {
    "min_relevance_score": 0.6,  # 最低相关性
    "auto_analyze": True,        # 自动触发分析
    "auto_confirm": False,       # 需要人工确认
}
```

## WebSocket 实时推送

### Python 客户端

```bash
python scripts/test_websocket.py
```

### HTML 客户端

在浏览器中打开 `docs/websocket_client.html`

### JavaScript 客户端

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/events');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'new_event') {
        console.log('新事件:', data.data);
        // 更新你的网站界面
    }
};
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/v1/realtime/stats` | GET | 路由器统计 |
| `/api/v1/realtime/test_news` | POST | 测试新闻处理 |
| `/api/v1/realtime/manual_trigger` | POST | 手动触发分析 |
| `/ws/events` | WebSocket | 实时推送 |

## 监控和日志

### 查看路由器统计

```bash
curl http://localhost:8000/api/v1/realtime/stats
```

响应：
```json
{
  "processed": 150,
  "filtered": 120,
  "analyzed": 30,
  "passed_rate": "20.0%"
}
```

### 日志

日志文件位置：
- `logs/live_monitor.log`
- `logs/realtime_router.log`

## 故障排查

### Playwright 未安装

```bash
pip install playwright
playwright install chromium
```

### 浏览器崩溃

系统会自动重启。如频繁崩溃，可关闭无头模式：
```python
"headless": False
```

### 初筛通过率过高/过低

调整 `min_relevance_score`:
```python
"min_relevance_score": 0.7  # 提高阈值
```

## 性能指标

- **抓取延迟**: 2-5秒（取决于网络）
- **初筛延迟**: 1-2秒（GLM-4 API）
- **完整分析**: 10-20秒（Kimi + 智谱）
- **总延迟**: < 30秒（从抓取到 API 可用）

## 扩展信息源

添加新信息源，编辑 `MONITOR_CONFIG["sources"]`:

```python
{
    "name": "custom_source",
    "url": "https://example.com/news",
    "refresh_interval": 30,
    "selector": ".news-item",
    "enabled": True
}
```

然后在 `live_monitor.py` 中添加对应的解析函数 `_parse_custom_source`。
