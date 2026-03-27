"""生成服务预约商城页 + 订单管理页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_services():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Header
    draw_gradient_rect(img, [0, 0, PHONE_W, 140], COLORS['gradient_start'], COLORS['gradient_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    draw.text((20, 50), "健康服务", fill=hex_to_rgb('#FFFFFF'), font=get_font(22, bold=True))
    draw.text((20, 78), "专业健康服务，一站式预约", fill=hex_to_rgb('#FFFFFFBB'), font=get_font(13))
    
    # Search
    draw_rounded_rect(draw, [20, 108, PHONE_W-20, 135], 14, fill='#FFFFFF30')
    draw.text((38, 114), "🔍 搜索服务项目...", fill=hex_to_rgb('#FFFFFFAA'), font=get_font(13))
    
    # Category tabs
    ty = 148
    categories = ["全部", "口腔服务", "体检服务", "专家咨询", "健康食品", "养老服务"]
    tx = 15
    for i, cat in enumerate(categories):
        f = get_font(13, bold=(i==0))
        tw = draw.textlength(cat, font=f)
        if i == 0:
            draw_rounded_rect(draw, [tx, ty, tx+tw+16, ty+28], 14, fill=COLORS['primary'])
            draw.text((tx+8, ty+5), cat, fill=hex_to_rgb('#FFFFFF'), font=f)
        else:
            draw.text((tx+8, ty+5), cat, fill=hex_to_rgb(COLORS['text_secondary']), font=f)
        tx += tw + 22
    
    # Service cards
    sy = ty + 40
    services = [
        ("🦷", "口腔清洁护理套餐", "专业洗牙+口腔检查", "¥198", "¥298", "已售 1.2k", COLORS['info']),
        ("🔬", "全面健康体检套餐", "28项深度检查", "¥688", "¥998", "已售 856", COLORS['primary']),
        ("👨‍⚕️", "专家一对一咨询", "三甲医院专家30分钟", "¥299", "¥499", "已售 523", COLORS['accent']),
        ("🥗", "有机健康蔬果礼盒", "新鲜有机蔬果 5kg装", "¥128", "¥168", "已售 2.1k", COLORS['success']),
    ]
    
    for icon, title, desc, price, orig_price, sales, color in services:
        draw_card(draw, [20, sy, PHONE_W-20, sy+120], 14)
        
        # Image placeholder
        draw_rounded_rect(draw, [28, sy+8, 128, sy+112], 10, fill=color+'15')
        draw.text((60, sy+40), icon, font=get_font(32))
        
        # Info
        draw.text((138, sy+12), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15, bold=True))
        draw.text((138, sy+35), desc, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        
        # Tags
        tag_y = sy + 58
        draw_rounded_rect(draw, [138, tag_y, 188, tag_y+20], 4, fill=COLORS['primary_light'])
        draw.text((143, tag_y+3), "平台自营", fill=hex_to_rgb(COLORS['primary']), font=get_font(10))
        draw_rounded_rect(draw, [193, tag_y, 243, tag_y+20], 4, fill=COLORS['accent_light'])
        draw.text((198, tag_y+3), "限时优惠", fill=hex_to_rgb(COLORS['accent']), font=get_font(10))
        
        # Price
        draw.text((138, sy+88), price, fill=hex_to_rgb(COLORS['danger']), font=get_font(18, bold=True))
        f_orig = get_font(12)
        draw.text((195, sy+92), orig_price, fill=hex_to_rgb(COLORS['text_tertiary']), font=f_orig)
        # Strikethrough
        otw = draw.textlength(orig_price, font=f_orig)
        draw.line([(195, sy+99), (195+otw, sy+99)], fill=hex_to_rgb(COLORS['text_tertiary']), width=1)
        
        # Sales
        draw.text((PHONE_W-90, sy+92), sales, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        # Buy button
        draw_rounded_rect(draw, [PHONE_W-85, sy+58, PHONE_W-30, sy+80], 11, fill=COLORS['primary'])
        draw.text((PHONE_W-75, sy+61), "立即预约", fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
        
        sy += 132
    
    draw_bottom_tab_bar(draw, img, active_index=1)
    
    save_image(img, "11_services_page.png")

def gen_order_management():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "我的订单", has_back=True, bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Order tabs
    ty = 95
    draw.rectangle([0, ty, PHONE_W, ty+42], fill=hex_to_rgb(COLORS['white']))
    tabs = ["全部", "待支付", "待使用", "待发货", "已完成"]
    tw_each = PHONE_W // len(tabs)
    for i, tab in enumerate(tabs):
        f = get_font(13, bold=(i==0))
        tw = draw.textlength(tab, font=f)
        tx = i * tw_each + tw_each//2 - tw//2
        color = COLORS['primary'] if i == 0 else COLORS['text_secondary']
        draw.text((tx, ty+12), tab, fill=hex_to_rgb(color), font=f)
        if i == 0:
            draw_rounded_rect(draw, [tx, ty+34, tx+tw, ty+37], 2, fill=COLORS['primary'])
        # Badge for pending
        if i == 1:
            draw_circle(draw, (tx+tw+8, ty+10), 8, fill=COLORS['danger'])
            draw.text((tx+tw+4, ty+4), "2", fill=hex_to_rgb('#FFFFFF'), font=get_font(10))
    
    draw.line([(0, ty+42), (PHONE_W, ty+42)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    # Order cards
    oy = ty + 52
    orders = [
        ("口腔清洁护理套餐", "🦷", "待使用", "¥198", "2025-03-20", COLORS['primary'], "去核销"),
        ("有机健康蔬果礼盒", "🥗", "配送中", "¥128", "2025-03-18", COLORS['info'], "查看物流"),
        ("全面健康体检套餐", "🔬", "已完成", "¥688", "2025-03-01", COLORS['success'], "再次预约"),
    ]
    
    for title, icon, status, price, date, color, action in orders:
        draw_card(draw, [20, oy, PHONE_W-20, oy+140], 14)
        
        # Order header
        draw.text((30, oy+10), "订单编号: BN20250320001", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        draw_tag(draw, (PHONE_W-90, oy+8), status, color)
        
        draw.line([(30, oy+35), (PHONE_W-30, oy+35)], fill=hex_to_rgb(COLORS['divider']), width=1)
        
        # Order content
        draw_rounded_rect(draw, [30, oy+42, 90, oy+102], 8, fill=color+'15')
        draw.text((48, oy+58), icon, font=get_font(24))
        
        draw.text((100, oy+48), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((100, oy+72), f"下单时间：{date}", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        draw.text((100, oy+92), price, fill=hex_to_rgb(COLORS['danger']), font=get_font(16, bold=True))
        
        # Action buttons
        draw.line([(30, oy+110), (PHONE_W-30, oy+110)], fill=hex_to_rgb(COLORS['divider']), width=1)
        
        draw_rounded_rect(draw, [PHONE_W-120, oy+115, PHONE_W-30, oy+135], 10, fill=COLORS['primary'])
        f_a = get_font(12)
        atw = draw.textlength(action, font=f_a)
        draw.text((PHONE_W-75-atw//2, oy+118), action, fill=hex_to_rgb('#FFFFFF'), font=f_a)
        
        if status != "已完成":
            draw_rounded_rect(draw, [PHONE_W-220, oy+115, PHONE_W-130, oy+135], 10, outline=COLORS['border'])
            draw.text((PHONE_W-208, oy+118), "申请退款", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        
        oy += 152
    
    draw_bottom_tab_bar(draw, img, active_index=4)
    
    save_image(img, "12_order_management.png")

gen_services()
gen_order_management()
print("Done: services + orders")
