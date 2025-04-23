"""
مؤشرات المشاعر (Long/Short Ratio, Funding Rate)
"""

import logging
import time
from typing import Dict, Any, List
import numpy as np
from dataclasses import dataclass

from api.binance_client import BinanceClient
from config import SYMBOL

logger = logging.getLogger(__name__)


@dataclass
class LSRatioData:
    timestamp: int
    long_ratio: float  # نسبة المراكز الطويلة
    short_ratio: float  # نسبة المراكز القصيرة
    ratio: float  # النسبة بين الطويلة والقصيرة


@dataclass
class FundingRateData:
    timestamp: int
    funding_rate: float  # معدل التمويل الحالي
    next_funding_time: int  # وقت التمويل القادم
    predicted_rate: float  # معدل التمويل المتوقع


class SentimentIndicators:
    def __init__(self):
        self.binance_client = BinanceClient()

    def get_long_short_ratio(self) -> LSRatioData:
        """
        الحصول على نسبة المراكز الطويلة/القصيرة
        """
        try:
            # الحصول على بيانات نسبة المراكز
            ls_ratio_data = self.binance_client.get_long_short_ratio(period="5m", limit=1)

            if not ls_ratio_data:
                logger.warning("لم يتم العثور على بيانات نسبة المراكز الطويلة/القصيرة")
                return LSRatioData(timestamp=int(time.time()), long_ratio=0.0, short_ratio=0.0, ratio=1.0)

            # استخراج البيانات
            data = ls_ratio_data[0]
            long_ratio = float(data["longAccount"])
            short_ratio = float(data["shortAccount"])

            # حساب النسبة بين الطويلة والقصيرة
            ratio = long_ratio / short_ratio if short_ratio > 0 else float('inf')

            return LSRatioData(
                timestamp=int(data["timestamp"]) // 1000,
                long_ratio=long_ratio,
                short_ratio=short_ratio,
                ratio=ratio
            )
        except Exception as e:
            logger.error(f"خطأ في الحصول على نسبة المراكز الطويلة/القصيرة: {e}")
            return LSRatioData(timestamp=int(time.time()), long_ratio=0.0, short_ratio=0.0, ratio=1.0)

    def get_funding_rate(self) -> FundingRateData:
        """
        الحصول على معدل التمويل
        """
        try:
            # الحصول على بيانات معدل التمويل
            funding_data = self.binance_client.get_funding_rate()

            if not funding_data:
                logger.warning("لم يتم العثور على بيانات معدل التمويل")
                return FundingRateData(timestamp=int(time.time()), funding_rate=0.0, next_funding_time=0,
                                       predicted_rate=0.0)

            # استخراج البيانات
            funding_rate = float(funding_data["lastFundingRate"])
            next_funding_time = int(funding_data["nextFundingTime"]) // 1000
            predicted_rate = float(funding_data.get("predictedFundingRate", 0.0))

            return FundingRateData(
                timestamp=int(time.time()),
                funding_rate=funding_rate,
                next_funding_time=next_funding_time,
                predicted_rate=predicted_rate
            )
        except Exception as e:
            logger.error(f"خطأ في الحصول على معدل التمويل: {e}")
            return FundingRateData(timestamp=int(time.time()), funding_rate=0.0, next_funding_time=0,
                                   predicted_rate=0.0)