"""生成AI智能问诊对话页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_ai_chat():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Header
    draw_nav_header(draw, img, "AI健康问诊", has_back=True, right_icon="📋", bg_gradient=True)
    
    # Chat background
    draw.rectangle([0, 90, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['bg']))
    
    # Context hint bar
    draw_rounded_rect(draw, [20, 100, PHONE_W-20, 130], 15, fill=COLORS['primary_light'])
    draw.text((32, 106), "💡 已关联您的健康档案，回答更精准", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    
    # Chat messages
    msg_y = 145
    
    # AI welcome message
    draw_circle(draw, (36, msg_y+15), 16, fill=COLORS['primary'])
    draw.text((28, msg_y+6), "🤖", font=get_font(14))
    draw_rounded_rect(draw, [60, msg_y, PHONE_W-50, msg_y+90], 14, fill=COLORS['white'])
    draw.text((74, msg_y+12), "您好！我是宾尼小康AI健康助手", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
    draw.text((74, msg_y+35), "我可以帮您解答健康问题、分析体", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((74, msg_y+55), "检报告、中医辨证等。请问有什么", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw.text((74, msg_y+75), "可以帮您的？", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    
    msg_y += 105
    
    # Quick action buttons
    actions = ["症状自查", "体检解读", "药物查询", "中医辨证"]
    ax = 60
    for act in actions:
        f = get_font(12)
        tw = draw.textlength(act, font=f)
        draw_rounded_rect(draw, [ax, msg_y, ax+tw+20, msg_y+30], 15, fill=COLORS['white'], outline=COLORS['primary'])
        draw.text((ax+10, msg_y+6), act, fill=hex_to_rgb(COLORS['primary']), font=f)
        ax += tw + 28
        if ax > PHONE_W - 80:
            ax = 60
            msg_y += 36
    
    msg_y += 45
    
    # User message
    user_msg = "最近经常头痛，尤其是下午"
    f_msg = get_font(14)
    tw = draw.textlength(user_msg, font=f_msg)
    msg_x = PHONE_W - 30 - tw - 24
    draw_rounded_rect(draw, [msg_x, msg_y, PHONE_W-30, msg_y+40], 14, fill=COLORS['chat_user'])
    draw.text((msg_x+12, msg_y+10), user_msg, fill=hex_to_rgb(COLORS['text_primary']), font=f_msg)
    
    msg_y += 55
    
    # AI response with structured answer
    draw_circle(draw, (36, msg_y+15), 16, fill=COLORS['primary'])
    draw.text((28, msg_y+6), "🤖", font=get_font(14))
    
    ai_card_h = 245
    draw_rounded_rect(draw, [60, msg_y, PHONE_W-30, msg_y+ai_card_h], 14, fill=COLORS['white'])
    
    ay = msg_y + 12
    draw.text((74, ay), "根据您的描述和健康档案，分析如下：", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(13, bold=True))
    
    ay += 28
    draw.text((74, ay), "🔍 可能原因", fill=hex_to_rgb(COLORS['primary']), font=get_font(13, bold=True))
    ay += 22
    draw.text((74, ay), "• 紧张性头痛（最常见）", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    ay += 20
    draw.text((74, ay), "• 颈椎问题引起的头痛", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    ay += 20
    draw.text((74, ay), "• 用眼过度或屏幕疲劳", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    ay += 28
    draw.text((74, ay), "💡 建议措施", fill=hex_to_rgb(COLORS['accent']), font=get_font(13, bold=True))
    ay += 22
    draw.text((74, ay), "1. 适当休息，避免长时间用电脑", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    ay += 20
    draw.text((74, ay), "2. 做颈部拉伸运动缓解肌肉紧张", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    ay += 20
    draw.text((74, ay), "3. 如频繁发作建议就医检查", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    ay += 28
    # Action buttons in AI message
    draw_rounded_rect(draw, [74, ay, 160, ay+28], 14, fill=COLORS['primary_light'])
    draw.text((84, ay+5), "🏥 预约就医", fill=hex_to_rgb(COLORS['primary']), font=get_font(12))
    draw_rounded_rect(draw, [168, ay, 260, ay+28], 14, fill=COLORS['accent_light'])
    draw.text((178, ay+5), "📋 详细报告", fill=hex_to_rgb(COLORS['accent']), font=get_font(12))
    
    # Voice/text indicator
    msg_y += ai_card_h + 15
    draw.text((PHONE_W//2-50, msg_y), "上午 10:32", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    
    # Input area at bottom
    input_y = PHONE_H - 83 - 60
    draw.rectangle([0, input_y, PHONE_W, PHONE_H-83], fill=hex_to_rgb(COLORS['white']))
    draw.line([(0, input_y), (PHONE_W, input_y)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    # Input field
    draw_rounded_rect(draw, [15, input_y+10, PHONE_W-110, input_y+46], 20, fill=COLORS['divider'])
    draw.text((30, input_y+18), "输入您的健康问题...", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(14))
    
    # Voice button
    draw_circle(draw, (PHONE_W-80, input_y+28), 18, fill=COLORS['primary_light'])
    draw.text((PHONE_W-88, input_y+18), "🎤", font=get_font(14))
    
    # Image button
    draw_circle(draw, (PHONE_W-40, input_y+28), 18, fill=COLORS['primary_light'])
    draw.text((PHONE_W-48, input_y+18), "📷", font=get_font(14))
    
    # Bottom tab bar
    draw_bottom_tab_bar(draw, img, active_index=2)
    
    save_image(img, "04_ai_chat_page.png")

gen_ai_chat()
print("Done: AI chat page")
