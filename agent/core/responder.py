import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config.llm_config import get_llm_for_task, FALLBACK_TEMPLATE_REPLY
from agent.config.agent_config import REPLY_TEMPERATURE, REPLY_MAX_TOKENS
from agent.prompts.reply_prompt import REPLY_SYSTEM_PROMPT, REPLY_USER_PROMPT

logger = logging.getLogger(__name__)


class ResponderAgent:
    def __init__(self, retriever=None):
        self._retriever = retriever
        self._retriever_initialized = retriever is not None

    @property
    def retriever(self):
        if not self._retriever_initialized:
            self._retriever_initialized = True
            try:
                from agent.rag.vector_store import VectorStore
                from agent.rag.retriever import SopRetriever
                self._retriever = SopRetriever(VectorStore())
            except Exception as e:
                logger.warning(f"VectorStore init failed, SOP retrieval disabled: {e}")
                self._retriever = None
        return self._retriever

    async def generate_reply(self, extracted_data: dict, assessment: dict, image_analysis: dict = None) -> dict:
        urgency_level = assessment.get("urgency_level", "Medium_Priority")
        issue_category = assessment.get("issue_category")
        fault_desc = extracted_data.get("core_fault_desc", "")

        sop_content = ""
        sop_title = ""
        try:
            if self.retriever is not None:
                # v1.4: 传入 issue_category 进行分类精确匹配，
                # 避免批次缺陷客诉被匹配到漏电SOP等跨分类问题
                sop_results = self.retriever.retrieve_sop(
                    fault_desc,
                    urgency_level=urgency_level,
                    issue_category=issue_category,
                    top_k=2,
                    prefer_emergency=(urgency_level == "High_Priority"),
                )
                if sop_results:
                    sop_content = sop_results[0].get("content", "")
                    sop_title = sop_results[0].get("metadata", {}).get("title", "")
        except Exception as e:
            logger.warning(f"SOP retrieval failed: {e}")

        llm = get_llm_for_task("rag_reply_generation", temperature=REPLY_TEMPERATURE, max_tokens=REPLY_MAX_TOKENS)

        if llm is None:
            return self._fallback_reply(extracted_data, assessment, sop_content, sop_title, image_analysis=image_analysis)

        extracted_json = json.dumps(extracted_data, ensure_ascii=False)
        assessment_json = json.dumps(assessment, ensure_ascii=False)
        emergency_actions_hint = self._build_emergency_hint(urgency_level, image_analysis)

        user_content = REPLY_USER_PROMPT.format(
            extracted_json=extracted_json,
            assessment_json=assessment_json,
            sop_content=sop_content if sop_content else "无匹配SOP文档",
            emergency_actions_hint=emergency_actions_hint,
        )

        messages = [
            SystemMessage(content=REPLY_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        try:
            response = await llm.ainvoke(messages)
            return self._parse_response(response.content, extracted_data, assessment, sop_content, sop_title)
        except Exception as e:
            logger.error(f"Reply generation LLM call failed: {e}")
            return self._fallback_reply(extracted_data, assessment, sop_content, sop_title, image_analysis=image_analysis)

    @staticmethod
    def _build_emergency_hint(urgency_level: str, image_analysis: dict = None) -> str:
        """根据紧急度和图片分析结果构造紧急提示"""
        if urgency_level != "High_Priority":
            return ""

        hints = ["【紧急处置提示】"]

        # 图片证据中的紧急指标
        if image_analysis and image_analysis.get("damage_detected"):
            fault_types = image_analysis.get("fault_types_found", [])
            if fault_types:
                hints.append(f"图片检测到故障类型：{'、'.join(fault_types)}")
            if image_analysis.get("has_emergency_indicators"):
                hints.append("图片检测到紧急安全指标，回复中必须包含安全警示步骤！")
            damage_level = image_analysis.get("damage_level", "none")
            if damage_level in ("severe", "moderate"):
                hints.append(f"图片损伤等级：{damage_level}，需提供详细止损指令")

        if len(hints) == 1:
            # 无图片证据时，通用紧急提示
            hints.append("该客诉为高优先级，回复中必须包含3-5个具体可操作的安全步骤")

        return "\n".join(hints)

    def _parse_response(self, content, extracted_data, assessment, sop_content, sop_title):
        try:
            cleaned = content.strip()

            import re
            cleaned = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', cleaned, flags=re.DOTALL)
            cleaned = cleaned.strip()

            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)
            return {
                "auto_reply_sent": result.get("auto_reply_sent", cleaned),
                "sop_applied": result.get("sop_applied", sop_title),
            }
        except (json.JSONDecodeError, AttributeError):
            reply_text = content
            import re
            think_match = re.search(r'<think\b[^>]*>.*?</think\s*>', reply_text, flags=re.DOTALL)
            if think_match:
                reply_text = reply_text[:think_match.start()] + reply_text[think_match.end():]
                reply_text = reply_text.strip()

            json_match = re.search(r'\{[^{}]*"auto_reply_sent"[^{}]*\}', reply_text, flags=re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    return {
                        "auto_reply_sent": result.get("auto_reply_sent", reply_text),
                        "sop_applied": result.get("sop_applied", sop_title),
                    }
                except json.JSONDecodeError:
                    pass

            return {
                "auto_reply_sent": reply_text,
                "sop_applied": sop_title,
            }

    @staticmethod
    def _fallback_reply(extracted_data, assessment, sop_content, sop_title, image_analysis=None):
        fault = extracted_data.get("core_fault_desc", "故障")
        urgency = assessment.get("urgency_level", "Medium_Priority")
        category = assessment.get("issue_category", "Other")

        # 图片证据中的故障类型
        img_fault_types = []
        if image_analysis and image_analysis.get("damage_detected"):
            img_fault_types = image_analysis.get("fault_types_found", [])

        if urgency == "High_Priority":
            if category in ("Hardware_Thermal_Runaway", "Electrical_Leakage"):
                # 细化止损步骤
                if "冒烟" in fault or "起火" in fault or any(t in str(img_fault_types) for t in ["冒烟", "烧焦", "起火"]):
                    reply = (
                        f"您好，已收到您的故障反馈（{fault}），该问题已标记为高优先级。"
                        "请立即执行以下步骤：1.请立即切断设备总电源/总闸；2.请人员远离设备并保持通风；3.严禁用水灭火。"
                        "我们的技术团队将立即介入处理，专业工程师将在1小时内与您联系。"
                        "如有紧急情况，请拨打售后热线400-XXX-XXXX。"
                    )
                    default_sop = "设备起火紧急处置SOP"
                elif "漏电" in fault or "触电" in fault or any(t in str(img_fault_types) for t in ["漏电", "触电"]):
                    reply = (
                        f"您好，已收到您的故障反馈（{fault}），该问题已标记为高优先级。"
                        "请立即执行以下步骤：1.请立即切断总闸并远离设备；2.严禁触碰设备任何部位；3.确保人员安全撤离。"
                        "我们的技术团队将立即介入处理，专业工程师将在1小时内与您联系。"
                        "如有紧急情况，请拨打售后热线400-XXX-XXXX。"
                    )
                    default_sop = "触电事故紧急处置SOP"
                else:
                    reply = (
                        f"您好，已收到您的故障反馈（{fault}），该问题已标记为高优先级。"
                        "请立即切断设备电源，确保人员安全。"
                        "我们的技术团队将立即介入处理，专业工程师将在1小时内与您联系。"
                        "如有紧急情况，请拨打售后热线400-XXX-XXXX。"
                    )
                    default_sop = "设备过热/冒烟紧急处置"
            else:
                reply = (
                    f"您好，已收到您的故障反馈（{fault}），该问题已标记为高优先级，"
                    "我们的技术团队将立即介入处理。请保持电话畅通，专业工程师将在1小时内与您联系。"
                    "如有紧急情况，请拨打售后热线400-XXX-XXXX。"
                )
                default_sop = "高优先级紧急处理"
        elif urgency == "Medium_Priority":
            reply = (
                f"您好，已收到您的故障反馈（{fault}），我们已安排相关技术人员跟进处理，"
                "预计24小时内给您回复。如有疑问，请联系售后热线400-XXX-XXXX。"
            )
            default_sop = "常规故障处理流程"
        else:
            if category == "Missing_Parts":
                reply = (
                    f"您好，已收到您的配件缺失反馈（{fault}），我们已记录您的问题，"
                    "将尽快为您安排补发配送，预计3-5个工作日送达。"
                    "感谢您的耐心等待。"
                )
                default_sop = "配件缺失补发流程"
            else:
                reply = (
                    f"您好，已收到您的反馈（{fault}），我们已记录您的问题，"
                    "将在2个工作日内处理并回复。感谢您的耐心等待。"
                )
                default_sop = "一般问题处理流程"

        return {
            "auto_reply_sent": reply,
            "sop_applied": sop_title if sop_title else default_sop,
        }
