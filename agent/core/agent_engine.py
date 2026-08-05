import logging
import os
import random
from datetime import datetime

from agent.config.llm_config import FALLBACK_TEMPLATE_REPLY
from agent.core.extractor import ExtractionAgent
from agent.core.assessor import AssessmentAgent
from agent.core.responder import ResponderAgent
from agent.core.router import RoutingAgent

logger = logging.getLogger(__name__)


class ComplaintAgentEngine:
    def __init__(self):
        self.extractor = ExtractionAgent()
        self.assessor = AssessmentAgent()
        self.responder = ResponderAgent()
        self.router = RoutingAgent()
        self._sop_indexed = False
        self._multimodal_analyzer = None
        self._multimodal_init_failed = False

    @property
    def multimodal_analyzer(self):
        """懒加载 MultimodalAnalyzer"""
        if self._multimodal_init_failed:
            return None
        if self._multimodal_analyzer is None:
            try:
                if os.getenv("OCR_ENABLED", "1") == "1":
                    from agent.multimodal import MultimodalAnalyzer
                    self._multimodal_analyzer = MultimodalAnalyzer()
                else:
                    logger.info("OCR disabled by OCR_ENABLED=0")
                    self._multimodal_init_failed = True
                    return None
            except Exception as e:
                logger.warning(f"MultimodalAnalyzer init failed: {e}")
                self._multimodal_init_failed = True
                return None
        return self._multimodal_analyzer

    async def _ensure_sop_index(self):
        if self._sop_indexed:
            return
        self._sop_indexed = True
        try:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from agent.rag.vector_store import VectorStore
            from agent.rag.sop_indexer import SopIndexer

            vs = VectorStore()
            if not vs.is_available():
                logger.warning("VectorStore not available, skip SOP indexing")
                return
            if vs.collection.count() == 0:
                indexer = SopIndexer(vs)
                await indexer.build_index_from_db()
                logger.info("SOP index initialized")
        except Exception as e:
            logger.warning(f"SOP index init skipped: {e}")

    async def process_complaint(
        self,
        text: str,
        image_paths: list[str] | None = None,
        video_paths: list[str] | None = None,
        customer_name: str | None = None,
        customer_phone: str | None = None,
    ) -> dict:
        logger.info(f"Processing complaint: {text[:50]}...")
        ticket_id = self._generate_ticket_id()

        # Step 0: 多模态分析
        image_analysis = None
        if image_paths and self.multimodal_analyzer is not None:
            try:
                import asyncio
                image_analysis = await asyncio.wait_for(
                    self.multimodal_analyzer.analyze_images(image_paths=image_paths, text_context=text),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                logger.warning("Multimodal analysis timeout(30s)")
                image_analysis = None
            except Exception as e:
                logger.error(f"Multimodal analysis failed: {e}")
                image_analysis = None
        elif image_paths:
            # 多模态分析器不可用，记录图片证据
            image_analysis = {
                "damage_detected": False, "damage_level": "none",
                "fault_types_found": [], "has_emergency_indicators": False,
                "overall_assessment": "图片分析服务不可用，已记录图片证据",
                "suggestion": "", "analysis_source": "none",
                "image_count": len(image_paths),
            }

        # Step 1: 提取（传入image_analysis）
        try:
            extracted_data = await self.extractor.extract(
                text=text,
                image_paths=image_paths or [],
                image_analysis=image_analysis,
            )
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            extracted_data = {"core_fault_desc": text}

        # Step 2: 定级（传入image_analysis和原始text）
        try:
            assessment = await self.assessor.assess(extracted_data=extracted_data, image_analysis=image_analysis, raw_text=text)
        except Exception as e:
            logger.error(f"Assessment failed: {e}")
            assessment = {
                "issue_category": "Other",
                "business_impact": "Minor_Inconvenience",
                "urgency_level": "Medium_Priority",
                "warranty_status": "Unknown",
            }

        # Step 3: 回复（传入image_analysis）
        try:
            await self._ensure_sop_index()
            reply_result = await self.responder.generate_reply(
                extracted_data=extracted_data,
                assessment=assessment,
                image_analysis=image_analysis,
            )
        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            reply_result = {
                "auto_reply_sent": FALLBACK_TEMPLATE_REPLY,
                "sop_applied": None,
            }

        # Step 4: 路由
        try:
            routing_decision = await self.router.route(
                urgency_level=assessment.get("urgency_level", "Medium_Priority"),
            )
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            routing_decision = "department_manager_queue"

        # v1.2: 出单决策已移除，Pipeline 为 4 步（提取→定级→回复→路由）
        # 工单入库与归档由 ticket_service.submit_complaint 处理

        result = {
            "ticket_id": ticket_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "raw_input": text,
            "extracted_data": extracted_data,
            "agent_business_assessment": assessment,
            "urgency_level": assessment.get("urgency_level", "Medium_Priority"),
            "issue_category": assessment.get("issue_category", "Other"),
            "warranty_status": assessment.get("warranty_status", "Unknown"),
            "routing_decision": routing_decision,
            "auto_reply_sent": reply_result.get("auto_reply_sent", FALLBACK_TEMPLATE_REPLY),
            "sop_applied": reply_result.get("sop_applied"),
            "image_analysis": image_analysis,  # v1.3新增
            "status": "routed",
        }

        logger.info(f"Complaint processed: {ticket_id} | urgency={assessment.get('urgency_level')} | route={routing_decision}")
        return result

    @staticmethod
    def _generate_ticket_id() -> str:
        now = datetime.now()
        seq = random.randint(1000, 9999)
        return f"CS-{now.strftime('%Y%m%d')}-{seq}"
