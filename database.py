"""
معالج قاعدة البيانات للنظام
"""

import os
import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime


class Database:
    def __init__(self, db_path="data/trading_system.db"):
        """
        تهيئة قاعدة البيانات

        المعلمات:
            db_path: مسار ملف قاعدة البيانات
        """
        # إنشاء مجلد للبيانات إذا لم يكن موجودًا
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        self.conn = None

        # إنشاء اتصال وإعداد الجداول
        self._connect()
        self._setup_tables()

    def _connect(self):
        """إنشاء اتصال بقاعدة البيانات"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # للحصول على النتائج كقواميس

    def _setup_tables(self):
        """إنشاء جداول قاعدة البيانات إذا لم تكن موجودة"""
        cursor = self.conn.cursor()

        # جدول الإشارات
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            name TEXT NOT NULL,
            strength REAL NOT NULL,
            direction INTEGER NOT NULL,
            confidence REAL NOT NULL,
            validity INTEGER NOT NULL,
            components TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        ''')

        # جدول قرارات التداول
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            action TEXT NOT NULL,
            confidence REAL NOT NULL,
            strength REAL NOT NULL,
            reason TEXT NOT NULL,
            signals TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        ''')

        # جدول بيانات السوق للتحليل التاريخي
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp INTEGER NOT NULL,
            price REAL NOT NULL,
            volume REAL NOT NULL,
            open_interest REAL,
            funding_rate REAL,
            long_short_ratio REAL,
            created_at TEXT NOT NULL
        )
        ''')

        self.conn.commit()

    def store_signal(self, signal) -> int:
        """
        تخزين إشارة في قاعدة البيانات

        المعلمات:
            signal: كائن الإشارة

        العائد:
            id: معرف الإشارة المخزنة
        """
        cursor = self.conn.cursor()

        # تحويل مكونات الإشارة إلى JSON لتخزينها
        components_json = json.dumps(signal.components, default=lambda o: o.__dict__)

        cursor.execute(
            '''
            INSERT INTO signals (
                timestamp, name, strength, direction, confidence, validity, components, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                signal.timestamp,
                signal.name,
                signal.strength,
                signal.direction,
                signal.confidence,
                signal.validity,
                components_json,
                datetime.now().isoformat()
            )
        )

        self.conn.commit()
        return cursor.lastrowid

    def store_decision(self, decision) -> int:
        """
        تخزين قرار في قاعدة البيانات

        المعلمات:
            decision: كائن القرار

        العائد:
            id: معرف القرار المخزن
        """
        cursor = self.conn.cursor()

        # تحويل الإشارات إلى JSON لتخزينها
        signals_json = json.dumps([s.__dict__ for s in decision.signals], default=lambda o: o.__dict__)

        cursor.execute(
            '''
            INSERT INTO decisions (
                timestamp, action, confidence, strength, reason, signals, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                decision.timestamp,
                decision.action,
                decision.confidence,
                decision.strength,
                decision.reason,
                signals_json,
                datetime.now().isoformat()
            )
        )

        self.conn.commit()
        return cursor.lastrowid

    def store_market_data(self, data: Dict[str, Any]) -> int:
        """
        تخزين بيانات السوق في قاعدة البيانات

        المعلمات:
            data: بيانات السوق (قاموس)

        العائد:
            id: معرف البيانات المخزنة
        """
        cursor = self.conn.cursor()

        cursor.execute(
            '''
            INSERT INTO market_data (
                timestamp, price, volume, open_interest, funding_rate, long_short_ratio, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                data.get("timestamp", int(time.time())),
                data.get("price", 0.0),
                data.get("volume", 0.0),
                data.get("open_interest"),
                data.get("funding_rate"),
                data.get("long_short_ratio"),
                datetime.now().isoformat()
            )
        )

        self.conn.commit()
        return cursor.lastrowid

    def get_recent_signals(self, limit: int = 10, signal_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        الحصول على أحدث الإشارات

        المعلمات:
            limit: عدد الإشارات المطلوبة
            signal_type: نوع الإشارات المطلوبة (اختياري)

        العائد:
            قائمة بالإشارات
        """
        cursor = self.conn.cursor()

        if signal_type:
            cursor.execute(
                "SELECT * FROM signals WHERE name = ? ORDER BY timestamp DESC LIMIT ?",
                (signal_type, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        signals = []

        for row in rows:
            signal = dict(row)
            signal["components"] = json.loads(signal["components"])
            signals.append(signal)

        return signals

    def get_recent_decisions(self, limit: int = 10, action: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        الحصول على أحدث القرارات

        المعلمات:
            limit: عدد القرارات المطلوبة
            action: نوع القرار المطلوب (اختياري)

        العائد:
            قائمة بالقرارات
        """
        cursor = self.conn.cursor()

        if action:
            cursor.execute(
                "SELECT * FROM decisions WHERE action = ? ORDER BY timestamp DESC LIMIT ?",
                (action, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        decisions = []

        for row in rows:
            decision = dict(row)
            decision["signals"] = json.loads(decision["signals"])
            decisions.append(decision)

        return decisions

    def get_market_data(self, start_time: int, end_time: int = None) -> List[Dict[str, Any]]:
        """
        الحصول على بيانات السوق في فترة زمنية معينة

        المعلمات:
            start_time: وقت البداية (timestamp)
            end_time: وقت النهاية (timestamp, اختياري)

        العائد:
            قائمة ببيانات السوق
        """
        cursor = self.conn.cursor()

        if end_time is None:
            end_time = int(time.time())

        cursor.execute(
            "SELECT * FROM market_data WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (start_time, end_time)
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def close(self):
        """إغلاق اتصال قاعدة البيانات"""
        if self.conn:
            self.conn.close()
            self.conn = None