"""生成个人中心页 + 消息通知中心页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_profile():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Gradient header
    draw_gradient_rect(img, [0, 0, PHONE_W, 230], COLORS['gradient_start'], COLORS['gradient_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    draw.text((PHONE_W-40, 52), "⚙️", font=get_font(18))
    
    # Avatar and info
    cx = PHONE_W // 2
    draw_circle(draw, (cx, 120), 38, fill='#FFFFFF')
    draw_avatar(draw, (cx, 120), 35)
    
    draw.text((cx-30, 168), "小明", fill=hex_to_rgb('#FFFFFF'), font=get_font(20, bold=True))
    
    # Level badge
    draw_rounded_rect(draw, [cx-50, 195, cx+50, 215], 10, fill='#FFD700')
    draw.text((cx-40, 198), "🌟 黄金会员", fill=hex_to_rgb('#8B6914'), font=get_font(12, bold=True))
    
    # Stats row
    draw.rectangle([0, 230, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    stats_y = 238
    draw_card(draw, [20, stats_y, PHONE_W-20, stats_y+65], 14)
    stat_items = [("3,680", "积分"), ("15", "优惠券"), ("7", "收藏"), ("23", "足迹")]
    sw = (PHONE_W - 40) // 4
    for i, (val, label) in enumerate(stat_items):
        sx = 20 + i * sw + sw//2
        draw.text((sx-draw.textlength(val, font=get_font(18, bold=True))//2, stats_y+10),
                  val, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(18, bold=True))
        f_l = get_font(11)
        draw.text((sx-draw.textlength(label, font=f_l)//2, stats_y+35),
                  label, fill=hex_to_rgb(COLORS['text_secondary']), font=f_l)
        if i < 3:
            draw.line([(20+sw*(i+1), stats_y+12), (20+sw*(i+1), stats_y+52)], fill=hex_to_rgb(COLORS['divider']), width=1)
    
    # Order quick access
    oy = stats_y + 78
    draw_card(draw, [20, oy, PHONE_W-20, oy+80], 12)
    draw.text((30, oy+8), "我的订单", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15, bold=True))
    draw.text((PHONE_W-80, oy+10), "全部订单 ›", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    
    order_items = [("💰", "待支付", "2"), ("📋", "待使用", "1"), ("🚚", "待收货", ""), ("⭐", "待评价", "")]
    ow = (PHONE_W - 40) // 4
    for i, (icon, label, badge) in enumerate(order_items):
        ox = 20 + i * ow + ow//2
        draw.text((ox-10, oy+32), icon, font=get_font(18))
        f_l = get_font(10)
        tw = draw.textlength(label, font=f_l)
        draw.text((ox-tw//2, oy+58), label, fill=hex_to_rgb(COLORS['text_secondary']), font=f_l)
        if badge:
            draw_circle(draw, (ox+12, oy+30), 8, fill=COLORS['danger'])
            draw.text((ox+8, oy+24), badge, fill=hex_to_rgb('#FFFFFF'), font=get_font(10))
    
    # Menu items
    my = oy + 95
    menus = [
        ("🏥", "健康档案", ""),
        ("👨‍👩‍👧", "家庭中心", ""),
        ("📊", "健康报告", "本周报告已生成"),
        ("🎫", "积分中心", "3,680积分"),
        ("💬", "客服中心", ""),
        ("📍", "收货地址", ""),
        ("🔔", "消息通知", "3条未读"),
        ("⭐", "收藏夹", ""),
        ("ℹ️", "关于我们", ""),
    ]
    
    for icon, title, detail in menus:
        draw_card(draw, [20, my, PHONE_W-20, my+48], 8)
        draw.text((32, my+10), icon, font=get_font(16))
        draw.text((58, my+13), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14))
        if detail:
            f_d = get_font(12)
            dw = draw.textlength(detail, font=f_d)
            draw.text((PHONE_W-45-dw, my+15), detail, fill=hex_to_rgb(COLORS['text_tertiary']), font=f_d)
        draw.text((PHONE_W-32, my+15), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(14))
        my += 52
    
    draw_bottom_tab_bar(draw, img, active_index=4)
    save_image(img, "17_profile_page.png")

def gen_messages():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "消息中心", has_back=True, right_icon="✓", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Message categories
    cy = 100
    draw_card(draw, [20, cy, PHONE_W-20, cy+85], 14)
    cats = [
        ("📋", "订单通知", "2", COLORS['primary']),
        ("💊", "健康提醒", "1", COLORS['success']),
        ("📢", "系统公告", "", COLORS['info']),
        ("🤖", "AI消息", "", COLORS['secondary']),
    ]
    cw = (PHONE_W - 40) // 4
    for i, (icon, name, badge, color) in enumerate(cats):
        cx2 = 20 + i * cw + cw//2
        draw_circle(draw, (cx2, cy+28), 20, fill=color+'18')
        draw.text((cx2-10, cy+16), icon, font=get_font(16))
        if badge:
            draw_circle(draw, (cx2+14, cy+12), 8, fill=COLORS['danger'])
            draw.text((cx2+10, cy+6), badge, fill=hex_to_rgb('#FFFFFF'), font=get_font(10))
        f_n = get_font(10)
        tw = draw.textlength(name, font=f_n)
        draw.text((cx2-tw//2, cy+55), name, fill=hex_to_rgb(COLORS['text_secondary']), font=f_n)
    
    # Messages list
    my = cy + 100
    draw.text((20, my), "最近消息", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    my += 28
    
    messages = [
        ("🔔", "服药提醒", "该服药啦！氨氯地平5mg，早餐后服用", "10分钟前", True, COLORS['success']),
        ("📦", "订单通知", "您的口腔清洁护理套餐已确认，请在3日内到店使用", "1小时前", True, COLORS['primary']),
        ("📊", "健康报告", "您的本周健康周报已生成，点击查看", "今天 08:00", True, COLORS['info']),
        ("🤖", "AI诊室", "您上次的问诊记录已保存，可随时查看", "昨天 15:30", False, COLORS['secondary']),
        ("📢", "系统通知", "宾尼小康 v1.2 新版本上线，多项功能优化", "3月25日", False, COLORS['text_tertiary']),
        ("💰", "积分通知", "恭喜获得 +20 积分（每日签到奖励）", "3月25日", False, COLORS['accent']),
    ]
    
    for icon, title, content, time, unread, color in messages:
        draw_card(draw, [20, my, PHONE_W-20, my+72], 10)
        
        # Icon
        draw_circle(draw, (48, my+36), 18, fill=color+'18')
        draw.text((38, my+24), icon, font=get_font(16))
        
        # Unread dot
        if unread:
            draw_circle(draw, (32, my+15), 4, fill=COLORS['danger'])
        
        # Content
        draw.text((74, my+10), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((PHONE_W-90, my+12), time, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        
        # Truncate content
        max_chars = 22
        display_content = content[:max_chars] + "..." if len(content) > max_chars else content
        draw.text((74, my+34), display_content, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        
        my += 80
    
    save_image(img, "18_messages_page.png")

gen_profile()
gen_messages()
print("Done: profile + messages")
