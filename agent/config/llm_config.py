import os
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from backend.app.config import settings

logger = logging.getLogger(__name__)


def get_deepseek_llm(temperature: float = 0.1, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def get_qwen_llm(temperature: float = 0.1, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        model="Qwen/QwQ-32B",
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.QWEN_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def get_qwen_vl_llm(temperature: float = 0.1, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        model="Qwen/QwQ-32B",
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.QWEN_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


MODEL_FACTORIES = {
    "deepseek": get_deepseek_llm,
    "qwen": get_qwen_llm,
    "qwen_vl": get_qwen_vl_llm,
}

TASK_MODEL_MAP = {
    "field_extraction": {"primary": "deepseek", "fallback": "qwen"},
    "business_assessment": {"primary": "deepseek", "fallback": "qwen"},
    "rag_reply_generation": {"primary": "qwen", "fallback": "deepseek"},
    "image_analysis": {"primary": "qwen_vl", "fallback": None},
}

FALLBACK_TEMPLATE_REPLY = (
    "您好，已收到您的反馈，我们正在紧急处理中。"
    "由于系统繁忙，我们的专业客服人员将在30分钟内与您联系。"
    "如有紧急情况，请拨打售后热线400-XXX-XXXX。"
)


def get_llm_for_task(task: str, temperature: float = 0.1, max_tokens: int = 2048) -> BaseChatModel:
    config = TASK_MODEL_MAP.get(task, {"primary": settings.LLM_PRIMARY, "fallback": settings.LLM_FALLBACK})

    primary_key = config["primary"]
    fallback_key = config.get("fallback")

    try:
        factory = MODEL_FACTORIES[primary_key]
        llm = factory(temperature=temperature, max_tokens=max_tokens)
        logger.info(f"Task[{task}] using primary model: {primary_key}")
        return llm
    except Exception as e:
        logger.warning(f"Task[{task}] primary model {primary_key} failed: {e}")

    if fallback_key:
        try:
            factory = MODEL_FACTORIES[fallback_key]
            llm = factory(temperature=temperature, max_tokens=max_tokens)
            logger.info(f"Task[{task}] using fallback model: {fallback_key}")
            return llm
        except Exception as e:
            logger.warning(f"Task[{task}] fallback model {fallback_key} failed: {e}")

    logger.error(f"Task[{task}] all models failed, returning None")
    return None
