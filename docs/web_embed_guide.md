# AI TradeBot - 网站集成指南

本指南提供将 AI TradeBot 数据集成到 www.myrwaai.com 网站的完整方案。

## API 基础信息

**API 基础 URL**: `http://your-server-ip:8000` (生产环境请使用 HTTPS)

**主要接口**:
- `GET /api/v1/public/active_events` - 获取活跃交易事件
- `GET /api/v1/public/reasoning/{event_id}` - 获取事件推理详情
- `GET /api/v1/public/dashboard` - 获取仪表板统计数据
- `GET /health` - 健康检查

---

## 方案一：纯 HTML/JavaScript 集成

直接在你的网站页面中嵌入以下代码即可显示 AI 交易动态。

### 完整示例代码

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI TradeBot - 实时交易动态</title>
    <style>
        /* ========== 基础样式 ========== */
        :root {
            --primary-color: #2563eb;
            --success-color: #10b981;
            --danger-color: #ef4444;
            --warning-color: #f59e0b;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border-color: #e2e8f0;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2rem;
            margin: 0 0 10px 0;
            color: var(--primary-color);
        }

        .header p {
            color: var(--text-secondary);
            margin: 0;
        }

        /* ========== 统计卡片 ========== */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: var(--card-bg);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            text-align: center;
        }

        .stat-card .label {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .stat-card .value {
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--text-primary);
        }

        .stat-card.success .value { color: var(--success-color); }
        .stat-card.warning .value { color: var(--warning-color); }
        .stat-card.danger .value { color: var(--danger-color); }

        /* ========== 事件卡片 ========== */
        .events-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }

        .event-card {
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }

        .event-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .event-card .ticker-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }

        .event-card .ticker {
            font-size: 1.25rem;
            font-weight: bold;
            color: var(--text-primary);
        }

        .event-card .ticker-name {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-left: 8px;
        }

        .event-card .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }

        .status-badge.observing { background: #dbeafe; color: #1e40af; }
        .status-badge.pending_confirm { background: #fef3c7; color: #92400e; }
        .status-badge.position_open { background: #e0e7ff; color: #3730a3; }
        .status-badge.take_profit { background: #d1fae5; color: #065f46; }
        .status-badge.stopped_out { background: #fee2e2; color: #991b1b; }

        .event-card .logic-summary {
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 15px;
            line-height: 1.5;
        }

        .event-card .metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }

        .event-card .metric {
            background: var(--bg-color);
            padding: 10px;
            border-radius: 6px;
        }

        .event-card .metric-label {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 4px;
        }

        .event-card .metric-value {
            font-size: 0.875rem;
            font-weight: 500;
        }

        .event-card .exit-plan {
            border-top: 1px solid var(--border-color);
            padding-top: 15px;
            margin-top: 15px;
        }

        .event-card .exit-plan-title {
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }

        .event-card .exit-plan-items {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }

        .event-card .exit-item {
            font-size: 0.875rem;
        }

        .event-card .exit-item span {
            font-weight: 500;
        }

        .event-card .exit-item.target { color: var(--success-color); }
        .event-card .exit-item.stop { color: var(--danger-color); }
        .event-card .exit-item.time { color: var(--warning-color); }

        /* ========== 加载状态 ========== */
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }

        .loading::after {
            content: '⏳';
            display: block;
            font-size: 2rem;
            margin-bottom: 10px;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .error {
            background: #fee2e2;
            color: #991b1b;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }

        .refresh-info {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 20px;
        }

        /* ========== 响应式 ========== */
        @media (max-width: 768px) {
            .events-grid {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <div class="header">
            <h1>🎯 AI TradeBot 实时动态</h1>
            <p>以终为始 - AI 量化交易系统</p>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="label">总事件数</div>
                <div class="value" id="total-events">-</div>
            </div>
            <div class="stat-card warning">
                <div class="label">观察中</div>
                <div class="value" id="observing">-</div>
            </div>
            <div class="stat-card success">
                <div class="label">持仓中</div>
                <div class="value" id="position-open">-</div>
            </div>
            <div class="stat-card">
                <div class="label">胜率</div>
                <div class="value" id="win-rate">-</div>
            </div>
        </div>

        <!-- 事件列表 -->
        <div id="events-container" class="events-grid">
            <div class="loading">加载中...</div>
        </div>

        <!-- 刷新信息 -->
        <div class="refresh-info">
            数据最后更新: <span id="last-update">-</span> | 每 30 秒自动刷新
        </div>
    </div>

    <script>
        // ========== 配置 ==========
        const API_BASE_URL = 'http://localhost:8000';  // 修改为你的服务器地址
        const AUTO_REFRESH_INTERVAL = 30000;  // 30秒

        // ========== 工具函数 ==========
        function formatDate(isoString) {
            if (!isoString) return '-';
            const date = new Date(isoString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        function formatStatus(status) {
            const map = {
                'observing': '观察中',
                'pending_confirm': '待确认',
                'position_open': '持仓中',
                'take_profit': '已止盈',
                'stopped_out': '已止损'
            };
            return map[status] || status;
        }

        function formatDirection(direction) {
            return direction === 'long' ? '做多' : '做空';
        }

        // ========== 渲染函数 ==========
        function renderStats(stats) {
            document.getElementById('total-events').textContent = stats.total_events || 0;
            document.getElementById('observing').textContent = stats.observing_count || 0;
            document.getElementById('position-open').textContent = stats.position_open_count || 0;
            document.getElementById('win-rate').textContent =
                stats.win_rate !== null ? stats.win_rate.toFixed(1) + '%' : '-';
        }

        function renderEvent(event) {
            const exitPlan = event.exit_plan || {};
            const hasEntry = event.actual_entry_price !== null;

            return `
                <div class="event-card" onclick="showEventDetail('${event.id}')">
                    <div class="ticker-header">
                        <div>
                            <span class="ticker">${event.ticker}</span>
                            ${event.ticker_name ? `<span class="ticker-name">${event.ticker_name}</span>` : ''}
                        </div>
                        <span class="status-badge ${event.current_status}">
                            ${formatStatus(event.current_status)}
                        </span>
                    </div>

                    ${event.logic_summary ? `
                        <div class="logic-summary">
                            💡 ${event.logic_summary}
                        </div>
                    ` : ''}

                    <div class="metrics">
                        ${hasEntry ? `
                            <div class="metric">
                                <div class="metric-label">入场价</div>
                                <div class="metric-value">¥${event.actual_entry_price.toFixed(2)}</div>
                            </div>
                        ` : ''}
                        ${event.confidence ? `
                            <div class="metric">
                                <div class="metric-label">置信度</div>
                                <div class="metric-value">${(event.confidence * 100).toFixed(0)}%</div>
                            </div>
                        ` : ''}
                        ${exitPlan.target_return_ratio ? `
                            <div class="metric">
                                <div class="metric-label">目标收益</div>
                                <div class="metric-value success">+${exitPlan.target_return_ratio}%</div>
                            </div>
                        ` : ''}
                    </div>

                    ${exitPlan.take_profit_price || exitPlan.stop_loss_price ? `
                        <div class="exit-plan">
                            <div class="exit-plan-title">🎯 退出计划</div>
                            <div class="exit-plan-items">
                                ${exitPlan.take_profit_price ? `
                                    <div class="exit-item target">
                                        止盈: <span>¥${exitPlan.take_profit_price.toFixed(2)}</span>
                                    </div>
                                ` : ''}
                                ${exitPlan.stop_loss_price ? `
                                    <div class="exit-item stop">
                                        止损: <span>¥${exitPlan.stop_loss_price.toFixed(2)}</span>
                                    </div>
                                ` : ''}
                                ${exitPlan.days_remaining !== null ? `
                                    <div class="exit-item time">
                                        剩余: <span>${exitPlan.days_remaining}天</span>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        }

        function renderEvents(events) {
            const container = document.getElementById('events-container');

            if (!events || events.length === 0) {
                container.innerHTML = '<div class="loading">暂无活跃事件</div>';
                return;
            }

            container.innerHTML = events.map(renderEvent).join('');
        }

        // ========== 数据获取 ==========
        async function fetchData() {
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/public/active_events`);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();

                // 更新统计
                if (data.stats) {
                    renderStats(data.stats);
                }

                // 更新事件列表
                renderEvents(data.events || []);

                // 更新时间
                document.getElementById('last-update').textContent = formatDate(new Date().toISOString());

            } catch (error) {
                console.error('获取数据失败:', error);
                document.getElementById('events-container').innerHTML =
                    `<div class="error">加载失败: ${error.message}<br>请检查 API 服务是否运行</div>`;
            }
        }

        // ========== 事件详情 ==========
        function showEventDetail(eventId) {
            // 可以在这里添加模态框显示详情
            console.log('查看详情:', eventId);
            // 或者跳转到详情页面
            // window.open(`/event-detail.html?id=${eventId}`, '_blank');
        }

        // ========== 初始化 ==========
        // 首次加载
        fetchData();

        // 定时刷新
        setInterval(fetchData, AUTO_REFRESH_INTERVAL);
    </script>
</body>
</html>
```

---

## 方案二：React 组件集成

如果你使用 React，可以直接复制以下组件：

```jsx
import React, { useState, useEffect } from 'react';

const API_BASE_URL = 'http://your-server-ip:8000';

function TradeBotDashboard() {
    const [events, setEvents] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30000); // 30秒刷新
        return () => clearInterval(interval);
    }, []);

    const fetchData = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/v1/public/active_events`);
            const data = await response.json();
            setEvents(data.events || []);
            setStats(data.stats);
            setLoading(false);
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    if (loading) return <div>加载中...</div>;
    if (error) return <div>错误: {error}</div>;

    return (
        <div>
            <h1>🎯 AI TradeBot 实时动态</h1>

            {/* 统计卡片 */}
            {stats && (
                <div style={{ display: 'flex', gap: '20px', marginBottom: '30px' }}>
                    <div>总事件: {stats.total_events}</div>
                    <div>观察中: {stats.observing_count}</div>
                    <div>持仓中: {stats.position_open_count}</div>
                    <div>胜率: {stats.win_rate?.toFixed(1)}%</div>
                </div>
            )}

            {/* 事件列表 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
                {events.map(event => (
                    <div key={event.id} style={{ border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px' }}>
                        <h3>{event.ticker} {event.ticker_name}</h3>
                        <p>{event.logic_summary}</p>
                        {event.exit_plan?.take_profit_price && (
                            <p>止盈目标: ¥{event.exit_plan.take_profit_price.toFixed(2)}</p>
                        )}
                        {event.exit_plan?.stop_loss_price && (
                            <p>止损: ¥{event.exit_plan.stop_loss_price.toFixed(2)}</p>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default TradeBotDashboard;
```

---

## 方案三：WordPress 短代码集成

如果你使用 WordPress，创建一个自定义插件：

```php
<?php
/*
Plugin Name: AI TradeBot Widget
Description: 在 WordPress 中显示 AI TradeBot 数据
Version: 1.0
*/

function ai_tradebot_shortcode($atts) {
    $api_url = 'http://your-server-ip:8000/api/v1/public/active_events';

    $response = wp_remote_get($api_url, array('timeout' => 10));

    if (is_wp_error($response)) {
        return '<p>数据加载失败</p>';
    }

    $data = json_decode(wp_remote_retrieve_body($response), true);

    if (!$data || empty($data['events'])) {
        return '<p>暂无活跃事件</p>';
    }

    $html = '<div class="ai-tradebot-widget">';
    $html .= '<h3>🎯 AI TradeBot 实时动态</h3>';

    foreach ($data['events'] as $event) {
        $html .= sprintf(
            '<div class="trade-event">
                <strong>%s %s</strong>
                <p>%s</p>
                <p>目标: ¥%s | 止损: ¥%s</p>
            </div>',
            esc_html($event['ticker']),
            esc_html($event['ticker_name'] ?? ''),
            esc_html($event['logic_summary'] ?? ''),
            esc_html($event['exit_plan']['take_profit_price'] ?? 'N/A'),
            esc_html($event['exit_plan']['stop_loss_price'] ?? 'N/A')
        );
    }

    $html .= '</div>';
    return $html;
}
add_shortcode('ai_tradebot', 'ai_tradebot_shortcode');
```

使用方式：在 WordPress 页面/文章中插入 `[ai_tradebot]`

---

## 部署建议

### 1. 本地开发

```bash
# 启动 API 服务
python run_all.py
```

### 2. 生产部署

#### 选项 A: 云服务器部署

1. 购买云服务器（阿里云/腾讯云/AWS）
2. 安装 Python 环境
3. 部署代码
4. 使用 Gunicorn + Nginx 部署

```bash
# 安装依赖
pip install gunicorn

# 启动服务
gunicorn core.api.app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Nginx 配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 选项 B: Docker 部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "core.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 选项 C: Serverless 部署

使用 Vercel/Serverless Framework 部署 FastAPI

---

## 安全配置

### 1. 启用 HTTPS

生产环境务必使用 HTTPS，修改 `core/api/app.py` 中的 CORS 配置：

```python
allowed_origins = [
    "https://www.myrwaai.com",
    "https://myrwaai.com",
]
```

### 2. API 密钥（可选）

如果需要限制访问，可以在 API 中添加简单密钥验证：

```python
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "your-secret-key":
        raise HTTPException(status_code=403, detail="Invalid API Key")

@app.get("/api/v1/public/active_events", dependencies=[Depends(verify_api_key)])
async def get_active_events():
    ...
```

前端请求时添加 header：

```javascript
fetch(`${API_BASE_URL}/api/v1/public/active_events`, {
    headers: {
        'X-API-Key': 'your-secret-key'
    }
})
```

---

## 故障排查

### 问题 1: CORS 错误

确保 API 服务器正在运行，并且 CORS 配置包含你的域名。

### 问题 2: 数据不更新

检查浏览器控制台是否有错误，确认 API 请求是否成功。

### 问题 3: 样式错乱

确保完整复制 CSS 样式，或者根据你的网站主题进行调整。

---

## 联系支持

如有问题，请查看 API 文档：`http://your-server:8000/docs`
