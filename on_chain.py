"""
مؤشرات على السلسلة (On-Chain)
"""

import logging
import time
from typing import Dict, Any, List
from dataclasses import dataclass

from api.solana_client import SolanaClient
from api.binance_client import BinanceClient
from config import SYMBOL

logger = logging.getLogger(__name__)


@dataclass
class OnChainData:
    timestamp: int
    transactions_count: int  # عدد المعاملات
    tps: float  # المعاملات في الثانية
    active_addresses: int  # عدد العناوين النشطة


class OnChainIndicators:
    def __init__(self):
        self.solana_client = SolanaClient()

    def get_onchain_metrics(self) -> OnChainData:
        """
        الحصول على مقاييس البلوكتشين
        """
        try:
            # الحصول على المعاملات الأخيرة
            transactions = self.solana_client.get_transactions()
            transactions_count = len(transactions)

            # حساب TPS
            tps = self.solana_client.get_tps()

            # تقدير عدد العناوين النشطة
            active_addresses = self.solana_client.get_active_addresses()

            return OnChainData(
                timestamp=int(time.time()),
                transactions_count=transactions_count,
                tps=tps,
                active_addresses=active_addresses
            )
        except Exception as e:
            logger.error(f"خطأ في الحصول على مقاييس البلوكتشين: {e}")
            return OnChainData(timestamp=int(time.time()), transactions_count=0, tps=0.0, active_addresses=0)