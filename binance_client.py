"""
واجهة الاتصال مع منصة بينانس
"""

import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
import json
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass

from config import BINANCE_API_KEY, BINANCE_SECRET_KEY, SYMBOL

logger = logging.getLogger(__name__)


@dataclass
class OrderBookEntry:
    price: float
    quantity: float


@dataclass
class OrderBook:
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    last_update_id: int


class BinanceClient:
    def __init__(self):
        self.base_url = "https://api.binance.com"
        self.api_key = BINANCE_API_KEY
        self.api_secret = BINANCE_SECRET_KEY
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        })

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """توليد توقيع للطلبات المصادق عليها"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Any:
        """إرسال طلب إلى Binance API"""
        import socket
        import time
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter

        url = f"{self.base_url}{endpoint}"

        # إضافة الطوابع الزمنية والتوقيع إذا كان مطلوبًا
        params = kwargs.get("params", {})
        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["signature"] = self._generate_signature(params)
            kwargs["params"] = params

        # إعداد استراتيجية إعادة المحاولة
        retry_strategy = Retry(
            total=3,  # عدد محاولات إعادة الاتصال
            backoff_factor=2,  # عامل التأخير التصاعدي
            status_forcelist=[429, 500, 502, 503, 504],  # أكواد الحالة التي تتطلب إعادة المحاولة
            allowed_methods=["GET", "POST"]  # الطرق المسموح بها لإعادة المحاولة
        )

        # تكوين جلسة HTTP مع استراتيجية إعادة المحاولة
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # تعيين مهلة أطول للاتصال - 30 ثانية للاتصال و 30 ثانية للاستجابة
        kwargs.setdefault('timeout', (30, 30))

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"خطأ في طلب Binance: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"استجابة الخطأ: {e.response.text}")
            raise

    def get_order_book(self, symbol: str = SYMBOL, limit: int = 100) -> OrderBook:
        """الحصول على دفتر الطلبات"""
        endpoint = "/api/v3/depth"
        params = {"symbol": symbol, "limit": limit}

        data = self._request("GET", endpoint, params=params)

        bids = [OrderBookEntry(float(bid[0]), float(bid[1])) for bid in data["bids"]]
        asks = [OrderBookEntry(float(ask[0]), float(ask[1])) for ask in data["asks"]]

        return OrderBook(
            bids=bids,
            asks=asks,
            last_update_id=data["lastUpdateId"]
        )

    def get_recent_trades(self, symbol: str = SYMBOL, limit: int = 1000) -> List[Dict[str, Any]]:
        """الحصول على الصفقات الأخيرة"""
        endpoint = "/api/v3/trades"
        params = {"symbol": symbol, "limit": limit}

        return self._request("GET", endpoint, params=params)

    def get_klines(self, symbol: str = SYMBOL, interval: str = "1m",
                   limit: int = 500, start_time: Optional[int] = None, end_time: Optional[int] = None) -> List[List]:
        """الحصول على بيانات الشموع اليابانية"""
        endpoint = "/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        return self._request("GET", endpoint, params=params)

    def get_ticker_24hr(self, symbol: str = SYMBOL) -> Dict[str, Any]:
        """الحصول على إحصاءات الـ 24 ساعة الماضية"""
        endpoint = "/api/v3/ticker/24hr"
        params = {"symbol": symbol}

        return self._request("GET", endpoint, params=params)

    def get_funding_rate(self, symbol: str = SYMBOL) -> Dict[str, Any]:
        """الحصول على معدل التمويل الحالي للعقود الآجلة"""
        # ملاحظة: يجب استخدام نقطة نهاية العقود الآجلة
        endpoint = "/fapi/v1/premiumIndex"
        params = {"symbol": symbol}
        # تغيير URL القاعدة لواجهة العقود الآجلة
        original_base = self.base_url
        self.base_url = "https://fapi.binance.com"

        try:
            result = self._request("GET", endpoint, params=params)
        finally:
            # إعادة URL القاعدة إلى الوضع الأصلي
            self.base_url = original_base

        return result

    def get_open_interest(self, symbol: str = SYMBOL) -> Dict[str, Any]:
        """الحصول على العقود المفتوحة"""
        # ملاحظة: يجب استخدام نقطة نهاية العقود الآجلة
        endpoint = "/fapi/v1/openInterest"
        params = {"symbol": symbol}
        # تغيير URL القاعدة لواجهة العقود الآجلة
        original_base = self.base_url
        self.base_url = "https://fapi.binance.com"

        try:
            result = self._request("GET", endpoint, params=params)
        finally:
            # إعادة URL القاعدة إلى الوضع الأصلي
            self.base_url = original_base

        return result

    def get_long_short_ratio(self, symbol: str = SYMBOL, period: str = "5m", limit: int = 500) -> List[Dict[str, Any]]:
        """الحصول على نسبة المراكز الطويلة/القصيرة"""
        # ملاحظة: يجب استخدام نقطة نهاية العقود الآجلة
        endpoint = "/futures/data/globalLongShortAccountRatio"
        params = {"symbol": symbol, "period": period, "limit": limit}
        # تغيير URL القاعدة لواجهة البيانات
        original_base = self.base_url
        self.base_url = "https://fapi.binance.com"

        try:
            result = self._request("GET", endpoint, params=params)
        finally:
            # إعادة URL القاعدة إلى الوضع الأصلي
            self.base_url = original_base

        return result

