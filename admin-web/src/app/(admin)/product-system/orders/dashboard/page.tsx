'use client';

/**
 * [门店预约看板与改期能力升级 v1.0] 门店端预约看板视图
 *
 * 三视图：日（9 宫格）/ 周（7 列）/ 月（月历 + 点击日期弹窗）
 * 9 宫格点击 → 抽屉展示该时段订单列表（操作型 5 字段，PC 端核销按钮置灰）
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, DatePicker, Radio, Drawer, Tag, Empty, Spin,
  Button, Space, Statistic, Modal, Typography, Tooltip, message,
} from 'antd';
import {
  LeftOutlined, RightOutlined, ReloadOutlined, PhoneOutlined,
  EyeOutlined, CalendarOutlined, AppstoreOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { get } from '@/lib/api';
import { useRouter } from 'next/navigation';

const { Title, Text } = Typography;

type ViewMode = 'day' | 'week' | 'month';

interface SlotCell {
  slot_no: number;
  label: string;
  appointment_count: number;
  verified_count: number;
  verified_amount: number;
}

interface DayResp {
  date: string;
  cells: SlotCell[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number; overflow_count: number };
  current_slot: number | null;
}

interface WeekDay {
  date: string;
  weekday: number;
  appointment_count: number;
  verified_count: number;
  verified_amount: number;
}

interface WeekResp {
  week_start: string;
  week_end: string;
  days: WeekDay[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number };
}

interface MonthDay {
  date: string;
  appointment_count: number;
  verified_count: number;
  verified_amount: number;
}

interface MonthResp {
  year: number;
  month: number;
  days: MonthDay[];
}

interface OrderCard {
  order_id: number;
  order_no: string;
  order_item_id: number;
  appointment_time: string | null;
  slot_no: number | null;
  slot_label: string;
  customer_name: string;
  customer_phone: string | null;
  product_name: string;
  amount: number;
  status: string;
}

interface SlotDetailResp {
  date: string;
  slot_no: number;
  slot_label: string;
  orders: OrderCard[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number };
}

interface MonthDayResp {
  date: string;
  morning: OrderCard[];
  afternoon: OrderCard[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number };
}

const STATUS_LABEL_MAP: Record<string, { label: string; color: string }> = {
  pending_payment: { label: '待支付', color: 'orange' },
  pending_appointment: { label: '待预约', color: 'gold' },
  appointed: { label: '已预约', color: 'blue' },
  pending_use: { label: '待核销', color: 'cyan' },
  verified: { label: '已核销', color: 'green' },
  pending_receipt: { label: '待收货', color: 'purple' },
  pending_shipment: { label: '待发货', color: 'lime' },
  completed: { label: '已完成', color: 'green' },
  cancelled: { label: '已取消', color: 'default' },
};

function statusTag(s: string) {
  const cfg = STATUS_LABEL_MAP[s] || { label: s, color: 'default' };
  return <Tag color={cfg.color}>{cfg.label}</Tag>;
}

function formatYuan(v: number): string {
  // [PRD-02 R-02-05] 金额格式：¥ + 整数（不带千分位、不带小数）
  return `¥${Math.round(v)}`;
}

// [PRD-02 R-02-04] 看板"日/周/月"视图记忆 key
const DASHBOARD_VIEW_KEY = 'bini_orders_dashboard_view';

export default function OrdersDashboardPage() {
  const router = useRouter();
  // [PRD-02 R-02-04] 默认日视图，但浏览器记忆上次选择
  const [view, setView] = useState<ViewMode>(() => {
    if (typeof window === 'undefined') return 'day';
    try {
      const v = localStorage.getItem(DASHBOARD_VIEW_KEY);
      if (v === 'day' || v === 'week' || v === 'month') return v;
    } catch (_) {
      /* 忽略 */
    }
    return 'day';
  });
  const [pickedDate, setPickedDate] = useState<Dayjs>(dayjs());
  const [loading, setLoading] = useState(false);
  const [dayData, setDayData] = useState<DayResp | null>(null);
  const [weekData, setWeekData] = useState<WeekResp | null>(null);
  const [monthData, setMonthData] = useState<MonthResp | null>(null);

  // 抽屉状态（9 宫格点击）
  const [slotDrawerOpen, setSlotDrawerOpen] = useState(false);
  const [slotDetail, setSlotDetail] = useState<SlotDetailResp | null>(null);

  // 月视图日期点击弹窗
  const [monthDayModalOpen, setMonthDayModalOpen] = useState(false);
  const [monthDayDetail, setMonthDayDetail] = useState<MonthDayResp | null>(null);

  const dateStr = pickedDate.format('YYYY-MM-DD');

  // ─────────── 数据加载 ───────────
  const loadDay = async (d: string) => {
    setLoading(true);
    try {
      const res = await get<DayResp>('/api/merchant/dashboard/day', { date: d });
      setDayData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载日视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadWeek = async (d: string) => {
    setLoading(true);
    try {
      const res = await get<WeekResp>('/api/merchant/dashboard/week', { date: d });
      setWeekData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载周视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMonth = async (year: number, month: number) => {
    setLoading(true);
    try {
      const res = await get<MonthResp>('/api/merchant/dashboard/month', { year, month });
      setMonthData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载月视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (view === 'day') loadDay(dateStr);
    else if (view === 'week') loadWeek(dateStr);
    else if (view === 'month') loadMonth(pickedDate.year(), pickedDate.month() + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, dateStr]);

  // [PRD-02 R-02-04] 进入看板页时，把"上次选择"刷为 board，
  // 下次再进 /product-system/orders 时会自动跳回看板
  useEffect(() => {
    try {
      localStorage.setItem('bini_orders_view_preference', 'board');
    } catch (_) {
      /* localStorage 不可用时忽略 */
    }
  }, []);

  const refresh = () => {
    if (view === 'day') loadDay(dateStr);
    else if (view === 'week') loadWeek(dateStr);
    else loadMonth(pickedDate.year(), pickedDate.month() + 1);
  };

  // ─────────── 9 宫格点击 → 抽屉 ───────────
  const openSlotDrawer = async (slot_no: number) => {
    setSlotDrawerOpen(true);
    setSlotDetail(null);
    try {
      const res = await get<SlotDetailResp>(`/api/merchant/dashboard/slot/${dateStr}/${slot_no}`);
      setSlotDetail(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载时段订单失败');
    }
  };

  // ─────────── 月视图日期点击 → 弹窗 ───────────
  const openMonthDayModal = async (d: string) => {
    setMonthDayModalOpen(true);
    setMonthDayDetail(null);
    try {
      const res = await get<MonthDayResp>('/api/merchant/dashboard/month-day', { date: d });
      setMonthDayDetail(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载当日订单失败');
    }
  };

  // ─────────── UI 渲染 ───────────

  const dateNav = (
    <Space>
      <Button icon={<LeftOutlined />} onClick={() => {
        if (view === 'day') setPickedDate(pickedDate.subtract(1, 'day'));
        else if (view === 'week') setPickedDate(pickedDate.subtract(1, 'week'));
        else setPickedDate(pickedDate.subtract(1, 'month'));
      }} />
      <DatePicker
        value={pickedDate}
        onChange={(d) => d && setPickedDate(d)}
        picker={view === 'month' ? 'month' : view === 'week' ? 'week' : 'date'}
        allowClear={false}
      />
      <Button icon={<RightOutlined />} onClick={() => {
        if (view === 'day') setPickedDate(pickedDate.add(1, 'day'));
        else if (view === 'week') setPickedDate(pickedDate.add(1, 'week'));
        else setPickedDate(pickedDate.add(1, 'month'));
      }} />
      <Button onClick={() => setPickedDate(dayjs())}>今天</Button>
      <Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button>
    </Space>
  );

  // 9 宫格
  const renderDayGrid = () => {
    if (!dayData) return <Empty />;
    return (
      <>
        <Row gutter={[16, 16]}>
          {dayData.cells.map((cell) => {
            const isCurrent = dayData.current_slot === cell.slot_no;
            const verifiedRate = cell.appointment_count
              ? cell.verified_count / cell.appointment_count
              : 0;
            // [PRD-02 §2.2 视觉规则] 已核率高的格用偏深色块（绿色加深），空闲格用浅灰色块
            let bg = '#fafafa';
            if (cell.appointment_count > 0) {
              if (verifiedRate >= 0.8) bg = '#b7eb8f';
              else if (verifiedRate >= 0.5) bg = '#d9f7be';
              else if (verifiedRate >= 0.2) bg = '#f6ffed';
              else bg = '#ffffff';
            }
            const empty = cell.appointment_count === 0;
            return (
              <Col key={cell.slot_no} xs={24} sm={12} md={8}>
                <Card
                  hoverable
                  onClick={() => openSlotDrawer(cell.slot_no)}
                  style={{
                    background: bg,
                    border: isCurrent ? '2px solid #52c41a' : undefined,
                    minHeight: 130,
                  }}
                  bodyStyle={{ padding: 16 }}
                >
                  <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 8 }}>
                    {cell.label}
                    {isCurrent && <Tag color="green" style={{ marginLeft: 8 }}>进行中</Tag>}
                  </div>
                  {empty ? (
                    <div style={{ color: '#999', fontSize: 14, padding: '8px 0' }}>
                      暂无预约
                    </div>
                  ) : (
                    <>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Statistic title="预约" value={cell.appointment_count} valueStyle={{ fontSize: 18 }} />
                        <Statistic title="已核" value={cell.verified_count} valueStyle={{ fontSize: 18 }} />
                      </div>
                      <div style={{ marginTop: 8, color: '#389e0d', fontSize: 14 }}>
                        已核金额：{formatYuan(cell.verified_amount)}
                      </div>
                    </>
                  )}
                </Card>
              </Col>
            );
          })}
        </Row>
        <Card style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="当日预约总数" value={dayData.summary.appointment_count} /></Col>
            <Col span={8}><Statistic title="当日已核销数" value={dayData.summary.verified_count} /></Col>
            <Col span={8}><Statistic title="当日已核金额" value={formatYuan(dayData.summary.verified_amount)} /></Col>
          </Row>
          {dayData.summary.overflow_count > 0 && (
            <div style={{ marginTop: 8, color: '#faad14' }}>
              ⚠️ 凌晨脏数据 {dayData.summary.overflow_count} 条，可在列表视图查看
            </div>
          )}
        </Card>
      </>
    );
  };

  // 周视图：7 列卡片
  const renderWeek = () => {
    if (!weekData) return <Empty />;
    const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    return (
      <>
        <Row gutter={[12, 12]}>
          {weekData.days.map((d) => (
            <Col key={d.date} flex="1 1 0" style={{ minWidth: 120 }}>
              <Card
                hoverable
                onClick={() => { setPickedDate(dayjs(d.date)); setView('day'); }}
                bodyStyle={{ padding: 12 }}
              >
                <div style={{ fontWeight: 600 }}>
                  {WEEK_LABELS[d.weekday]} {dayjs(d.date).format('MM-DD')}
                </div>
                <div style={{ marginTop: 8, fontSize: 13 }}>预约：{d.appointment_count}</div>
                <div style={{ fontSize: 13 }}>已核：{d.verified_count}</div>
                <div style={{ fontSize: 13, color: '#52c41a' }}>{formatYuan(d.verified_amount)}</div>
              </Card>
            </Col>
          ))}
        </Row>
        <Card style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}><Statistic title="本周预约总数" value={weekData.summary.appointment_count} /></Col>
            <Col span={8}><Statistic title="本周已核销数" value={weekData.summary.verified_count} /></Col>
            <Col span={8}><Statistic title="本周已核金额" value={formatYuan(weekData.summary.verified_amount)} /></Col>
          </Row>
        </Card>
      </>
    );
  };

  // 月视图：标准月历
  const renderMonth = () => {
    if (!monthData) return <Empty />;
    const firstDay = dayjs(`${monthData.year}-${String(monthData.month).padStart(2, '0')}-01`);
    const startWeekday = (firstDay.day() + 6) % 7; // 转为周一为 0
    const cells: (MonthDay | null)[] = Array(startWeekday).fill(null);
    monthData.days.forEach((d) => cells.push(d));
    while (cells.length % 7 !== 0) cells.push(null);

    const WEEK_HEADER = ['一', '二', '三', '四', '五', '六', '日'];
    return (
      <Card>
        <Row>
          {WEEK_HEADER.map((w) => (
            <Col key={w} span={Math.floor(24 / 7)} style={{ padding: 4, textAlign: 'center', fontWeight: 600 }}>
              {w}
            </Col>
          ))}
        </Row>
        {Array.from({ length: cells.length / 7 }).map((_, rowIdx) => (
          <Row key={rowIdx}>
            {cells.slice(rowIdx * 7, rowIdx * 7 + 7).map((c, cIdx) => (
              <Col key={cIdx} span={Math.floor(24 / 7)} style={{ padding: 4 }}>
                {c ? (
                  <Card
                    size="small"
                    hoverable
                    onClick={() => openMonthDayModal(c.date)}
                    bodyStyle={{ padding: 8, minHeight: 80 }}
                    style={{
                      background: c.appointment_count > 0 ? '#e6f7ff' : '#fafafa',
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{dayjs(c.date).date()}</div>
                    {c.appointment_count > 0 && (
                      <>
                        <div style={{ fontSize: 12 }}>预约 {c.appointment_count}</div>
                        <div style={{ fontSize: 12, color: '#52c41a' }}>{formatYuan(c.verified_amount)}</div>
                      </>
                    )}
                  </Card>
                ) : (
                  <div style={{ minHeight: 80 }} />
                )}
              </Col>
            ))}
          </Row>
        ))}
      </Card>
    );
  };

  // ─────────── 抽屉：9 宫格点击 ───────────
  const renderOrderCard = (o: OrderCard) => (
    <Card key={o.order_item_id} size="small" style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <strong>{o.customer_name}</strong>
        {statusTag(o.status)}
      </div>
      {o.customer_phone && (
        <div style={{ marginBottom: 4, color: '#666' }}>
          📞 {o.customer_phone}
        </div>
      )}
      <div style={{ marginBottom: 4 }}>{o.product_name}</div>
      <div style={{ marginBottom: 8, color: '#52c41a' }}>{formatYuan(o.amount)}</div>
      <Space>
        <Tooltip title="PC 端不允许发起核销，请到手机端操作">
          <Button size="small" disabled icon={<CalendarOutlined />}>核销（请到手机端）</Button>
        </Tooltip>
        <Button
          size="small"
          icon={<EyeOutlined />}
          onClick={() => router.push(`/product-system/orders?id=${o.order_id}`)}
        >
          详情
        </Button>
        {o.customer_phone && (
          <Button
            size="small"
            icon={<PhoneOutlined />}
            onClick={() => {
              // [PRD-02 §2.7] 抽屉订单卡片提供「📞拨打」操作：
              // 桌面端浏览器没有原生拨号能力，故先尝试用 tel: 协议唤起本机拨号软件，
              // 再兜底将完整 11 位手机号复制到剪贴板，方便商家直接电话客户。
              const phone = o.customer_phone || '';
              try {
                window.location.href = `tel:${phone}`;
              } catch (_) {
                /* tel: 不可用时忽略 */
              }
              navigator.clipboard?.writeText(phone).catch(() => {});
              message.success(`已复制手机号 ${phone}，可直接拨打`);
            }}
          >
            📞拨打
          </Button>
        )}
      </Space>
    </Card>
  );

  return (
    <div>
      <Title level={3} style={{ marginBottom: 16 }}>
        <AppstoreOutlined /> 预约看板
      </Title>

      <Card style={{ marginBottom: 16 }}>
        <Space size={16} wrap>
          <Radio.Group
            value={view}
            onChange={(e) => {
              const v = e.target.value as ViewMode;
              setView(v);
              try {
                localStorage.setItem(DASHBOARD_VIEW_KEY, v);
              } catch (_) {
                /* 忽略 */
              }
            }}
          >
            <Radio.Button value="day">日视图</Radio.Button>
            <Radio.Button value="week">周视图</Radio.Button>
            <Radio.Button value="month">月视图</Radio.Button>
          </Radio.Group>
          {dateNav}
          <Button
            onClick={() => {
              // [PRD-02 R-02-04] 用户主动切到列表视图时，写入浏览器记忆为 list，
              // 下次再进订单管理就停留列表页，不再被自动跳转回看板
              try {
                localStorage.setItem('bini_orders_view_preference', 'list');
              } catch (_) {
                /* localStorage 不可用时忽略 */
              }
              router.push('/product-system/orders');
            }}
          >
            切换到列表视图
          </Button>
        </Space>
      </Card>

      <Spin spinning={loading}>
        {view === 'day' && renderDayGrid()}
        {view === 'week' && renderWeek()}
        {view === 'month' && renderMonth()}
      </Spin>

      {/* 9 宫格点击抽屉 */}
      <Drawer
        title={slotDetail ? `${slotDetail.date}  ${slotDetail.slot_label}` : '加载中…'}
        open={slotDrawerOpen}
        onClose={() => setSlotDrawerOpen(false)}
        width={520}
      >
        {!slotDetail ? (
          <Spin />
        ) : (
          <>
            <Row gutter={8} style={{ marginBottom: 16 }}>
              <Col span={8}><Statistic title="预约" value={slotDetail.summary.appointment_count} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={8}><Statistic title="已核" value={slotDetail.summary.verified_count} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={8}><Statistic title="金额" value={formatYuan(slotDetail.summary.verified_amount)} valueStyle={{ fontSize: 18 }} /></Col>
            </Row>
            {slotDetail.orders.length === 0
              ? <Empty description="该时段暂无预约" />
              : slotDetail.orders.map(renderOrderCard)}
          </>
        )}
      </Drawer>

      {/* 月视图日期点击弹窗 */}
      <Modal
        title={monthDayDetail ? `${monthDayDetail.date} 当日订单` : '加载中…'}
        open={monthDayModalOpen}
        onCancel={() => setMonthDayModalOpen(false)}
        footer={null}
        width={900}
      >
        {!monthDayDetail ? (
          <Spin />
        ) : (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={8}><Statistic title="预约" value={monthDayDetail.summary.appointment_count} /></Col>
              <Col span={8}><Statistic title="已核" value={monthDayDetail.summary.verified_count} /></Col>
              <Col span={8}><Statistic title="已核金额" value={formatYuan(monthDayDetail.summary.verified_amount)} /></Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Title level={5}>上午（06:00-12:00）</Title>
                {monthDayDetail.morning.length === 0
                  ? <Empty description="无订单" />
                  : monthDayDetail.morning.map(renderOrderCard)}
              </Col>
              <Col span={12}>
                <Title level={5}>下午+晚上（12:00-24:00）</Title>
                {monthDayDetail.afternoon.length === 0
                  ? <Empty description="无订单" />
                  : monthDayDetail.afternoon.map(renderOrderCard)}
              </Col>
            </Row>
          </>
        )}
      </Modal>
    </div>
  );
}
