"""生成健康档案页 + 家庭健康中心页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_health_profile():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "健康档案", has_back=True, right_icon="✏️", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # User info card
    uy = 100
    draw_card(draw, [20, uy, PHONE_W-20, uy+90], 16)
    draw_avatar(draw, (60, uy+45), 25)
    draw.text((95, uy+18), "小明", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(18, bold=True))
    draw.text((95, uy+44), "男 · 30岁 · 175cm · 68kg", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((95, uy+66), "血型：A型", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(12))
    # Completeness
    draw_rounded_rect(draw, [PHONE_W-110, uy+20, PHONE_W-35, uy+42], 11, fill=COLORS['primary_light'])
    draw.text((PHONE_W-105, uy+24), "完善度 85%", fill=hex_to_rgb(COLORS['primary']), font=get_font(11))
    
    # Health data sections
    sections = [
        ("📋", "基础信息", "身高、体重、血型等", "已完善"),
        ("⚠️", "过敏史", "青霉素过敏", "已记录"),
        ("🏥", "既往病史", "无重大疾病", "已记录"),
        ("👨‍👩‍👧", "家族病史", "高血压（父亲）", "已记录"),
        ("🏃", "生活习惯", "运动/睡眠/饮食习惯", "待完善"),
        ("📊", "体检记录", "3份报告", "查看趋势"),
        ("💊", "用药记录", "当前用药1种", "管理"),
        ("🏨", "就诊记录", "近6个月2次就诊", "查看"),
    ]
    
    sy = uy + 105
    for icon, title, desc, action in sections:
        draw_card(draw, [20, sy, PHONE_W-20, sy+60], 10)
        draw.text((32, sy+15), icon, font=get_font(18))
        draw.text((62, sy+10), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((62, sy+32), desc, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        action_color = COLORS['primary'] if action != "待完善" else COLORS['warning']
        f_a = get_font(12)
        tw = draw.textlength(action, font=f_a)
        draw.text((PHONE_W-35-tw, sy+22), action, fill=hex_to_rgb(action_color), font=f_a)
        draw.text((PHONE_W-30, sy+22), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(14))
        sy += 68
    
    save_image(img, "09_health_profile.png")

def gen_family_center():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "家庭健康中心", has_back=True, right_icon="➕", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Family members horizontal scroll
    fy = 105
    draw.text((20, fy), "家庭成员", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    fy += 30
    
    members = [
        ("我", "🧑", COLORS['primary'], True),
        ("妈妈", "👩", "#E74C3C", False),
        ("爸爸", "👨", "#3498DB", False),
        ("女儿", "👧", "#F5A623", False),
        ("添加", "➕", COLORS['border'], False),
    ]
    
    mx = 20
    for name, icon, color, is_active in members:
        if is_active:
            draw_circle(draw, (mx+28, fy+28), 30, fill=color)
            draw_circle(draw, (mx+28, fy+28), 32, outline=color, width=2)
        else:
            draw_circle(draw, (mx+28, fy+28), 28, fill=color+'20')
        draw.text((mx+16, fy+15), icon, font=get_font(20))
        f_n = get_font(11)
        tw = draw.textlength(name, font=f_n)
        draw.text((mx+28-tw//2, fy+62), name, fill=hex_to_rgb(COLORS['text_primary'] if name != "添加" else COLORS['text_tertiary']), font=f_n)
        mx += 72
    
    # Selected member health overview
    fy += 90
    draw_card(draw, [20, fy, PHONE_W-20, fy+100], 14)
    draw.text((35, fy+12), "妈妈的健康概况", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15, bold=True))
    draw.text((35, fy+35), "女 · 55岁 · 160cm · 58kg", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    # Health score
    draw_circle(draw, (PHONE_W-65, fy+45), 28, fill=COLORS['success'])
    draw.text((PHONE_W-78, fy+32), "78", fill=hex_to_rgb('#FFFFFF'), font=get_font(18, bold=True))
    draw.text((PHONE_W-78, fy+52), "健康分", fill=hex_to_rgb('#FFFFFFCC'), font=get_font(9))
    
    # Health alerts
    draw_rounded_rect(draw, [35, fy+60, PHONE_W-100, fy+82], 8, fill=COLORS['warning']+'18')
    draw.text((42, fy+63), "⚡ 注意：血压偏高，建议定期监测", fill=hex_to_rgb(COLORS['warning']), font=get_font(11))
    
    # Family features
    fy += 115
    draw.text((20, fy), "家庭功能", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    fy += 30
    
    features = [
        ("👥", "共享问诊", "替家人AI问诊", COLORS['primary']),
        ("📊", "家庭报告", "整体健康报告", COLORS['info']),
        ("🚨", "紧急求助", "一键SOS通知", COLORS['danger']),
        ("🔗", "关系管理", "成员绑定管理", COLORS['secondary']),
    ]
    
    fw = (PHONE_W - 52) // 2
    fh = 80
    for i, (icon, title, desc, color) in enumerate(features):
        col = i % 2
        row = i // 2
        fx = 20 + col * (fw + 12)
        fy2 = fy + row * (fh + 10)
        draw_card(draw, [fx, fy2, fx+fw, fy2+fh], 12)
        draw_circle(draw, (fx+30, fy2+30), 18, fill=color+'18')
        draw.text((fx+20, fy2+18), icon, font=get_font(16))
        draw.text((fx+55, fy2+18), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
        draw.text((fx+55, fy2+40), desc, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
    
    # Family health timeline
    fy3 = fy + 2*(fh+10) + 10
    draw.text((20, fy3), "家庭健康动态", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    fy3 += 28
    
    timeline = [
        ("今天 09:30", "妈妈", "完成了血压测量记录", COLORS['success']),
        ("昨天 14:00", "爸爸", "完成了体检报告上传", COLORS['info']),
        ("3月25日", "女儿", "完成了每日健康打卡", COLORS['primary']),
    ]
    
    for time, who, what, color in timeline:
        draw_card(draw, [20, fy3, PHONE_W-20, fy3+50], 8)
        draw_circle(draw, (40, fy3+25), 5, fill=color)
        draw.text((55, fy3+8), f"{who}：{what}", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(12))
        draw.text((55, fy3+28), time, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
        fy3 += 58
    
    save_image(img, "10_family_center.png")

gen_health_profile()
gen_family_center()
print("Done: health profile + family center")
