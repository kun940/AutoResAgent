import os
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
os.makedirs(OUT_DIR, exist_ok=True)

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
FONT_PATH_BOLD = "C:/Windows/Fonts/msyhbd.ttc"

def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

def get_bold_font(size):
    try:
        return ImageFont.truetype(FONT_PATH_BOLD, size)
    except:
        return get_font(size)

BLUE = (41, 98, 168)
LIGHT_BLUE = (220, 235, 250)
WHITE = (255, 255, 255)
BLACK = (30, 30, 30)
GRAY = (120, 120, 120)
LIGHT_GRAY = (245, 245, 245)
BORDER = (180, 200, 220)
ARROW_COLOR = (80, 130, 190)
GREEN = (46, 139, 87)
ORANGE = (230, 140, 30)
RED = (200, 50, 50)


def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_centered_text(draw, text, cx, cy, font, fill=BLACK):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def draw_arrow(draw, x1, y1, x2, y2, color=ARROW_COLOR, width=3):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    arrow_len = 12
    draw.polygon([
        (x2, y2),
        (x2 - arrow_len * math.cos(angle - 0.4), y2 - arrow_len * math.sin(angle - 0.4)),
        (x2 - arrow_len * math.cos(angle + 0.4), y2 - arrow_len * math.sin(angle + 0.4)),
    ], fill=color)


