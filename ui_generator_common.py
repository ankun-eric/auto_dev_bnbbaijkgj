"""
宾尼小康 AI健康管家 - UI设计图生成 - 通用工具模块
设计风格：健康清新，浅色系，绿色/蓝绿色调，扁平化设计
"""
from PIL import Image, ImageDraw, ImageFont
import os
import math

OUTPUT_DIR = r"C:\auto_output\bnbbaijkgj\ui_design_outputs"

# Color Palette - 健康清新风
COLORS = {
    'bg': '#F5F9F7',           # 浅灰绿背景
    'white': '#FFFFFF',
    'primary': '#2EAD6B',      # 主色-清新绿
    'primary_light': '#E8F5EE', # 浅绿色
    'primary_dark': '#1D8A53',  # 深绿
    'secondary': '#4EBBAA',    # 蓝绿色
    'secondary_light': '#E0F5F1',
    'accent': '#FF8C42',       # 强调色-暖橙
    'accent_light': '#FFF0E5',
    'text_primary': '#1A1A2E', # 主文字
    'text_secondary': '#6B7B8D', # 次要文字
    'text_tertiary': '#A0AEC0',  # 辅助文字
    'border': '#E2E8F0',       # 边框
    'card_shadow': '#D4E5DC',  # 卡片阴影
    'danger': '#E74C3C',       # 危险红
    'warning': '#F5A623',      # 警告黄
    'info': '#3498DB',         # 信息蓝
    'success': '#27AE60',      # 成功绿
    'gradient_start': '#2EAD6B',
    'gradient_end': '#4EBBAA',
    'tab_inactive': '#C4CDD5',
    'divider': '#F0F4F2',
    'status_bar': '#1D8A53',
    'chat_user': '#DCF5E7',
    'chat_ai': '#FFFFFF',
    'overlay': '#00000066',
}

PHONE_W, PHONE_H = 390, 844  # iPhone 14 标准尺寸
ADMIN_W, ADMIN_H = 1440, 900  # Web后台尺寸

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 8:
        r, g, b, a = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, a)
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(size=16, bold=False):
    font_paths = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    if bold:
        font_paths.insert(0, r"C:\Windows\Fonts\msyhbd.ttc")
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except:
                continue
    return ImageFont.load_default()

def draw_rounded_rect(draw, xy, radius, fill=None, outline=None, width=1):
    x1, y1, x2, y2 = xy
    r = min(radius, (x2-x1)//2, (y2-y1)//2)
    if fill:
        fill_c = hex_to_rgb(fill) if isinstance(fill, str) else fill
        draw.rectangle([x1+r, y1, x2-r, y2], fill=fill_c)
        draw.rectangle([x1, y1+r, x2, y2-r], fill=fill_c)
        draw.pieslice([x1, y1, x1+2*r, y1+2*r], 180, 270, fill=fill_c)
        draw.pieslice([x2-2*r, y1, x2, y1+2*r], 270, 360, fill=fill_c)
        draw.pieslice([x1, y2-2*r, x1+2*r, y2], 90, 180, fill=fill_c)
        draw.pieslice([x2-2*r, y2-2*r, x2, y2], 0, 90, fill=fill_c)
    if outline:
        outline_c = hex_to_rgb(outline) if isinstance(outline, str) else outline
        draw.arc([x1, y1, x1+2*r, y1+2*r], 180, 270, fill=outline_c, width=width)
        draw.arc([x2-2*r, y1, x2, y1+2*r], 270, 360, fill=outline_c, width=width)
        draw.arc([x1, y2-2*r, x1+2*r, y2], 90, 180, fill=outline_c, width=width)
        draw.arc([x2-2*r, y2-2*r, x2, y2], 0, 90, fill=outline_c, width=width)
        draw.line([x1+r, y1, x2-r, y1], fill=outline_c, width=width)
        draw.line([x1+r, y2, x2-r, y2], fill=outline_c, width=width)
        draw.line([x1, y1+r, x1, y2-r], fill=outline_c, width=width)
        draw.line([x2, y1+r, x2, y2-r], fill=outline_c, width=width)

def draw_gradient_rect(img, xy, color_start, color_end, direction='horizontal'):
    x1, y1, x2, y2 = xy
    c1 = hex_to_rgb(color_start)
    c2 = hex_to_rgb(color_end)
    draw = ImageDraw.Draw(img)
    if direction == 'horizontal':
        for x in range(x1, x2):
            ratio = (x - x1) / max((x2 - x1 - 1), 1)
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(x, y1), (x, y2)], fill=(r, g, b))
    else:
        for y in range(y1, y2):
            ratio = (y - y1) / max((y2 - y1 - 1), 1)
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(x1, y), (x2, y)], fill=(r, g, b))

