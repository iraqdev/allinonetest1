"""
مؤشرات البلوكتشين ومؤشرات العقود المفتوحة
"""

import logging
import time
from typing import Dict, Any, List
import numpy as np
from dataclasses import dataclass

from api.binance_client import BinanceClient
from api.solana_client import SolanaClient
from config import SYMBOL

logger = logging.getLogger(__name__)


@dataclass
class OpenInterestData:
    timestamp: int
    open_interest: float
    open_interest_value: float  # قيمة العقود المفتوحة بالدولار
    change_24h: float  # التغيير خلال 24 ساعة بالنسبة المئوية


@dataclass
class VWAPData:
    timestamp: int
    vwap: float
    price: float
    distance_from_vwap: float  # البعد عن الـ VWAP بالنسبة المئوية


class BlockchainIndicators:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.solana_client = SolanaClient()
        self.last_oi = None  # آخر قيمة للعقود المفتوحة للمقارنة

    def get_open_interest(self) -> OpenInterestData:
        """
        الحصول على بيانات العقود المفتوحة
        """
        try:
            # الحصول على بيانات العقود المفتوحة من Binance
            oi_data = self.binance_client.get_open_interest()

            # الحصول على سعر العملة الحالي
            ticker = self.binance_client.get_ticker_24hr()
            price = float(ticker["lastPrice"])

            # حساب قيمة العقود المفتوحة بالدولار
            open_interest = float(oi_data["openInterest"])
            open_interest_value = open_interest * price

            # حساب التغيير خلال 24 ساعة (في التطبيق الحقيقي، هذا سيتطلب تخزين البيانات التاريخية)
            change_24h = 0.0
            if self.last_oi:
                change_24h = ((open_interest - self.last_oi) / self.last_oi) * 100

            self.last_oi = open_interest

            return OpenInterestData(
                timestamp=int(time.time()),
                open_interest=open_interest,
                open_interest_value=open_interest_value,
                change_24h=change_24h
            )
        except Exception as e:
            logger.error(f"خطأ في الحصول على بيانات العقود المفتوحة: {e}")
            return OpenInterestData(
                timestamp=int(time.time()),
                open_interest=0.0,
                open_interest_value=0.0,
                change_24h=0.0
            )

    def calculate_vwap(self, timeframe_minutes: int = 60) -> VWAPData:
        """
        حساب مؤشر VWAP (Volume Weighted Average Price)
        """
        try:
            # تحويل الدقائق إلى ميلي ثانية
            interval = "1m"  # فترة الشموع اليابانية
            limit = min(500, timeframe_minutes)  # الحد الأقصى هو 500 شمعة

            # الحصول على بيانات الشموع اليابانية
            klines = self.binance_client.get_klines(interval=interval, limit=limit)

            if not klines:
                logger.warning("لم يتم العثور على بيانات الشموع اليابانية")
                return VWAPData(timestamp=int(time.time()), vwap=0.0, price=0.0, distance_from_vwap=0.0)

            # استخراج بيانات السعر والحجم
            # هيكل الشموع اليابانية: [وقت الفتح, سعر الفتح, أعلى سعر, أدنى سعر, سعر الإغلاق, الحجم, ...]
            prices = []
            volumes = []

            for kline in klines:
                typical_price = (float(kline[2]) + float(kline[3]) + float(kline[4])) / 3  # (H+L+C)/3
                volume = float(kline[5])

                prices.append(typical_price)
                volumes.append(volume)

            # حساب VWAP
            vwap = np.average(prices, weights=volumes)

            # الحصول على السعر الحالي
            current_price = float(klines[-1][4])  # سعر الإغلاق للشمعة الأخيرة

            # حساب البعد عن الـ VWAP بالنسبة المئوية
            distance_from_vwap = ((current_price - vwap) / vwap) * 100

            return VWAPData(
                timestamp=int(time.time()),
                vwap=vwap,
                price=current_price,
                distance_from_vwap=distance_from_vwap
            )
        except Exception as e:
            logger.error(f"خطأ في حساب VWAP: {e}")
            return VWAPData(timestamp=int(time.time()), vwap=0.0, price=0.0, distance_from_vwap=0.0)