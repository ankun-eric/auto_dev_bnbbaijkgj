"""生成Web管理后台-数据大屏 + 用户管理页"""
import sys
sys.path.insert(0, r"C:\auto_output\bnbbaijkgj")
from ui_generator_common import *

def gen_admin_dashboard():
    img = Image.new('RGBA', (ADMIN_W, ADMIN_H), hex_to_rgb('#0D1B2A'))
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.rectangle([0, 0, ADMIN_W, 60], fill=hex_to_rgb('#132B44'))
    draw.text((20, 15), "🏥 宾尼小康", fill=hex_to_rgb('#FFFFFF'), font=get_font(20, bold=True))
    draw.text((170, 18), "AI健康管家 · 运营数据大屏", fill=hex_to_rgb('#4EBBAA'), font=get_font(16))
    draw.text((ADMIN_W-200, 18), "2025年3月27日 星期四", fill=hex_to_rgb('#8899AA'), font=get_font(14))
    
    # Real-time stats row
    sy = 75
    stats = [
        ("在线用户", "12,580", "+8.2%", "👥"),
        ("今日订单", "1,256", "+12.5%", "📋"),
        ("AI问诊量", "3,892", "+15.3%", "🤖"),
        ("今日营收", "¥86,420", "+6.8%", "💰"),
        ("新增用户", "328", "+3.2%", "📈"),
        ("服务核销", "186", "+9.1%", "✅"),
    ]
    
    sw = (ADMIN_W - 40) // 6
    for i, (label, value, change, icon) in enumerate(stats):
        sx = 20 + i * sw
        draw_rounded_rect(draw, [sx, sy, sx+sw-10, sy+100], 10, fill='#162D46')
        draw.text((sx+15, sy+12), icon, font=get_font(20))
        draw.text((sx+15, sy+40), value, fill=hex_to_rgb('#FFFFFF'), font=get_font(20, bold=True))
        draw.text((sx+15, sy+70), label, fill=hex_to_rgb('#8899AA'), font=get_font(12))
        draw.text((sx+sw-65, sy+72), change, fill=hex_to_rgb('#2EAD6B'), font=get_font(11))
    
    # Left column: Revenue trend chart
    chart_y = 190
    draw_rounded_rect(draw, [20, chart_y, 710, chart_y+320], 10, fill='#162D46')
    draw.text((35, chart_y+12), "营收趋势", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    
    tabs = ["日", "周", "月", "年"]
    tx = 580
    for i, t in enumerate(tabs):
        if i == 2:
            draw_rounded_rect(draw, [tx, chart_y+10, tx+35, chart_y+30], 8, fill='#2EAD6B')
            draw.text((tx+10, chart_y+12), t, fill=hex_to_rgb('#FFFFFF'), font=get_font(12))
        else:
            draw.text((tx+10, chart_y+12), t, fill=hex_to_rgb('#8899AA'), font=get_font(12))
        tx += 32
    
    # Line chart
    chart_x_start = 70
    chart_x_end = 690
    chart_y_start = chart_y + 50
    chart_h = 230
    
    # Grid lines
    for i in range(5):
        y = chart_y_start + i * (chart_h // 4)
        draw.line([(chart_x_start, y), (chart_x_end, y)], fill=hex_to_rgb('#1E3A56'), width=1)
        draw.text((25, y-8), f"{100-i*25}k", fill=hex_to_rgb('#667788'), font=get_font(10))
    
    # Data line
    import random
    random.seed(42)
    months = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
    values = [65, 72, 58, 80, 75, 85, 92, 88, 95, 78, 82, 90]
    points = []
    x_step = (chart_x_end - chart_x_start) // 11
    for i, (m, v) in enumerate(zip(months, values)):
        px = chart_x_start + i * x_step
        py = chart_y_start + int((100 - v) / 100 * chart_h)
        points.append((px, py))
        draw.text((px-10, chart_y_start+chart_h+8), m, fill=hex_to_rgb('#667788'), font=get_font(9))
    
    # Fill area under line
    fill_points = points + [(points[-1][0], chart_y_start+chart_h), (points[0][0], chart_y_start+chart_h)]
    for i in range(len(points)-1):
        draw.line([points[i], points[i+1]], fill=hex_to_rgb('#2EAD6B'), width=2)
    
    for px, py in points:
        draw_circle(draw, (px, py), 3, fill='#2EAD6B')
    
    # Right column: AI usage pie chart area
    draw_rounded_rect(draw, [730, chart_y, ADMIN_W-20, chart_y+155], 10, fill='#162D46')
    draw.text((745, chart_y+12), "AI服务分布", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    
    # Simplified pie chart as colored blocks
    pie_data = [
        ("健康问答", "42%", '#2EAD6B'),
        ("体检解读", "25%", '#3498DB'),
        ("中医辨证", "18%", '#F5A623'),
        ("药物查询", "15%", '#E74C3C'),
    ]
    py2 = chart_y + 45
    for label, pct, color in pie_data:
        draw_rounded_rect(draw, [745, py2, 745+int(float(pct[:-1])/100*660), py2+18], 3, fill=color)
        draw.text((750, py2+1), f"{label} {pct}", fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
        py2 += 25
    
    # User distribution
    draw_rounded_rect(draw, [730, chart_y+165, ADMIN_W-20, chart_y+320], 10, fill='#162D46')
    draw.text((745, chart_y+177), "用户增长趋势", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    
    # Bar chart simplified
    bar_y = chart_y + 210
    bar_data = [("1月", 45), ("2月", 52), ("3月", 68), ("4月", 58), ("5月", 72), ("6月", 85)]
    bw = 80
    for i, (month, val) in enumerate(bar_data):
        bx = 755 + i * (bw + 15)
        bh = int(val / 100 * 80)
        draw_rounded_rect(draw, [bx, bar_y+80-bh, bx+40, bar_y+80], 4, fill='#4EBBAA')
        draw.text((bx+10, bar_y+85), month, fill=hex_to_rgb('#667788'), font=get_font(10))
    
    # Bottom row: Recent orders + Alerts
    bot_y = 530
    
    # Recent orders table
    draw_rounded_rect(draw, [20, bot_y, 930, bot_y+345], 10, fill='#162D46')
    draw.text((35, bot_y+12), "最新订单", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    draw.text((850, bot_y+14), "查看全部 ›", fill=hex_to_rgb('#4EBBAA'), font=get_font(12))
    
    # Table header
    headers = ["订单号", "用户", "服务项目", "金额", "状态", "时间"]
    hx = [35, 185, 320, 520, 630, 770]
    thy = bot_y + 45
    for h, x in zip(headers, hx):
        draw.text((x, thy), h, fill=hex_to_rgb('#8899AA'), font=get_font(12, bold=True))
    draw.line([(35, thy+22), (910, thy+22)], fill=hex_to_rgb('#1E3A56'), width=1)
    
    # Table rows
    rows = [
        ("BN2025032700128", "小明", "口腔清洁护理", "¥198", "已支付", "10:32"),
        ("BN2025032700127", "小红", "全面健康体检", "¥688", "待核销", "10:15"),
        ("BN2025032700126", "张先生", "专家咨询", "¥299", "已完成", "09:48"),
        ("BN2025032700125", "李女士", "健康食品礼盒", "¥128", "已发货", "09:30"),
        ("BN2025032700124", "王同学", "口腔清洁护理", "¥198", "待支付", "09:12"),
        ("BN2025032700123", "赵阿姨", "体检套餐(高级)", "¥1288", "已完成", "08:55"),
        ("BN2025032700122", "孙先生", "养老康复服务", "¥588", "已支付", "08:40"),
        ("BN2025032700121", "刘同学", "专家咨询", "¥299", "已完成", "08:22"),
        ("BN2025032700120", "陈女士", "有机蔬果礼盒", "¥168", "配送中", "08:10"),
        ("BN2025032700119", "马先生", "口腔服务(深度)", "¥398", "待核销", "07:55"),
    ]
    
    status_colors = {"已支付": '#2EAD6B', "待核销": '#F5A623', "已完成": '#3498DB', "已发货": '#4EBBAA', "待支付": '#E74C3C', "配送中": '#4EBBAA'}
    
    ry = thy + 30
    for order_id, user, service, amount, status, time in rows:
        draw.text((hx[0], ry), order_id, fill=hex_to_rgb('#AABBCC'), font=get_font(11))
        draw.text((hx[1], ry), user, fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
        draw.text((hx[2], ry), service, fill=hex_to_rgb('#FFFFFF'), font=get_font(11))
        draw.text((hx[3], ry), amount, fill=hex_to_rgb('#FFD700'), font=get_font(11, bold=True))
        sc = status_colors.get(status, '#8899AA')
        draw_rounded_rect(draw, [hx[4], ry-2, hx[4]+55, ry+16], 8, fill=sc+'30')
        draw.text((hx[4]+5, ry), status, fill=hex_to_rgb(sc), font=get_font(10))
        draw.text((hx[5], ry), time, fill=hex_to_rgb('#8899AA'), font=get_font(11))
        ry += 28
    
    # System alerts
    draw_rounded_rect(draw, [950, bot_y, ADMIN_W-20, bot_y+345], 10, fill='#162D46')
    draw.text((965, bot_y+12), "⚡ 实时告警", fill=hex_to_rgb('#FFFFFF'), font=get_font(16, bold=True))
    
    alerts = [
        ("🟢", "系统运行正常", "所有服务均在线", "10:30"),
        ("🟡", "AI调用量预警", "今日调用已达配额80%", "10:15"),
        ("🟢", "数据库备份完成", "自动备份成功", "06:00"),
        ("🔴", "支付回调异常", "1笔订单支付回调超时", "09:45"),
        ("🟢", "已自动处理", "异常订单已重新回调", "09:50"),
        ("🟡", "存储空间预警", "OSS存储使用已达75%", "08:00"),
    ]
    
    aly = bot_y + 45
    for dot, title, desc, time in alerts:
        draw.text((965, aly), dot, font=get_font(12))
        draw.text((985, aly), title, fill=hex_to_rgb('#FFFFFF'), font=get_font(12, bold=True))
        draw.text((985, aly+18), desc, fill=hex_to_rgb('#8899AA'), font=get_font(10))
        draw.text((ADMIN_W-80, aly+2), time, fill=hex_to_rgb('#667788'), font=get_font(10))
        aly += 45
    
    save_image(img, "19_admin_dashboard.png")

def gen_admin_user_management():
    img = Image.new('RGBA', (ADMIN_W, ADMIN_H), hex_to_rgb(COLORS['bg']))
    draw = ImageDraw.Draw(img)
    
    # Sidebar
    sidebar_w = 220
    draw.rectangle([0, 0, sidebar_w, ADMIN_H], fill=hex_to_rgb('#1A1A2E'))
    
    # Logo
    draw.text((20, 20), "🏥 宾尼小康", fill=hex_to_rgb('#FFFFFF'), font=get_font(18, bold=True))
    draw.text((25, 48), "管理后台", fill=hex_to_rgb('#8899AA'), font=get_font(12))
    
    draw.line([(15, 70), (sidebar_w-15, 70)], fill=hex_to_rgb('#2D2D4A'), width=1)
    
    # Sidebar menu
    menus = [
        ("📊", "数据总览", False),
        ("👥", "用户管理", True),
        ("🤖", "AI模型配置", False),
        ("📝", "内容管理", False),
        ("🛒", "服务商品", False),
        ("📋", "订单管理", False),
        ("🏆", "积分体系", False),
        ("📈", "数据报表", False),
        ("💬", "客服工作台", False),
        ("⚙️", "系统设置", False),
    ]
    
    my = 85
    for icon, label, active in menus:
        if active:
            draw_rounded_rect(draw, [10, my, sidebar_w-10, my+38], 8, fill='#2EAD6B20')
            draw.line([(3, my+5), (3, my+33)], fill=hex_to_rgb('#2EAD6B'), width=3)
            draw.text((20, my+8), icon, font=get_font(15))
            draw.text((45, my+10), label, fill=hex_to_rgb('#2EAD6B'), font=get_font(14, bold=True))
        else:
            draw.text((20, my+8), icon, font=get_font(15))
            draw.text((45, my+10), label, fill=hex_to_rgb('#8899AA'), font=get_font(13))
        my += 42
    
    # Top bar
    draw.rectangle([sidebar_w, 0, ADMIN_W, 56], fill=hex_to_rgb('#FFFFFF'))
    draw.line([(sidebar_w, 56), (ADMIN_W, 56)], fill=hex_to_rgb(COLORS['border']), width=1)
    draw.text((sidebar_w+20, 16), "用户管理", fill=hex_to_rgb(COLORS['text_primary']), font=get_font(18, bold=True))
    
    # Admin user info
    draw.text((ADMIN_W-150, 18), "管理员", fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(13))
    draw_avatar(draw, (ADMIN_W-30, 28), 14)
    draw.text((ADMIN_W-100, 18), "🔔", font=get_font(16))
    
    # Content area
    content_x = sidebar_w + 20
    content_w = ADMIN_W - sidebar_w - 40
    
    # Stats cards
    sy = 70
    user_stats = [
        ("总用户数", "128,560", "+1,256", COLORS['primary']),
        ("今日活跃", "12,580", "+8.2%", COLORS['info']),
        ("新增用户", "328", "+3.2%", COLORS['success']),
        ("会员用户", "45,320", "35.2%", COLORS['accent']),
    ]
    
    usw = content_w // 4
    for i, (label, value, change, color) in enumerate(user_stats):
        ux = content_x + i * usw
        draw_card(draw, [ux, sy, ux+usw-10, sy+85], 10)
        draw.text((ux+15, sy+12), label, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12))
        draw.text((ux+15, sy+35), value, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(22, bold=True))
        draw.text((ux+15, sy+65), change, fill=hex_to_rgb(color), font=get_font(12))
    
    # Search and filter bar
    fy = sy + 100
    draw_card(draw, [content_x, fy, content_x+content_w, fy+50], 10)
    draw_rounded_rect(draw, [content_x+15, fy+10, content_x+250, fy+40], 8, fill=COLORS['divider'])
    draw.text((content_x+25, fy+16), "🔍 搜索用户手机号/昵称...", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(12))
    
    # Filter buttons
    filters = ["全部用户", "普通用户", "会员用户", "已封禁"]
    fx = content_x + 270
    for i, f_name in enumerate(filters):
        f = get_font(12)
        fw = draw.textlength(f_name, font=f)
        if i == 0:
            draw_rounded_rect(draw, [fx, fy+12, fx+fw+16, fy+36], 8, fill=COLORS['primary'])
            draw.text((fx+8, fy+15), f_name, fill=hex_to_rgb('#FFFFFF'), font=f)
        else:
            draw_rounded_rect(draw, [fx, fy+12, fx+fw+16, fy+36], 8, outline=COLORS['border'])
            draw.text((fx+8, fy+15), f_name, fill=hex_to_rgb(COLORS['text_secondary']), font=f)
        fx += fw + 24
    
    # Export button
    draw_rounded_rect(draw, [content_x+content_w-100, fy+12, content_x+content_w-15, fy+36], 8, fill=COLORS['primary'])
    draw.text((content_x+content_w-90, fy+15), "📥 导出", fill=hex_to_rgb('#FFFFFF'), font=get_font(12))
    
    # User table
    ty = fy + 60
    draw_card(draw, [content_x, ty, content_x+content_w, ty+530], 10)
    
    # Table headers
    headers = ["用户ID", "昵称", "手机号", "注册时间", "会员等级", "积分", "订单数", "状态", "操作"]
    hx_offsets = [15, 85, 185, 310, 445, 555, 645, 725, 850]
    
    thy = ty + 12
    for h, offset in zip(headers, hx_offsets):
        draw.text((content_x+offset, thy), h, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(12, bold=True))
    draw.line([(content_x+10, thy+22), (content_x+content_w-10, thy+22)], fill=hex_to_rgb(COLORS['border']), width=1)
    
    # Table data
    users_data = [
        ("100001", "小明", "138****8888", "2025-01-15", "🌟 黄金", "3,680", "12", "正常"),
        ("100002", "小红", "139****6666", "2025-01-20", "🥈 白银", "1,520", "8", "正常"),
        ("100003", "张先生", "137****5555", "2025-02-01", "🥉 青铜", "680", "5", "正常"),
        ("100004", "李女士", "136****4444", "2025-02-10", "普通", "120", "2", "正常"),
        ("100005", "王同学", "135****3333", "2025-02-15", "普通", "50", "1", "正常"),
        ("100006", "赵阿姨", "133****2222", "2025-03-01", "🌟 黄金", "5,200", "18", "正常"),
        ("100007", "异常用户", "132****1111", "2025-03-05", "普通", "0", "0", "已封禁"),
        ("100008", "孙先生", "131****9999", "2025-03-10", "🥈 白银", "2,100", "9", "正常"),
        ("100009", "周女士", "130****8888", "2025-03-12", "🥉 青铜", "890", "4", "正常"),
        ("100010", "吴同学", "158****7777", "2025-03-15", "普通", "200", "3", "正常"),
    ]
    
    ry = thy + 30
    for uid, name, phone, reg_time, level, points, orders, status in users_data:
        draw.text((content_x+hx_offsets[0], ry), uid, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        draw.text((content_x+hx_offsets[1], ry), name, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(11))
        draw.text((content_x+hx_offsets[2], ry), phone, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        draw.text((content_x+hx_offsets[3], ry), reg_time, fill=hex_to_rgb(COLORS['text_secondary']), font=get_font(11))
        draw.text((content_x+hx_offsets[4], ry), level, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(11))
        draw.text((content_x+hx_offsets[5], ry), points, fill=hex_to_rgb(COLORS['accent']), font=get_font(11))
        draw.text((content_x+hx_offsets[6], ry), orders, fill=hex_to_rgb(COLORS['text_primary']), font=get_font(11))
        
        sc = COLORS['success'] if status == "正常" else COLORS['danger']
        draw_rounded_rect(draw, [content_x+hx_offsets[7], ry-2, content_x+hx_offsets[7]+45, ry+16], 8, fill=sc+'18')
        draw.text((content_x+hx_offsets[7]+5, ry), status, fill=hex_to_rgb(sc), font=get_font(10))
        
        draw.text((content_x+hx_offsets[8], ry), "查看", fill=hex_to_rgb(COLORS['primary']), font=get_font(11))
        draw.text((content_x+hx_offsets[8]+40, ry), "编辑", fill=hex_to_rgb(COLORS['info']), font=get_font(11))
        
        draw.line([(content_x+10, ry+24), (content_x+content_w-10, ry+24)], fill=hex_to_rgb(COLORS['divider']), width=1)
        ry += 48
    
    # Pagination
    pg_y = ty + 505
    draw.text((content_x+content_w-300, pg_y), "共 128,560 条记录", fill=hex_to_rgb(COLORS['text_tertiary']), font=get_font(12))
    pages = ["‹", "1", "2", "3", "...", "1286", "›"]
    px = content_x + content_w - 160
    for p in pages:
        f = get_font(12)
        pw = draw.textlength(p, font=f)
        if p == "1":
            draw_rounded_rect(draw, [px, pg_y-2, px+24, pg_y+18], 4, fill=COLORS['primary'])
            draw.text((px+6, pg_y), p, fill=hex_to_rgb('#FFFFFF'), font=f)
        else:
            draw.text((px+6, pg_y), p, fill=hex_to_rgb(COLORS['text_secondary']), font=f)
        px += 28
    
    save_image(img, "20_admin_user_management.png")

gen_admin_dashboard()
gen_admin_user_management()
print("Done: admin pages")
