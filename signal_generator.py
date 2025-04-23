"""
منشئ الإشارات بناءً على المؤشرات
"""

import logging
import time
from typing import Dict, Any, List
from dataclasses import dataclass
import numpy as np

from indicators.order_flow import OrderFlowIndicators
from indicators.blockchain import BlockchainIndicators
from indicators.market_depth import MarketDepthIndicators
from indicators.sentiment import SentimentIndicators
from indicators.on_chain import OnChainIndicators
from config import INDICATORS

logger = logging.getLogger(__name__)


@dataclass
class SignalData:
    timestamp: int
    name: str  # اسم الإشارة
    strength: float  # قوة الإشارة (-100 إلى 100)
    direction: int  # 1 للشراء، -1 للبيع، 0 محايد
    confidence: float  # مستوى الثقة (0 إلى 1)
    validity: int  # مدة صلاحية الإشارة بالثواني
    components: Dict[str, Any]  # مكونات الإشارة


class SignalGenerator:
    def __init__(self):
        self.order_flow = OrderFlowIndicators()
        self.blockchain = BlockchainIndicators()
        self.market_depth = MarketDepthIndicators()
        self.sentiment = SentimentIndicators()
        self.on_chain = OnChainIndicators()

        self.last_update = {}  # آخر تحديث للإشارات
        self.signal_cache = {}  # ذاكرة التخزين المؤقت للإشارات

    def _should_update_signal(self, signal_name: str) -> bool:
        """
        التحقق مما إذا كان يجب تحديث الإشارة بناءً على فترة التحديث المحددة
        """
        if signal_name not in INDICATORS:
            return True  # تحديث دائمًا إذا لم تكن موجودة في الإعدادات

        update_interval = INDICATORS[signal_name]["update_interval"]
        last_update = self.last_update.get(signal_name, 0)
        current_time = int(time.time())

        return (current_time - last_update) >= update_interval

    def _is_signal_valid(self, signal_name: str) -> bool:
        """
        التحقق من صلاحية الإشارة
        """
        if signal_name not in self.signal_cache:
            return False

        validity_period = INDICATORS[signal_name]["validity_period"]
        signal_time = self.signal_cache[signal_name].timestamp
        current_time = int(time.time())

        return (current_time - signal_time) <= validity_period

    def generate_order_flow_signal(self) -> SignalData:
        """
        توليد إشارة تدفق الأوامر
        """
        if not self._should_update_signal("ORDER_FLOW") and self._is_signal_valid("ORDER_FLOW"):
            return self.signal_cache["ORDER_FLOW"]

        # جمع البيانات
        delta_data = self.order_flow.calculate_delta()
        footprint_data = self.order_flow.calculate_footprint()
        whale_data = self.order_flow.track_whale_transfers()

        # تحليل الدلتا
        delta = delta_data.delta
        delta_direction = 1 if delta > 0 else -1 if delta < 0 else 0
        delta_strength = min(abs(delta) / 100, 1.0)  # تطبيع القوة

        # تحليل الـ Footprint
        net_delta = sum(footprint_data.delta_by_level.values())
        footprint_direction = 1 if net_delta > 0 else -1 if net_delta < 0 else 0
        footprint_strength = min(abs(net_delta) / 200, 1.0)  # تطبيع القوة

        # تحليل تحويلات الحيتان
        whale_direction = 0
        whale_strength = 0.0

        if whale_data.transfers:
            # تحليل نسبة تدفقات CEX مقارنة بـ DEX
            if whale_data.cex_value > 0 or whale_data.dex_value > 0:
                net_flow = whale_data.dex_value - whale_data.cex_value

                # إذا كان التدفق من DEX أكثر من CEX، فهذه إشارة شرائية (تراكم)
                # وإذا كان التدفق إلى CEX أكثر من DEX، فهذه إشارة بيعية (توزيع)
                whale_direction = 1 if net_flow > 0 else -1 if net_flow < 0 else 0
                whale_strength = min(abs(net_flow) / whale_data.total_value if whale_data.total_value > 0 else 0, 1.0)

                # تعزيز قوة الإشارة إذا كان حجم التحويلات كبيرًا
                whale_strength = min(whale_strength * (whale_data.total_value / 100000), 1.0)

        # حساب الإشارة النهائية كما هو
        # توزيع الأوزان: 40% للدلتا، 30% للـ Footprint، 30% لتحويلات الحيتان
        signal_direction = round(0.4 * delta_direction + 0.3 * footprint_direction + 0.3 * whale_direction)
        signal_strength = (0.4 * delta_strength + 0.3 * footprint_strength + 0.3 * whale_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة
        confidence = 0.7  # قيمة افتراضية للتوضيح

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if delta_direction == footprint_direction and footprint_direction == whale_direction and delta_direction != 0:
            confidence = 0.9

        signal = SignalData(
            timestamp=int(time.time()),
            name="ORDER_FLOW",
            strength=signal_strength * direction,  # القوة مع الاتجاه
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["ORDER_FLOW"]["validity_period"],
            components={
                "delta": delta_data,
                "footprint": footprint_data,
                "whale_transfers": whale_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["ORDER_FLOW"] = signal
        self.last_update["ORDER_FLOW"] = int(time.time())

        return signal

    def generate_blockchain_oi_signal(self) -> SignalData:
        """
        توليد إشارة البلوكتشين و Open Interest
        """
        if not self._should_update_signal("BLOCKCHAIN_OI") and self._is_signal_valid("BLOCKCHAIN_OI"):
            return self.signal_cache["BLOCKCHAIN_OI"]

        # جمع البيانات
        whale_data = self.order_flow.track_whale_transfers()
        oi_data = self.blockchain.get_open_interest()
        vwap_data = self.blockchain.calculate_vwap()

        # تحليل تحويلات الحيتان
        whale_direction = 0
        whale_strength = 0.0

        if whale_data.transfers:
            # تحليل اتجاه تحويلات الحيتان
            whale_strength = min(whale_data.total_value / 1000000, 1.0)
            whale_direction = 1  # افتراضي للتوضيح

        # تحليل العقود المفتوحة
        oi_direction = 1 if oi_data.change_24h > 0 else -1 if oi_data.change_24h < 0 else 0
        oi_strength = min(abs(oi_data.change_24h) / 10, 1.0)  # تطبيع القوة

        # تحليل VWAP
        vwap_direction = 1 if vwap_data.distance_from_vwap < 0 else -1 if vwap_data.distance_from_vwap > 0 else 0
        vwap_strength = min(abs(vwap_data.distance_from_vwap) / 5, 1.0)  # تطبيع القوة

        # حساب الإشارة النهائية
        # توزيع الأوزان: 30% للـ Whale، 40% للـ OI، 30% للـ VWAP
        signal_direction = round(0.3 * whale_direction + 0.4 * oi_direction + 0.3 * vwap_direction)
        signal_strength = (0.3 * whale_strength + 0.4 * oi_strength + 0.3 * vwap_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة
        confidence = 0.7  # قيمة افتراضية للتوضيح

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if whale_direction == oi_direction and oi_direction == vwap_direction and whale_direction != 0:
            confidence = 0.9

        signal = SignalData(
            timestamp=int(time.time()),
            name="BLOCKCHAIN_OI",
            strength=signal_strength * direction,
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["BLOCKCHAIN_OI"]["validity_period"],
            components={
                "whale_transfers": whale_data,
                "open_interest": oi_data,
                "vwap": vwap_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["BLOCKCHAIN_OI"] = signal
        self.last_update["BLOCKCHAIN_OI"] = int(time.time())

        return signal

    def generate_market_depth_signal(self) -> SignalData:
        """
        توليد إشارة عمق السوق
        """
        if not self._should_update_signal("MARKET_DEPTH") and self._is_signal_valid("MARKET_DEPTH"):
            return self.signal_cache["MARKET_DEPTH"]

        # جمع البيانات
        iceberg_data = self.market_depth.detect_icebergs()
        cvd_data = self.market_depth.calculate_cvd()
        spoofing_data = self.market_depth.detect_spoofing()

        # تحليل Iceberg
        iceberg_direction = 0
        iceberg_strength = 0.0

        if iceberg_data.detected_levels:
            buy_volume = sum(
                level["estimated_total"] for level in iceberg_data.detected_levels if level["side"] == "buy")
            sell_volume = sum(
                level["estimated_total"] for level in iceberg_data.detected_levels if level["side"] == "sell")

            if buy_volume > sell_volume:
                iceberg_direction = 1
                iceberg_strength = min((buy_volume - sell_volume) / buy_volume, 1.0)
            elif sell_volume > buy_volume:
                iceberg_direction = -1
                iceberg_strength = min((sell_volume - buy_volume) / sell_volume, 1.0)

        # تحليل CVD
        cvd_direction = 1 if cvd_data.cvd_change > 0 else -1 if cvd_data.cvd_change < 0 else 0
        cvd_strength = min(abs(cvd_data.cvd_change) / 100, 1.0)  # تطبيع القوة

        # تحليل Spoofing
        spoofing_direction = 0
        spoofing_strength = 0.0

        if spoofing_data.detected_levels:
            buy_spoof = sum(level["original_quantity"] * level["disappearance_ratio"]
                            for level in spoofing_data.detected_levels if level["side"] == "buy")
            sell_spoof = sum(level["original_quantity"] * level["disappearance_ratio"]
                             for level in spoofing_data.detected_levels if level["side"] == "sell")

            # Spoofing يكون في الاتجاه المعاكس
            if buy_spoof > sell_spoof:
                spoofing_direction = -1  # إشارة بيع
                spoofing_strength = min(buy_spoof / (buy_spoof + sell_spoof), 1.0)
            elif sell_spoof > buy_spoof:
                spoofing_direction = 1  # إشارة شراء
                spoofing_strength = min(sell_spoof / (buy_spoof + sell_spoof), 1.0)

        # حساب الإشارة النهائية
        # توزيع الأوزان: 30% للـ Iceberg، 40% للـ CVD، 30% للـ Spoofing
        signal_direction = round(0.3 * iceberg_direction + 0.4 * cvd_direction + 0.3 * spoofing_direction)
        signal_strength = (0.3 * iceberg_strength + 0.4 * cvd_strength + 0.3 * spoofing_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة
        confidence = 0.7  # قيمة افتراضية للتوضيح

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if (iceberg_direction == cvd_direction and cvd_direction != 0) or \
                (cvd_direction == spoofing_direction and cvd_direction != 0):
            confidence = 0.85

        signal = SignalData(
            timestamp=int(time.time()),
            name="MARKET_DEPTH",
            strength=signal_strength * direction,
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["MARKET_DEPTH"]["validity_period"],
            components={
                "iceberg": iceberg_data,
                "cvd": cvd_data,
                "spoofing": spoofing_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["MARKET_DEPTH"] = signal
        self.last_update["MARKET_DEPTH"] = int(time.time())

        return signal

    def generate_sentiment_signal(self) -> SignalData:
        """
        توليد إشارة المشاعر
        """
        if not self._should_update_signal("SENTIMENT") and self._is_signal_valid("SENTIMENT"):
            return self.signal_cache["SENTIMENT"]

        # جمع البيانات
        ls_ratio_data = self.sentiment.get_long_short_ratio()
        funding_data = self.sentiment.get_funding_rate()
        footprint_data = self.order_flow.calculate_footprint()

        # تحليل نسبة Long/Short
        ls_direction = 0
        ls_strength = 0.0

        if ls_ratio_data.ratio != 1.0:
            if ls_ratio_data.ratio > 1.0:
                # نسبة المراكز الطويلة أكبر - إشارة محتملة للبيع (عكسية)
                ls_direction = -1
                ls_strength = min((ls_ratio_data.ratio - 1) / 2, 1.0)
            else:
                # نسبة المراكز القصيرة أكبر - إشارة محتملة للشراء (عكسية)
                ls_direction = 1
                ls_strength = min((1 - ls_ratio_data.ratio) / 0.5, 1.0)

        # تحليل معدل التمويل
        funding_direction = -1 if funding_data.funding_rate > 0 else 1 if funding_data.funding_rate < 0 else 0
        funding_strength = min(abs(funding_data.funding_rate) * 100, 1.0)  # تطبيع القوة

        # تحليل الـ Footprint
        net_delta = sum(footprint_data.delta_by_level.values())
        footprint_direction = 1 if net_delta > 0 else -1 if net_delta < 0 else 0
        footprint_strength = min(abs(net_delta) / 200, 1.0)  # تطبيع القوة

        # حساب الإشارة النهائية
        # توزيع الأوزان: 40% للـ L/S Ratio، 30% للـ Funding، 30% للـ Footprint
        signal_direction = round(0.4 * ls_direction + 0.3 * funding_direction + 0.3 * footprint_direction)
        signal_strength = (0.4 * ls_strength + 0.3 * funding_strength + 0.3 * footprint_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة
        confidence = 0.7  # قيمة افتراضية للتوضيح

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if ls_direction == funding_direction and funding_direction != 0:
            confidence = 0.85
        if ls_direction == funding_direction and funding_direction == footprint_direction and ls_direction != 0:
            confidence = 0.95

        signal = SignalData(
            timestamp=int(time.time()),
            name="SENTIMENT",
            strength=signal_strength * direction,
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["SENTIMENT"]["validity_period"],
            components={
                "long_short_ratio": ls_ratio_data,
                "funding_rate": funding_data,
                "footprint": footprint_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["SENTIMENT"] = signal
        self.last_update["SENTIMENT"] = int(time.time())

        return signal

    def generate_onchain_signal(self) -> SignalData:
        """
        توليد إشارة معاملات البلوكتشين
        """
        if not self._should_update_signal("ON_CHAIN") and self._is_signal_valid("ON_CHAIN"):
            return self.signal_cache["ON_CHAIN"]

        # جمع البيانات
        onchain_data = self.on_chain.get_onchain_metrics()

        # تحليل معاملات البلوكتشين - نهج مبسط للتوضيح
        # في التطبيق الحقيقي، يجب مقارنة البيانات الحالية مع متوسط تاريخي

        # تحليل TPS
        tps_baseline = 1000  # خط أساس تقديري لـ Solana
        tps_direction = 1 if onchain_data.tps > tps_baseline else -1 if onchain_data.tps < tps_baseline * 0.7 else 0
        tps_strength = min(abs(onchain_data.tps - tps_baseline) / tps_baseline, 1.0)

        # تحليل عدد المعاملات
        tx_baseline = 50  # مثال: نتوقع 50 معاملة في عينة
        tx_direction = 1 if onchain_data.transactions_count > tx_baseline else -1 if onchain_data.transactions_count < tx_baseline * 0.7 else 0
        tx_strength = min(abs(onchain_data.transactions_count - tx_baseline) / tx_baseline, 1.0)

        # تحليل العناوين النشطة
        addr_baseline = 1000  # مثال: نتوقع 1000 عنوان نشط
        addr_direction = 1 if onchain_data.active_addresses > addr_baseline else -1 if onchain_data.active_addresses < addr_baseline * 0.7 else 0
        addr_strength = min(abs(onchain_data.active_addresses - addr_baseline) / addr_baseline, 1.0)

        # حساب الإشارة النهائية
        # توزيع الأوزان: 30% للمعاملات، 40% للـ TPS، 30% للعناوين النشطة
        signal_direction = round(0.3 * tx_direction + 0.4 * tps_direction + 0.3 * addr_direction)
        signal_strength = (0.3 * tx_strength + 0.4 * tps_strength + 0.3 * addr_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة
        confidence = 0.7  # قيمة افتراضية للتوضيح

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if tx_direction == tps_direction and tps_direction == addr_direction and tx_direction != 0:
            confidence = 0.9

        signal = SignalData(
            timestamp=int(time.time()),
            name="ON_CHAIN",
            strength=signal_strength * direction,
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["ON_CHAIN"]["validity_period"],
            components={
                "onchain_metrics": onchain_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["ON_CHAIN"] = signal
        self.last_update["ON_CHAIN"] = int(time.time())

        return signal

    def generate_scalp_signal(self) -> SignalData:
        """
        توليد إشارة السكالب السريع
        """
        if not self._should_update_signal("SCALP") and self._is_signal_valid("SCALP"):
            return self.signal_cache["SCALP"]

        # جمع البيانات
        delta_data = self.order_flow.calculate_delta()
        iceberg_data = self.market_depth.detect_icebergs()
        whale_data = self.order_flow.track_whale_transfers()

        # تحليل الدلتا
        delta = delta_data.delta
        delta_direction = 1 if delta > 0 else -1 if delta < 0 else 0
        delta_strength = min(abs(delta) / 100, 1.0)  # تطبيع القوة

        # تحليل Iceberg
        iceberg_direction = 0
        iceberg_strength = 0.0

        if iceberg_data.detected_levels:
            buy_volume = sum(
                level["estimated_total"] for level in iceberg_data.detected_levels if level["side"] == "buy")
            sell_volume = sum(
                level["estimated_total"] for level in iceberg_data.detected_levels if level["side"] == "sell")

            if buy_volume > sell_volume:
                iceberg_direction = 1
                iceberg_strength = min((buy_volume - sell_volume) / buy_volume, 1.0)
            elif sell_volume > buy_volume:
                iceberg_direction = -1
                iceberg_strength = min((sell_volume - buy_volume) / sell_volume, 1.0)

        # تحليل تحويلات الحيتان
        whale_direction = 0
        whale_strength = 0.0

        if whale_data.transfers:
            whale_strength = min(whale_data.total_value / 1000000, 1.0)
            whale_direction = 1  # افتراضي للتوضيح

        # حساب الإشارة النهائية - سكالب سريع يحتاج تفاعل أسرع
        # توزيع الأوزان: 50% للدلتا، 30% للـ Iceberg، 20% لتحويلات الحيتان
        signal_direction = round(0.5 * delta_direction + 0.3 * iceberg_direction + 0.2 * whale_direction)
        signal_strength = (0.5 * delta_strength + 0.3 * iceberg_strength + 0.2 * whale_strength) * 100

        # تعديل الاتجاه بناءً على الإشارة النهائية
        if signal_direction > 0:
            direction = 1
        elif signal_direction < 0:
            direction = -1
        else:
            direction = 0

        # حساب مستوى الثقة - سكالب يحتاج ثقة أعلى
        confidence = 0.65  # قيمة افتراضية للسكالب

        # تعديل مستوى الثقة إذا كانت المؤشرات متوافقة
        if delta_direction == iceberg_direction and delta_direction != 0:
            confidence = 0.8
        if delta_direction == iceberg_direction and iceberg_direction == whale_direction and delta_direction != 0:
            confidence = 0.95

        signal = SignalData(
            timestamp=int(time.time()),
            name="SCALP",
            strength=signal_strength * direction,
            direction=direction,
            confidence=confidence,
            validity=INDICATORS["SCALP"]["validity_period"],
            components={
                "delta": delta_data,
                "iceberg": iceberg_data,
                "whale_transfers": whale_data
            }
        )

        # تخزين الإشارة والوقت
        self.signal_cache["SCALP"] = signal
        self.last_update["SCALP"] = int(time.time())

        return signal

    def get_all_signals(self) -> Dict[str, SignalData]:
        """
        الحصول على جميع الإشارات المتاحة
        """
        signals = {}

        # توليد جميع الإشارات المتاحة
        if "ORDER_FLOW" in INDICATORS:
            signals["ORDER_FLOW"] = self.generate_order_flow_signal()

        if "BLOCKCHAIN_OI" in INDICATORS:
            signals["BLOCKCHAIN_OI"] = self.generate_blockchain_oi_signal()

        if "MARKET_DEPTH" in INDICATORS:
            signals["MARKET_DEPTH"] = self.generate_market_depth_signal()

        if "SENTIMENT" in INDICATORS:
            signals["SENTIMENT"] = self.generate_sentiment_signal()

        if "ON_CHAIN" in INDICATORS:
            signals["ON_CHAIN"] = self.generate_onchain_signal()

        if "SCALP" in INDICATORS:
            signals["SCALP"] = self.generate_scalp_signal()

        return signals