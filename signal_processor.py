"""
معالج الإشارات وتوليد قرارات التداول
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from signals.signal_generator import SignalData
from config import INDICATORS

logger = logging.getLogger(__name__)


@dataclass
class TradingDecision:
    timestamp: int
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # مستوى الثقة (0 إلى 1)
    signals: List[SignalData]  # الإشارات التي اعتمد عليها القرار
    reason: str  # سبب القرار
    strength: float  # قوة القرار (0 إلى 100)


class SignalProcessor:
    def __init__(self, confidence_threshold: float = 0.7, strength_threshold: float = 30.0):
        """
        معالج الإشارات

        المعلمات:
            confidence_threshold: عتبة الثقة للقرارات (0 إلى 1)
            strength_threshold: عتبة قوة الإشارة للقرارات (0 إلى 100)
        """
        self.confidence_threshold = confidence_threshold
        self.strength_threshold = strength_threshold
        self.last_decision = None

    def _calculate_signal_weights(self) -> Dict[str, float]:
        """
        حساب أوزان الإشارات استنادًا إلى سياق السوق

        هذه طريقة مبسطة - يمكن تعزيزها بمنطق أكثر تقدمًا
        """
        # أوزان افتراضية
        weights = {
            "ORDER_FLOW": 0.20,
            "BLOCKCHAIN_OI": 0.15,
            "MARKET_DEPTH": 0.20,
            "SENTIMENT": 0.15,
            "ON_CHAIN": 0.10,
            "SCALP": 0.20
        }

        # هنا يمكن إضافة منطق لتعديل الأوزان استنادًا إلى حالة السوق
        # مثلاً: زيادة وزن SENTIMENT في أوقات التقلبات العالية

        return weights

    def process_signals(self, signals: Dict[str, SignalData]) -> Optional[TradingDecision]:
        """
        معالجة الإشارات واتخاذ قرار التداول
        """
        if not signals:
            logger.warning("لا توجد إشارات متاحة للمعالجة")
            return None

        # التحقق من صلاحية الإشارات
        valid_signals = {}
        current_time = int(time.time())

        for name, signal in signals.items():
            if signal.timestamp + INDICATORS[name]["validity_period"] >= current_time:
                valid_signals[name] = signal

        if not valid_signals:
            logger.warning("لا توجد إشارات صالحة للمعالجة")
            return None

        # حساب أوزان الإشارات
        weights = self._calculate_signal_weights()

        # حساب المتوسط المرجح للاتجاه والقوة والثقة
        weighted_direction = 0.0
        weighted_strength = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0

        for name, signal in valid_signals.items():
            if name in weights:
                weight = weights[name]
                weighted_direction += signal.direction * weight
                weighted_strength += abs(signal.strength) * weight
                weighted_confidence += signal.confidence * weight
                total_weight += weight

        if total_weight == 0:
            logger.warning("لا يمكن حساب المتوسط المرجح: الوزن الكلي صفر")
            return None

        # تطبيع النتائج
        weighted_direction /= total_weight
        weighted_strength /= total_weight
        weighted_confidence /= total_weight

        # تقرير الاتجاه النهائي
        if weighted_direction > 0.3:
            action = "BUY"
        elif weighted_direction < -0.3:
            action = "SELL"
        else:
            action = "HOLD"

        # التحقق من العتبات
        if weighted_confidence < self.confidence_threshold or weighted_strength < self.strength_threshold:
            action = "HOLD"
            reason = f"لم تتجاوز الإشارة العتبات المطلوبة (الثقة: {weighted_confidence:.2f}, القوة: {weighted_strength:.2f})"
        else:
            # إنشاء شرح للسبب
            positive_signals = [name for name, signal in valid_signals.items() if signal.direction > 0]
            negative_signals = [name for name, signal in valid_signals.items() if signal.direction < 0]

            if action == "BUY":
                reason = f"إشارات إيجابية: {', '.join(positive_signals)}"
            elif action == "SELL":
                reason = f"إشارات سلبية: {', '.join(negative_signals)}"
            else:
                reason = "إشارات متضاربة أو غير حاسمة"

        # إنشاء قرار التداول
        decision = TradingDecision(
            timestamp=current_time,
            action=action,
            confidence=weighted_confidence,
            signals=list(valid_signals.values()),
            reason=reason,
            strength=weighted_strength
        )

        self.last_decision = decision
        return decision

    def get_decision_summary(self, decision: TradingDecision) -> str:
        """
        إنشاء ملخص لقرار التداول
        """
        if not decision:
            return "لا يوجد قرار متاح"

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(decision.timestamp))

        summary = []
        summary.append(f"=== قرار التداول: {decision.action} ===")
        summary.append(f"الوقت: {timestamp}")
        summary.append(f"الثقة: {decision.confidence:.2f}")
        summary.append(f"القوة: {decision.strength:.2f}")
        summary.append(f"السبب: {decision.reason}")
        summary.append("\nإشارات مؤثرة:")

        for signal in decision.signals:
            direction = "↑" if signal.direction > 0 else "↓" if signal.direction < 0 else "↔"
            summary.append(
                f"  • {signal.name}: {direction} (قوة: {abs(signal.strength):.2f}, ثقة: {signal.confidence:.2f})")

        return "\n".join(summary)