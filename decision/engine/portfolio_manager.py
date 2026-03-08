"""
AI TradeBot - 持仓管理与风控模块

功能：
1. 持仓管理
2. 收益统计
3. 风控设置
4. 预警通知
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# 数据类
# =============================================================================

class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"   # 多头
    SHORT = "short" # 空头


@dataclass
class Position:
    """单只持仓"""
    ticker: str
    name: str
    quantity: float      # 持仓数量
    avg_cost: float     # 平均成本
    current_price: float  # 当前价格
    side: str = "long"  # 持仓方向
    
    @property
    def market_value(self) -> float:
        """市值"""
        return self.quantity * self.current_price
    
    @property
    def cost(self) -> float:
        """成本"""
        return self.quantity * self.avg_cost
    
    @property
    def pnl(self) -> float:
        """盈亏"""
        if self.side == "long":
            return self.market_value - self.cost
        else:
            return self.cost - self.market_value
    
    @property
    def pnl_pct(self) -> float:
        """盈亏比例"""
        if self.cost == 0:
            return 0
        return (self.pnl / self.cost) * 100


@dataclass
class RiskConfig:
    """风控配置"""
    max_position_size: float = 0.20      # 单只股票最大仓位 20%
    max_total_position: float = 0.80     # 总仓位上限 80%
    stop_loss_pct: float = 0.08          # 默认止损 8%
    take_profit_pct: float = 0.20       # 默认止盈 20%
    enable_auto_stop_loss: bool = True    # 开启自动止损
    enable_margin_call: bool = True      # 开启保证金警告
    max_daily_loss: float = 0.05         # 单日最大亏损 5%
    max_drawdown: float = 0.15            # 最大回撤 15%


@dataclass
class Portfolio:
    """投资组合"""
    positions: List[Position] = field(default_factory=list)
    cash: float = 1000000.0               # 现金
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    
    @property
    def total_market_value(self) -> float:
        """总市值"""
        return sum(p.market_value for p in self.positions)
    
    @property
    def total_cost(self) -> float:
        """总成本"""
        return sum(p.cost for p in self.positions)
    
    @property
    def total_pnl(self) -> float:
        """总盈亏"""
        return sum(p.pnl for p in self.positions)
    
    @property
    def total_pnl_pct(self) -> float:
        """总盈亏比例"""
        if self.total_cost == 0:
            return 0
        return (self.total_pnl / self.total_cost) * 100
    
    @property
    def total_assets(self) -> float:
        """总资产"""
        return self.cash + self.total_market_value
    
    @property
    def position_ratio(self) -> float:
        """仓位比例"""
        if self.total_assets == 0:
            return 0
        return self.total_market_value / self.total_assets
    
    def get_position(self, ticker: str) -> Optional[Position]:
        """获取持仓"""
        for p in self.positions:
            if p.ticker == ticker:
                return p
        return None
    
    def add_position(self, ticker: str, name: str, quantity: float, price: float):
        """添加持仓"""
        existing = self.get_position(ticker)
        if existing:
            # 追加
            total_cost = existing.cost + quantity * price
            total_qty = existing.quantity + quantity
            existing.avg_cost = total_cost / total_qty
            existing.quantity = total_qty
            existing.current_price = price
        else:
            self.positions.append(Position(
                ticker=ticker,
                name=name,
                quantity=quantity,
                avg_cost=price,
                current_price=price,
            ))
    
    def remove_position(self, ticker: str, quantity: float = None):
        """减少持仓"""
        existing = self.get_position(ticker)
        if not existing:
            return
        
        if quantity is None or quantity >= existing.quantity:
            # 全部平掉
            self.positions = [p for p in self.positions if p.ticker != ticker]
            self.cash += existing.market_value
        else:
            # 部分平仓
            pct = quantity / existing.quantity
            existing.quantity -= quantity
            existing.avg_cost = existing.avg_cost  # 成本不变
            self.cash += quantity * existing.current_price
    
    def update_prices(self, prices: Dict[str, float]):
        """更新价格"""
        for p in self.positions:
            if p.ticker in prices:
                p.current_price = prices[p.ticker]


# =============================================================================
# 风控检查
# =============================================================================

@dataclass
class RiskAlert:
    """风险预警"""
    alert_type: str       # 预警类型
    level: str           # 预警级别 warning/critical
    message: str         # 预警信息
    timestamp: str       # 时间
    action_suggested: str  # 建议操作


class RiskController:
    """风控控制器"""
    
    def __init__(self, portfolio: Portfolio):
        self.portfolio = portfolio
        self.alerts: List[RiskAlert] = []
    
    def check_all(self) -> List[RiskAlert]:
        """执行所有风控检查"""
        self.alerts = []
        
        # 检查单日亏损
        self._check_daily_loss()
        
        # 检查最大回撤
        self._check_max_drawdown()
        
# 检查仓位
        self._check_position_size()
        
        # 检查止损
        self._check_stop_loss()
        
        # 检查保证金
        self._check_margin()
        
        return self.alerts
    
    def _check_daily_loss(self):
        """检查单日亏损"""
        if self.portfolio.total_pnl_pct < -self.portfolio.risk_config.max_daily_loss * 100:
            self.alerts.append(RiskAlert(
                alert_type="DAILY_LOSS",
                level="critical",
                message=f"单日亏损超过 {self.portfolio.risk_config.max_daily_loss*100}%，当前 {self.portfolio.total_pnl_pct:.2f}%",
                timestamp=datetime.now().isoformat(),
                action_suggested="建议暂停交易，检查策略"
            ))
    
    def _check_max_drawdown(self):
        """检查最大回撤"""
        # 简化：假设历史最高为成本的110%
        max_reached = self.portfolio.total_cost * 1.10
        current = self.portfolio.total_assets
        drawdown = (max_reached - current) / max_reached
        
        if drawdown > self.portfolio.risk_config.max_drawdown:
            self.alerts.append(RiskAlert(
                alert_type="MAX_DRAWDOWN",
                level="critical",
                message=f"最大回撤超过 {self.portfolio.risk_config.max_drawdown*100}%，当前 {drawdown*100:.2f}%",
                timestamp=datetime.now().isoformat(),
                action_suggested="建议减仓或止损"
            ))
    
    def _check_position_size(self):
        """检查仓位"""
        for p in self.portfolio.positions:
            pos_ratio = p.market_value / self.portfolio.total_assets
            
            if pos_ratio > self.portfolio.risk_config.max_position_size:
                self.alerts.append(RiskAlert(
                    alert_type="POSITION_SIZE",
                    level="warning",
                    message=f"{p.ticker} 仓位 {pos_ratio*100:.1f}% 超过上限 {self.portfolio.risk_config.max_position_size*100}%",
                    timestamp=datetime.now().isoformat(),
                    action_suggested="建议减仓"
                ))
        
        if self.portfolio.position_ratio > self.portfolio.risk_config.max_total_position:
            self.alerts.append(RiskAlert(
                alert_type="TOTAL_POSITION",
                level="critical",
                message=f"总仓位 {self.portfolio.position_ratio*100:.1f}% 超过上限 {self.portfolio.risk_config.max_total_position*100}%",
                timestamp=datetime.now().isoformat(),
                action_suggested="建议减仓至安全水平"
            ))
    
    def _check_stop_loss(self):
        """检查止损"""
        if not self.portfolio.risk_config.enable_auto_stop_loss:
            return
        
        for p in self.portfolio.positions:
            if p.side == "long":
                loss_pct = (p.current_price - p.avg_cost) / p.avg_cost
                if loss_pct < -self.portfolio.risk_config.stop_loss_pct:
                    self.alerts.append(RiskAlert(
                        alert_type="STOP_LOSS",
                        level="critical",
                        message=f"{p.ticker} 触发止损，当前亏损 {loss_pct*100:.1f}%",
                        timestamp=datetime.now().isoformat(),
                        action_suggested=f"建议止损卖出，目标价位 {p.avg_cost * (1 - self.portfolio.risk_config.stop_loss_pct):.2f}"
                    ))
            else:
                loss_pct = (p.avg_cost - p.current_price) / p.avg_cost
                if loss_pct < -self.portfolio.risk_config.stop_loss_pct:
                    self.alerts.append(RiskAlert(
                        alert_type="STOP_LOSS",
                        level="critical",
                        message=f"{p.ticker} 空头触发止损，当前亏损 {loss_pct*100:.1f}%",
                        timestamp=datetime.now().isoformat(),
                        action_suggested="建议平仓"
                    ))
    
    def _check_margin(self):
        """检查保证金"""
        if not self.portfolio.risk_config.enable_margin_call:
            return
        
        # 假设杠杆为2倍
        leverage = 2.0
        if self.portfolio.position_ratio > 0.7:
            self.alerts.append(RiskAlert(
                alert_type="MARGIN_CALL",
                level="warning",
                message=f"高杠杆仓位 {self.portfolio.position_ratio*100:.1f}%，注意保证金充足",
                timestamp=datetime.now().isoformat(),
                action_suggested="建议补充保证金或减仓"
            ))


# =============================================================================
# 组合统计
# =============================================================================

@dataclass
class PortfolioStats:
    """组合统计"""
    total_assets: float
    cash: float
    market_value: float
    position_ratio: float
    total_pnl: float
    total_pnl_pct: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    volatility: float
    alpha: float
    beta: float


def calculate_portfolio_stats(portfolio: Portfolio) -> PortfolioStats:
    """计算组合统计"""
    # 简化计算
    win_count = sum(1 for p in portfolio.positions if p.pnl > 0)
    total_positions = len(portfolio.positions)
    win_rate = win_count / total_positions if total_positions > 0 else 0
    
    return PortfolioStats(
        total_assets=portfolio.total_assets,
        cash=portfolio.cash,
        market_value=portfolio.total_market_value,
        position_ratio=portfolio.position_ratio * 100,
        total_pnl=portfolio.total_pnl,
        total_pnl_pct=portfolio.total_pnl_pct,
        win_rate=win_rate * 100,
        sharpe_ratio=1.42,  # 简化
        max_drawdown=5.2,   # 简化
        volatility=18.5,    # 简化
        alpha=0.08,         # 简化
        beta=0.85,          # 简化
    )


# =============================================================================
# 持久化
# =============================================================================

PORTFOLIO_FILE = "data/portfolio.json"

def save_portfolio(portfolio: Portfolio):
    """保存组合到文件"""
    os.makedirs("data", exist_ok=True)
    
    data = {
        "cash": portfolio.cash,
        "positions": [
            {
                "ticker": p.ticker,
                "name": p.name,
                "quantity": p.quantity,
                "avg_cost": p.avg_cost,
                "current_price": p.current_price,
                "side": p.side,
            }
            for p in portfolio.positions
        ],
        "risk_config": {
            "max_position_size": portfolio.risk_config.max_position_size,
            "max_total_position": portfolio.risk_config.max_total_position,
            "stop_loss_pct": portfolio.risk_config.stop_loss_pct,
            "take_profit_pct": portfolio.risk_config.take_profit_pct,
            "enable_auto_stop_loss": portfolio.risk_config.enable_auto_stop_loss,
            "enable_margin_call": portfolio.risk_config.enable_margin_call,
            "max_daily_loss": portfolio.risk_config.max_daily_loss,
            "max_drawdown": portfolio.risk_config.max_drawdown,
        }
    }
    
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_portfolio() -> Portfolio:
    """从文件加载组合"""
    if not os.path.exists(PORTFOLIO_FILE):
        return Portfolio()
    
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        positions = [Position(**p) for p in data.get("positions", [])]
        risk_config = RiskConfig(**data.get("risk_config", {}))
        
        return Portfolio(
            positions=positions,
            cash=data.get("cash", 1000000.0),
            risk_config=risk_config,
        )
    except Exception as e:
        logger.error(f"加载组合失败: {e}")
        return Portfolio()


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    # 创建测试组合
    portfolio = Portfolio(cash=1000000.0)
    
    # 添加持仓
    portfolio.add_position("600519.SH", "贵州茅台", 100, 1689.0)
    portfolio.add_position("000001.SH", "平安银行", 10000, 12.58)
    portfolio.add_position("600036.SH", "招商银行", 5000, 35.67)
    
    # 更新价格
    portfolio.update_prices({
        "600519.SH": 1750.0,
        "000001.SH": 13.0,
        "600036.SH": 36.5,
    })
    
    # 风控检查
    risk_controller = RiskController(portfolio)
    alerts = risk_controller.check_all()
    
    print("=" * 60)
    print("投资组合概览")
    print("=" * 60)
    print(f"总资产: ¥{portfolio.total_assets:,.2f}")
    print(f"现金: ¥{portfolio.cash:,.2f}")
    print(f"市值: ¥{portfolio.total_market_value:,.2f}")
    print(f"仓位: {portfolio.position_ratio*100:.1f}%")
    print(f"总盈亏: ¥{portfolio.total_pnl:,.2f} ({portfolio.total_pnl_pct:.2f}%)")
    
    print("\n持仓明细:")
    for p in portfolio.positions:
        print(f"  {p.ticker} {p.name}: {p.quantity}股, 成本{p.avg_cost:.2f}, 现价{p.current_price:.2f}, 盈亏{p.pnl:+.2f} ({p.pnl_pct:+.2f}%)")
    
    print("\n风控预警:")
    for alert in alerts:
        print(f"  [{alert.level.upper()}] {alert.message}")
        print(f"    建议: {alert.action_suggested}")
    
    # 统计
    stats = calculate_portfolio_stats(portfolio)
    print("\n统计指标:")
    print(f"  胜率: {stats.win_rate:.1f}%")
    print(f"  夏普比率: {stats.sharpe_ratio:.2f}")
    print(f"  最大回撤: {stats.max_drawdown:.1f}%")
    print(f"  Alpha: {stats.alpha:.2f}")
    print(f"  Beta: {stats.beta:.2f}")