def draw_gradient_rounded_rect(img, xy, radius, color_start, color_end, direction='horizontal'):
    x1, y1, x2, y2 = xy
    temp = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw_gradient_rect(temp, xy, color_start, color_end, direction)
    mask = Image.new('L', img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    r = min(radius, (x2-x1)//2, (y2-y1)//2)
    mask_draw.rectangle([x1+r, y1, x2-r, y2], fill=255)
    mask_draw.rectangle([x1, y1+r, x2, y2-r], fill=255)
    mask_draw.pieslice([x1, y1, x1+2*r, y1+2*r], 180, 270, fill=255)
    mask_draw.pieslice([x2-2*r, y1, x2, y1+2*r], 270, 360, fill=255)
    mask_draw.pieslice([x1, y2-2*r, x1+2*r, y2], 90, 180, fill=255)
    mask_draw.pieslice([x2-2*r, y2-2*r, x2, y2], 0, 90, fill=255)
    img.paste(Image.composite(temp, Image.new('RGBA', img.size, (0,0,0,0)), mask), (0, 0), mask)

def create_phone_frame():
    img = Image.new('RGBA', (PHONE_W, PHONE_H), hex_to_rgb(COLORS['bg']))
    return img

def draw_status_bar(draw, y=0, light=False):
    color = COLORS['white'] if light else COLORS['text_primary']
    font = get_font(12)
    draw.text((20, y+8), "9:41", fill=hex_to_rgb(color), font=font)
    draw.text((PHONE_W-70, y+8), "100%", fill=hex_to_rgb(color), font=font)
    # Battery icon
    bx = PHONE_W - 40
    draw.rectangle([bx, y+10, bx+20, y+20], outline=hex_to_rgb(color), width=1)
    draw.rectangle([bx+2, y+12, bx+16, y+18], fill=hex_to_rgb(color))
    # Signal bars
    sx = PHONE_W - 95
    for i in range(4):
        h = 4 + i * 3
        draw.rectangle([sx + i*5, y+20-h, sx + i*5 + 3, y+20], fill=hex_to_rgb(color))

def draw_bottom_tab_bar(draw, img, active_index=0, tabs=None):
    if tabs is None:
        tabs = [("首页", "🏠"), ("服务", "🛒"), ("AI问诊", "🤖"), ("健康", "💊"), ("我的", "👤")]
    y = PHONE_H - 83
    draw.rectangle([0, y, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['white']))
    draw.line([(0, y), (PHONE_W, y)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    tab_w = PHONE_W // len(tabs)
    for i, (label, icon) in enumerate(tabs):
        cx = i * tab_w + tab_w // 2
        is_active = (i == active_index)
        
        if i == 2:  # AI问诊 - 中间突出按钮
            draw_rounded_rect(draw, [cx-25, y-10, cx+25, y+40], 25, fill=COLORS['primary'])
            icon_font = get_font(20)
            draw.text((cx-10, y-2), icon, fill=hex_to_rgb(COLORS['white']), font=icon_font)
            label_font = get_font(10)
            draw.text((cx-15, y+35), label, fill=hex_to_rgb(COLORS['primary']), font=label_font)
        else:
            color = COLORS['primary'] if is_active else COLORS['tab_inactive']
            icon_font = get_font(20)
            tw = draw.textlength(icon, font=icon_font)
            draw.text((cx - tw//2, y+10), icon, fill=hex_to_rgb(color), font=icon_font)
            label_font = get_font(11)
            tw2 = draw.textlength(label, font=label_font)
            draw.text((cx - tw2//2, y+35), label, fill=hex_to_rgb(color), font=label_font)
    
    # Home indicator
    draw.rounded_rectangle([PHONE_W//2-67, PHONE_H-5-5, PHONE_W//2+67, PHONE_H-5], radius=3, fill=hex_to_rgb(COLORS['text_tertiary']))

def draw_nav_header(draw, img, title, has_back=False, right_icon=None, bg_gradient=False):
    if bg_gradient:
        draw_gradient_rect(img, [0, 0, PHONE_W, 90], COLORS['gradient_start'], COLORS['gradient_end'])
        draw_status_bar(draw, 0, light=True)
        color = COLORS['white']
    else:
        draw.rectangle([0, 0, PHONE_W, 90], fill=hex_to_rgb(COLORS['white']))
        draw_status_bar(draw, 0, light=False)
        color = COLORS['text_primary']
    
    font = get_font(18, bold=True)
    tw = draw.textlength(title, font=font)
    draw.text((PHONE_W//2 - tw//2, 52), title, fill=hex_to_rgb(color), font=font)
    
    if has_back:
        draw.text((16, 52), "‹", fill=hex_to_rgb(color), font=get_font(24, bold=True))
    
    if right_icon:
        draw.text((PHONE_W-40, 55), right_icon, fill=hex_to_rgb(color), font=get_font(18))
    
    if not bg_gradient:
        draw.line([(0, 90), (PHONE_W, 90)], fill=hex_to_rgb(COLORS['border']), width=1)

def draw_circle(draw, center, radius, fill=None, outline=None, width=1):
    x, y = center
    if fill:
        f = hex_to_rgb(fill) if isinstance(fill, str) else fill
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill=f)
    if outline:
        o = hex_to_rgb(outline) if isinstance(outline, str) else outline
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], outline=o, width=width)

def draw_avatar(draw, center, radius, fill_color=None):
    if fill_color is None:
        fill_color = COLORS['primary_light']
    draw_circle(draw, center, radius, fill=fill_color)
    x, y = center
    head_r = radius * 0.35
    draw_circle(draw, (x, y - radius*0.15), head_r, fill=COLORS['primary'])
    body_y = y + radius * 0.4
    draw.pieslice([x-radius*0.5, body_y-radius*0.2, x+radius*0.5, body_y+radius*0.5], 
                  180, 0, fill=hex_to_rgb(COLORS['primary']))

def draw_icon_circle(draw, center, radius, icon_text, bg_color, icon_color='#FFFFFF'):
    draw_circle(draw, center, radius, fill=bg_color)
    font = get_font(int(radius * 0.9))
    tw = draw.textlength(icon_text, font=font)
    x, y = center
    draw.text((x - tw//2, y - radius*0.5), icon_text, fill=hex_to_rgb(icon_color), font=font)

def draw_card(draw, xy, radius=12, fill=None):
    if fill is None:
        fill = COLORS['white']
    x1, y1, x2, y2 = xy
    draw_rounded_rect(draw, [x1+2, y1+2, x2+2, y2+2], radius, fill=COLORS['card_shadow'])
    draw_rounded_rect(draw, xy, radius, fill=fill)

def draw_search_bar(draw, xy, placeholder="搜索"):
    x1, y1, x2, y2 = xy
    draw_rounded_rect(draw, xy, (y2-y1)//2, fill=COLORS['divider'])
    font = get_font(14)
    draw.text((x1+35, y1+(y2-y1)//2-8), placeholder, fill=hex_to_rgb(COLORS['text_tertiary']), font=font)
    draw.text((x1+12, y1+(y2-y1)//2-8), "🔍", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(13))

def draw_tag(draw, xy, text, bg_color, text_color='#FFFFFF'):
    x, y = xy
    font = get_font(11)
    tw = draw.textlength(text, font=font)
    draw_rounded_rect(draw, [x, y, x+tw+16, y+22], 11, fill=bg_color)
    draw.text((x+8, y+4), text, fill=hex_to_rgb(text_color), font=font)
    return tw + 16

def draw_button(draw, xy, text, bg_color=None, text_color=None, radius=20):
    if bg_color is None:
        bg_color = COLORS['primary']
    if text_color is None:
        text_color = COLORS['white']
    x1, y1, x2, y2 = xy
    draw_rounded_rect(draw, xy, radius, fill=bg_color)
    font = get_font(15, bold=True)
    tw = draw.textlength(text, font=font)
    draw.text(((x1+x2)//2 - tw//2, (y1+y2)//2 - 9), text, fill=hex_to_rgb(text_color), font=font)

def draw_text_centered(draw, xy, text, font, fill):
    x, y, w = xy
    tw = draw.textlength(text, font=font)
    if isinstance(fill, str):
        fill = hex_to_rgb(fill)
    draw.text((x + (w - tw)//2, y), text, fill=fill, font=font)

def draw_progress_bar(draw, xy, progress, bar_color=None, bg_color=None):
    if bar_color is None:
        bar_color = COLORS['primary']
    if bg_color is None:
        bg_color = COLORS['divider']
    x1, y1, x2, y2 = xy
    r = (y2-y1)//2
    draw_rounded_rect(draw, xy, r, fill=bg_color)
    if progress > 0:
        pw = x1 + int((x2-x1) * min(progress, 1.0))
        draw_rounded_rect(draw, [x1, y1, pw, y2], r, fill=bar_color)

def save_image(img, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path, 'PNG', quality=95)
    print(f"Saved: {path}")
    return path
