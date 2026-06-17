import logging
import os
import random
from datetime import datetime

from agent.config.llm_config import FALLBACK_TEMPLATE_REPLY
from agent.core.extractor import ExtractionAgent
from agent.core.assessor import AssessmentAgent
from agent.core.responder import ResponderAgent
from agent.core.router import RoutingAgent
from agent.core.order_engine import OrderEngine

logger = logging.getLogger(__name__)


class ComplaintAgentEngine:
    def __init__(self):
        self.extractor = ExtractionAgent()
        self.assessor = AssessmentAgent()
        self.responder = ResponderAgent()
        self.router = RoutingAgent()
        self.order_engine = OrderEngine()
        self._sop_indexed = False

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

        try:
            extracted_data = await self.extractor.extract(
                text=text,
                image_paths=image_paths or [],
            )
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            extracted_data = {"core_fault_desc": text}

        try:
            assessment = await self.assessor.assess(extracted_data=extracted_data)
        except Exception as e:
            logger.error(f"Assessment failed: {e}")
            assessment = {
                "issue_category": "Other",
                "business_impact": "Minor_Inconvenience",
                "urgency_level": "Medium_Priority",
                "warranty_status": "Unknown",
            }

        try:
            await self._ensure_sop_index()
            reply_result = await self.responder.generate_reply(
                extracted_data=extracted_data,
                assessment=assessment,
            )
        except Exception as e:
            logger.error(f"Reply generation failed: {e}")
            reply_result = {
                "auto_reply_sent": FALLBACK_TEMPLATE_REPLY,
                "sop_applied": None,
            }

        try:
            routing_decision = await self.router.route(
                urgency_level=assessment.get("urgency_level", "Medium_Priority"),
            )
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            routing_decision = "department_manager_queue"

        # Step5: 出单决策（延迟到工单入库后执行，由 ticket_service 调用）
        # order_result 由 ticket_service.submit_complaint 在 flush 后调用

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
            "status": "routed",
        }

        logger.info(f"Complaint processed: {ticket_id} | urgency={assessment.get('urgency_level')} | route={routing_decision}")
        return result

    @staticmethod
    def _generate_ticket_id() -> str:
        now = datetime.now()
        seq = random.randint(1000, 9999)
        return f"CS-{now.strftime('%Y%m%d')}-{seq}"
