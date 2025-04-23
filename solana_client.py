"""
واجهة الاتصال مع شبكة سولانا
"""

import time
import logging
import json
import uuid
from typing import Dict, Any, List, Optional
import requests
from dataclasses import dataclass

from config import SOLANA_RPC_URL

logger = logging.getLogger(__name__)


@dataclass
class TransactionInfo:
    signature: str
    slot: int
    block_time: int
    fee: int
    lamports: Optional[int] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    is_success: bool = True
    tx_type: Optional[str] = None
    program_id: Optional[str] = None
    instructions_data: Optional[list] = None


class SolanaClient:
    def __init__(self, rpc_url: str = None):
        """تهيئة عميل سولانا"""
        # تعديل عنوان RPC للسماح بتخصيص نقاط نهاية مختلفة
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"

        # قائمة بنقاط النهاية البديلة إذا فشلت النقطة الأساسية
        self.fallback_endpoints = [
            "https://solana-api.projectserum.com",
            "https://solana-mainnet.g.alchemy.com/v2/demo",
            "https://rpc.ankr.com/solana"
        ]

        # تتبع عدد الطلبات لكل ثانية للمساعدة في تجنب تجاوز الحد
        self.request_count = 0
        self.request_time = time.time()
        self.max_requests_per_second = 5  # تحديد الحد الأقصى للطلبات في الثانية

    def _make_request(self, method: str, params: List = None) -> Any:
        """إرسال طلب إلى Solana RPC API مع آلية متطورة للتعامل مع حدود الطلبات"""
        import uuid  # تأكد من استيراد uuid

        retry_count = 0
        max_retries = 3
        base_delay = 2  # ثانيتان

        # إنشاء نسخة من قائمة نقاط النهاية لاستخدامها في المحاولات
        endpoints = [self.rpc_url] + self.fallback_endpoints
        current_endpoint_index = 0

        while retry_count <= max_retries:
            # اختيار نقطة النهاية الحالية
            current_endpoint = endpoints[current_endpoint_index % len(endpoints)]

            try:
                # إضافة تأخير قبل كل طلب لتجنب تجاوز الحد
                if retry_count > 0:
                    # استراتيجية تأخير تصاعدية (exponential backoff)
                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.info(f"الانتظار لمدة {delay} ثوانٍ قبل إعادة المحاولة ({retry_count}/{max_retries})")
                    time.sleep(delay)

                payload = {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": method,
                    "params": params or []
                }

                headers = {
                    "Content-Type": "application/json"
                }

                logger.debug(f"إرسال طلب إلى {current_endpoint}: {method}")
                response = requests.post(current_endpoint, headers=headers, json=payload, timeout=30)

                # التعامل مع خطأ Rate Limit
                if response.status_code == 429:
                    logger.warning(f"تم تجاوز الحد المسموح به من الطلبات على {current_endpoint}.")

                    # تحاول استخدام نقطة نهاية بديلة قبل زيادة عداد المحاولات
                    current_endpoint_index += 1

                    # إذا جربنا جميع نقاط النهاية وعدنا إلى الأصلية، زيادة عداد المحاولات
                    if current_endpoint_index % len(endpoints) == 0:
                        retry_count += 1

                    # احصل على وقت الانتظار من الرأس إن وجد، وإلا استخدم تأخير تصاعدي
                    retry_delay = int(response.headers.get("Retry-After", 2))
                    logger.warning(f"الانتظار لمدة {retry_delay} ثوانٍ قبل المحاولة التالية.")
                    time.sleep(retry_delay)
                    continue

                # التحقق من الاستجابة لأي أخطاء أخرى
                response.raise_for_status()

                result = response.json()
                if "error" in result:
                    error = result["error"]

                    # إذا كان الخطأ يتعلق بالقيود، حاول نقطة نهاية أخرى
                    if "rate limit" in str(error).lower() or "too many" in str(error).lower():
                        logger.warning(f"قيود معدل الطلبات على {current_endpoint}: {error}")
                        current_endpoint_index += 1
                        continue

                    logger.error(f"خطأ RPC سولانا: {error}")
                    raise Exception(f"خطأ RPC سولانا: {error}")

                # نجاح! إرجاع النتيجة
                return result["result"]

            except requests.exceptions.RequestException as e:
                logger.warning(f"خطأ في طلب سولانا ({current_endpoint}): {str(e)}")

                # تجربة نقطة نهاية أخرى قبل زيادة عداد المحاولات
                current_endpoint_index += 1

                # إذا جربنا جميع نقاط النهاية وعدنا إلى الأصلية، زيادة عداد المحاولات
                if current_endpoint_index % len(endpoints) == 0:
                    retry_count += 1

                # إذا استنفدنا جميع المحاولات، ارفع الخطأ
                if retry_count > max_retries:
                    logger.error(f"فشلت كل المحاولات بعد تجربة {len(endpoints)} نقاط نهاية و {max_retries} محاولات")
                    raise Exception(f"خطأ في طلب سولانا: {str(e)}")

                # استمرار إلى المحاولة التالية
                continue

    def get_transactions(self, limit: int = 100) -> List[TransactionInfo]:
        """الحصول على أحدث المعاملات بطريقة تحافظ على حدود الطلبات"""
        try:
            # عنوان برنامج نظام سولانا (ستحتوي معظم المعاملات على هذا البرنامج)
            system_program_address = "11111111111111111111111111111111"

            # الحصول على التوقيعات للمعاملات الأخيرة في دفعة واحدة
            # تقليل عدد الطلبات عن طريق زيادة حد التوقيعات للحصول عليها مرة واحدة
            signatures_options = {
                "limit": min(limit, 25)  # تحديد عدد التوقيعات للحد من الطلبات
            }

            signatures_result = self._make_request(
                "getSignaturesForAddress",
                [system_program_address, signatures_options]
            )

            if not signatures_result:
                logger.warning("لم يتم العثور على توقيعات حديثة")
                return []

            # الحصول على تفاصيل المعاملات في دفعة واحدة لتقليل عدد الطلبات
            batch_size = 5  # عدد المعاملات للحصول عليها في كل دفعة
            transactions = []

            # معالجة التوقيعات على دفعات
            for i in range(0, min(len(signatures_result), limit), batch_size):
                batch_signatures = signatures_result[i:i + batch_size]

                # إدخال تأخير بين الدفعات لتجنب تجاوز الحد
                if i > 0:
                    time.sleep(1)  # ثانية واحدة بين الدفعات

                # جمع التوقيعات لهذه الدفعة
                current_batch = [sig_info["signature"] for sig_info in batch_signatures]

                # استخدام getMultipleAccounts بدلاً من العديد من الاستدعاءات المنفصلة
                # ملاحظة: لا يمكن استخدام getMultipleAccounts للمعاملات، لذلك سنستخدم دفعات معالجة

                for signature in current_batch:
                    try:
                        # الحصول على تفاصيل المعاملة باستخدام التوقيع
                        tx_options = {"encoding": "json", "maxSupportedTransactionVersion": 0}

                        # إضافة تأخير صغير بين استدعاءات API في نفس الدفعة
                        time.sleep(0.2)  # 200 مللي ثانية بين كل معاملة

                        tx_response = self._make_request("getTransaction", [signature, tx_options])

                        if not tx_response:
                            logger.warning(f"لا يمكن استرداد المعاملة للتوقيع: {signature}")
                            continue

                        # استخراج معلومات المعاملة
                        tx_info = TransactionInfo(
                            signature=signature,
                            slot=tx_response.get("slot", 0),
                            block_time=tx_response.get("blockTime", int(time.time())),
                            fee=tx_response.get("meta", {}).get("fee", 0),
                            is_success=tx_response.get("meta", {}).get("err") is None
                        )

                        # استخراج معلومات التحويل إذا كانت متوفرة
                        if "transaction" in tx_response and "message" in tx_response["transaction"]:
                            message = tx_response["transaction"]["message"]

                            if "instructions" in message:
                                instructions = message["instructions"]

                                for instr in instructions:
                                    if isinstance(instr, dict) and "parsed" in instr:
                                        parsed = instr["parsed"]

                                        if isinstance(parsed, dict) and "type" in parsed and parsed[
                                            "type"] == "transfer":
                                            info = parsed.get("info", {})
                                            tx_info.from_address = info.get("source")
                                            tx_info.to_address = info.get("destination")
                                            tx_info.lamports = info.get("lamports")
                                            break

                        transactions.append(tx_info)

                    except Exception as e:
                        logger.warning(f"خطأ في معالجة المعاملة {signature}: {str(e)}")
                        # استمرار في المعاملة التالية بدلاً من التوقف

            logger.info(f"تم استرداد {len(transactions)} معاملة بنجاح")
            return transactions

        except Exception as e:
            logger.error(f"خطأ عام في الحصول على المعاملات: {str(e)}")
            raise

    def get_tps(self) -> float:
        """حساب المعاملات في الثانية (TPS)"""
        performance = self._make_request("getRecentPerformanceSamples", [1])

        if not performance:
            return 0.0

        sample = performance[0]
        # عدد المعاملات مقسوماً على المدة بالثواني
        tps = sample.get("numTransactions", 0) / sample.get("samplePeriodSecs", 1)
        return tps

    def _is_cex_address(self, address: str) -> bool:
        """
        التحقق ما إذا كان العنوان ينتمي إلى منصة تبادل مركزية (CEX)
        """
        # قائمة عناوين محافظ CEX المعروفة
        cex_addresses = {
            # Binance
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM": "Binance",
            "BSxLLQWFbNwDrK1PvNQbJxZeqkRc5LjvNi8vJJWJigHc": "Binance",
            "GbTQKhL7BCTvuYetJQeQZgGTqEHM2rFZVUdKPvSKaM2B": "Binance",
            # OKX
            "GJR8pNeRDWNWZ6Wy5Eix1emxNRwj8xrQmCJiKCF3GTG1": "OKX",
            "2tUokhMnqAJgP5uv5QKNfa1UA5GhPfgSJ4krk2phPvMH": "OKX",
            # Kucoin
            "2vRqFpAVTpz46zUPkQvPqJYLszwuTdPb3vBqTJLHgrvm": "Kucoin",
            # FTX (now bankrupt, but still useful for historical data)
            "2mCTG7jRoHG8xQjS3xjrC5vQBzMJYzwBmJFXKJ1r7Zk5": "FTX",
            # Coinbase
            "3FuYPMXJHVF8UQcZCCchG3uQvNx8FD8aQbT8zJ9JKBpj": "Coinbase",
        }
        return address in cex_addresses

    def _is_dex_program_id(self, program_id: str) -> bool:
        """
        التحقق ما إذا كان معرف البرنامج ينتمي إلى DEX
        """
        # قائمة معرفات برامج DEX المعروفة
        dex_program_ids = {
            # Serum DEX
            "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin": "Serum",
            # Raydium
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium",
            # Orca
            "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Orca",
            # Saber
            "SSwpkEEcbUqx4vtoEByFjSkhKdCT862DNVb52nZg1UZ": "Saber",
        }
        return program_id in dex_program_ids

    def _analyze_transaction_type(self, tx: TransactionInfo) -> str:
        """
        تحليل نوع المعاملة (CEX/DEX/UNKNOWN)
        """
        # تحقق من العناوين CEX
        if tx.from_address and self._is_cex_address(tx.from_address):
            return "CEX"
        if tx.to_address and self._is_cex_address(tx.to_address):
            return "CEX"

        # تحقق من برامج DEX
        if tx.program_id and self._is_dex_program_id(tx.program_id):
            return "DEX"

        # تحقق من نوع التعليمات للتعرف على DEX
        if tx.instructions_data:
            for instr in tx.instructions_data:
                if "parsed" in instr:
                    # البحث عن مؤشرات DEX في التعليمات
                    if "type" in instr["parsed"] and instr["parsed"]["type"] in ["swap", "trade", "liquidityPool",
                                                                                 "settleFunds"]:
                        return "DEX"
                elif "programId" in instr and self._is_dex_program_id(instr["programId"]):
                    return "DEX"

        # إذا وصلنا إلى هنا، فالمعاملة غير معروفة
        return "UNKNOWN"

    def get_active_addresses(self, days: int = 1) -> int:
        """
        تقدير عدد العناوين النشطة (يتطلب تحليل أكثر تعقيدًا في التطبيق الحقيقي)
        ملاحظة: هذه مجرد تقريب بسيط استنادًا إلى العينة، خدمة حقيقية ستحتاج لتنفيذ أكثر تعقيدًا
        """
        try:
            # نحاول الحصول على عينة من العناوين النشطة مؤخرًا من خلال طلب نتائج برنامج الرموز
            token_accounts = self._make_request("getTokenAccountsByOwner",
                                                ["11111111111111111111111111111111",
                                                 {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                                                 {"encoding": "jsonParsed", "limit": 100}])

            # في التطبيق الحقيقي، ستحتاج إلى استعلامات أكثر تعقيدًا وتتبع العناوين عبر فترة زمنية
            # هذا مجرد تقدير
            if token_accounts and "value" in token_accounts:
                return len(token_accounts["value"]) * 10  # عامل تقديري
            return 0
        except Exception as e:
            logger.error(f"خطأ في الحصول على العناوين النشطة: {e}")
            return 0

    def _analyze_transaction_type(self, tx: TransactionInfo) -> str:
        """
        تحليل نوع المعاملة (CEX/DEX/UNKNOWN)
        """
        # تحقق من العناوين CEX
        if tx.from_address and self._is_cex_address(tx.from_address):
            return "CEX"
        if tx.to_address and self._is_cex_address(tx.to_address):
            return "CEX"

        # تحقق من برامج DEX
        if tx.program_id and self._is_dex_program_id(tx.program_id):
            return "DEX"

        # تحقق من نوع التعليمات للتعرف على DEX
        if tx.instructions_data:
            for instr in tx.instructions_data:
                if "parsed" in instr:
                    # البحث عن مؤشرات DEX في التعليمات
                    if "type" in instr["parsed"] and instr["parsed"]["type"] in ["swap", "trade", "liquidityPool",
                                                                                 "settleFunds"]:
                        return "DEX"
                elif "programId" in instr and self._is_dex_program_id(instr["programId"]):
                    return "DEX"

        # إذا وصلنا إلى هنا، فالمعاملة غير معروفة
        return "UNKNOWN"

    def get_whale_transfers(self, threshold_sol: int = 500) -> List[TransactionInfo]:
        """
        الحصول على تحويلات الحيتان التي تتجاوز عتبة معينة

        المعلمات:
            threshold_sol: عتبة قيمة التحويل بالـ SOL (500 SOL افتراضيًا)

        العائد:
            قائمة المعاملات التي تتجاوز العتبة
        """
        # تحويل SOL إلى lamports
        threshold_lamports = threshold_sol * 1_000_000_000  # 1 SOL = 10^9 lamports

        # الحصول على المعاملات
        transactions = self.get_transactions(limit=100)

        # تصفية المعاملات حسب القيمة
        whale_transfers = []

        for tx in transactions:
            if tx.is_success and tx.lamports is not None and tx.lamports >= threshold_lamports:
                whale_transfers.append(tx)

        return whale_transfers