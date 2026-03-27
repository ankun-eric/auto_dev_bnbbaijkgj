"""生成APP首页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_home():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Top gradient header area
    draw_gradient_rect(img, [0, 0, PHONE_W, 220], COLORS['gradient_start'], COLORS['gradient_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    # Decorative circles
    draw_circle(draw, (350, 30), 60, fill='#FFFFFF08')
    draw_circle(draw, (40, 180), 80, fill='#FFFFFF06')
    
    # User greeting area
    draw_avatar(draw, (36, 58), 16, COLORS['white'])
    draw.text((58, 48), "Hi，小明", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    draw.text((58, 68), "今天也要健康哦~", fill=hex_to_rgb('#FFFFFFBB'), font=get_font(12))
    
    # Notification & message icons
    draw.text((PHONE_W-70, 52), "🔔", font=get_font(20))
    draw.text((PHONE_W-38, 52), "✉️", font=get_font(20))
    # Red dot
    draw_circle(draw, (PHONE_W-55, 52), 5, fill=COLORS['danger'])
    
    # Search bar
    draw_rounded_rect(draw, [20, 95, PHONE_W-20, 130], 18, fill='#FFFFFF30')
    draw.text((42, 103), "🔍", font=get_font(14))
    draw.text((65, 105), "搜索健康问题、症状、药物...", fill=hex_to_rgb('#FFFFFFAA'), font=get_font(13))
    
    # Health overview card
    card_y = 150
    draw_rounded_rect(draw, [20, card_y, PHONE_W-20, card_y+80], 16, fill=COLORS['white'])
    
    stats = [
        ("68", "心率", "bpm", COLORS['danger']),
        ("120/80", "血压", "mmHg", COLORS['info']),
        ("7.5h", "睡眠", "昨晚", COLORS['secondary']),
        ("6,280", "步数", "步", COLORS['primary']),
    ]
    sw = (PHONE_W - 40) // 4
    for i, (val, label, unit, color) in enumerate(stats):
        sx = 20 + i * sw + sw//2
        draw.text((sx - draw.textlength(val, font=get_font(18, bold=True))//2, card_y+15), 
                  val, fill=hex_to_rgb(color), font=get_font(18, bold=True))
        f_l = get_font(11)
        draw.text((sx - draw.textlength(label, font=f_l)//2, card_y+40), 
                  label, fill=hex_to_rgb(COLORS['text_secondary']), font=f_l)
        f_u = get_font(9)
        draw.text((sx - draw.textlength(unit, font=f_u)//2, card_y+56),
                  unit, fill=hex_to_rgb(COLORS['text_tertiary']), font=f_u)
    
    # AI Core Features - 2x2 grid
    grid_y = card_y + 100
    features = [
        ("🤖", "AI智能问诊", "随时随地健康咨询", COLORS['primary']),
        ("📋", "体检报告解读", "AI专业解读分析", COLORS['info']),
        ("🏥", "中医辨证", "舌诊面诊体质测评", COLORS['accent']),
        ("💊", "药物查询", "用药安全智能分析", COLORS['danger']),
    ]
    
    section_font = get_font(16, bold=True)
    draw.text((20, grid_y-5), "AI健康服务", fill=hex_to_rgb(COLORS['text_primary']), font=section_font)
    draw.text((PHONE_W-60, grid_y-2), "更多 ›", fill=hex_to_rgb(COLORS['primary']), font=get_font(13))
    
    grid_y += 25
    gw = (PHONE_W - 52) // 2
    gh = 85
    for i, (icon, title, desc, color) in enumerate(features):
        col = i % 2
        row = i // 2
        gx = 20 + col * (gw + 12)
        gy = grid_y + row * (gh + 12)
        draw_card(draw, [gx, gy, gx+gw, gy+gh], 14)
        
        # Icon circle
        draw_circle(draw, (gx+30, gy+30), 18, fill=color+'20')
        draw.text((gx+20, gy+18), icon, font=get_font(18))
        
        draw.text((gx+56, gy+16), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((gx+56, gy+38), desc, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        
        # Arrow
        draw.text((gx+gw-20, gy+28), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(16))
    
    # Quick Services
    qs_y = grid_y + 2*(gh+12) + 15
    draw.text((20, qs_y), "健康服务", fill=hex_to_rgb(COLORS['text_primary']), font=section_font)
    draw.text((PHONE_W-60, qs_y+3), "更多 ›", fill=hex_to_rgb(COLORS['primary']), font=get_font(13))
    
    qs_y += 30
    services = [
        ("🦷", "口腔服务", COLORS['info']),
        ("🔬", "体检预约", COLORS['primary']),
        ("👨‍⚕️", "专家咨询", COLORS['accent']),
        ("🥗", "健康食品", COLORS['success']),
        ("🏠", "养老服务", COLORS['secondary']),
    ]
    
    svc_w = (PHONE_W - 40) // 5
    for i, (icon, name, color) in enumerate(services):
        sx = 20 + i * svc_w + svc_w//2
        draw_circle(draw, (sx, qs_y+20), 22, fill=color+'18')
        draw.text((sx-10, qs_y+8), icon, font=get_font(18))
        f_n = get_font(10)
        tw = draw.textlength(name, font=f_n)
        draw.text((sx-tw//2, qs_y+48), name, fill=hex_to_rgb(COLORS['text_secondary']), font=f_n)
    
    # Health Knowledge Banner
    bn_y = qs_y + 80
    draw.text((20, bn_y), "健康知识", fill=hex_to_rgb(COLORS['text_primary']), font=section_font)
    draw.text((PHONE_W-60, bn_y+3), "更多 ›", fill=hex_to_rgb(COLORS['primary']), font=get_font(13))
    
    bn_y += 30
    # Article card 1
    draw_card(draw, [20, bn_y, PHONE_W//2-6, bn_y+100], 12)
    draw_rounded_rect(draw, [24, bn_y+4, PHONE_W//2-10, bn_y+55], 10, fill=COLORS['primary_light'])
    draw.text((30, bn_y+15), "🥦 春季养生", fill=hex_to_rgb(COLORS['primary']), font=get_font(16, bold=True))
    draw.text((28, bn_y+62), "春季如何调理身体", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(12, bold=True))
    draw.text((28, bn_y+80), "阅读 2.3k", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    
    # Article card 2
    draw_card(draw, [PHONE_W//2+6, bn_y, PHONE_W-20, bn_y+100], 12)
    draw_rounded_rect(draw, [PHONE_W//2+10, bn_y+4, PHONE_W-24, bn_y+55], 10, fill=COLORS['secondary_light'])
    draw.text((PHONE_W//2+16, bn_y+15), "💤 睡眠指南", fill=hex_to_rgb(COLORS['secondary']), font=get_font(16, bold=True))
    draw.text((PHONE_W//2+14, bn_y+62), "提升睡眠质量秘诀", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(12, bold=True))
    draw.text((PHONE_W//2+14, bn_y+80), "阅读 1.8k", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    
    # Bottom tab bar
    draw_bottom_tab_bar(draw, img, active_index=0)
    
    save_image(img, "03_home_page.png")

gen_home()
print("Done: home page")
