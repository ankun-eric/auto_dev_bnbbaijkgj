"""生成启动页和登录注册页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_splash():
    img = Image.new('RGBA', (PHONE_W, PHONE_H), hex_to_rgb('#FFFFFF'))
    draw = ImageDraw.Draw(img)
    
    # Gradient background top area
    draw_gradient_rect(img, [0, 0, PHONE_W, PHONE_H//2+100], '#2EAD6B', '#4EBBAA', 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    # Decorative circles
    draw_circle(draw, (50, 200), 80, fill='#FFFFFF15')
    draw_circle(draw, (340, 150), 60, fill='#FFFFFF10')
    draw_circle(draw, (300, 350), 100, fill='#FFFFFF08')
    
    # App Logo area
    cx = PHONE_W // 2
    draw_circle(draw, (cx, 280), 60, fill='#FFFFFF')
    # Cross / health icon inside
    draw_rounded_rect(draw, [cx-20, 260, cx+20, 300], 4, fill=COLORS['primary'])
    draw_rounded_rect(draw, [cx-8, 248, cx+8, 312], 4, fill=COLORS['primary'])
    # Heart shape hint
    draw.text((cx-7, 268), "♥", fill=hex_to_rgb('#FFFFFF'), font=get_font(16))
    
    # App name
    font_title = get_font(32, bold=True)
    tw = draw.textlength("宾尼小康", font=font_title)
    draw.text((cx - tw//2, 365), "宾尼小康", fill=hex_to_rgb('#FFFFFF'), font=font_title)
    
    font_sub = get_font(15)
    tw2 = draw.textlength("AI健康管家 · 守护您的每一天", font=font_sub)
    draw.text((cx - tw2//2, 410), "AI健康管家 · 守护您的每一天", fill=hex_to_rgb('#FFFFFFCC'), font=font_sub)
    
    # Bottom area - white
    # Wave shape transition
    for x in range(PHONE_W):
        wave_y = int(PHONE_H//2 + 100 + 20 * math.sin(x * 3.14159 / PHONE_W * 2))
        draw.line([(x, wave_y), (x, PHONE_H)], fill=hex_to_rgb('#FFFFFF'))
    
    # Features preview
    features = [
        ("🤖", "AI问诊", "智能健康助手"),
        ("📋", "体检解读", "专业报告分析"),
        ("🏥", "中医辨证", "传统养生方案"),
    ]
    
    for i, (icon, title, desc) in enumerate(features):
        fx = 40 + i * 115
        fy = PHONE_H//2 + 160
        draw_rounded_rect(draw, [fx, fy, fx+100, fy+90], 12, fill=COLORS['primary_light'])
        draw.text((fx+35, fy+10), icon, fill=hex_to_rgb(COLORS['primary']), font=get_font(24))
        f1 = get_font(13, bold=True)
        tw = draw.textlength(title, font=f1)
        draw.text((fx+50-tw//2, fy+42), title, fill=hex_to_rgb(COLORS['text_primary']), font=f1)
        f2 = get_font(10)
        tw = draw.textlength(desc, font=f2)
        draw.text((fx+50-tw//2, fy+62), desc, fill=hex_to_rgb(COLORS['text_secondary']), font=f2)

    # Version info
    font_ver = get_font(11)
    tw = draw.textlength("v1.0.0", font=font_ver)
    draw.text((cx - tw//2, PHONE_H - 60), "v1.0.0", fill=hex_to_rgb(COLORS['text_tertiary']), font=font_ver)
    
    save_image(img, "01_splash_screen.png")

def gen_login():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    
    # Top gradient header
    draw_gradient_rect(img, [0, 0, PHONE_W, 280], COLORS['gradient_start'], COLORS['gradient_end'], 'vertical')
    draw = ImageDraw.Draw(img)
    draw_status_bar(draw, 0, light=True)
    
    # Decorative
    draw_circle(draw, (-20, 100), 120, fill='#FFFFFF10')
    draw_circle(draw, (PHONE_W+30, 200), 100, fill='#FFFFFF08')
    
    # Logo and title
    cx = PHONE_W // 2
    draw_circle(draw, (cx, 130), 35, fill='#FFFFFF')
    draw_rounded_rect(draw, [cx-12, 118, cx+12, 142], 3, fill=COLORS['primary'])
    draw_rounded_rect(draw, [cx-5, 108, cx+5, 152], 3, fill=COLORS['primary'])
    
    font_t = get_font(24, bold=True)
    tw = draw.textlength("宾尼小康", font=font_t)
    draw.text((cx - tw//2, 178), "宾尼小康", fill=hex_to_rgb('#FFFFFF'), font=font_t)
    
    font_s = get_font(13)
    tw = draw.textlength("您的AI健康管家", font=font_s)
    draw.text((cx - tw//2, 210), "您的AI健康管家", fill=hex_to_rgb('#FFFFFFBB'), font=font_s)
    
    # Login card
    card_y = 260
    draw_rounded_rect(draw, [24, card_y, PHONE_W-24, card_y+420], 20, fill=COLORS['white'])
    
    # Tabs: 验证码登录 / 密码登录
    tab_y = card_y + 20
    tab_font = get_font(16, bold=True)
    draw.text((50, tab_y), "验证码登录", fill=hex_to_rgb(COLORS['primary']), font=tab_font)
    draw_rounded_rect(draw, [50, tab_y+28, 130, tab_y+31], 2, fill=COLORS['primary'])
    draw.text((170, tab_y), "密码登录", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(16))
    
    # Phone input
    iy = tab_y + 60
    draw.line([(40, iy+40), (PHONE_W-64, iy+40)], fill=hex_to_rgb(COLORS['border']), width=1)
    draw.text((48, iy+5), "📱", font=get_font(18))
    draw.text((78, iy+8), "+86", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15))
    draw.text((120, iy+8), "|", fill=hex_to_rgb(COLORS['border']), font=get_font(15))
    draw.text((135, iy+8), "请输入手机号", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(15))
    
    # Verification code input
    iy2 = iy + 60
    draw.line([(40, iy2+40), (PHONE_W-64, iy2+40)], fill=hex_to_rgb(COLORS['border']), width=1)
    draw.text((48, iy2+5), "🔐", font=get_font(18))
    draw.text((78, iy2+8), "请输入验证码", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(15))
    draw_rounded_rect(draw, [PHONE_W-160, iy2+2, PHONE_W-68, iy2+36], 18, fill=COLORS['primary_light'])
    draw.text((PHONE_W-152, iy2+8), "获取验证码", fill=hex_to_rgb(COLORS['primary']), font=get_font(13))
    
    # Login button
    btn_y = iy2 + 70
    draw_gradient_rounded_rect(img, [40, btn_y, PHONE_W-64, btn_y+48], 24, COLORS['gradient_start'], COLORS['gradient_end'])
    draw = ImageDraw.Draw(img)
    f_btn = get_font(17, bold=True)
    tw = draw.textlength("登 录", font=f_btn)
    draw.text(((PHONE_W)//2 - tw//2, btn_y+13), "登 录", fill=hex_to_rgb('#FFFFFF'), font=f_btn)
    
    # Agreement
    agr_y = btn_y + 65
    agr_font = get_font(11)
    draw_circle(draw, (52, agr_y+7), 7, outline=COLORS['border'], width=1)
    draw.text((64, agr_y), "我已阅读并同意 ", fill=hex_to_rgb(COLORS['text_tertiary']), font=agr_font)
    draw.text((155, agr_y), "用户协议", fill=hex_to_rgb(COLORS['primary']), font=agr_font)
    draw.text((200, agr_y), " 和 ", fill=hex_to_rgb(COLORS['text_tertiary']), font=agr_font)
    draw.text((222, agr_y), "隐私政策", fill=hex_to_rgb(COLORS['primary']), font=agr_font)
    
    # Third party login
    tp_y = agr_y + 55
    draw.line([(40, tp_y), (PHONE_W//2-40, tp_y)], fill=hex_to_rgb(COLORS['border']), width=1)
    f_or = get_font(12)
    tw = draw.textlength("其他登录方式", font=f_or)
    draw.text((PHONE_W//2 - tw//2, tp_y-8), "其他登录方式", fill=hex_to_rgb(COLORS['text_tertiary']), font=f_or)
    draw.line([(PHONE_W//2+40, tp_y), (PHONE_W-64, tp_y)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    tp_y2 = tp_y + 25
    # WeChat
    draw_circle(draw, (PHONE_W//2-60, tp_y2+20), 22, fill='#07C160')
    draw.text((PHONE_W//2-68, tp_y2+10), "微", fill=hex_to_rgb('#FFFFFF'), font=get_font(14, bold=True))
    # Apple
    draw_circle(draw, (PHONE_W//2+60, tp_y2+20), 22, fill='#000000')
    draw.text((PHONE_W//2+52, tp_y2+10), "🍎", fill=hex_to_rgb('#FFFFFF'), font=get_font(14))
    # label
    draw.text((PHONE_W//2-75, tp_y2+48), "微信登录", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    draw.text((PHONE_W//2+42, tp_y2+48), "Apple ID", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(10))
    
    save_image(img, "02_login_page.png")

gen_splash()
gen_login()
print("Done: splash + login")
