"""生成专家咨询预约页 + 签到页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_expert_page():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "专家咨询", has_back=True, right_icon="🔍", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Filter tabs
    ty = 95
    draw.rectangle([0, ty, PHONE_W, ty+38], fill=hex_to_rgb(COLORS['white']))
    tabs = ["全部", "心血管科", "消化内科", "骨科", "中医科", "营养科"]
    tx = 12
    for i, tab in enumerate(tabs):
        f = get_font(12, bold=(i==0))
        tw = draw.textlength(tab, font=f)
        color = COLORS['primary'] if i == 0 else COLORS['text_secondary']
        draw.text((tx, ty+12), tab, fill=hex_to_rgb(color), font=f)
        if i == 0:
            draw_rounded_rect(draw, [tx, ty+32, tx+tw, ty+35], 2, fill=COLORS['primary'])
        tx += tw + 16
    
    # Expert cards
    ey = ty + 48
    experts = [
        ("张教授", "主任医师", "心血管科", "30年临床经验", "擅长高血压、冠心病、心力衰竭", "4.9", "256", "¥299"),
        ("王主任", "副主任医师", "消化内科", "20年临床经验", "擅长胃炎、肠道疾病、肝病", "4.8", "189", "¥199"),
        ("李医生", "主治医师", "中医科", "15年中医经验", "擅长中医调理、针灸推拿、体质辨识", "4.9", "312", "¥259"),
    ]
    
    for name, title, dept, exp, skill, rating, reviews, price in experts:
        draw_card(draw, [20, ey, PHONE_W-20, ey+175], 14)
        
        # Avatar
        draw_circle(draw, (55, ey+40), 25, fill=COLORS['primary_light'])
        draw.text((43, ey+28), "👨‍⚕️", font=get_font(20))
        
        # Info
        draw.text((90, ey+12), name, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
        draw_tag(draw, (90+draw.textlength(name, font=get_font(16, bold=True))+8, ey+14), title, COLORS['primary'])
        draw.text((90, ey+38), f"{dept}  ·  {exp}", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        
        # Rating
        draw.text((PHONE_W-85, ey+12), f"⭐ {rating}", fill=hex_to_rgb(COLORS['accent']), font=get_font(14, bold=True))
        draw.text((PHONE_W-85, ey+32), f"{reviews}条评价", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        
        # Skills
        draw.text((30, ey+70), "擅长领域：", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        draw.text((30, ey+90), skill, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(12))
        
        # Available times
        draw.text((30, ey+115), "可预约时段：", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        slots = ["明天 09:00", "明天 14:00", "后天 10:00"]
        sx = 30
        for slot in slots:
            f_s = get_font(11)
            sw = draw.textlength(slot, font=f_s)
            draw_rounded_rect(draw, [sx, ey+132, sx+sw+12, ey+152], 6, fill=COLORS['primary_light'])
            draw.text((sx+6, ey+135), slot, fill=hex_to_rgb(COLORS['primary']), font=f_s)
            sx += sw + 18
        
        # Price and book button
        draw.text((30, ey+158), price, fill=hex_to_rgb(COLORS['danger']), font=get_font(16, bold=True))
        draw.text((80, ey+162), "/次", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        draw_rounded_rect(draw, [PHONE_W-110, ey+150, PHONE_W-30, ey+172], 11, fill=COLORS['primary'])
        draw.text((PHONE_W-100, ey+153), "立即预约", fill=hex_to_rgb('#FFFFFF'), font=get_font(12))
        
        ey += 187
    
    draw_bottom_tab_bar(draw, img, active_index=1)
    save_image(img, "23_expert_page.png")

def gen_sign_in():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "每日签到", has_back=True, bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Streak card
    sy = 100
    draw_card(draw, [20, sy, PHONE_W-20, sy+120], 16)
    
    cx = PHONE_W // 2
    draw.text((cx-60, sy+12), "已连续签到", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(14))
    draw.text((cx-30, sy+35), "7", fill=hex_to_rgb(COLORS['primary']), font=get_font(40, bold=True))
    draw.text((cx+20, sy+55), "天", fill=hex_to_rgb(COLORS['primary']), font=get_font(16))
    
    # Weekly view
    days = ["一", "二", "三", "四", "五", "六", "日"]
    dw = (PHONE_W - 60) // 7
    for i, day in enumerate(days):
        dx = 30 + i * dw + dw//2
        dy = sy + 85
        is_checked = i < 5
        is_today = i == 4
        
        if is_today:
            draw_circle(draw, (dx, dy), 14, fill=COLORS['primary'])
            draw.text((dx-4, dy-7), "✓", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
        elif is_checked:
            draw_circle(draw, (dx, dy), 14, fill=COLORS['success']+'30')
            draw.text((dx-4, dy-7), "✓", fill=hex_to_rgb(COLORS['success']), font=get_font(12))
        else:
            draw_circle(draw, (dx, dy), 14, outline=COLORS['border'], width=1)
        
        f_d = get_font(10)
        tw = draw.textlength(day, font=f_d)
        draw.text((dx-tw//2, dy-28), day, fill=hex_to_rgb(COLORS['text_tertiary']), font=f_d)
    
    # Sign in button
    btn_y = sy + 135
    draw_gradient_rounded_rect(img, [60, btn_y, PHONE_W-60, btn_y+50], 25, COLORS['gradient_start'], COLORS['gradient_end'])
    draw = ImageDraw.Draw(img)
    f_btn = get_font(17, bold=True)
    tw = draw.textlength("签到领积分 +10", font=f_btn)
    draw.text((cx-tw//2, btn_y+13), "签到领积分 +10", fill=hex_to_rgb('#FFFFFF'), font=f_btn)
    
    # Rewards preview
    ry = btn_y + 65
    draw.text((20, ry), "连续签到奖励", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    ry += 30
    
    rewards = [
        ("3天", "+30积分", True),
        ("7天", "+100积分", False),
        ("15天", "+500积分", False),
        ("30天", "+1500积分", False),
    ]
    
    rw = (PHONE_W - 52) // 4
    for i, (days_r, points, done) in enumerate(rewards):
        rx = 20 + i * (rw + 8)
        draw_card(draw, [rx, ry, rx+rw, ry+80], 10)
        
        if done:
            draw_circle(draw, (rx+rw//2, ry+25), 15, fill=COLORS['success'])
            draw.text((rx+rw//2-5, ry+17), "✓", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
        else:
            draw_circle(draw, (rx+rw//2, ry+25), 15, fill=COLORS['divider'])
            draw.text((rx+rw//2-5, ry+17), "🎁", font=get_font(12))
        
        f_d = get_font(11, bold=True)
        tw = draw.textlength(days_r, font=f_d)
        draw.text((rx+rw//2-tw//2, ry+45), days_r, fill=hex_to_rgb(COLORS['text_primary']), font=f_d)
        f_p = get_font(10)
        tw = draw.textlength(points, font=f_p)
        draw.text((rx+rw//2-tw//2, ry+63), points, fill=hex_to_rgb(COLORS['accent']), font=f_p)
    
    # Health tasks
    ty = ry + 100
    draw.text((20, ty), "今日健康任务", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    ty += 28
    
    tasks = [
        ("💧", "喝满8杯水", "+10积分", False),
        ("🏃", "运动30分钟", "+20积分", False),
        ("📋", "完善健康档案", "+50积分", True),
    ]
    
    for icon, task, reward, done in tasks:
        draw_card(draw, [20, ty, PHONE_W-20, ty+50], 8)
        draw.text((32, ty+10), icon, font=get_font(16))
        draw.text((58, ty+14), task, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14))
        draw.text((PHONE_W-120, ty+16), reward, fill=hex_to_rgb(COLORS['accent']), font=get_font(12))
        
        if done:
            draw_rounded_rect(draw, [PHONE_W-65, ty+12, PHONE_W-28, ty+34], 11, fill=COLORS['divider'])
            draw.text((PHONE_W-58, ty+15), "已完成", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        else:
            draw_rounded_rect(draw, [PHONE_W-60, ty+12, PHONE_W-28, ty+34], 11, fill=COLORS['primary'])
            draw.text((PHONE_W-55, ty+15), "去做", fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
        ty += 58
    
    save_image(img, "24_sign_in_page.png")

gen_expert_page()
gen_sign_in()
print("Done: expert + sign-in pages")
