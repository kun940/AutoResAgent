import logging
from datetime import datetime, timedelta
from typing import Optional

from shared.constants import (
    OrderType, OrderStatus, OrderTicketStatus,
    ORDER_TYPE_PREFIX, ORDER_TYPE_LABELS, DEFAULT_ORDER_MAPPING,
    IssueCategory, UrgencyLevel, NotificationType, TicketAction,
)

logger = logging.getLogger(__name__)


class OrderEngine:
    """出单决策引擎 - Agent Pipeline Step5

    根据 issue_category + urgency_level 自动判断出单类型，
    生成对应单据并流转到执行部门。
    """

    def __init__(self):
        self._mapping_cache = None

    async def decide_and_create(
        self,
        ticket_id: str,
        issue_category: str,
        urgency_level: str,
        extracted_data: dict,
        db=None,
    ) -> dict:
        """出单决策与单据创建主入口

        Args:
            ticket_id: 工单ID
            issue_category: 问题分类
            urgency_level: 紧急度
            extracted_data: 提取的结构化数据

        Returns:
            {
                "success": True,
                "orders": [
                    {
                        "order_no": "SO-REP-20260617-0001",
                        "order_type": "Replacement",
                        "order_type_label": "补发单",
                        "department": "售后服务部",
                        "sla_hours": 48,
                        "status": "pending",
                        "material_list": [...],
                        "deadline": "2026-06-19T10:00:00",
                        "model_number": "Pro-Max-V2",
                        "batch_code": "B2026-03",
                    },
                    ...
                ],
                "order_status": "ordered",
            }
        """
        try:
            # 1. 解析出单映射规则
            mapping_rules = await self._resolve_mapping(issue_category, urgency_level, db=db)
            if not mapping_rules:
                logger.warning(f"未找到出单映射规则: category={issue_category}, urgency={urgency_level}")
                await self._update_ticket_order_status(ticket_id, OrderTicketStatus.PENDING_MANUAL, db=db)
                return {
                    "success": False,
                    "orders": [],
                    "order_status": OrderTicketStatus.PENDING_MANUAL,
                    "error": "no_mapping_rule",
                }

            # 2. 逐条规则生成单据
            created_orders = []
            for rule in mapping_rules:
                try:
                    order_info = await self._create_single_order(
                        ticket_id=ticket_id,
                        rule=rule,
                        issue_category=issue_category,
                        urgency_level=urgency_level,
                        extracted_data=extracted_data,
                        db=db,
                    )
                    if order_info:
                        created_orders.append(order_info)
                except Exception as e:
                    logger.error(f"单据创建失败(规则:{rule}): {e}")
                    continue

            if not created_orders:
                logger.error(f"所有单据创建均失败: ticket_id={ticket_id}")
                await self._update_ticket_order_status(ticket_id, OrderTicketStatus.PENDING_MANUAL, db=db)
                return {
                    "success": False,
                    "orders": [],
                    "order_status": OrderTicketStatus.PENDING_MANUAL,
                    "error": "all_orders_failed",
                }

            # 3. 更新工单出单状态为已出单
            await self._update_ticket_order_status(ticket_id, OrderTicketStatus.ORDERED, db=db)

            # 4. 写入工单日志
            order_nos = [o["order_no"] for o in created_orders]
            await self._write_ticket_log(
                ticket_id=ticket_id,
                action=TicketAction.ORDER_CREATED,
                detail=f"自动出单: {', '.join(order_nos)}",
                db=db,
            )

            # 5. 创建通知给执行部门人员
            for order_info in created_orders:
                await self._create_order_notification(
                    ticket_id=ticket_id,
                    order_info=order_info,
                    db=db,
                )

            logger.info(f"出单完成: ticket_id={ticket_id}, 共{len(created_orders)}张单据")

            return {
                "success": True,
                "orders": created_orders,
                "order_status": OrderTicketStatus.ORDERED,
            }

        except Exception as e:
            logger.error(f"出单引擎异常: ticket_id={ticket_id}, error={e}")
            try:
                await self._update_ticket_order_status(ticket_id, OrderTicketStatus.PENDING_MANUAL, db=db)
            except Exception:
                pass
            return {
                "success": False,
                "orders": [],
                "order_status": OrderTicketStatus.PENDING_MANUAL,
                "error": str(e),
            }

    async def _resolve_mapping(
        self,
        issue_category: str,
        urgency_level: str,
        db=None,
    ) -> list[dict]:
        """解析出单映射规则

        优先从数据库 order_mapping_rules 表查询，
        查不到则回退到硬编码默认规则 DEFAULT_ORDER_MAPPING。

        Returns:
            匹配到的规则列表，每条规则包含:
            {
                "order_type": "Replacement",
                "department": "售后服务部",
                "sla_hours": 48,
            }
        """
        # 1. 先尝试从数据库查询
        try:
            from backend.app.models.models import OrderMappingRule
            from sqlalchemy import select

            async def _query_rules(session):
                stmt = (
                    select(OrderMappingRule)
                    .where(
                        OrderMappingRule.issue_category == issue_category,
                        OrderMappingRule.urgency_level == urgency_level,
                        OrderMappingRule.is_active == 1,
                    )
                    .order_by(OrderMappingRule.priority.desc())
                )
                result = await session.execute(stmt)
                return result.scalars().all()

            if db:
                rules = await _query_rules(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    rules = await _query_rules(session)

            if rules:
                mapping_list = []
                for rule in rules:
                    mapping_list.append({
                        "order_type": rule.order_type,
                        "department": rule.department,
                        "sla_hours": rule.sla_hours,
                    })
                logger.info(
                    f"数据库映射规则命中: category={issue_category}, "
                    f"urgency={urgency_level}, 规则数={len(mapping_list)}"
                )
                return mapping_list

        except Exception as e:
            logger.warning(f"数据库映射规则查询失败，回退到默认规则: {e}")

        # 2. 回退到硬编码默认规则
        try:
            category_enum = IssueCategory(issue_category)
        except ValueError:
            logger.warning(f"未知问题分类: {issue_category}, 使用 Other")
            category_enum = IssueCategory.OTHER

        order_types = DEFAULT_ORDER_MAPPING.get(category_enum, [OrderType.TECH_SUPPORT])
        mapping_list = []
        for ot in order_types:
            mapping_list.append({
                "order_type": ot.value,
                "department": self._get_default_department(ot.value),
                "sla_hours": self._get_default_sla_hours(urgency_level),
            })

        logger.info(
            f"默认映射规则: category={issue_category}, "
            f"urgency={urgency_level}, 规则数={len(mapping_list)}"
        )
        return mapping_list

    async def _generate_order_no(self, order_type: str, db=None) -> str:
        """生成单据编号: SO-{TYPE_PREFIX}-{YYYYMMDD}-{SEQ}"""
        try:
            type_enum = OrderType(order_type)
            prefix = ORDER_TYPE_PREFIX.get(type_enum, "UNK")
        except ValueError:
            prefix = "UNK"

        date_str = datetime.now().strftime("%Y%m%d")
        seq = await self._get_next_seq(prefix, date_str, db=db)

        return f"SO-{prefix}-{date_str}-{seq:04d}"

    async def _get_next_seq(self, prefix: str, date_str: str, db=None) -> int:
        """获取下一个序号，通过查询数据库中当日该类型最大序号+1"""
        try:
            from backend.app.models.models import ServiceOrder
            from sqlalchemy import select, func

            async def _query(session):
                like_pattern = f"SO-{prefix}-{date_str}-%"
                stmt = select(func.max(ServiceOrder.order_no)).where(
                    ServiceOrder.order_no.like(like_pattern)
                )
                result = await session.execute(stmt)
                max_no = result.scalar_one_or_none()
                if max_no:
                    parts = max_no.split("-")
                    if len(parts) >= 4:
                        return int(parts[-1]) + 1
                return 1

            if db:
                return await _query(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    return await _query(session)

        except Exception as e:
            logger.warning(f"序号查询失败，使用时间戳兜底: {e}")
            return datetime.now().microsecond % 10000 or 1

    async def _create_single_order(
        self,
        ticket_id: str,
        rule: dict,
        issue_category: str,
        urgency_level: str,
        extracted_data: dict,
        db=None,
    ) -> Optional[dict]:
        """根据单条映射规则创建一张服务单据

        Args:
            ticket_id: 工单ID
            rule: 映射规则
            issue_category: 问题分类
            urgency_level: 紧急度
            extracted_data: 提取的结构化数据

        Returns:
            创建的单据信息字典，失败返回 None
        """
        order_type = rule["order_type"]
        department = rule["department"]
        sla_hours = rule["sla_hours"]

        # 生成单据编号
        order_no = await self._generate_order_no(order_type, db=db)

        # 从 extracted_data 获取设备信息
        model_number = extracted_data.get("model_number", "UNKNOWN") or "UNKNOWN"
        batch_code = extracted_data.get("batch_code", "UNKNOWN") or "UNKNOWN"

        # 计算截止时间
        deadline = datetime.now() + timedelta(hours=sla_hours)

        # 构建物料清单
        material_list = self._build_material_list(order_type, extracted_data)

        # 获取类型标签
        try:
            type_enum = OrderType(order_type)
            order_type_label = ORDER_TYPE_LABELS.get(type_enum, order_type)
        except ValueError:
            order_type_label = order_type

        # 写入数据库
        try:
            from backend.app.models.models import ServiceOrder, QualityTraceIndex

            async def _do_create(session):
                # 创建服务单据
                service_order = ServiceOrder(
                    order_no=order_no,
                    ticket_id=ticket_id,
                    order_type=order_type,
                    order_type_label=order_type_label,
                    department=department,
                    sla_hours=sla_hours,
                    status=OrderStatus.PENDING,
                    priority=urgency_level,
                    material_list=material_list,
                    deadline=deadline,
                    model_number=model_number,
                    batch_code=batch_code,
                    issue_category=issue_category,
                    urgency_level=urgency_level,
                )
                session.add(service_order)
                await session.flush()

                # 更新质量追溯索引
                trace_index = QualityTraceIndex(
                    ticket_id=ticket_id,
                    order_id=service_order.id,
                    model_number=model_number,
                    batch_code=batch_code,
                    issue_category=issue_category,
                    urgency_level=urgency_level,
                    order_type=order_type,
                    trace_date=datetime.now().date(),
                )
                session.add(trace_index)
                if not db:
                    await session.commit()

            if db:
                await _do_create(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    await _do_create(session)

        except Exception as e:
            logger.error(f"单据写入数据库失败: order_no={order_no}, error={e}")
            return None

        order_info = {
            "order_no": order_no,
            "order_type": order_type,
            "order_type_label": order_type_label,
            "department": department,
            "sla_hours": sla_hours,
            "status": OrderStatus.PENDING,
            "material_list": material_list,
            "deadline": deadline.isoformat(),
            "model_number": model_number,
            "batch_code": batch_code,
        }

        logger.info(
            f"单据创建成功: {order_no} | 类型={order_type_label} | "
            f"部门={department} | SLA={sla_hours}h"
        )
        return order_info

    async def _update_ticket_order_status(
        self,
        ticket_id: str,
        order_status: OrderTicketStatus,
        db=None,
    ) -> None:
        """更新工单的出单状态"""
        try:
            from backend.app.models.models import Ticket
            from sqlalchemy import select

            async def _do_update(session):
                stmt = select(Ticket).where(Ticket.ticket_id == ticket_id)
                result = await session.execute(stmt)
                ticket = result.scalar_one_or_none()
                if ticket:
                    ticket.order_status = order_status
                    if not db:
                        await session.commit()
                    logger.info(f"工单出单状态更新: {ticket_id} -> {order_status}")

            if db:
                await _do_update(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    await _do_update(session)

        except Exception as e:
            logger.error(f"工单出单状态更新失败: ticket_id={ticket_id}, error={e}")

    async def _write_ticket_log(
        self,
        ticket_id: str,
        action: str,
        detail: Optional[str] = None,
        db=None,
    ) -> None:
        """写入工单操作日志"""
        try:
            from backend.app.models.models import TicketLog

            async def _do_log(session):
                log = TicketLog(
                    ticket_id=ticket_id,
                    action=action,
                    detail=detail,
                )
                session.add(log)
                if not db:
                    await session.commit()

            if db:
                await _do_log(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    await _do_log(session)

        except Exception as e:
            logger.error(f"工单日志写入失败: ticket_id={ticket_id}, action={action}, error={e}")

    async def _create_order_notification(
        self,
        ticket_id: str,
        order_info: dict,
        db=None,
    ) -> None:
        """创建出单通知给执行部门人员"""
        try:
            from backend.app.models.models import User, Notification
            from sqlalchemy import select

            async def _do_notify(session):
                department = order_info.get("department", "")
                stmt = select(User).where(
                    User.department == department,
                    User.is_active == 1,
                )
                result = await session.execute(stmt)
                users = result.scalars().all()

                if not users:
                    logger.warning(f"未找到部门用户: department={department}")
                    return

                order_no = order_info.get("order_no", "")
                order_type_label = order_info.get("order_type_label", "")
                content = (
                    f"新单据通知: {order_no} ({order_type_label})，"
                    f"请及时处理。SLA: {order_info.get('sla_hours', 48)}小时"
                )

                for user in users:
                    notification = Notification(
                        ticket_id=ticket_id,
                        target_user_id=user.id,
                        type=NotificationType.ORDER_CREATED,
                        content=content,
                    )
                    session.add(notification)

                if not db:
                    await session.commit()
                logger.info(
                    f"出单通知已创建: order_no={order_no}, "
                    f"department={department}, 通知人数={len(users)}"
                )

            if db:
                await _do_notify(db)
            else:
                from backend.app.database import async_session
                async with async_session() as session:
                    await _do_notify(session)

        except Exception as e:
            logger.error(f"出单通知创建失败: ticket_id={ticket_id}, error={e}")

    def _build_material_list(
        self,
        order_type: str,
        extracted_data: dict,
    ) -> list:
        """根据出单类型和提取数据构建物料清单

        规则:
        - Replacement: 从 extracted_data 中提取缺失配件信息
        - Repair: 从 extracted_data 中提取故障部件信息
        - Return_Exchange: 从 extracted_data 中提取设备信息(整机退换+新设备)
        - Tech_Support: 无物料清单(技术指导)
        - QC: 从 extracted_data 中提取待检产品信息
        """
        model = extracted_data.get("model_number", "UNKNOWN") or "UNKNOWN"
        batch = extracted_data.get("batch_code", "UNKNOWN") or "UNKNOWN"

        if order_type == OrderType.REPLACEMENT:
            return [
                {
                    "item_code": f"PART-{model}",
                    "item_name": f"{model} 配件套件",
                    "quantity": 1,
                }
            ]

        if order_type == OrderType.REPAIR:
            return [
                {
                    "item_code": f"DEVICE-{model}",
                    "item_name": f"{model} 待维修设备",
                    "quantity": 1,
                }
            ]

        if order_type == OrderType.RETURN_EXCHANGE:
            return [
                {
                    "item_code": f"DEVICE-{model}",
                    "item_name": f"{model} 退换设备",
                    "quantity": 1,
                },
                {
                    "item_code": f"NEW-{model}",
                    "item_name": f"{model} 新设备",
                    "quantity": 1,
                },
            ]

        if order_type == OrderType.TECH_SUPPORT:
            # 技术指导无需物料清单
            return []

        if order_type == OrderType.QC:
            return [
                {
                    "item_code": f"QC-{model}-{batch}",
                    "item_name": f"{model} (批次:{batch}) 待检产品",
                    "quantity": 1,
                }
            ]

        # 未知类型返回空列表
        logger.warning(f"未知出单类型: {order_type}, 物料清单为空")
        return []

    def _get_default_department(self, order_type: str) -> str:
        """获取默认处理部门"""
        department_map = {
            OrderType.REPLACEMENT: "售后服务部",
            OrderType.REPAIR: "技术维修部",
            OrderType.RETURN_EXCHANGE: "售后服务部",
            OrderType.TECH_SUPPORT: "技术支持部",
            OrderType.QC: "质量管理部",
        }
        try:
            type_enum = OrderType(order_type)
            return department_map.get(type_enum, "售后服务部")
        except ValueError:
            return "售后服务部"

    def _get_default_sla_hours(self, urgency_level: str) -> int:
        """根据紧急度获取默认SLA小时数"""
        sla_map = {
            UrgencyLevel.HIGH: 24,
            UrgencyLevel.MEDIUM: 48,
            UrgencyLevel.LOW: 72,
        }
        try:
            level_enum = UrgencyLevel(urgency_level)
            return sla_map.get(level_enum, 48)
        except ValueError:
            return 48
