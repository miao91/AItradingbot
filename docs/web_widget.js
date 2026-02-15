/**
 * AI TradeBot - 网站集成组件
 *
 * 金融科技风格展示墙 - 黑色背景 + 荧光绿文字
 * 可直接嵌入 www.myrwaai.com 使用
 *
 * 使用方法:
 * 1. 将此代码保存为 ai-tradebot-widget.js
 * 2. 在 HTML 中引入: <script src="ai-tradebot-widget.js"></script>
 * 3. 添加容器: <div id="ai-tradebot-wall"></div>
 * 4. 配置 API_BASE_URL 指向你的服务器
 */

(function() {
    'use strict';

    // ========== 配置 ==========
    const CONFIG = {
        API_BASE_URL: 'http://localhost:8000',  // 修改为你的服务器地址
        AUTO_REFRESH_INTERVAL: 30000,  // 30秒自动刷新
        MAX_EVENTS: 10,  // 最多显示的事件数
        THEME: {
            bg: '#0a0e27',
            cardBg: '#111827',
            primary: '#00ff88',
            secondary: '#00d4ff',
            success: '#00ff88',
            danger: '#ff4757',
            warning: '#ffa502',
            text: '#e0e6ed',
            textMuted: '#94a3b8',
            border: '#1e293b'
        }
    };

    // ========== 样式注入 ==========
    const STYLES = `
        <style>
            .ai-tradebot-wall {
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
                background: ${CONFIG.THEME.bg};
                color: ${CONFIG.THEME.text};
                padding: 20px;
                min-height: 400px;
                box-sizing: border-box;
            }

            .ai-tradebot-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 1px solid ${CONFIG.THEME.border};
            }

            .ai-tradebot-title {
                font-size: 1.5rem;
                font-weight: 700;
                color: ${CONFIG.THEME.primary};
                text-transform: uppercase;
                letter-spacing: 2px;
            }

            .ai-tradebot-title::before {
                content: '▸';
                margin-right: 10px;
            }

            .ai-tradebot-stats {
                display: flex;
                gap: 20px;
                font-size: 0.875rem;
            }

            .ai-tradebot-stat {
                text-align: center;
            }

            .ai-tradebot-stat-label {
                color: ${CONFIG.THEME.textMuted};
                font-size: 0.75rem;
                margin-bottom: 4px;
            }

            .ai-tradebot-stat-value {
                color: ${CONFIG.THEME.primary};
                font-weight: 600;
                font-size: 1.125rem;
            }

            .ai-tradebot-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 15px;
            }

            .ai-tradebot-card {
                background: ${CONFIG.THEME.cardBg};
                border: 1px solid ${CONFIG.THEME.border};
                border-radius: 8px;
                padding: 16px;
                position: relative;
                overflow: hidden;
                transition: all 0.3s ease;
            }

            .ai-tradebot-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                width: 3px;
                height: 100%;
                background: ${CONFIG.THEME.primary};
                opacity: 0.7;
            }

            .ai-tradebot-card:hover {
                border-color: ${CONFIG.THEME.primary};
                box-shadow: 0 0 20px rgba(0, 255, 136, 0.2);
                transform: translateY(-2px);
            }

            .ai-tradebot-card-header {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 12px;
            }

            .ai-tradebot-ticker {
                font-size: 1.25rem;
                font-weight: 700;
                color: ${CONFIG.THEME.text};
                letter-spacing: 1px;
            }

            .ai-tradebot-ticker-name {
                font-size: 0.75rem;
                color: ${CONFIG.THEME.textMuted};
                margin-left: 8px;
                font-weight: 400;
            }

            .ai-tradebot-status {
                font-size: 0.75rem;
                padding: 3px 10px;
                border-radius: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .ai-tradebot-status.observing {
                background: rgba(0, 212, 255, 0.15);
                color: ${CONFIG.THEME.secondary};
                border: 1px solid ${CONFIG.THEME.secondary};
            }

            .ai-tradebot-status.pending_confirm {
                background: rgba(255, 165, 2, 0.15);
                color: ${CONFIG.THEME.warning};
                border: 1px solid ${CONFIG.THEME.warning};
                animation: pulse 2s infinite;
            }

            .ai-tradebot-status.position_open {
                background: rgba(0, 255, 136, 0.15);
                color: ${CONFIG.THEME.success};
                border: 1px solid ${CONFIG.THEME.success};
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }

            .ai-tradebot-summary {
                font-size: 0.875rem;
                color: ${CONFIG.THEME.text};
                line-height: 1.6;
                margin-bottom: 12px;
                padding: 10px;
                background: rgba(0, 255, 136, 0.05);
                border-left: 2px solid ${CONFIG.THEME.primary};
            }

            .ai-tradebot-metrics {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 10px;
                margin-bottom: 12px;
            }

            .ai-tradebot-metric {
                background: rgba(30, 41, 59, 0.5);
                padding: 10px;
                border-radius: 6px;
                border: 1px solid ${CONFIG.THEME.border};
            }

            .ai-tradebot-metric-label {
                font-size: 0.7rem;
                color: ${CONFIG.THEME.textMuted};
                margin-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .ai-tradebot-metric-value {
                font-size: 0.9rem;
                font-weight: 600;
                color: ${CONFIG.THEME.primary};
            }

            .ai-tradebot-metric-value.positive {
                color: ${CONFIG.THEME.success};
            }

            .ai-tradebot-metric-value.negative {
                color: ${CONFIG.THEME.danger};
            }

            .ai-tradebot-exit {
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px solid ${CONFIG.THEME.border};
            }

            .ai-tradebot-exit-title {
                font-size: 0.75rem;
                color: ${CONFIG.THEME.textMuted};
                margin-bottom: 8px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            .ai-tradebot-exit-items {
                display: flex;
                flex-wrap: wrap;
                gap: 15px;
                font-size: 0.8rem;
            }

            .ai-tradebot-exit-item {
                display: flex;
                align-items: center;
                gap: 5px;
            }

            .ai-tradebot-exit-item.target {
                color: ${CONFIG.THEME.success};
            }

            .ai-tradebot-exit-item.stop {
                color: ${CONFIG.THEME.danger};
            }

            .ai-tradebot-exit-item.time {
                color: ${CONFIG.THEME.warning};
            }

            .ai-tradebot-countdown {
                display: inline-flex;
                align-items: center;
                padding: 4px 12px;
                background: rgba(255, 165, 2, 0.1);
                border: 1px solid ${CONFIG.THEME.warning};
                border-radius: 20px;
                font-size: 0.75rem;
                color: ${CONFIG.THEME.warning};
                font-weight: 600;
            }

            .ai-tradebot-countdown::before {
                content: '⏱';
                margin-right: 5px;
            }

            .ai-tradebot-confidence {
                display: inline-flex;
                align-items: center;
                padding: 4px 12px;
                background: rgba(0, 255, 136, 0.1);
                border: 1px solid ${CONFIG.THEME.primary};
                border-radius: 20px;
                font-size: 0.75rem;
                color: ${CONFIG.THEME.primary};
                font-weight: 600;
            }

            .ai-tradebot-footer {
                margin-top: 20px;
                padding-top: 15px;
                border-top: 1px solid ${CONFIG.THEME.border};
                text-align: center;
            }

            .ai-tradebot-loading {
                text-align: center;
                padding: 60px 20px;
                color: ${CONFIG.THEME.textMuted};
            }

            .ai-tradebot-loading::after {
                content: '⏳';
                display: block;
                font-size: 2rem;
                margin-bottom: 15px;
                animation: spin 1s linear infinite;
            }

            .ai-tradebot-error {
                background: rgba(255, 71, 87, 0.1);
                border: 1px solid ${CONFIG.THEME.danger};
                color: ${CONFIG.THEME.danger};
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }

            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }

            /* 响应式 */
            @media (max-width: 768px) {
                .ai-tradebot-grid {
                    grid-template-columns: 1fr;
                }
                .ai-tradebot-stats {
                    flex-wrap: wrap;
                }
            }
        </style>
    `;

    // ========== 工具函数 ==========
    function formatPrice(price) {
        if (price === null || price === undefined) return '-';
        return `¥${price.toFixed(2)}`;
    }

    function formatPercent(value) {
        if (value === null || value === undefined) return '-';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(2)}%`;
    }

    function formatTimeRemaining(days, hours) {
        if (days === null || days === undefined) return '';
        if (days <= 0 && hours <= 0) return '即将失效';
        if (days > 0) return `${days}天${hours}小时`;
        return `${hours}小时`;
    }

    // ========== 渲染函数 ==========
    function renderHeader(data) {
        const stats = data.stats;
        return `
            <div class="ai-tradebot-header">
                <div class="ai-tradebot-title">AI TradeBot 实时动态</div>
                <div class="ai-tradebot-stats">
                    <div class="ai-tradebot-stat">
                        <div class="ai-tradebot-stat-label">总事件</div>
                        <div class="ai-tradebot-stat-value">${stats.total_events || 0}</div>
                    </div>
                    <div class="ai-tradebot-stat">
                        <div class="ai-tradebot-stat-label">观察中</div>
                        <div class="ai-tradebot-stat-value">${stats.observing_count || 0}</div>
                    </div>
                    <div class="ai-tradebot-stat">
                        <div class="ai-tradebot-stat-label">持仓中</div>
                        <div class="ai-tradebot-stat-value">${stats.position_open_count || 0}</div>
                    </div>
                    ${stats.win_rate !== null ? `
                        <div class="ai-tradebot-stat">
                            <div class="ai-tradebot-stat-label">胜率</div>
                            <div class="ai-tradebot-stat-value">${stats.win_rate.toFixed(1)}%</div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    function renderCard(event) {
        const exitPlan = event.exit_plan || {};
        const reasoningCore = event.reasoning_core || {};

        return `
            <div class="ai-tradebot-card">
                <div class="ai-tradebot-card-header">
                    <div>
                        <span class="ai-tradebot-ticker">${event.ticker}</span>
                        ${event.ticker_name ? `<span class="ai-tradebot-ticker-name">${event.ticker_name}</span>` : ''}
                    </div>
                    <span class="ai-tradebot-status ${event.current_status}">${event.status_display}</span>
                </div>

                ${event.event_summary ? `
                    <div class="ai-tradebot-summary">
                        ${event.event_summary}
                    </div>
                ` : ''}

                ${event.confidence ? `
                    <div style="margin-bottom: 12px;">
                        <span class="ai-tradebot-confidence">置信度 ${(event.confidence * 100).toFixed(0)}%</span>
                    </div>
                ` : ''}

                <div class="ai-tradebot-metrics">
                    ${event.entry_price_display ? `
                        <div class="ai-tradebot-metric">
                            <div class="ai-tradebot-metric-label">入场价</div>
                            <div class="ai-tradebot-metric-value">${event.entry_price_display}</div>
                        </div>
                    ` : ''}
                    ${event.target_price ? `
                        <div class="ai-tradebot-metric">
                            <div class="ai-tradebot-metric-label">目标价</div>
                            <div class="ai-tradebot-metric-value positive">¥${event.target_price.toFixed(2)}</div>
                        </div>
                    ` : ''}
                    ${event.stop_loss ? `
                        <div class="ai-tradebot-metric">
                            <div class="ai-tradebot-metric-label">止损价</div>
                            <div class="ai-tradebot-metric-value">¥${event.stop_loss.toFixed(2)}</div>
                        </div>
                    ` : ''}
                    ${exitPlan.target_return_ratio !== null ? `
                        <div class="ai-tradebot-metric">
                            <div class="ai-tradebot-metric-label">目标收益</div>
                            <div class="ai-tradebot-metric-value positive">+${exitPlan.target_return_ratio}%</div>
                        </div>
                    ` : ''}
                    ${event.distance_to_target_pct !== null ? `
                        <div class="ai-tradebot-metric">
                            <div class="ai-tradebot-metric-label">距目标</div>
                            <div class="ai-tradebot-metric-value">${formatPercent(event.distance_to_target_pct)}</div>
                        </div>
                    ` : ''}
                </div>

                ${exitPlan.days_remaining !== null || exitPlan.hours_remaining !== null ? `
                    <div style="margin-bottom: 12px;">
                        <span class="ai-tradebot-countdown">
                            剩余 ${formatTimeRemaining(exitPlan.days_remaining, exitPlan.hours_remaining)}
                        </span>
                    </div>
                ` : ''}

                ${reasoningCore.key_points && reasoningCore.key_points.length > 0 ? `
                    <div style="margin-bottom: 12px;">
                        <div class="ai-tradebot-exit-title">关键要点</div>
                        <ul style="margin: 5px 0; padding-left: 20px; font-size: 0.8rem; color: ${CONFIG.THEME.textMuted};">
                            ${reasoningCore.key_points.slice(0, 3).map(point => `<li>${point}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}

                <div class="ai-tradebot-footer" style="font-size: 0.75rem; color: ${CONFIG.THEME.textMuted}; border: none; padding: 10px 0 0 0; margin: 0;">
                    ${event.created_display}
                </div>
            </div>
        `;
    }

    function renderEvents(events) {
        if (!events || events.length === 0) {
            return `
                <div class="ai-tradebot-loading">
                    暂无活跃交易事件
                </div>
            `;
        }

        return `
            ${events.slice(0, CONFIG.MAX_EVENTS).map(renderCard).join('')}
        `;
    }

    function renderFooter(data) {
        return `
            <div class="ai-tradebot-footer">
                <span style="color: ${CONFIG.THEME.textMuted};">${data.last_updated_display || ''}</span>
                <span style="color: ${CONFIG.THEME.primary}; margin: 0 10px;">|</span>
                <span style="color: ${CONFIG.THEME.textMuted};">Powered by AI TradeBot v1.0</span>
            </div>
        `;
    }

    // ========== 主渲染函数 ==========
    async function render(container) {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}/api/v1/public/active_events`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            container.innerHTML = `
                ${STYLES}
                ${renderHeader(data)}
                <div class="ai-tradebot-grid">
                    ${renderEvents(data.events)}
                </div>
                ${renderFooter(data)}
            `;

        } catch (error) {
            console.error('AI TradeBot Widget Error:', error);
            container.innerHTML = `
                ${STYLES}
                <div class="ai-tradebot-error">
                    加载失败: ${error.message}<br>
                    <small>请检查 API 服务是否正常运行</small>
                </div>
            `;
        }
    }

    // ========== 初始化 ==========
    function init() {
        const container = document.getElementById('ai-tradebot-wall');

        if (!container) {
            console.error('AI TradeBot Widget: Container #ai-tradebot-wall not found');
            return;
        }

        // 初始渲染
        render(container);

        // 自动刷新
        setInterval(() => render(container), CONFIG.AUTO_REFRESH_INTERVAL);
    }

    // ========== 启动 ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
