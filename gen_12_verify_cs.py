"""生成核销小程序页面 + 客服系统页面"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_verify_miniapp():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Header
    draw_gradient_rect(img, [0, 0, PHONE_W, 160], COLORS['gradient_start'], COLORS['gradient_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    draw.text((20, 48), "宾尼小康 · 核销端", fill=hex_to_rgb('#FFFFFF'), font=get_font(18, bold=True))
    draw.text((20, 75), "门店工作人员核销工具", fill=hex_to_rgb('#FFFFFFBB'), font=get_font(13))
    
    # Store info
    draw_rounded_rect(draw, [20, 105, PHONE_W-20, 145], 12, fill='#FFFFFF20')
    draw.text((35, 112), "🏪", font=get_font(16))
    draw.text((58, 114), "阳光口腔诊所（朝阳店）", fill=hex_to_rgb('#FFFFFF'), font=get_font(14))
    draw.text((PHONE_W-70, 116), "切换 ›", fill=hex_to_rgb('#FFFFFFBB'), font=get_font(12))
    
    draw.rectangle([0, 160, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Scan button - big center button
    scan_y = 180
    cx = PHONE_W // 2
    draw_card(draw, [40, scan_y, PHONE_W-40, scan_y+200], 20)
    
    # Scan icon
    draw_circle(draw, (cx, scan_y+80), 55, fill=COLORS['primary'])
    draw.text((cx-18, scan_y+60), "📷", font=get_font(32))
    draw.text((cx-38, scan_y+145), "扫码核销", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(18, bold=True))
    draw.text((cx-65, scan_y+172), "扫描用户订单核销码", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(13))
    
    # Today stats
    sy = scan_y + 220
    draw.text((20, sy), "今日核销统计", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    sy += 30
    
    draw_card(draw, [20, sy, PHONE_W-20, sy+80], 14)
    stats = [("已核销", "12", COLORS['success']), ("待核销", "5", COLORS['warning']), ("总订单", "17", COLORS['info'])]
    sw = (PHONE_W - 40) // 3
    for i, (label, val, color) in enumerate(stats):
        sx2 = 20 + i * sw + sw//2
        draw.text((sx2-draw.textlength(val, font=get_font(24, bold=True))//2, sy+12),
                  val, fill=hex_to_rgb(color), font=get_font(24, bold=True))
        f_l = get_font(12)
        tw = draw.textlength(label, font=f_l)
        draw.text((sx2-tw//2, sy+48), label, fill=hex_to_rgb(COLORS['text_secondary']), font=f_l)
        if i < 2:
            draw.line([(20+sw*(i+1), sy+15), (20+sw*(i+1), sy+60)], fill=hex_to_rgb(COLORS['divider']), width=1)
    
    # Recent verifications
    ry = sy + 100
    draw.text((20, ry), "最近核销记录", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    ry += 28
    
    records = [
        ("BN20250327001", "口腔清洁护理", "小明", "10:32", COLORS['success']),
        ("BN20250327002", "全面健康体检", "小红", "10:15", COLORS['success']),
        ("BN20250327003", "口腔深度护理", "张先生", "09:48", COLORS['success']),
    ]
    
    for order_id, service, user, time, color in records:
        draw_card(draw, [20, ry, PHONE_W-20, ry+65], 10)
        draw_circle(draw, (42, ry+32), 12, fill=color)
        draw.text((36, ry+24), "✓", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
        draw.text((62, ry+8), service, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((62, ry+30), f"用户：{user}  |  {order_id}", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        draw.text((62, ry+48), f"核销时间：{time}", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        ry += 73
    
    save_image(img, "21_verify_miniapp.png")

def gen_customer_service():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "在线客服", has_back=True, bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # AI/Human toggle
    ty = 100
    draw_rounded_rect(draw, [PHONE_W//2-80, ty, PHONE_W//2+80, ty+32], 16, fill=COLORS['white'])
    draw_rounded_rect(draw, [PHONE_W//2-78, ty+2, PHONE_W//2, ty+30], 14, fill=COLORS['primary'])
    draw.text((PHONE_W//2-65, ty+7), "AI客服", fill=hex_to_rgb('#FFFFFF'), font=get_font(13, bold=True))
    draw.text((PHONE_W//2+15, ty+7), "人工客服", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(13))
    
    # Chat messages
    my = ty + 45
    
    # AI welcome
    draw_circle(draw, (36, my+15), 16, fill=COLORS['primary'])
    draw.text((28, my+6), "🤖", font=get_font(14))
    draw_rounded_rect(draw, [60, my, PHONE_W-40, my+70], 14, fill=COLORS['white'])
    draw.text((74, my+10), "您好！我是宾尼小康AI客服 🌿", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
    draw.text((74, my+32), "请问有什么可以帮您的？", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((74, my+52), "以下是常见问题，您可以直接点击：", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    my += 80
    
    # Quick questions
    questions = ["如何使用优惠券？", "退款政策说明", "如何预约服务？", "积分如何获取？"]
    qx = 60
    qy = my
    for q in questions:
        f = get_font(12)
        tw = draw.textlength(q, font=f)
        if qx + tw + 20 > PHONE_W - 40:
            qx = 60
            qy += 32
        draw_rounded_rect(draw, [qx, qy, qx+tw+16, qy+26], 13, fill=COLORS['white'], outline=COLORS['primary'])
        draw.text((qx+8, qy+5), q, fill=hex_to_rgb(COLORS['primary']), font=f)
        qx += tw + 22
    
    my = qy + 40
    
    # User question
    user_msg = "我想申请退款"
    f_msg = get_font(14)
    tw = draw.textlength(user_msg, font=f_msg)
    draw_rounded_rect(draw, [PHONE_W-30-tw-24, my, PHONE_W-30, my+36], 14, fill=COLORS['chat_user'])
    draw.text((PHONE_W-30-tw-12, my+8), user_msg, fill=hex_to_rgb(COLORS['text_primary']), font=f_msg)
    
    my += 50
    
    # AI response with structured info
    draw_circle(draw, (36, my+15), 16, fill=COLORS['primary'])
    draw.text((28, my+6), "🤖", font=get_font(14))
    draw_rounded_rect(draw, [60, my, PHONE_W-30, my+170], 14, fill=COLORS['white'])
    
    draw.text((74, my+10), "关于退款，以下是退款政策说明：", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
    draw.text((74, my+34), "📌 退款规则：", fill=hex_to_rgb(COLORS['primary']), font=get_font(12, bold=True))
    draw.text((74, my+54), "• 未核销/未使用的订单可全额退款", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    draw.text((74, my+72), "• 已核销/已使用的订单不可退款", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    draw.text((74, my+92), "• 退款将在3个工作日内原路返回", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    
    draw.text((74, my+118), "请问您需要退款哪个订单？", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(12))
    
    # Transfer to human
    draw_rounded_rect(draw, [74, my+140, 200, my+162], 11, fill=COLORS['accent_light'])
    draw.text((82, my+143), "🙋 转人工客服", fill=hex_to_rgb(COLORS['accent']), font=get_font(12))
    
    # Input
    input_y = PHONE_H - 60
    draw.rectangle([0, input_y, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['white']))
    draw.line([(0, input_y), (PHONE_W, input_y)], fill=hex_to_rgb(COLORS['border']), width=1)
    draw_rounded_rect(draw, [15, input_y+10, PHONE_W-80, input_y+46], 20, fill=COLORS['divider'])
    draw.text((30, input_y+18), "输入您的问题...", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(14))
    draw_rounded_rect(draw, [PHONE_W-70, input_y+12, PHONE_W-15, input_y+44], 16, fill=COLORS['primary'])
    draw.text((PHONE_W-58, input_y+18), "发送", fill=hex_to_rgb('#FFFFFF'), font=get_font(14))
    
    save_image(img, "22_customer_service.png")

gen_verify_miniapp()
gen_customer_service()
print("Done: verify + customer service")
