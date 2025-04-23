"""
نظام تحليل وتداول سولانا - النقطة الرئيسية للنظام
"""

import time
import logging
import os
import argparse
import signal
import sys
from typing import Dict, Any

from api.binance_client import BinanceClient
from api.solana_client import SolanaClient
from signals.signal_generator import SignalGenerator
from signals.signal_processor import SignalProcessor
from utils.logger import setup_logger, SignalLogger
from utils.database import Database
from config import INDICATORS

# إعداد نظام التسجيل
logger = setup_logger()


class TradingSystem:
    def __init__(self):
        """
        تهيئة نظام التداول
        """
        logger.info("بدء تهيئة نظام التداول...")

        # تهيئة العملاء
        self.binance_client = BinanceClient()
        self.solana_client = SolanaClient()

        # تهيئة مولد ومعالج الإشارات
        self.signal_generator = SignalGenerator()
        self.signal_processor = SignalProcessor()

        # تهيئة قاعدة البيانات
        self.database = Database()

        # تهيئة مسجل الإشارات والقرارات
        self.signal_logger = SignalLogger()

        # حالة التشغيل
        self.is_running = False

        # تهيئة معالج إشارات النظام
        signal.signal(signal.SIGINT, self._handle_termination)
        signal.signal(signal.SIGTERM, self._handle_termination)

        logger.info("تم الانتهاء من تهيئة نظام التداول")

    def _handle_termination(self, signum, frame):
        """
        معالجة إشارة الإنهاء (Ctrl+C)
        """
        logger.info("تم استلام إشارة الإنهاء. جارٍ إيقاف النظام...")
        self.is_running = False

    def _store_market_data(self):
        """
        تخزين بيانات السوق الأساسية للتحليل التاريخي
        """
        try:
            # الحصول على بيانات السوق من Binance
            ticker = self.binance_client.get_ticker_24hr()

            # الحصول على بيانات إضافية
            oi_data = self.binance_client.get_open_interest()
            funding_data = self.binance_client.get_funding_rate()
            ls_ratio_data = self.binance_client.get_long_short_ratio(limit=1)

            # تجميع البيانات
            market_data = {
                "timestamp": int(time.time()),
                "price": float(ticker["lastPrice"]),
                "volume": float(ticker["volume"]),
                "open_interest": float(oi_data["openInterest"]),
                "funding_rate": float(funding_data["lastFundingRate"]),
                "long_short_ratio": float(ls_ratio_data[0]["longShortRatio"]) if ls_ratio_data else None
            }

            # تخزين البيانات في قاعدة البيانات
            self.database.store_market_data(market_data)

            logger.debug("تم تخزين بيانات السوق")
        except Exception as e:
            logger.error(f"خطأ في تخزين بيانات السوق: {e}")

    def start(self):
        """
        بدء تشغيل نظام التداول
        """
        logger.info("بدء تشغيل نظام التداول...")
        self.is_running = True

        # ملاحظة: هذه حلقة غير حاظرة تسمح بالاستجابة للإشارات الخارجية (مثل Ctrl+C)
        try:
            last_market_data_time = 0

            while self.is_running:
                current_time = int(time.time())

                # تخزين بيانات السوق كل 5 دقائق
                if current_time - last_market_data_time >= 300:
                    self._store_market_data()
                    last_market_data_time = current_time

                # توليد جميع الإشارات
                signals = self.signal_generator.get_all_signals()

                # تسجيل الإشارات
                for signal_name, signal in signals.items():
                    self.signal_logger.log_signal(signal)
                    self.database.store_signal(signal)

                # معالجة الإشارات
                decision = self.signal_processor.process_signals(signals)

                if decision:
                    # تسجيل القرار
                    self.signal_logger.log_decision(decision)
                    self.database.store_decision(decision)

                    # عرض ملخص القرار
                    decision_summary = self.signal_processor.get_decision_summary(decision)
                    logger.info(f"\n{decision_summary}")

                # انتظار قبل التكرار التالي
                # يمكن تعديل هذا حسب احتياجات النظام
                time.sleep(5)

        except Exception as e:
            logger.error(f"خطأ غير متوقع في حلقة التشغيل الرئيسية: {e}")
        finally:
            # إغلاق الموارد
            logger.info("جارٍ إغلاق نظام التداول...")
            self.database.close()

    def run_console(self):
        """
        تشغيل الوضع التفاعلي للنظام
        """
        print("\n=== نظام تحليل وتداول سولانا ===")
        print("اكتب 'help' للحصول على المساعدة")

        while True:
            try:
                command = input("\n> ").strip().lower()

                if command == "exit" or command == "quit":
                    print("جارٍ إنهاء النظام...")
                    break

                elif command == "help":
                    print("\nالأوامر المتاحة:")
                    print("  signals - عرض أحدث الإشارات")
                    print("  decision - عرض أحدث قرار")
                    print("  market - عرض بيانات السوق الحالية")
                    print("  update - تحديث الإشارات والقرارات")
                    print("  exit/quit - إنهاء النظام")

                elif command == "signals":
                    print("\n=== أحدث الإشارات ===")
                    signals = self.signal_generator.get_all_signals()

                    for name, signal in signals.items():
                        direction = "↑" if signal.direction > 0 else "↓" if signal.direction < 0 else "↔"
                        print(f"• {name}: {direction} (قوة: {abs(signal.strength):.2f}, ثقة: {signal.confidence:.2f})")

                elif command == "decision":
                    print("\n=== أحدث قرار ===")
                    signals = self.signal_generator.get_all_signals()
                    decision = self.signal_processor.process_signals(signals)

                    if decision:
                        summary = self.signal_processor.get_decision_summary(decision)
                        print(summary)
                    else:
                        print("لم يتم اتخاذ أي قرار حاليًا")

                elif command == "market":
                    print("\n=== بيانات السوق الحالية ===")
                    try:
                        ticker = self.binance_client.get_ticker_24hr()
                        oi_data = self.binance_client.get_open_interest()

                        price = float(ticker["lastPrice"])
                        change = float(ticker["priceChangePercent"])
                        volume = float(ticker["volume"])
                        oi = float(oi_data["openInterest"])

                        print(f"السعر الحالي: {price:.2f} USD")
                        print(f"نسبة التغيير (24 ساعة): {change:.2f}%")
                        print(f"حجم التداول (24 ساعة): {volume:.2f}")
                        print(f"العقود المفتوحة: {oi:.2f}")

                        # عرض بيانات إضافية
                        vwap = self.signal_generator.blockchain.calculate_vwap()
                        if vwap:
                            print(f"VWAP: {vwap.vwap:.2f} (البعد: {vwap.distance_from_vwap:.2f}%)")

                        ls_ratio = self.signal_generator.sentiment.get_long_short_ratio()
                        if ls_ratio:
                            print(f"نسبة المراكز الطويلة/القصيرة: {ls_ratio.ratio:.2f}")

                    except Exception as e:
                        print(f"خطأ في الحصول على بيانات السوق: {e}")

                elif command == "update":
                    print("جارٍ تحديث الإشارات...")
                    signals = self.signal_generator.get_all_signals()
                    decision = self.signal_processor.process_signals(signals)

                    print("تم التحديث بنجاح")

                    if decision:
                        summary = self.signal_processor.get_decision_summary(decision)
                        print(f"\n{summary}")

                else:
                    print(f"أمر غير معروف: {command}")

            except KeyboardInterrupt:
                print("\nجارٍ إنهاء النظام...")
                break
            except Exception as e:
                print(f"خطأ: {e}")


def parse_arguments():
    """
    تحليل معلمات سطر الأوامر
    """
    parser = argparse.ArgumentParser(description="نظام تحليل وتداول سولانا")

    parser.add_argument("--console", action="store_true", help="تشغيل النظام في وضع التحكم")
    parser.add_argument("--daemon", action="store_true", help="تشغيل النظام كخدمة خلفية")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    system = TradingSystem()

    if args.console:
        system.run_console()
    elif args.daemon:
        system.start()
    else:
        # الوضع الافتراضي: التحكم
        system.run_console()