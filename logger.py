"""
نظام التسجيل للنظام
"""

import logging
import os
from logging.handlers import RotatingFileHandler
import time
from datetime import datetime
import sys
from config import LOG_LEVEL, LOG_FILE
# في بداية الملف utils/logger.py
import io
import sys

# إنشاء فئة معالج خاصة للتعامل مع النص العبي
class EncodingStreamHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        try:
            msg = self.format(record)
            try:
                self.stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                # في حالة فشل الترميز، استخدم ترميز 'utf-8' مع تعيين 'replace'
                self.stream.write(msg.encode('utf-8', 'replace').decode('utf-8') + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


# ثم في دالة setup_logger() استخدم هذه الفئة الجديدة
console_handler = EncodingStreamHandler(sys.stdout)

def setup_logger() -> logging.Logger:
    """
    إعداد نظام التسجيل
    """
    # إنشاء مجلد للسجلات إذا لم يكن موجودًا
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # تحديد مستوى التسجيل
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    level = level_map.get(LOG_LEVEL, logging.INFO)

    # إعداد المسجل
    logger = logging.getLogger("solana_trading_system")
    logger.setLevel(level)

    # منع تكرار رسائل التسجيل
    if logger.handlers:
        return logger

    # تنسيق الرسائل
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    console_handler.stream.reconfigure(encoding='utf-8', errors='replace')  # تعيين الترميز وطريقة التعامل مع الأخطاء
    logger.addHandler(console_handler)

    # استخدام RotatingFileHandler للتعامل مع تدوير الملفات
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 ميجابايت كحد أقصى
        backupCount=5  # الاحتفاظ بـ 5 ملفات احتياطية
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info(f"=== بدء نظام تداول سولانا - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    return logger


class SignalLogger:
    """
    مسجل خاص للإشارات والقرارات
    """

    def __init__(self, base_path="logs"):
        self.base_path = base_path

        # إنشاء مجلد للسجلات إذا لم يكن موجودًا
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

        # إنشاء مجلد للإشارات
        self.signals_path = os.path.join(self.base_path, "signals")
        if not os.path.exists(self.signals_path):
            os.makedirs(self.signals_path)

        # إنشاء مجلد للقرارات
        self.decisions_path = os.path.join(self.base_path, "decisions")
        if not os.path.exists(self.decisions_path):
            os.makedirs(self.decisions_path)

    def log_signal(self, signal):
        """
        تسجيل إشارة في ملف
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(self.signals_path, f"signals_{date_str}.log")

        timestamp = time.strftime('%H:%M:%S', time.localtime(signal.timestamp))

        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"=== {timestamp} - {signal.name} ===\n")
            f.write(f"الاتجاه: {signal.direction}\n")
            f.write(f"القوة: {signal.strength}\n")
            f.write(f"الثقة: {signal.confidence}\n")
            f.write(f"الصلاحية: {signal.validity} ثانية\n")
            f.write("المكونات:\n")

            for component_name, component_data in signal.components.items():
                f.write(f"  • {component_name}: {component_data}\n")

            f.write("\n")

    def log_decision(self, decision):
        """
        تسجيل قرار في ملف
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(self.decisions_path, f"decisions_{date_str}.log")

        timestamp = time.strftime('%H:%M:%S', time.localtime(decision.timestamp))

        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"=== {timestamp} - قرار: {decision.action} ===\n")
            f.write(f"الثقة: {decision.confidence}\n")
            f.write(f"القوة: {decision.strength}\n")
            f.write(f"السبب: {decision.reason}\n")
            f.write("الإشارات المؤثرة:\n")

            for signal in decision.signals:
                direction = "↑" if signal.direction > 0 else "↓" if signal.direction < 0 else "↔"
                f.write(
                    f"  • {signal.name}: {direction} (قوة: {abs(signal.strength):.2f}, ثقة: {signal.confidence:.2f})\n")

            f.write("\n")