"""生成中医辨证页面 + 症状自查页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_tcm():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "中医辨证", has_back=True, bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Banner
    by = 100
    draw_rounded_rect(draw, [20, by, PHONE_W-20, by+100], 16, fill='#FFF8F0')
    draw.text((35, by+12), "🏮 传统中医智慧 × AI科技", fill=hex_to_rgb(COLORS['accent']), font=get_font(15, bold=True))
    draw.text((35, by+38), "结合舌诊、面诊、体质测评", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((35, by+58), "为您提供个性化养生方案", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((PHONE_W-70, by+30), "🧧", font=get_font(40))
    
    # TCM Services Grid
    gy = by + 120
    draw.text((20, gy), "辨证服务", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    gy += 30
    
    services = [
        ("👅", "舌诊分析", "拍舌照AI分析", "#E74C3C"),
        ("😊", "面诊分析", "拍面部AI分析", "#F5A623"),
        ("📝", "体质测评", "九种体质辨识", "#3498DB"),
        ("🌿", "辨证方案", "综合养生推荐", "#27AE60"),
    ]
    
    gw = (PHONE_W - 52) // 2
    gh = 110
    for i, (icon, title, desc, color) in enumerate(services):
        col = i % 2
        row = i // 2
        gx = 20 + col * (gw + 12)
        gy2 = gy + row * (gh + 12)
        draw_card(draw, [gx, gy2, gx+gw, gy2+gh], 14)
        
        draw_circle(draw, (gx+35, gy2+35), 22, fill=color+'18')
        draw.text((gx+24, gy2+22), icon, font=get_font(20))
        
        draw.text((gx+15, gy2+65), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((gx+15, gy2+87), desc, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        # Arrow
        draw.text((gx+gw-25, gy2+65), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(18))
    
    # My Constitution Result
    cy = gy + 2*(gh+12) + 10
    draw.text((20, cy), "我的体质档案", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    cy += 30
    
    draw_card(draw, [20, cy, PHONE_W-20, cy+140], 14)
    
    # Constitution type
    draw_circle(draw, (65, cy+40), 28, fill='#E8F5EE')
    draw.text((50, cy+25), "🌱", font=get_font(24))
    
    draw.text((105, cy+18), "平和质", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(18, bold=True))
    draw.text((105, cy+44), "总体体质偏向：平和质 (72%)", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    # Mini radar chart hint (simplified as bars)
    bar_y = cy + 75
    constitutions = [
        ("平和质", 0.72), ("气虚质", 0.15), ("阳虚质", 0.08), ("湿热质", 0.05)
    ]
    for i, (name, pct) in enumerate(constitutions):
        by2 = bar_y + i * 16
        draw.text((30, by2), name, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(10))
        draw_progress_bar(draw, [90, by2+3, PHONE_W-60, by2+11], pct)
        draw.text((PHONE_W-55, by2), f"{int(pct*100)}%", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    
    # Recommendation section
    ry = cy + 155
    draw.text((20, ry), "养生推荐", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    ry += 30
    
    recs = [
        ("🥦", "饮食调理", "多吃新鲜蔬果，少油少盐"),
        ("🧘", "运动建议", "适宜太极拳、慢跑等有氧运动"),
        ("💆", "穴位保健", "常按足三里、合谷穴"),
    ]
    
    for icon, title, desc in recs:
        draw_card(draw, [20, ry, PHONE_W-20, ry+55], 10)
        draw.text((32, ry+12), icon, font=get_font(18))
        draw.text((62, ry+10), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((62, ry+32), desc, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        draw.text((PHONE_W-35, ry+22), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(16))
        ry += 65
    
    save_image(img, "07_tcm_page.png")

def gen_symptom_check():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "症状自查", has_back=True, bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Progress bar
    py = 100
    draw_rounded_rect(draw, [20, py, PHONE_W-20, py+35], 8, fill=COLORS['white'])
    steps = ["选择部位", "描述症状", "详细信息", "分析结果"]
    step_w = (PHONE_W - 40) // 4
    for i, step in enumerate(steps):
        sx = 20 + i * step_w + step_w // 2
        is_active = i <= 1
        color = COLORS['primary'] if is_active else COLORS['text_tertiary']
        draw_circle(draw, (sx, py+12), 8, fill=color if is_active else COLORS['divider'])
        draw.text((sx-3, py+5), str(i+1), fill=hex_to_rgb('#FFFFFF' if is_active else COLORS['text_tertiary']), font=get_font(10, bold=True))
        f = get_font(9)
        tw = draw.textlength(step, font=f)
        draw.text((sx-tw//2, py+24), step, fill=hex_to_rgb(color), font=f)
        if i < 3:
            nx = 20 + (i+1) * step_w + step_w // 2
            line_color = COLORS['primary'] if i < 1 else COLORS['divider']
            draw.line([(sx+10, py+12), (nx-10, py+12)], fill=hex_to_rgb(line_color), width=2)
    
    # AI Doctor conversation
    cy = py + 50
    draw_circle(draw, (36, cy+15), 16, fill=COLORS['primary'])
    draw.text((28, cy+6), "👨‍⚕️", font=get_font(14))
    draw_rounded_rect(draw, [60, cy, PHONE_W-40, cy+50], 14, fill=COLORS['white'])
    draw.text((74, cy+8), "请告诉我，您现在哪个部位", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13))
    draw.text((74, cy+28), "感到不舒服？", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13))
    
    # Body part selection
    cy += 65
    draw.text((20, cy), "点击选择不适部位", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    
    cy += 28
    # Body outline (simplified)
    draw_card(draw, [20, cy, PHONE_W-20, cy+280], 14)
    
    body_cx = PHONE_W // 2
    body_cy = cy + 130
    
    # Head
    draw_circle(draw, (body_cx, cy+35), 25, outline=COLORS['primary'], width=2)
    draw.text((body_cx-8, cy+25), "头", fill=hex_to_rgb(COLORS['primary']), font=get_font(14))
    
    # Neck
    draw.rectangle([body_cx-8, cy+60, body_cx+8, cy+75], outline=hex_to_rgb(COLORS['text_tertiary']), width=1)
    
    # Torso
    draw_rounded_rect(draw, [body_cx-40, cy+75, body_cx+40, cy+170], 8, outline=COLORS['text_tertiary'], width=1)
    
    # Selected area highlight - 头部
    draw_circle(draw, (body_cx, cy+35), 28, outline=COLORS['danger'], width=2)
    draw_circle(draw, (body_cx, cy+35), 28, fill=COLORS['danger']+'15')
    
    # Labels around body
    parts = [
        (body_cx-100, cy+25, "眼睛"),
        (body_cx+65, cy+25, "耳朵"),
        (body_cx-100, cy+80, "胸部"),
        (body_cx+65, cy+80, "肩膀"),
        (body_cx-100, cy+120, "腹部"),
        (body_cx+65, cy+120, "腰部"),
        (body_cx-100, cy+180, "腿部"),
        (body_cx+65, cy+180, "膝盖"),
    ]
    
    for px, py2, name in parts:
        draw_rounded_rect(draw, [px, py2, px+55, py2+25], 12, fill=COLORS['divider'])
        draw.text((px+8, py2+5), name, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    # Arms
    draw.line([(body_cx-40, cy+85), (body_cx-70, cy+150)], fill=hex_to_rgb(COLORS['text_tertiary']), width=2)
    draw.line([(body_cx+40, cy+85), (body_cx+70, cy+150)], fill=hex_to_rgb(COLORS['text_tertiary']), width=2)
    
    # Legs
    draw.line([(body_cx-15, cy+170), (body_cx-25, cy+250)], fill=hex_to_rgb(COLORS['text_tertiary']), width=2)
    draw.line([(body_cx+15, cy+170), (body_cx+25, cy+250)], fill=hex_to_rgb(COLORS['text_tertiary']), width=2)
    
    # Selected: 头痛
    sel_y = cy + 290
    draw_rounded_rect(draw, [20, sel_y, PHONE_W-20, sel_y+40], 12, fill=COLORS['primary_light'])
    draw.text((35, sel_y+10), "已选择：头部", fill=hex_to_rgb(COLORS['primary']), font=get_font(14, bold=True))
    draw.text((PHONE_W-100, sel_y+10), "重新选择", fill=hex_to_rgb(COLORS['primary']), font=get_font(13))
    
    # Next button
    btn_y = sel_y + 55
    draw_button(draw, [20, btn_y, PHONE_W-20, btn_y+48], "下一步", radius=24)
    
    draw_bottom_tab_bar(draw, img, active_index=2)
    
    save_image(img, "08_symptom_check.png")

gen_tcm()
gen_symptom_check()
print("Done: TCM + symptom pages")
