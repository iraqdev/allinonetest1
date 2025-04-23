"""
مؤشرات تدفق الأوامر (Order Flow)
"""

import logging
from typing import Dict, Any, List, Tuple
import numpy as np
import time
from dataclasses import dataclass

from api.binance_client import BinanceClient
from api.solana_client import SolanaClient
from config import SYMBOL, WHALE_THRESHOLD

logger = logging.getLogger(__name__)


@dataclass
class DeltaData:
    timestamp: int
    buy_volume: float
    sell_volume: float
    delta: float  # الفرق بين حجم الشراء والبيع (مؤشر لتدفق الأوامر)
    price: float


@dataclass
class FootprintData:
    timestamp: int
    price_levels: Dict[float, Tuple[float, float]]  # سعر -> (حجم الشراء، حجم البيع)
    delta_by_level: Dict[float, float]  # سعر -> دلتا


@dataclass
@dataclass
class WhaleData:
    timestamp: int
    transfers: List[Dict[str, Any]]  # معلومات التحويلات الكبيرة
    total_value: float  # إجمالي قيمة التحويلات بالدولار
    cex_transfers: List[Dict[str, Any]]  # تحويلات CEX
    dex_transfers: List[Dict[str, Any]]  # تحويلات DEX
    cex_value: float  # قيمة تحويلات CEX بالدولار
    dex_value: float  # قيمة تحويلات DEX بالدولار


class OrderFlowIndicators:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.solana_client = SolanaClient()

    def calculate_delta(self, timeframe_minutes: int = 1) -> DeltaData:
        """
        حساب دلتا تدفق الأوامر (الفرق بين حجم الشراء والبيع)
        """
        # الحصول على الصفقات الأخيرة
        trades = self.binance_client.get_recent_trades()
        current_time = int(time.time() * 1000)  # الوقت الحالي بالميلي ثانية
        timeframe_ms = timeframe_minutes * 60 * 1000  # تحويل الدقائق إلى ميلي ثانية

        # تصفية الصفقات ضمن الإطار الزمني المطلوب
        recent_trades = [
            trade for trade in trades
            if trade["time"] > (current_time - timeframe_ms)
        ]

        if not recent_trades:
            logger.warning(f"لم يتم العثور على صفقات خلال آخر {timeframe_minutes} دقيقة")
            return DeltaData(
                timestamp=current_time // 1000,
                buy_volume=0.0,
                sell_volume=0.0,
                delta=0.0,
                price=float(trades[-1]["price"]) if trades else 0.0
            )

        # حساب حجم الشراء والبيع
        buy_volume = sum(float(trade["qty"]) for trade in recent_trades if trade["isBuyerMaker"] is False)
        sell_volume = sum(float(trade["qty"]) for trade in recent_trades if trade["isBuyerMaker"] is True)

        # حساب الدلتا
        delta = buy_volume - sell_volume

        # سعر آخر صفقة
        latest_price = float(recent_trades[-1]["price"])

        return DeltaData(
            timestamp=current_time // 1000,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=delta,
            price=latest_price
        )

    def calculate_footprint(self, timeframe_minutes: int = 1) -> FootprintData:
        """
        حساب مؤشر Footprint (حجم التداول على مستويات الأسعار)
        """
        # الحصول على الصفقات الأخيرة
        trades = self.binance_client.get_recent_trades()
        current_time = int(time.time() * 1000)  # الوقت الحالي بالميلي ثانية
        timeframe_ms = timeframe_minutes * 60 * 1000  # تحويل الدقائق إلى ميلي ثانية

        # تصفية الصفقات ضمن الإطار الزمني المطلوب
        recent_trades = [
            trade for trade in trades
            if trade["time"] > (current_time - timeframe_ms)
        ]

        price_levels = {}  # سعر -> (حجم الشراء، حجم البيع)

        for trade in recent_trades:
            price = float(trade["price"])
            qty = float(trade["qty"])
            is_buy = not trade["isBuyerMaker"]

            # تقريب السعر إلى مستويات مناسبة للتجميع
            # يمكن تغيير مستوى التقريب حسب الحاجة
            rounded_price = round(price, 2)

            if rounded_price not in price_levels:
                price_levels[rounded_price] = (0.0, 0.0)  # (buy, sell)

            buy_vol, sell_vol = price_levels[rounded_price]

            if is_buy:
                price_levels[rounded_price] = (buy_vol + qty, sell_vol)
            else:
                price_levels[rounded_price] = (buy_vol, sell_vol + qty)

        # حساب الدلتا على كل مستوى سعر
        delta_by_level = {
            price: buy_vol - sell_vol
            for price, (buy_vol, sell_vol) in price_levels.items()
        }

        return FootprintData(
            timestamp=current_time // 1000,
            price_levels=price_levels,
            delta_by_level=delta_by_level
        )

    def track_whale_transfers(self) -> WhaleData:
        """
        تتبع تحويلات الحيتان (كبار المستثمرين)
        """
        # الحصول على سعر SOL الحالي
        ticker = self.binance_client.get_ticker_24hr()
        sol_price = float(ticker["lastPrice"])

        # الحصول على تحويلات الحيتان من البلوكتشين (أكثر من 500 SOL)
        whale_transfers = self.solana_client.get_whale_transfers(threshold_sol=500)

        # تحويل البيانات إلى تنسيق أكثر سهولة للاستخدام
        formatted_transfers = []
        cex_transfers = []
        dex_transfers = []
        total_value = 0.0
        cex_value = 0.0
        dex_value = 0.0

        for tx in whale_transfers:
            value_sol = tx.lamports / 1_000_000_000 if tx.lamports else 0
            value_usd = value_sol * sol_price

            transfer_info = {
                "signature": tx.signature,
                "timestamp": tx.block_time,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "value_sol": value_sol,
                "value_usd": value_usd,
                "type": tx.tx_type
            }

            formatted_transfers.append(transfer_info)
            total_value += value_usd

            # تصنيف التحويل حسب النوع
            if tx.tx_type == "CEX":
                cex_transfers.append(transfer_info)
                cex_value += value_usd
            elif tx.tx_type == "DEX":
                dex_transfers.append(transfer_info)
                dex_value += value_usd

        return WhaleData(
            timestamp=int(time.time()),
            transfers=formatted_transfers,
            total_value=total_value,
            cex_transfers=cex_transfers,
            dex_transfers=dex_transfers,
            cex_value=cex_value,
            dex_value=dex_value
        )