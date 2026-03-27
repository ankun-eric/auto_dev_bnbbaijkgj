"""生成体检报告解读页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_report_upload():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "体检报告解读", has_back=True, bg_gradient=True)
    
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Upload area
    uy = 110
    draw_rounded_rect(draw, [20, uy, PHONE_W-20, uy+180], 16, fill=COLORS['white'])
    
    # Dashed border upload zone
    cx = PHONE_W // 2
    draw_rounded_rect(draw, [40, uy+15, PHONE_W-40, uy+165], 12, outline=COLORS['primary'], width=2)
    
    draw_circle(draw, (cx, uy+60), 28, fill=COLORS['primary_light'])
    draw.text((cx-12, uy+48), "📤", font=get_font(22))
    
    f1 = get_font(15, bold=True)
    tw = draw.textlength("上传体检报告", font=f1)
    draw.text((cx-tw//2, uy+98), "上传体检报告", fill=hex_to_rgb(COLORS['text_primary']), font=f1)
    
    f2 = get_font(12)
    tw = draw.textlength("支持拍照上传或PDF文件上传", font=f2)
    draw.text((cx-tw//2, uy+120), "支持拍照上传或PDF文件上传", fill=hex_to_rgb(COLORS['text_tertiary']), font=f2)
    
    # Two buttons
    btn_y = uy + 140
    bw = (PHONE_W - 100) // 2
    draw_rounded_rect(draw, [50, btn_y, 50+bw, btn_y+30], 15, fill=COLORS['primary'])
    draw.text((60, btn_y+6), "📷 拍照上传", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
    draw_rounded_rect(draw, [60+bw, btn_y, 60+bw*2, btn_y+30], 15, fill=COLORS['secondary'])
    draw.text((70+bw, btn_y+6), "📄 选择文件", fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
    
    # Historical reports section
    hy = uy + 200
    draw.text((20, hy), "历史报告", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    
    reports = [
        ("2025年年度体检报告", "2025-03-15", "已解读", COLORS['success']),
        ("血常规检查报告", "2025-01-20", "已解读", COLORS['success']),
        ("肝功能检查报告", "2024-11-08", "待解读", COLORS['warning']),
    ]
    
    hy += 30
    for title, date, status, color in reports:
        draw_card(draw, [20, hy, PHONE_W-20, hy+72], 12)
        draw_circle(draw, (50, hy+36), 18, fill=COLORS['primary_light'])
        draw.text((42, hy+24), "📋", font=get_font(16))
        draw.text((78, hy+14), title, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
        draw.text((78, hy+38), date, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(12))
        # Status tag
        draw_tag(draw, (PHONE_W-90, hy+22), status, color)
        draw.text((PHONE_W-35, hy+32), "›", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(18))
        hy += 84
    
    save_image(img, "05_report_upload.png")

def gen_report_result():
    img = create_phone_frame()
    draw = ImageDraw.Draw(img)
    draw_nav_header(draw, img, "报告解读结果", has_back=True, right_icon="📤", bg_gradient=True)
    
    draw.rectangle([0, 90, PHONE_W, PHONE_H], fill=hex_to_rgb(COLORS['bg']))
    
    # Summary card
    sy = 100
    draw_card(draw, [20, sy, PHONE_W-20, sy+110], 16)
    
    # Overall score
    draw_circle(draw, (70, sy+55), 35, fill=COLORS['primary'])
    draw.text((55, sy+38), "85", fill=hex_to_rgb('#FFFFFF'), font=get_font(22, bold=True))
    f_s = get_font(10)
    draw.text((55, sy+64), "健康评分", fill=hex_to_rgb('#FFFFFFCC'), font=f_s)
    
    draw.text((120, sy+18), "2025年年度体检报告", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(15, bold=True))
    draw.text((120, sy+42), "检查日期：2025-03-15", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
    
    # Mini stats
    mini_stats = [("正常", "18项", COLORS['success']), ("异常", "3项", COLORS['danger']), ("偏高", "2项", COLORS['warning'])]
    mx = 120
    for label, val, color in mini_stats:
        draw_rounded_rect(draw, [mx, sy+65, mx+65, sy+92], 8, fill=color+'18')
        draw.text((mx+8, sy+70), val, fill=hex_to_rgb(color), font=get_font(12, bold=True))
        draw.text((mx+35, sy+72), label, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(10))
        mx += 75
    
    # AI Analysis
    ay = sy + 125
    draw.text((20, ay), "🤖 AI解读分析", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    
    ay += 30
    draw_card(draw, [20, ay, PHONE_W-20, ay+80], 12)
    draw_rounded_rect(draw, [30, ay+8, 68, ay+24], 8, fill=COLORS['danger']+'20')
    draw.text((35, ay+8), "⚠ 异常", fill=hex_to_rgb(COLORS['danger']), font=get_font(11, bold=True))
    draw.text((30, ay+32), "总胆固醇：6.2 mmol/L", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
    draw.text((230, ay+32), "↑ 偏高", fill=hex_to_rgb(COLORS['danger']), font=get_font(13, bold=True))
    draw.text((30, ay+55), "正常范围 2.8-5.7 mmol/L，建议控制饮食", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    
    ay += 92
    draw_card(draw, [20, ay, PHONE_W-20, ay+80], 12)
    draw_rounded_rect(draw, [30, ay+8, 68, ay+24], 8, fill=COLORS['warning']+'20')
    draw.text((35, ay+8), "⚡ 偏高", fill=hex_to_rgb(COLORS['warning']), font=get_font(11, bold=True))
    draw.text((30, ay+32), "空腹血糖：6.0 mmol/L", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
    draw.text((230, ay+32), "↑ 偏高", fill=hex_to_rgb(COLORS['warning']), font=get_font(13, bold=True))
    draw.text((30, ay+55), "正常范围 3.9-6.1 mmol/L，处于临界值", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    
    ay += 92
    draw_card(draw, [20, ay, PHONE_W-20, ay+80], 12)
    draw_rounded_rect(draw, [30, ay+8, 68, ay+24], 8, fill=COLORS['success']+'20')
    draw.text((35, ay+8), "✓ 正常", fill=hex_to_rgb(COLORS['success']), font=get_font(11, bold=True))
    draw.text((30, ay+32), "血红蛋白：145 g/L", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(14, bold=True))
    draw.text((230, ay+32), "正常", fill=hex_to_rgb(COLORS['success']), font=get_font(13, bold=True))
    draw.text((30, ay+55), "正常范围 120-160 g/L，指标良好", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
    
    # Trend chart area
    ay += 95
    draw.text((20, ay), "📊 指标趋势", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(16, bold=True))
    ay += 28
    draw_card(draw, [20, ay, PHONE_W-20, ay+120], 12)
    
    # Simple line chart
    chart_x = 50
    chart_y_start = ay + 20
    chart_h = 80
    chart_w = PHONE_W - 100
    
    # Y axis
    for i in range(4):
        yy = chart_y_start + i * (chart_h // 3)
        draw.line([(chart_x, yy), (chart_x+chart_w, yy)], fill=hex_to_rgb(COLORS['divider']), width=1)
        draw.text((28, yy-6), str(7-i), fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(9))
    
    # Data points and line
    months = ["1月", "3月", "6月", "9月", "12月"]
    values = [5.8, 5.9, 6.1, 6.0, 6.2]
    points = []
    for i, (m, v) in enumerate(zip(months, values)):
        px = chart_x + i * (chart_w // 4)
        py = chart_y_start + int((7 - v) / 3 * chart_h)
        points.append((px, py))
        draw.text((px-10, chart_y_start+chart_h+5), m, fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(9))
    
    for i in range(len(points)-1):
        draw.line([points[i], points[i+1]], fill=hex_to_rgb(COLORS['primary']), width=2)
    for px, py in points:
        draw_circle(draw, (px, py), 4, fill=COLORS['primary'])
        draw_circle(draw, (px, py), 2, fill=COLORS['white'])
    
    # Reference line
    ref_y = chart_y_start + int((7 - 6.1) / 3 * chart_h)
    draw.line([(chart_x, ref_y), (chart_x+chart_w, ref_y)], fill=hex_to_rgb(COLORS['danger']+'80'), width=1)
    draw.text((chart_x+chart_w+5, ref_y-6), "上限", fill=hex_to_rgb(COLORS['danger']), font=get_font(9))
    
    save_image(img, "06_report_result.png")

gen_report_upload()
gen_report_result()
print("Done: report pages")
