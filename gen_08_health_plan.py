"""生成健康计划与提醒页 + 药物查询页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_health_plan():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "健康计划", has_back=True, right_icon="⚙️", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Today's stats card
    ty = 100
    draw_card(draw, [20, ty, PHONE_W-20, ty+100], 16)
    
    draw.text((35, ty+12), "今日健康任务", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15, bold=True))
    draw.text((35, ty+35), "已完成 3/5 项任务", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    draw_progress_bar(draw, [35, ty+58, PHONE_W-100, ty+66], 0.6)
    draw.text((PHONE_W-90, ty+53), "60%", fill=hex_to_rgb(COLORS['primary']), font=get_font(14, bold=True))
    
    # Points earned today
    draw_rounded_rect(draw, [35, ty+74, 130, ty+92], 9, fill=COLORS['accent_light'])
    draw.text((42, ty+77), "🏆 今日获得 +30 积分", fill=hex_to_rgb(COLORS['accent']), font=get_font(10))
    
    # Today's tasks
    tasks_y = ty + 115
    draw.text((20, tasks_y), "今日任务", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    draw.text((PHONE_W-80, tasks_y+3), "AI推荐 ✨", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    tasks_y += 30
    
    tasks = [
        ("💧", "喝水打卡", "已喝 1200ml / 目标 2000ml", True, 0.6),
        ("🏃", "运动30分钟", "快走或慢跑", True, 1.0),
        ("💊", "服用降压药", "早餐后服用氨氯地平5mg", True, 1.0),
        ("😴", "22:30 前入睡", "保持规律作息", False, 0),
        ("🥦", "吃一份蔬菜", "午餐或晚餐", False, 0),
    ]
    
    for icon, title, desc, done, progress in tasks:
        draw_card(draw, [20, tasks_y, PHONE_W-20, tasks_y+65], 10)
        
        # Checkbox
        if done:
            draw_circle(draw, (42, tasks_y+32), 12, fill=COLORS['success'])
            draw.text((36, tasks_y+24), "✓", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
        else:
            draw_circle(draw, (42, tasks_y+32), 12, outline=COLORS['border'], width=2)
        
        draw.text((62, tasks_y+8), icon, font=get_font(14))
        title_color = COLORS['text_tertiary'] if done else COLORS['text_primary']
        draw.text((84, tasks_y+10), title, fill=hex_to_rgb(title_color), font=get_font(14, bold=True))
        draw.text((84, tasks_y+32), desc, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        if progress > 0 and progress < 1:
            draw_progress_bar(draw, [84, tasks_y+50, PHONE_W-60, tasks_y+56], progress)
        
        if not done:
            draw_rounded_rect(draw, [PHONE_W-70, tasks_y+20, PHONE_W-28, tasks_y+42], 11, fill=COLORS['primary'])
            draw.text((PHONE_W-62, tasks_y+23), "打卡", fill=hex_to_rgb('#FFFFFF'), font=get_font(12))
        
        tasks_y += 73
    
    # Reminders section
    ry = tasks_y + 5
    draw.text((20, ry), "健康提醒", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    draw.text((PHONE_W-80, ry+3), "添加提醒 +", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    ry += 28
    
    reminders = [
        ("⏰", "服药提醒", "每日 08:00", "已开启", COLORS['success']),
        ("💧", "喝水提醒", "每2小时一次", "已开启", COLORS['success']),
        ("🏃", "运动提醒", "每日 18:00", "已关闭", COLORS['text_tertiary']),
    ]
    
    for icon, title, time, status, color in reminders:
        draw_card(draw, [20, ry, PHONE_W-20, ry+50], 8)
        draw.text((32, ry+12), icon, font=get_font(16))
        draw.text((58, ry+8), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
        draw.text((58, ry+28), time, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        
        # Toggle
        toggle_x = PHONE_W - 60
        is_on = status == "已开启"
        if is_on:
            draw_rounded_rect(draw, [toggle_x, ry+16, toggle_x+40, ry+34], 9, fill=COLORS['primary'])
            draw_circle(draw, (toggle_x+30, ry+25), 7, fill='#FFFFFF')
        else:
            draw_rounded_rect(draw, [toggle_x, ry+16, toggle_x+40, ry+34], 9, fill=COLORS['divider'])
            draw_circle(draw, (toggle_x+10, ry+25), 7, fill='#FFFFFF')
        ry += 58
    
    draw_bottom_tab_bar(draw, img, active_index=3)
    save_image(img, "13_health_plan.png")

def gen_drug_query():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "药物查询", has_back=True, right_icon="📷", bg_gradient=True)
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Search bar
    sy = 100
    draw_search_bar(draw, [20, sy, PHONE_W-20, sy+40], "输入药名或拍照识别...")
    
    # Quick actions
    qy = sy + 55
    actions = [
        ("💊", "药名查询", COLORS['primary']),
        ("📷", "拍照识药", COLORS['info']),
        ("⚡", "相互作用", COLORS['danger']),
        ("📋", "用药分析", COLORS['accent']),
    ]
    aw = (PHONE_W - 40) // 4
    for i, (icon, name, color) in enumerate(actions):
        ax = 20 + i * aw + aw//2
        draw_circle(draw, (ax, qy+18), 22, fill=color+'18')
        draw.text((ax-10, qy+6), icon, font=get_font(18))
        f_n = get_font(10)
        tw = draw.textlength(name, font=f_n)
        draw.text((ax-tw//2, qy+46), name, fill=hex_to_rgb(COLORS['text_secondary']), font=f_n)
    
    # Drug result card
    dy = qy + 75
    draw.text((20, dy), "搜索结果", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    dy += 28
    
    draw_card(draw, [20, dy, PHONE_W-20, dy+250], 14)
    
    # Drug header
    draw_rounded_rect(draw, [30, dy+10, 80, dy+60], 8, fill=COLORS['primary_light'])
    draw.text((43, dy+22), "💊", font=get_font(24))
    
    draw.text((90, dy+12), "氨氯地平片", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    draw.text((90, dy+36), "Amlodipine Tablets", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
    draw_tag(draw, (90, dy+55), "处方药", COLORS['danger'])
    draw_tag(draw, (148, dy+55), "降压药", COLORS['info'])
    
    draw.line([(30, dy+82), (PHONE_W-30, dy+82)], fill=hex_to_rgb(COLORS['divider']), width=1)
    
    # Drug details
    details = [
        ("功效主治", "高血压、冠心病、心绞痛"),
        ("用法用量", "口服，一次5mg，一日一次"),
        ("不良反应", "头痛、水肿、面部潮红等"),
        ("禁忌事项", "对本品过敏者禁用"),
    ]
    
    ddy = dy + 90
    for label, value in details:
        draw.text((30, ddy), label, fill=hex_to_rgb(COLORS['primary']), font=get_font(13, bold=True))
        draw.text((30, ddy+20), value, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        ddy += 42
    
    # AI safety analysis
    ay = dy + 262
    draw_card(draw, [20, ay, PHONE_W-20, ay+100], 14)
    draw_rounded_rect(draw, [20, ay, PHONE_W-20, ay+30], 14, fill=COLORS['primary_light'])
    draw.text((30, ay+6), "🤖 AI用药安全分析", fill=hex_to_rgb(COLORS['primary']), font=get_font(13, bold=True))
    
    draw.text((30, ay+38), "✓ 该药物适合您的当前健康状况", fill=hex_to_rgb(COLORS['success']), font=get_font(12))
    draw.text((30, ay+58), "⚡ 注意：与您正在服用的阿司匹林", fill=hex_to_rgb(COLORS['warning']), font=get_font(12))
    draw.text((30, ay+78), "   无明显相互作用风险", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    # My medications
    my = ay + 115
    draw.text((20, my), "我的用药记录", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    draw.text((PHONE_W-60, my+3), "管理 ›", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    my += 28
    
    meds = [("氨氯地平 5mg", "每日一次，早餐后"), ("阿司匹林 100mg", "每日一次，睡前")]
    for name, dosage in meds:
        draw_card(draw, [20, my, PHONE_W-20, my+45], 8)
        draw.text((32, my+6), "💊", font=get_font(14))
        draw.text((55, my+6), name, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
        draw.text((55, my+26), dosage, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(11))
        my += 53
    
    save_image(img, "14_drug_query.png")

gen_health_plan()
gen_drug_query()
print("Done: health plan + drug query")
