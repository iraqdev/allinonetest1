"""
ملف التكوين للنظام
"""

# إعدادات Binance API
BINANCE_API_KEY = "tD7nUk2VsgfoixMPGUCg4nM343Y7Fb2vSfvmeJvqPWtUxArW7lNlrzhBveL8PmJk"  # يجب استبدالها بمفتاح API الخاص بك
BINANCE_SECRET_KEY = "GYtTNJ63XXNHaytK3fWdsEJ7bGYuMPD98v6bnRGUJXDosaglt9lqYTYuTXejMfQD"  # يجب استبدالها بالمفتاح السري الخاص بك

# إعدادات Solana
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"

# إعدادات العملة
SYMBOL = "SOLUSDT"  # رمز زوج التداول

# إعدادات المؤشرات وفترات التحديث (بالثواني)
INDICATORS = {
    "ORDER_FLOW": {
        "update_interval": 60,  # كل دقيقة
        "validity_period": 120,  # صالحة لمدة دقيقتين
        "components": ["delta", "footprint", "whale_transfers"]
    },
    "BLOCKCHAIN_OI": {
        "update_interval": 120,  # كل دقيقتين
        "validity_period": 180,  # صالحة لمدة 3 دقائق
        "components": ["whale_transfers", "open_interest", "vwap"]
    },
    "MARKET_DEPTH": {
        "update_interval": 60,  # كل دقيقة
        "validity_period": 120,  # صالحة لمدة دقيقتين
        "components": ["iceberg", "cvd", "spoofing"]
    },
    "SENTIMENT": {
        "update_interval": 180,  # كل 3 دقائق
        "validity_period": 180,  # صالحة لمدة 3 دقائق
        "components": ["long_short_ratio", "funding_rate", "footprint"]
    },
    "ON_CHAIN": {
        "update_interval": 120,  # كل دقيقتين
        "validity_period": 180,  # صالحة لمدة 3 دقائق
        "components": ["transactions", "tps", "active_addresses"]
    },
    "SCALP": {
        "update_interval": 60,  # كل دقيقة
        "validity_period": 120,  # صالحة لمدة دقيقتين
        "components": ["delta", "iceberg", "whale_transfers"]
    }
}

# إعدادات التسجيل
LOG_LEVEL = "INFO"
LOG_FILE = "trading_system.log"

# عتبات الحيتان (بالدولار)
WHALE_THRESHOLD = 100000  # اعتبار تحويل يتجاوز 100 ألف دولار من تحويلات الحيتان