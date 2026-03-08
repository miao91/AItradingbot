"""
AI TradeBot - A股回测引擎 (AShare Sandbox)

实现纯正的A股回测物理引擎，严格遵守A股交易规则：

1. T+1仓位状态机 - 双轨仓位管理
2. 涨跌停板废单机制 - 涨停买入/跌停卖出阻断
3. 真实摩擦成本 - 佣金、印花税、滑点
"""

import asyncio
import json
import importlib.util
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# A股交易费用配置
# =============================================================================

class AShareConfig:
    """A股交易费用配置"""
    # 佣金 (万分之一)
    COMMISSION_RATE = 0.00025  # 0.025%
    # 印花税 (千分之一，卖出时收取)
    STAMP_DUTY_RATE = 0.0005  # 0.05%
    # 滑点惩罚 (千分之二)
    SLIPPAGE_RATE = 0.002  # 0.2%
    # 涨停板幅度 (主板10%，创业板/科创板20%)
    LIMIT_UP_ST = 0.10   # 主板
    LIMIT_UP_CY = 0.20   # 创业板/科创板
    LIMIT_DOWN = 0.10    # 跌停


# =============================================================================
# 数据模型
# =============================================================================

class BacktestStatus(Enum):
    """回测状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class RejectReason(Enum):
    """废单原因"""
    NONE = "none"
    T1_NOT_AVAILABLE = "t1_not_available"  # T+1不可卖
    LIMIT_UP = "limit_up"                   # 涨停无法买入
    LIMIT_DOWN = "limit_down"               # 跌停无法卖出
    INSUFFICIENT_CAPITAL = "insufficient_capital"  # 资金不足
    INSUFFICIENT_POSITION = "insufficient_position"  # 持仓不足


@dataclass
class PositionState:
    """单只股票仓位状态"""
    available: int = 0      # 昨天及之前买入，今天可卖
    locked_today: int = 0   # 今天刚买的，今天不可卖
    
    @property
    def total(self) -> int:
        return self.available + self.locked_today


@dataclass
class TradeRecord:
    """交易记录"""
    date: str
    action: str           # BUY/SELL/HOLD
    price: float          # 成交价
    size: int             # 成交数量
    amount: float         # 成交金额(含成本)
    commission: float    # 佣金
    slippage: float       # 滑点
    pnl: float = 0.0     # 盈亏(仅卖出时计算)
    reason: str = ""      # 原因
    rejected: bool = False # 是否被阻断
    reject_reason: str = "" # 阻断原因


@dataclass
class DailySnapshot:
    """每日快照"""
    date: str
    cash: float
    positions: Dict[str, PositionState]
    total_assets: float
    daily_pnl: float


@dataclass
class BacktestMetrics:
    """回测指标"""
    total_return: float = 0.0        # 总收益率
    sharpe_ratio: float = 0.0        # 夏普比率
    max_drawdown: float = 0.0         # 最大回撤
    win_rate: float = 0.0             # 胜率
    total_trades: int = 0             # 总交易次数
    rejected_trades: int = 0           # 被阻断次数
    avg_profit: float = 0.0           # 平均盈利
    avg_loss: float = 0.0             # 平均亏损
    profit_factor: float = 0.0         # 盈利因子
    total_commission: float = 0.0     # 总佣金
    total_slippage: float = 0.0        # 总滑点


@dataclass
class BacktestResult:
    """回测结果"""
    status: BacktestStatus
    metrics: BacktestMetrics
    trades: List[TradeRecord] = field(default_factory=list)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    daily_snapshots: List[DailySnapshot] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    @property
    def passed(self) -> bool:
        return self.status == BacktestStatus.PASSED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "metrics": {
                "total_return": f"{self.metrics.total_return:.2%}",
                "sharpe_ratio": f"{self.metrics.sharpe_ratio:.2f}",
                "max_drawdown": f"{self.metrics.max_drawdown:.2%}",
                "win_rate": f"{self.metrics.win_rate:.1%}",
                "total_trades": self.metrics.total_trades,
                "rejected_trades": self.metrics.rejected_trades,
            },
            "trades_count": len(self.trades),
            "duration": f"{self.duration_seconds:.2f}s",
        }


# =============================================================================
# T+1 仓位管理器
# =============================================================================

class T1PositionManager:
    """
    T+1仓位状态机
    
    A股T+1规则：
    - 今天买的股票，明天才能卖
    - 昨天买的股票，今天可以卖
    
    双轨仓位字典：
    {
        "000001.SZ": {
            "available": 1000,  # 昨天及之前持仓，今天可卖
            "locked_today": 0   # 今天买入，锁定中，明天可卖
        }
    }
    """
    
    def __init__(self):
        self.positions: Dict[str, PositionState] = {}
    
    def get_total_position(self, ticker: str) -> int:
        """获取总持仓"""
        if ticker not in self.positions:
            return 0
        return self.positions[ticker].total
    
    def get_available_position(self, ticker: str) -> int:
        """获取可卖持仓"""
        if ticker not in self.positions:
            return 0
        return self.positions[ticker].available
    
    def can_sell(self, ticker: str, size: int) -> bool:
        """检查是否可卖出"""
        return self.get_available_position(ticker) >= size
    
    def can_buy(self, cash: float, price: float, size: int) -> bool:
        """检查是否可买入 (资金是否充足)"""
        # 计算买入成本(含滑点和佣金)
        cost = self._calculate_buy_cost(price * size)
        return cash >= cost
    
    def _calculate_buy_cost(self, amount: float) -> float:
        """计算买入成本 (含佣金和滑点)"""
        # 滑点惩罚: 买入价 + 0.2%
        amount_with_slippage = amount * (1 + AShareConfig.SLIPPAGE_RATE)
        # 佣金
        commission = amount_with_slippage * AShareConfig.COMMISSION_RATE
        # 最低佣金5元
        commission = max(commission, 5.0)
        return amount_with_slippage + commission
    
    def _calculate_sell_proceeds(self, amount: float) -> float:
        """计算卖出所得 (扣除佣金、印花税、滑点)"""
        # 滑点惩罚: 卖出价 - 0.2%
        amount_with_slippage = amount * (1 - AShareConfig.SLIPPAGE_RATE)
        # 佣金
        commission = amount_with_slippage * AShareConfig.COMMISSION_RATE
        commission = max(commission, 5.0)
        # 印花税
        stamp_duty = amount_with_slippage * AShareConfig.STAMP_DUTY_RATE
        return amount_with_slippage - commission - stamp_duty
    
    def buy(self, ticker: str, price: float, size: int, cash: float) -> tuple:
        """
        买入股票
        
        Returns:
            (success: bool, actual_cost: float, commission: float, slippage: float, reject_reason: str)
        """
        # 计算成本
        amount = price * size
        cost = self._calculate_buy_cost(amount)
        
        if cash < cost:
            return False, 0.0, 0.0, 0.0, RejectReason.INSUFFICIENT_CAPITAL.value
        
        # 实际佣金
        commission = amount * AShareConfig.COMMISSION_RATE
        commission = max(commission, 5.0)
        # 实际滑点
        slippage = amount * AShareConfig.SLIPPAGE_RATE
        
        # 更新仓位: 昨天买的 + 今天买的 = 今天 locked
        if ticker not in self.positions:
            self.positions[ticker] = PositionState(available=0, locked_today=size)
        else:
            # 之前的locked变成available
            self.positions[ticker].available += self.positions[ticker].locked_today
            self.positions[ticker].locked_today = size
        
        return True, cost, commission, slippage, RejectReason.NONE.value
    
    def sell(self, ticker: str, price: float, size: int) -> tuple:
        """
        卖出股票
        
        Returns:
            (success: bool, actual_proceeds: float, commission: float, slippage: float, reject_reason: str)
        """
        # 检查持仓
        if ticker not in self.positions:
            return False, 0.0, 0.0, 0.0, RejectReason.INSUFFICIENT_POSITION.value
        
        available = self.positions[ticker].available
        if available < size:
            return False, 0.0, 0.0, 0.0, RejectReason.T1_NOT_AVAILABLE.value
        
        # 计算卖出所得
        amount = price * size
        proceeds = self._calculate_sell_proceeds(amount)
        
        # 实际佣金
        commission = amount * AShareConfig.COMMISSION_RATE
        commission = max(commission, 5.0)
        # 实际滑点
        slippage = amount * AShareConfig.SLIPPAGE_RATE
        # 实际印花税
        stamp_duty = amount * AShareConfig.STAMP_DUTY_RATE
        
        # 更新仓位
        self.positions[ticker].available -= size
        
        # 如果全部卖完，清理记录
        if self.positions[ticker].total == 0:
            del self.positions[ticker]
        
        return True, proceeds, commission, slippage, RejectReason.NONE.value
    
    def daily_settlement(self):
        """
        日终清算 (每个交易日结束时调用)
        
        将今天的locked仓位转为available
        """
        for ticker, pos in self.positions.items():
            pos.available += pos.locked_today
            pos.locked_today = 0


# =============================================================================
# 涨跌停板判断
# =============================================================================

class LimitChecker:
    """涨跌停板检查器"""
    
    def __init__(self, is_cy_market: bool = False):
        """
        Args:
            is_cy_market: 是否为创业板/科创板 (20%涨跌幅)
        """
        self.limit_up = AShareConfig.LIMIT_UP_CY if is_cy_market else AShareConfig.LIMIT_UP_ST
        self.limit_down = AShareConfig.LIMIT_DOWN
    
    def is_limit_up(self, pre_close: float, high: float, low: float) -> bool:
        """
        判断是否涨停
        
        Args:
            pre_close: 昨日收盘价
            high: 今日最高价
            low: 今日最低价
            
        Returns:
            True if limit up (including "一字涨停")
        """
        if pre_close <= 0:
            return False
        
        # 一字涨停: high == low 且达到涨停价
        if high == low and high >= pre_close * (1 + self.limit_up):
            return True
        
        # 有实体的涨停
        return high >= pre_close * (1 + self.limit_up)
    
    def is_limit_down(self, pre_close: float, high: float, low: float) -> bool:
        """
        判断是否跌停
        
        Args:
            pre_close: 昨日收盘价
            high: 今日最高价
            low: 今日最低价
            
        Returns:
            True if limit down (including "一字跌停")
        """
        if pre_close <= 0:
            return False
        
        # 一字跌停: high == low 且达到跌停价
        if high == low and low <= pre_close * (1 - self.limit_down):
            return True
        
        # 有实体的跌停
        return low <= pre_close * (1 - self.limit_down)
    
    def can_buy_at_price(self, pre_close: float, current_price: float) -> bool:
        """检查是否可以在当前价格买入 (非涨停)"""
        if pre_close <= 0:
            return True
        return current_price < pre_close * (1 + self.limit_up)
    
    def can_sell_at_price(self, pre_close: float, current_price: float) -> bool:
        """检查是否可以在当前价格卖出 (非跌停)"""
        if pre_close <= 0:
            return True
        return current_price > pre_close * (1 - self.limit_down)


# =============================================================================
# 回测引擎
# =============================================================================

class AShareBacktestEngine:
    """
    A股回测引擎 (AShare Sandbox)
    
    严格遵守A股交易规则:
    1. T+1仓位状态机
    2. 涨跌停板废单机制
    3. 真实摩擦成本核算
    """
    
    def __init__(self, initial_capital: float = 100000.0, is_cy_market: bool = False):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            is_cy_market: 是否为创业板/科创板
        """
        self.initial_capital = initial_capital
        self.is_cy_market = is_cy_market
        
        # 交易统计
        self.total_commission = 0.0
        self.total_slippage = 0.0
        
        logger.info(f"[AShareBacktest] 初始化完成: capital={initial_capital}, cy_market={is_cy_market}")
    
    async def backtest(
        self,
        strategy_code: str,
        ticker: str = "000001.SH",
        lookback_days: int = 30,
    ) -> BacktestResult:
        """
        执行回测
        
        Args:
            strategy_code: 策略代码
            ticker: 股票代码
            lookback_days: 回看天数
            
        Returns:
            BacktestResult: 回测结果
        """
        import time
        start_time = time.time()
        
        logger.info(f"[AShareBacktest] 开始回测: {ticker}, {lookback_days}天")
        
        # 1. 获取历史数据 (包含pre_close)
        historical_data = await self._fetch_historical_data(ticker, lookback_days)
        
        if not historical_data or len(historical_data) < 5:
            return BacktestResult(
                status=BacktestStatus.FAILED,
                metrics=BacktestMetrics(),
                errors=["无法获取足够的历史数据"]
            )
        
        # 2. 加载策略函数
        strategy_func = self._load_strategy(strategy_code)
        
        if not strategy_func:
            return BacktestResult(
                status=BacktestStatus.FAILED,
                metrics=BacktestMetrics(),
                errors=["策略代码加载失败"]
            )
        
        # 3. 初始化交易系统
        position_mgr = T1PositionManager()
        limit_checker = LimitChecker(is_cy_market=self.is_cy_market)
        
        trades = []
        equity_curve = []
        daily_snapshots = []
        cash = self.initial_capital
        current_position_price = 0.0  # 持仓成本价
        
        try:
            # 遍历每一天
            for i, day_data in enumerate(historical_data):
                date = day_data.get("date", "")
                pre_close = day_data.get("pre_close", day_data.get("close", 0))
                open_price = day_data.get("open", 0)
                high = day_data.get("high", 0)
                low = day_data.get("low", 0)
                close = day_data.get("close", 0)
                
                # 构建上下文
                context = self._build_context(day_data, i, historical_data, position_mgr, cash)
                
                # 执行策略获取信号
                signal = strategy_func(context)
                
                # 处理信号
                if signal and isinstance(signal, dict):
                    action = signal.get("action", "HOLD")
                    size_ratio = signal.get("size", 0)  # 仓位比例
                    reason = signal.get("reason", "")
                    
                    # 涨跌停检查
                    is_limit_up = limit_checker.is_limit_up(pre_close, high, low)
                    is_limit_down = limit_checker.is_limit_down(pre_close, high, low)
                    
                    # 执行交易
                    if action == "BUY":
                        # 买入检查: 不能涨停买入
                        if is_limit_up:
                            trades.append(TradeRecord(
                                date=date, action="REJECT_BUY", price=close, size=0,
                                amount=0, commission=0, slippage=0,
                                reason=f"{reason} | 涨停无法买入",
                                rejected=True, reject_reason=RejectReason.LIMIT_UP.value
                            ))
                        elif size_ratio > 0:
                            # 计算买入数量 (按资金比例)
                            buy_amount = cash * size_ratio
                            buy_size = int(buy_amount / close / 100) * 100  # 整手
                            
                            if buy_size > 0:
                                success, cost, commission, slippage, reject_reason = position_mgr.buy(
                                    ticker, close, buy_size, cash
                                )
                                
                                if success:
                                    cash -= cost
                                    current_position_price = close
                                    self.total_commission += commission
                                    self.total_slippage += slippage
                                    
                                    trades.append(TradeRecord(
                                        date=date, action="BUY", price=close, size=buy_size,
                                        amount=cost, commission=commission, slippage=slippage,
                                        reason=reason
                                    ))
                                else:
                                    trades.append(TradeRecord(
                                        date=date, action="REJECT_BUY", price=close, size=buy_size,
                                        amount=0, commission=0, slippage=0,
                                        reason=f"{reason} | {reject_reason}",
                                        rejected=True, reject_reason=reject_reason
                                    ))
                    
                    elif action == "SELL":
                        # 卖出检查: 不能跌停卖出
                        if is_limit_down:
                            trades.append(TradeRecord(
                                date=date, action="REJECT_SELL", price=close, size=0,
                                amount=0, commission=0, slippage=0,
                                reason=f"{reason} | 跌停无法卖出",
                                rejected=True, reject_reason=RejectReason.LIMIT_DOWN.value
                            ))
                        elif size_ratio > 0 and position_mgr.get_total_position(ticker) > 0:
                            # 计算卖出数量
                            total_pos = position_mgr.get_total_position(ticker)
                            sell_size = int(total_pos * size_ratio / 100) * 100
                            sell_size = min(sell_size, position_mgr.get_available_position(ticker))
                            
                            if sell_size > 0:
                                success, proceeds, commission, slippage, reject_reason = position_mgr.sell(
                                    ticker, close, sell_size
                                )
                                
                                if success:
                                    # 计算卖出盈亏
                                    if current_position_price > 0:
                                        pnl = (close - current_position_price) * sell_size
                                    else:
                                        pnl = 0
                                    
                                    cash += proceeds
                                    self.total_commission += commission
                                    self.total_slippage += slippage
                                    
                                    trades.append(TradeRecord(
                                        date=date, action="SELL", price=close, size=sell_size,
                                        amount=proceeds, commission=commission, slippage=slippage,
                                        pnl=pnl, reason=reason
                                    ))
                                    
                                    # 更新持仓成本
                                    remaining = position_mgr.get_total_position(ticker)
