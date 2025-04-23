"""
مؤشرات عمق السوق (Iceberg, CVD, Spoofing)
"""

import logging
import time
from typing import Dict, Any, List, Tuple
import numpy as np
from collections import deque
from dataclasses import dataclass

from api.binance_client import BinanceClient
from config import SYMBOL

logger = logging.getLogger(__name__)


@dataclass
class IcebergData:
    timestamp: int
    detected_levels: List[Dict[str, Any]]  # مستويات الـ Iceberg المكتشفة
    strength: float  # قوة الإشارة


@dataclass
class CVDData:
    timestamp: int
    cvd_value: float  # قيمة الـ CVD الحالية
    cvd_change: float  # التغيير في الـ CVD
    buy_volume: float  # حجم الشراء
    sell_volume: float  # حجم البيع


@dataclass
class SpoofingData:
    timestamp: int
    detected_levels: List[Dict[str, Any]]  # مستويات الـ spoofing المكتشفة
    strength: float  # قوة الإشارة


class MarketDepthIndicators:
    def __init__(self, history_length: int = 60):
        self.binance_client = BinanceClient()
        self.order_book_history = deque(maxlen=history_length)  # تاريخ دفتر الطلبات
        self.cvd_history = deque(maxlen=history_length)  # تاريخ الـ CVD
        self.last_order_book = None  # آخر دفتر طلبات

    def _update_order_book_history(self):
        """تحديث تاريخ دفتر الطلبات"""
        try:
            order_book = self.binance_client.get_order_book(limit=100)
            self.order_book_history.append(order_book)
            self.last_order_book = order_book
            return order_book
        except Exception as e:
            logger.error(f"خطأ في تحديث دفتر الطلبات: {e}")
            return None

    def detect_icebergs(self, volume_threshold: float = 100.0, repetition_threshold: int = 3) -> IcebergData:
        """
        اكتشاف أوامر الـ Iceberg (الأوامر الكبيرة المقسمة إلى أوامر صغيرة)
        """
        try:
            # تحديث دفتر الطلبات
            order_book = self._update_order_book_history()
            if not order_book or len(self.order_book_history) < 2:
                return IcebergData(timestamp=int(time.time()), detected_levels=[], strength=0.0)

            # البحث عن الأنماط في دفتر الطلبات: أوامر متكررة بنفس السعر والحجم
            bid_count = {}  # عدد تكرار أوامر الشراء بنفس السعر والحجم
            ask_count = {}  # عدد تكرار أوامر البيع بنفس السعر والحجم

            for book in self.order_book_history:
                # تحليل أوامر الشراء
                for bid in book.bids:
                    if bid.quantity >= volume_threshold:
                        key = (bid.price, bid.quantity)
                        bid_count[key] = bid_count.get(key, 0) + 1

                # تحليل أوامر البيع
                for ask in book.asks:
                    if ask.quantity >= volume_threshold:
                        key = (ask.price, ask.quantity)
                        ask_count[key] = ask_count.get(key, 0) + 1

            # تحديد مستويات الـ Iceberg
            detected_levels = []

            # أوامر الشراء
            for (price, quantity), count in bid_count.items():
                if count >= repetition_threshold:
                    detected_levels.append({
                        "price": price,
                        "quantity": quantity,
                        "repetitions": count,
                        "side": "buy",
                        "estimated_total": quantity * count
                    })

            # أوامر البيع
            for (price, quantity), count in ask_count.items():
                if count >= repetition_threshold:
                    detected_levels.append({
                        "price": price,
                        "quantity": quantity,
                        "repetitions": count,
                        "side": "sell",
                        "estimated_total": quantity * count
                    })

            # حساب قوة الإشارة بناءً على عدد المستويات المكتشفة وحجمها
            strength = sum(level["estimated_total"] for level in detected_levels)

            return IcebergData(
                timestamp=int(time.time()),
                detected_levels=detected_levels,
                strength=strength
            )
        except Exception as e:
            logger.error(f"خطأ في اكتشاف Icebergs: {e}")
            return IcebergData(timestamp=int(time.time()), detected_levels=[], strength=0.0)

    def calculate_cvd(self, timeframe_minutes: int = 1) -> CVDData:
        """
        حساب مؤشر CVD (Cumulative Volume Delta)
        """
        try:
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
                return CVDData(
                    timestamp=int(time.time()),
                    cvd_value=0.0 if not self.cvd_history else self.cvd_history[-1],
                    cvd_change=0.0,
                    buy_volume=0.0,
                    sell_volume=0.0
                )

            # حساب حجم الشراء والبيع
            buy_volume = sum(float(trade["qty"]) for trade in recent_trades if trade["isBuyerMaker"] is False)
            sell_volume = sum(float(trade["qty"]) for trade in recent_trades if trade["isBuyerMaker"] is True)

            # حساب الـ CVD
            delta = buy_volume - sell_volume

            # إضافة الدلتا الحالية إلى الـ CVD السابق
            if self.cvd_history:
                cvd_value = self.cvd_history[-1] + delta
            else:
                cvd_value = delta

            self.cvd_history.append(cvd_value)

            # حساب التغيير في الـ CVD
            cvd_change = delta
            if len(self.cvd_history) > 1:
                cvd_change = self.cvd_history[-1] - self.cvd_history[-2]

            return CVDData(
                timestamp=int(time.time()),
                cvd_value=cvd_value,
                cvd_change=cvd_change,
                buy_volume=buy_volume,
                sell_volume=sell_volume
            )
        except Exception as e:
            logger.error(f"خطأ في حساب CVD: {e}")
            return CVDData(timestamp=int(time.time()), cvd_value=0.0, cvd_change=0.0, buy_volume=0.0, sell_volume=0.0)

    def detect_spoofing(self, disappearance_threshold: float = 0.7) -> SpoofingData:
        """
        اكتشاف عمليات الـ Spoofing (أوامر وهمية تختفي قبل التنفيذ)
        """
        try:
            # تحديث دفتر الطلبات
            order_book = self._update_order_book_history()
            if not order_book or len(self.order_book_history) < 3:
                return SpoofingData(timestamp=int(time.time()), detected_levels=[], strength=0.0)

            # تتبع الأوامر التي اختفت فجأة
            disappeared_orders = []

            # نستخدم آخر كتابين للطلبات لمقارنتهما
            current_book = self.order_book_history[-1]
            previous_book = self.order_book_history[-2]

            # تحويل أوامر الشراء والبيع إلى قواميس لتسهيل البحث
            current_bids = {bid.price: bid.quantity for bid in current_book.bids}
            current_asks = {ask.price: ask.quantity for ask in current_book.asks}

            previous_bids = {bid.price: bid.quantity for bid in previous_book.bids}
            previous_asks = {ask.price: ask.quantity for ask in previous_book.asks}

            # البحث عن أوامر الشراء التي اختفت
            for price, quantity in previous_bids.items():
                if price not in current_bids:
                    # الأمر اختفى تمامًا
                    disappeared_orders.append({
                        "price": price,
                        "original_quantity": quantity,
                        "current_quantity": 0,
                        "disappearance_ratio": 1.0,
                        "side": "buy"
                    })
                elif current_bids[price] < quantity * (1 - disappearance_threshold):
                    # الكمية انخفضت بشكل كبير
                    disappeared_orders.append({
                        "price": price,
                        "original_quantity": quantity,
                        "current_quantity": current_bids[price],
                        "disappearance_ratio": (quantity - current_bids[price]) / quantity,
                        "side": "buy"
                    })

            # البحث عن أوامر البيع التي اختفت
            for price, quantity in previous_asks.items():
                if price not in current_asks:
                    # الأمر اختفى تمامًا
                    disappeared_orders.append({
                        "price": price,
                        "original_quantity": quantity,
                        "current_quantity": 0,
                        "disappearance_ratio": 1.0,
                        "side": "sell"
                    })
                elif current_asks[price] < quantity * (1 - disappearance_threshold):
                    # الكمية انخفضت بشكل كبير
                    disappeared_orders.append({
                        "price": price,
                        "original_quantity": quantity,
                        "current_quantity": current_asks[price],
                        "disappearance_ratio": (quantity - current_asks[price]) / quantity,
                        "side": "sell"
                    })

            # تصفية لإظهار الأوامر الأكثر أهمية فقط
            disappeared_orders.sort(key=lambda x: x["original_quantity"] * x["disappearance_ratio"], reverse=True)
            top_disappeared = disappeared_orders[:10]  # الاحتفاظ بأهم 10 أوامر

            # حساب قوة الإشارة
            strength = sum(order["original_quantity"] * order["disappearance_ratio"] for order in top_disappeared)

            return SpoofingData(
                timestamp=int(time.time()),
                detected_levels=top_disappeared,
                strength=strength
            )
        except Exception as e:
            logger.error(f"خطأ في اكتشاف Spoofing: {e}")
            return SpoofingData(timestamp=int(time.time()), detected_levels=[], strength=0.0)