# ==================== 2.2 核心流程设计 ====================
def gen_pipeline():
    W, H = 1200, 900
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_bold_font(28)
    step_font = get_bold_font(20)
    detail_font = get_font(16)
    small_font = get_font(14)

    draw_centered_text(draw, "2.2 核心流程设计 — Agent Pipeline", W // 2, 35, title_font, BLUE)

    steps = [
        ("Step 1: Extractor", "字段提取", "DeepSeek-V3 提取结构化字段", "订单号、产品型号、批次号、核心故障描述", "正则表达式提取 + 默认值填充"),
        ("Step 2: Assessor", "业务定级", "DeepSeek-V3 判断分类/影响/紧急度/质保", "issue_category, urgency_level等", "关键词匹配（冒烟→高紧急, 缺件→低紧急）"),
        ("Step 3: Responder", "RAG排障回复", "ChromaDB语义检索SOP → Qwen-Plus生成回复", "专业排障指导文本", "按issue_category选模板回复+标记人工"),
        ("Step 4: Router", "路由分发", "规则引擎匹配路由规则", "路由目标队列 + 指派处理人", "URGENCY_ROUTING_MAP静态映射"),
    ]

    box_w, box_h = 700, 150
    start_y = 80
    gap = 30
    cx = W // 2

    for i, (title, subtitle, process, output, fallback) in enumerate(steps):
        bx = cx - box_w // 2
        by = start_y + i * (box_h + gap)

        draw_rounded_rect(draw, (bx, by, bx + box_w, by + box_h), 12, LIGHT_BLUE, BLUE, 2)

        header_h = 36
        draw_rounded_rect(draw, (bx, by, bx + box_w, by + header_h), 12, BLUE, BLUE, 2)
        draw.rectangle([bx, by + 20, bx + box_w, by + header_h], fill=BLUE)
        draw_centered_text(draw, title, cx, by + header_h // 2, step_font, WHITE)

        ty = by + header_h + 12
        draw.text((bx + 20, ty), f"处理：{process}", font=detail_font, fill=BLACK)
        draw.text((bx + 20, ty + 24), f"输出：{output}", font=detail_font, fill=BLACK)
        draw.text((bx + 20, ty + 48), f"降级：{fallback}", font=small_font, fill=ORANGE)

        if i < len(steps) - 1:
            arrow_y1 = by + box_h
            arrow_y2 = by + box_h + gap
            draw_arrow(draw, cx, arrow_y1, cx, arrow_y2)

    final_y = start_y + 4 * (box_h + gap) - gap + 15
    draw_centered_text(draw, "工单入库 + 通知处理人  |  客户收到AI即时回复", cx, final_y, get_bold_font(18), GREEN)

    img.save(os.path.join(OUT_DIR, "pipeline_flow.jpg"), "JPEG", quality=95)
    print("pipeline_flow.jpg OK")


# ==================== 2.3 三级降级策略 ====================
def gen_degradation():
    W, H = 1000, 320
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_bold_font(26)
    header_font = get_bold_font(18)
    cell_font = get_font(16)

    draw_centered_text(draw, "2.3 三级降级策略", W // 2, 25, title_font, BLUE)

    headers = ["降级级别", "触发条件", "行为", "用户体验"]
    rows = [
        ["L0 正常", "主模型响应成功", "AI完整处理", "完整AI回复"],
        ["L1 备选", "主模型超时/报错", "关键词匹配+规则引擎+模板回复", "回复质量略降，功能正常"],
        ["L2 兜底", "所有AI服务不可用", "通用模板回复+标记\"需人工处理\"", "收到确认，人工跟进"],
    ]

    col_widths = [150, 200, 300, 250]
    row_height = 50
    header_height = 45
    start_x = 50
    start_y = 55

    x = start_x
    for j, (header, cw) in enumerate(zip(headers, col_widths)):
        draw.rectangle([x, start_y, x + cw, start_y + header_height], fill=BLUE)
        draw.rectangle([x, start_y, x + cw, start_y + header_height], outline=BORDER, width=1)
        draw_centered_text(draw, header, x + cw // 2, start_y + header_height // 2, header_font, WHITE)
        x += cw

    for i, row in enumerate(rows):
        y = start_y + header_height + i * row_height
        bg = LIGHT_GRAY if i % 2 == 1 else WHITE
        x = start_x
        for j, (cell, cw) in enumerate(zip(row, col_widths)):
            draw.rectangle([x, y, x + cw, y + row_height], fill=bg, outline=BORDER, width=1)
            color = BLACK
            if j == 0:
                if "L0" in cell:
                    color = GREEN
                elif "L1" in cell:
                    color = ORANGE
                elif "L2" in cell:
                    color = RED
                color_bold = get_bold_font(16)
                draw_centered_text(draw, cell, x + cw // 2, y + row_height // 2, color_bold, color)
            else:
                draw_centered_text(draw, cell, x + cw // 2, y + row_height // 2, cell_font, BLACK)
            x += cw

    img.save(os.path.join(OUT_DIR, "degradation_table.jpg"), "JPEG", quality=95)
    print("degradation_table.jpg OK")


# ==================== 2.4 数据隔离与安全方案 ====================
def gen_security():
    W, H = 1000, 320
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_bold_font(26)
    header_font = get_bold_font(18)
    cell_font = get_font(15)

    draw_centered_text(draw, "2.4 数据隔离与安全方案", W // 2, 25, title_font, BLUE)

    headers = ["维度", "客户侧（H5）", "企业侧（桌面端）"]
    rows = [
        ["认证", "无需登录", "JWT Token认证"],
        ["可见字段", "工单号/紧急度/状态/AI回复/时间线", "全部字段含路由/处理人/SOP"],
        ["不可见字段", "routing_decision / assigned_to / sop_applied", "—"],
        ["操作权限", "提交 + 查询", "状态变更 / 升级 / 转派"],
    ]

    col_widths = [150, 380, 370]
    row_height = 50
    header_height = 45
    start_x = 50
    start_y = 55

    x = start_x
    for j, (header, cw) in enumerate(zip(headers, col_widths)):
        draw.rectangle([x, start_y, x + cw, start_y + header_height], fill=BLUE)
        draw.rectangle([x, start_y, x + cw, start_y + header_height], outline=BORDER, width=1)
        draw_centered_text(draw, header, x + cw // 2, start_y + header_height // 2, header_font, WHITE)
        x += cw

    for i, row in enumerate(rows):
        y = start_y + header_height + i * row_height
        bg = LIGHT_GRAY if i % 2 == 1 else WHITE
        x = start_x
        for j, (cell, cw) in enumerate(zip(row, col_widths)):
            draw.rectangle([x, y, x + cw, y + row_height], fill=bg, outline=BORDER, width=1)
            if j == 0:
                draw_centered_text(draw, cell, x + cw // 2, y + row_height // 2, get_bold_font(15), BLUE)
            else:
                draw_centered_text(draw, cell, x + cw // 2, y + row_height // 2, cell_font, BLACK)
            x += cw

    img.save(os.path.join(OUT_DIR, "security_table.jpg"), "JPEG", quality=95)
    print("security_table.jpg OK")


# ==================== 2.5 工单生命周期管理 ====================
def gen_lifecycle():
    W, H = 1100, 600
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    title_font = get_bold_font(26)
    step_font = get_bold_font(18)
    detail_font = get_font(15)
    small_font = get_font(14)

    draw_centered_text(draw, "2.5 工单生命周期管理", W // 2, 25, title_font, BLUE)

    statuses = ["pending", "processing", "routed", "resolved", "closed"]
    labels = ["待处理", "处理中", "已路由", "已解决", "已关闭"]
    colors = [(255, 243, 205), (214, 234, 248), (232, 218, 239), (213, 245, 227), (242, 243, 244)]
    border_colors = [(133, 100, 4), (36, 113, 163), (125, 60, 152), (30, 132, 73), (127, 140, 141)]

    box_w, box_h = 140, 60
    start_x = 80
    cy = 100
    gap = 60

    for i, (status, label, bg, bc) in enumerate(zip(statuses, labels, colors, border_colors)):
        bx = start_x + i * (box_w + gap)
        draw_rounded_rect(draw, (bx, cy - box_h // 2, bx + box_w, cy + box_h // 2), 10, bg, bc, 2)
        draw_centered_text(draw, label, bx + box_w // 2, cy - 8, step_font, bc)
        draw_centered_text(draw, status, bx + box_w // 2, cy + 14, small_font, GRAY)

        if i < len(statuses) - 1:
            ax1 = bx + box_w
            ax2 = bx + box_w + gap
            draw_arrow(draw, ax1 + 5, cy, ax2 - 5, cy, ARROW_COLOR, 3)

    sla_y = 220
    draw.text((80, sla_y), "SLA超时自动升级：", font=get_bold_font(18), fill=RED)
    draw.text((80, sla_y + 30), "Low_Priority → Medium_Priority (48小时)", font=detail_font, fill=BLACK)
    draw.text((80, sla_y + 55), "Medium_Priority → High_Priority (24小时)", font=detail_font, fill=BLACK)

    features_y = 340
    draw.text((80, features_y), "其他管理机制：", font=get_bold_font(18), fill=BLUE)

    feature_items = [
        ("手动升级", "客服人员可在桌面端手动升级工单紧急度"),
        ("转派", "支持将工单转派给其他处理人员"),
        ("通知", "新工单/升级/SLA预警自动推送通知给处理人"),
    ]

    fx = 100
    for i, (title, desc) in enumerate(feature_items):
        fy = features_y + 40 + i * 55
        draw_rounded_rect(draw, (fx, fy, fx + 120, fy + 35), 8, LIGHT_BLUE, BLUE, 1)
        draw_centered_text(draw, title, fx + 60, fy + 17, get_bold_font(15), BLUE)
        draw.text((fx + 140, fy + 8), desc, font=detail_font, fill=BLACK)

    img.save(os.path.join(OUT_DIR, "lifecycle_flow.jpg"), "JPEG", quality=95)
    print("lifecycle_flow.jpg OK")


if __name__ == "__main__":
    gen_pipeline()
    gen_degradation()
    gen_security()
    gen_lifecycle()
    print("All done!")
