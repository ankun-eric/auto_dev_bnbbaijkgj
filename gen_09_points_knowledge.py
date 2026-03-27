"""生成积分商城/会员中心页 + 健康知识科普页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_points_center():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Gradient header
    draw_gradient_rect(img, [0, 0, PHONE_W, 250], COLORS['gradient_start'], '#1D8A53', 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    draw.text((16, 48), "‹", fill=hex_to_rgb('#FFFFFF'), font=get_font(24, bold=True))
    font_t = get_font(18, bold=True)
    tw = draw.textlength("积分中心", font=font_t)
    draw.text((PHONE_W//2-tw//2, 52), "积分中心", fill=hex_to_rgb('#FFFFFF'), font=font_t)
    draw.text((PHONE_W-50, 55), "规则", fill=hex_to_rgb('#FFFFFF'), font=get_font(14))
    
    # Points overview
    cx = PHONE_W // 2
    draw.text((cx-50, 100), "我的积分", fill=hex_to_rgb('#FFFFFFBB'), font=get_font(13))
    draw.text((cx-55, 125), "3,680", fill=hex_to_rgb('#FFFFFF'), font=get_font(36, bold=True))
    
    # Level badge
    draw_rounded_rect(draw, [cx-45, 175, cx+45, 198], 12, fill='#FFD700')
    draw.text((cx-35, 179), "🌟 黄金会员", fill=hex_to_rgb('#8B6914'), font=get_font(12, bold=True))
    draw.text((cx-60, 205), "距下一等级还需 1,320 积分", fill=hex_to_rgb('#FFFFFFAA'), font=get_font(11))
    draw_progress_bar(draw, [60, 225, PHONE_W-60, 233], 0.74, bar_color='#FFD700', bg_color='#FFFFFF30')
    
    # Tab bar
    ty = 248
    draw.rectangle([0, ty, PHONE_W, ty+38], fill=hex_to_rgb(COLORS['white']))
    tabs = ["积分商城", "积分获取", "积分记录"]
    tw_each = PHONE_W // 3
    for i, tab in enumerate(tabs):
        f = get_font(14, bold=(i==0))
        tw = draw.textlength(tab, font=f)
        tx = i * tw_each + tw_each//2 - tw//2
        color = COLORS['primary'] if i == 0 else COLORS['text_secondary']
        draw.text((tx, ty+10), tab, fill=hex_to_rgb(color), font=f)
        if i == 0:
            draw_rounded_rect(draw, [tx, ty+32, tx+tw, ty+35], 2, fill=COLORS['primary'])
    
    # Points mall items
    sy = ty + 45
    draw.rectangle([0, sy, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Category filter
    cats = ["全部", "虚拟权益", "服务抵扣", "实物商品"]
    cx2 = 20
    for i, cat in enumerate(cats):
        f = get_font(12)
        tw = draw.textlength(cat, font=f)
        if i == 0:
            draw_rounded_rect(draw, [cx2, sy+5, cx2+tw+14, sy+27], 11, fill=COLORS['primary'])
            draw.text((cx2+7, sy+8), cat, fill=hex_to_rgb('#FFFFFF'), font=f)
        else:
            draw_rounded_rect(draw, [cx2, sy+5, cx2+tw+14, sy+27], 11, fill=COLORS['white'])
            draw.text((cx2+7, sy+8), cat, fill=hex_to_rgb(COLORS['text_secondary']), font=f)
        cx2 += tw + 20
    
    # Products grid
    py = sy + 38
    products = [
        ("🎫", "5元优惠券", "500积分", COLORS['accent']),
        ("🤖", "AI问诊次数×3", "800积分", COLORS['primary']),
        ("📱", "话费充值10元", "1000积分", COLORS['info']),
        ("🥤", "健康果汁兑换", "1200积分", COLORS['success']),
        ("🎬", "视频会员月卡", "1500积分", COLORS['danger']),
        ("🧴", "护肤礼盒", "2000积分", COLORS['secondary']),
    ]
    
    gw = (PHONE_W - 52) // 2
    gh = 140
    for i, (icon, name, points, color) in enumerate(products):
        col = i % 2
        row = i // 2
        gx = 20 + col * (gw + 12)
        gy = py + row * (gh + 10)
        draw_card(draw, [gx, gy, gx+gw, gy+gh], 12)
        
        # Image area
        draw_rounded_rect(draw, [gx+6, gy+6, gx+gw-6, gy+80], 8, fill=color+'12')
        draw.text((gx+gw//2-14, gy+25), icon, font=get_font(28))
        
        draw.text((gx+10, gy+88), name, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
        draw.text((gx+10, gy+110), points, fill=hex_to_rgb(COLORS['accent']), font=get_font(12, bold=True))
        
        draw_rounded_rect(draw, [gx+gw-55, gy+108, gx+gw-8, gy+128], 10, fill=COLORS['primary'])
        draw.text((gx+gw-48, gy+111), "兑换", fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
    
    save_image(img, "15_points_center.png")

def gen_knowledge():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "健康知识", has_back=False, right_icon="🔍", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Category tabs
    ty = 95
    draw.rectangle([0, ty, PHONE_W, ty+38], fill=hex_to_rgb(COLORS['white']))
    tabs = ["推荐", "养生", "饮食", "运动", "心理", "专家专栏"]
    tx = 12
    for i, tab in enumerate(tabs):
        f = get_font(13, bold=(i==0))
        tw = draw.textlength(tab, font=f)
        color = COLORS['primary'] if i == 0 else COLORS['text_secondary']
        draw.text((tx, ty+10), tab, fill=hex_to_rgb(color), font=f)
        if i == 0:
            draw_rounded_rect(draw, [tx, ty+32, tx+tw, ty+35], 2, fill=COLORS['primary'])
        tx += tw + 18
    
    # AI recommendation tag
    cy = ty + 44
    draw_rounded_rect(draw, [20, cy, PHONE_W-20, cy+30], 8, fill=COLORS['primary_light'])
    draw.text((30, cy+6), "✨ 根据您的健康档案智能推荐", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    
    # Featured article (big card)
    fy = cy + 40
    draw_card(draw, [20, fy, PHONE_W-20, fy+160], 14)
    draw_rounded_rect(draw, [24, fy+4, PHONE_W-24, fy+100], 12, fill=COLORS['primary_light'])
    draw.text((40, fy+30), "🌿 春季养生专题", fill=hex_to_rgb(COLORS['primary']), font=get_font(20, bold=True))
    draw.text((40, fy+60), "春回大地，健康先行", fill=hex_to_rgb(COLORS['secondary']), font=get_font(14))
    draw_tag(draw, (PHONE_W-80, fy+12), "专题", COLORS['primary'])
    
    draw.text((30, fy+108), "春季养生关键：疏肝理气、调理脾胃", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
    draw.text((30, fy+132), "5分钟阅读  ·  阅读 3.2k  ·  收藏 256", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
    
    # Article list
    ay = fy + 175
    articles = [
        ("高血压患者饮食指南", "张医生", "🩺", "2.1k阅读", "5min"),
        ("每天30分钟运动的科学方法", "李教授", "🏃", "1.8k阅读", "3min"),
        ("失眠怎么办？中西医联合方案", "王主任", "😴", "3.5k阅读", "8min"),
    ]
    
    for title, author, icon, reads, time in articles:
        draw_card(draw, [20, ay, PHONE_W-20, ay+90], 10)
        
        # Thumbnail
        draw_rounded_rect(draw, [28, ay+8, 98, ay+82], 8, fill=COLORS['secondary_light'])
        draw.text((50, ay+30), icon, font=get_font(24))
        
        draw.text((108, ay+10), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((108, ay+34), f"作者：{author}", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        
        # Stats
        draw.text((108, ay+58), f"📖 {reads}", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        draw.text((180, ay+58), f"⏱ {time}", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        draw.text((230, ay+58), "❤️ 收藏", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        
        # Article type tag
        draw_tag(draw, (108, ay+72), "图文", COLORS['info'])
        
        ay += 100
    
    # Video card
    draw_card(draw, [20, ay, PHONE_W-20, ay+90], 10)
    draw_rounded_rect(draw, [28, ay+8, 98, ay+82], 8, fill='#1A1A2E')
    draw.text((52, ay+30), "▶", fill=hex_to_rgb('#FFFFFF'), font=get_font(24))
    draw.text((108, ay+10), "科学减脂：每日10分钟居家锻炼", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
    draw.text((108, ay+34), "健身达人小李", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    draw.text((108, ay+58), "🎥 4.2k播放", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    draw_tag(draw, (108, ay+72), "视频", COLORS['danger'])
    
    draw_bottom_tab_bar(draw, img, active_index=3)
    save_image(img, "16_health_knowledge.png")

gen_points_center()
gen_knowledge()
print("Done: points + knowledge")