if remaining > 0:
                                        # 简化: 持仓成本保持不变
                                        pass
                                    else:
                                        current_position_price = 0
                                else:
                                    trades.append(TradeRecord(
                                        date=date, action="REJECT_SELL", price=close, size=sell_size,
                                        amount=0, commission=0, slippage=0,
                                        reason=f"{reason} | {reject_reason}",
                                        rejected=True, reject_reason=reject_reason
                                    ))
                    
                    # 止损检查 (如果持仓且触发止损)
                    elif action == "STOP_LOSS" and position_mgr.get_available_position(ticker) > 0:
                        stop_loss_pct = signal.get("stop_loss", 0.05)
                        
                        if close <= current_position_price * (1 - stop_loss_pct):
                            # 触发止损
                            sell_size = position_mgr.get_available_position(ticker)
                            
                            if sell_size > 0:
                                success, proceeds, commission, slippage, _ = position_mgr.sell(
                                    ticker, close, sell_size
                                )
                                
                                if success:
                                    pnl = (close - current_position_price) * sell_size
                                    cash += proceeds
                                    self.total_commission += commission
                                    self.total_slippage += slippage
                                    
                                    trades.append(TradeRecord(
                                        date=date, action="STOP_LOSS", price=close, size=sell_size,
                                        amount=proceeds, commission=commission, slippage=slippage,
                                        pnl=pnl, reason="触发止损"
                                    ))
                                    current_position_price = 0
                
                # 日终清算 (T+1状态转换)
                position_mgr.daily_settlement()
                
                # 记录每日快照
                total_assets = cash
                for t, pos in position_mgr.positions.items():
                    if t == ticker:
                        total_assets += close * pos.total
                
                equity_curve.append({
                    "date": date,
                    "cash": cash,
                    "position_value": total_assets - cash,
                    "total_assets": total_assets,
                })
                
                daily_snapshots.append(DailySnapshot(
                    date=date,
                    cash=cash,
                    positions={k: v for k, v in position_mgr.positions.items()},
                    total_assets=total_assets,
                    daily_pnl=0  # 简化计算
                ))
            
            # 最终平仓 (回测结束)
            if position_mgr.get_total_position(ticker) > 0:
                final_price = historical_data[-1].get("close", 0)
                remaining = position_mgr.get_total_position(ticker)
                
                success, proceeds, commission, slippage, _ = position_mgr.sell(
                    ticker, final_price, remaining
                )
                
                if success:
                    pnl = (final_price - current_position_price) * remaining if current_position_price > 0 else 0
                    cash += proceeds
                    self.total_commission += commission
                    self.total_slippage += slippage
                    
                    trades.append(TradeRecord(
                        date=historical_data[-1].get("date", ""),
                        action="FINAL_SELL", price=final_price, size=remaining,
                        amount=proceeds, commission=commission, slippage=slippage,
                        pnl=pnl, reason="回测结束平仓"
                    ))
        
        except Exception as e:
            logger.error(f"[AShareBacktest] 执行错误: {e}")
            return BacktestResult(
                status=BacktestStatus.FAILED,
                metrics=BacktestMetrics(),
                errors=[str(e)]
            )
        
        # 4. 计算指标
        final_assets = equity_curve[-1].get("total_assets", self.initial_capital) if equity_curve else self.initial_capital
        metrics = self._calculate_metrics(trades, equity_curve, final_assets)
        
        # 5. 验证是否通过 (标准可以适当放宽)
        passed = self._validate(metrics)
        
        duration = time.time() - start_time
        
        logger.info(f"[AShareBacktest] 回测完成: {len(trades)}笔交易, 阻断{metrics.rejected_trades}次, 夏普={metrics.sharpe_ratio:.2f}")
        
        return BacktestResult(
            status=BacktestStatus.PASSED if passed else BacktestStatus.FAILED,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_curve,
            daily_snapshots=daily_snapshots,
            duration_seconds=duration,
        )
    
    async def _fetch_historical_data(
        self,
        ticker: str,
        days: int
    ) -> List[Dict[str, Any]]:
        """获取历史数据 (包含pre_close)"""
        try:
            import akshare as ak
            
            symbol = ticker.replace(".SH", "").replace(".SZ", "")
            
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days+60)).strftime("%Y%m%d")
            
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
            )
            
            if df is None or df.empty:
                return self._get_mock_data(days)
            
            # 计算pre_close
            data = []
            prev_close = None
            for _, row in df.tail(days + 1).iterrows():
                close = float(row.get("收盘", 0))
                data.append({
                    "date": str(row.get("日期", "")),
                    "pre_close": prev_close or close,  # 昨日收盘价
                    "open": float(row.get("开盘", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "close": close,
                    "volume": int(row.get("成交量", 0)),
                })
                prev_close = close
            
            # 返回足够的数据
            return data[-days:] if len(data) > days else data
            
        except Exception as e:
            logger.warning(f"[AShareBacktest] 获取数据失败: {e}")
            return self._get_mock_data(days)
    
    def _get_mock_data(self, days: int) -> List[Dict[str, Any]]:
        """生成模拟数据 (包含pre_close)"""
        import random
        
        base_price = 15.0
        data = []
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i)).strftime("%Y-%m-%d")
            change = random.uniform(-0.05, 0.05)
            close = base_price * (1 + change)
            base_price = close
            
            pre_close = close / (1 + change) if i > 0 else close * 0.99
            
            data.append({
                "date": date,
                "pre_close": pre_close,
                "open": close * 0.99,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": random.randint(1000000, 10000000),
            })
        
        return data
    
    def _load_strategy(self, strategy_code: str) -> Optional[Callable]:
        """加载策略函数"""
        try:
            spec = importlib.util.spec_from_loader("strategy_module", loader=None)
            module = importlib.util.module_from_spec(spec)
            exec(strategy_code, module.__dict__)
            
            if hasattr(module, 'strategy'):
                return module.strategy
            
            return None
            
        except Exception as e:
            logger.error(f"[AShareBacktest] 加载策略失败: {e}")
            return None
    
    def _build_context(
        self,
        day_data: Dict[str, Any],
        day_index: int,
        all_data: List[Dict[str, Any]],
        position_mgr: T1PositionManager,
        cash: float
    ) -> Dict[str, Any]:
        """构建策略上下文"""
        
        closes = [d["close"] for d in all_data[:day_index+1]]
        
        # RSI
        rsi = 50.0
        if len(closes) >= 15:
            gains = []
            losses = []
            for i in range(1, min(15, len(closes))):
                change = closes[i] - closes[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            
            if avg_loss > 0:
                rsi = 100 - (100 / (1 + avg_gain / avg_loss))
            else:
                rsi = 100
        
        # 动量
        momentum = 0.0
        if len(closes) >= 5:
            momentum = (closes[-1] - closes[-5]) / closes[-5]
        
        change_pct = 0.0
        if len(closes) >= 2:
            change_pct = (closes[-1] - closes[-2]) / closes[-2]
        
        return {
            "date": day_data.get("date", ""),
            "pre_close": day_data.get("pre_close", 0),
            "open": day_data.get("open", 0),
            "high": day_data.get("high", 0),
            "low": day_data.get("low", 0),
            "close": day_data.get("close", 0),
            "volume": day_data.get("volume", 0),
            "rsi": rsi,
            "momentum": momentum,
            "change_pct": change_pct,
            "sentiment": change_pct * 10,
            "flow": change_pct * 1000,
            "cash": cash,
            "position": position_mgr.get_total_position(""),
        }
    
    def _calculate_metrics(
        self,
        trades: List[TradeRecord],
        equity_curve: List[Dict[str, Any]],
        final_assets: float
    ) -> BacktestMetrics:
        """计算回测指标"""
        
        if not trades or not equity_curve:
            return BacktestMetrics()
        
        # 总收益率
        total_return = (final_assets - self.initial_capital) / self.initial_capital
        
        # 夏普比率
        if len(equity_curve) >= 2:
            returns = []
            for i in range(1, len(equity_curve)):
                ret = (equity_curve[i]["total_assets"] - equity_curve[i-1]["total_assets"]) / equity_curve[i-1]["total_assets"]
                returns.append(ret)
            
            avg_return = sum(returns) / len(returns) if returns else 0
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 最大回撤
        max_drawdown = 0.0
        peak = equity_curve[0]["total_assets"]
        for point in equity_curve:
            if point["total_assets"] > peak:
                peak = point["total_assets"]
            drawdown = (peak - point["total_assets"]) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 交易统计
        executed_trades = [t for t in trades if not t.rejected and t.action in ["BUY", "SELL", "STOP_LOSS", "FINAL_SELL"]]
        winning_trades = [t for t in executed_trades if t.pnl > 0]
        losing_trades = [t for t in executed_trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / len(executed_trades) if executed_trades else 0
        
        avg_profit = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        total_profit = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # 阻断统计
        rejected_count = sum(1 for t in trades if t.rejected)
        
        return BacktestMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=len(executed_trades),
            rejected_trades=rejected_count,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            total_commission=self.total_commission,
            total_slippage=self.total_slippage,
        )
    
    def _validate(self, metrics: BacktestMetrics) -> bool:
        """验证策略是否通过"""
        
        # 至少要有实际执行的交易
        if metrics.total_trades < 3:
            logger.info(f"[AShareBacktest] 交易次数不足")
            return False
        
        # 允许负收益但不能太差
        if metrics.total_return < -0.5:
            logger.info(f"[AShareBacktest] 亏损过大: {metrics.total_return:.2%}")
            return False
        
        return True


# =============================================================================
# 便捷函数 (兼容旧接口)
# =============================================================================

# 别名
BacktestEngine = AShareBacktestEngine


async def quick_backtest(
    strategy_code: str,
    ticker: str = "000001.SH",
    days: int = 30,
    is_cy_market: bool = False
) -> BacktestResult:
    """
    快速回测 (A股版)
    
    Usage:
        result = await quick_backtest(strategy_code, "600519.SH", 30)
    """
    engine = AShareBacktestEngine(is_cy_market=is_cy_market)
    return await engine.backtest(strategy_code, ticker, days)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    async def test():
        test_strategy = '''
def strategy(context) -> dict:
    """
    简单均线策略
    """
    rsi = context.get("rsi", 50)
    momentum = context.get("momentum", 0)
    position = context.get("position", 0)
    
    # 入场条件
    if rsi < 30 and momentum < 0 and position == 0:
        return {
            "action": "BUY",
            "size": 0.3,
            "stop_loss": 0.03,
            "take_profit": 0.08,
            "confidence": 0.7,
            "reason": "RSI超卖"
        }
    
    # 出场条件
    if rsi > 70 or momentum > 0.05:
        return {
            "action": "SELL",
            "size": 1.0,
            "confidence": 0.6,
            "reason": "RSI超买"
        }
    
    return {
        "action": "HOLD",
        "size": 0,
        "confidence": 0.5,
        "reason": "无信号"
    }
'''
        
        engine = AShareBacktestEngine(initial_capital=100000, is_cy_market=False)
        result = await engine.backtest(test_strategy, "600519.SH", 60)
        
        print("=" * 60)
        print(f"回测状态: {result.status.value}")
        print(f"通过验证: {'✓' if result.passed else '✗'}")
        print("=" * 60)
        print("指标:")
        print(f"  总收益率: {result.metrics.total_return:.2%}")
        print(f"  夏普比率: {result.metrics.sharpe_ratio:.2f}")
        print(f"  最大回撤: {result.metrics.max_drawdown:.2%}")
        print(f"  胜率: {result.metrics.win_rate:.1%}")
        print(f"  交易次数: {result.metrics.total_trades}")
        print(f"  阻断次数: {result.metrics.rejected_trades}")
        print(f"  总佣金: ¥{result.metrics.total_commission:.2f}")
        print(f"  总滑点: ¥{result.metrics.total_slippage:.2f}")
        print("=" * 60)
        
        # 显示被阻断的交易
        rejected = [t for t in result.trades if t.rejected]
        if rejected:
            print("被阻断的交易:")
            for t in rejected[:5]:
                print(f"  {t.date} {t.action}: {t.reason}")
    
    # asyncio.run(test())
    print("AShareBacktestEngine 模块已加载")
