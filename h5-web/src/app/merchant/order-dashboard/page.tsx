'use client';

/**
 * [PRD-365 商家后台「预约看板」替换升级 v1.0]
 *
 * 路径：/merchant/order-dashboard/
 * 商家端 PC 版预约看板，物理拷贝自 admin 端 `/admin/product-system/orders/dashboard/`，
 * 数据按当前登录商家 + localStorage.merchant_current_store 的双重过滤。
 *
 * 与 admin 版差异：
 *   1. 不展示「商菜单（预约看板）」标题与「返回门店列表」按钮
 *   2. 标题改为「预约看板」并展示当前门店名
 *   3. 列表视图跳转改为商家端「订单管理」`/merchant/orders/`
 *   4. 通过 getCurrentStoreId() 注入门店上下文，未选门店则提示
 *
 * 视觉规范沿用 PRD-09：4 色状态（待到店 / 已到店 / 已核销 / 已取消）
 * 时段切片：固定 9 段（06-08 / 08-10 / ... / 22-24）
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, DatePicker, Drawer, Tag, Empty, Spin,
  Button, Space, Statistic, Modal, Typography, Tooltip, message, Tabs, Badge,
  ConfigProvider,
} from 'antd';
import zhCN from 'antd/locale/zh_CN';
import {
  LeftOutlined, RightOutlined, ReloadOutlined, PhoneOutlined,
  CalendarOutlined, AppstoreOutlined, CheckCircleOutlined, EditOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import 'dayjs/locale/zh-cn';
import api from '@/lib/api';
import { useRouter } from 'next/navigation';
import { getCurrentStoreId, getProfile } from '../lib';

dayjs.locale('zh-cn');

const { Title, Text } = Typography;

// ─────────────── 4 色状态色板（Ant Design 5 默认） ───────────────
type StatusCode = 'pending' | 'arrived' | 'verified' | 'cancelled';

const STATUS_COLOR: Record<StatusCode, { color: string; label: string; tag: string }> = {
  pending:   { color: '#1677FF', label: '待到店', tag: 'blue' },
  arrived:   { color: '#FA8C16', label: '已到店', tag: 'orange' },
  verified:  { color: '#52C41A', label: '已核销', tag: 'green' },
  cancelled: { color: '#BFBFBF', label: '已取消', tag: 'default' },
};

function statusBadge(code?: string) {
  const sc = (code as StatusCode) || 'pending';
  const cfg = STATUS_COLOR[sc] || STATUS_COLOR.pending;
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0 8px',
        height: 20,
        lineHeight: '20px',
        borderRadius: 4,
        background: cfg.color,
        color: '#fff',
        fontSize: 12,
      }}
    >
      {cfg.label}
    </span>
  );
}

// ─────────────── 类型定义 ───────────────
type ViewMode = 'day' | 'week' | 'month';
type TopTab = 'board' | 'service_group' | 'resource' | 'list';

interface TopOrder {
  order_id: number;
  order_item_id: number;
  customer_name: string;
  product_name: string;
  appointment_time_text: string;
  status_code: StatusCode;
}

interface SlotCell {
  slot_no: number;
  label: string;
  appointment_count: number;
  verified_count: number;
  verified_amount: number;
  top_orders?: TopOrder[];
  status_code?: StatusCode;
}

interface DayResp {
  date: string;
  cells: SlotCell[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number; overflow_count: number };
  current_slot: number | null;
}

interface WeekCell {
  date: string;
  weekday: number;
  period: 'morning' | 'afternoon' | 'evening';
  appointment_count: number;
  status_code?: StatusCode;
}

interface WeekResp {
  week_start: string;
  week_end: string;
  cells?: WeekCell[];
  periods?: { key: string; label: string }[];
  days: { date: string; weekday: number; appointment_count: number; verified_count: number; verified_amount: number }[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number };
}

interface MonthDay {
  date: string;
  appointment_count: number;
  verified_count: number;
  verified_amount: number;
  status_code?: StatusCode;
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
  appointment_time_text?: string;
  slot_no: number | null;
  slot_label: string;
  customer_name: string;
  customer_phone: string | null;
  product_name: string;
  amount: number;
  status: string;
  status_code?: StatusCode;
  notes?: string | null;
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
  orders?: OrderCard[];
  morning: OrderCard[];
  afternoon: OrderCard[];
  summary: { appointment_count: number; verified_count: number; verified_amount: number };
}

function formatYuan(v: number): string {
  return `¥${Math.round(v)}`;
}

const DASHBOARD_VIEW_KEY = 'bini_merchant_dashboard_view';
const DASHBOARD_TOP_TAB_KEY = 'bini_merchant_dashboard_top_tab';

const TOP_TABS: { key: TopTab; label: string }[] = [
  { key: 'board', label: '预约看板' },
  { key: 'service_group', label: '服务分组日视图' },
  { key: 'resource', label: '资源视图' },
  { key: 'list', label: '列表视图' },
];

// ─────────────── helper：调用看板接口（强制注入 store_id） ───────────────
async function dashApi<T = any>(path: string, params: any = {}): Promise<T> {
  const sid = getCurrentStoreId();
  const res = await api.get(path, { params: { ...params, store_id: sid ?? undefined } });
  return res as unknown as T;
}

// ─────────────── 主组件 ───────────────
export default function MerchantOrderDashboardPage() {
  const router = useRouter();

  const [storeId, setStoreId] = useState<number | null>(null);
  const [storeName, setStoreName] = useState<string>('');

  useEffect(() => {
    const sid = getCurrentStoreId();
    setStoreId(sid);
    const profile = getProfile();
    if (sid && profile) {
      const found = profile.stores.find((s) => s.id === sid);
      if (found) setStoreName(found.name);
    }
  }, []);

  // 顶层 Tab：默认 board
  const [topTab, setTopTab] = useState<TopTab>(() => {
    if (typeof window === 'undefined') return 'board';
    try {
      const t = localStorage.getItem(DASHBOARD_TOP_TAB_KEY);
      if (t === 'board' || t === 'service_group' || t === 'resource' || t === 'list') return t as TopTab;
    } catch (_) { /* 忽略 */ }
    return 'board';
  });

  // 子视图：默认 day
  const [view, setView] = useState<ViewMode>(() => {
    if (typeof window === 'undefined') return 'day';
    try {
      const v = localStorage.getItem(DASHBOARD_VIEW_KEY);
      if (v === 'day' || v === 'week' || v === 'month') return v;
    } catch (_) { /* 忽略 */ }
    return 'day';
  });
  const [pickedDate, setPickedDate] = useState<Dayjs>(dayjs());
  const [loading, setLoading] = useState(false);
  const [dayData, setDayData] = useState<DayResp | null>(null);
  const [weekData, setWeekData] = useState<WeekResp | null>(null);
  const [monthData, setMonthData] = useState<MonthResp | null>(null);

  // 抽屉状态
  const [slotDrawerOpen, setSlotDrawerOpen] = useState(false);
  const [slotDetail, setSlotDetail] = useState<SlotDetailResp | null>(null);
  const [weekDrawerTitle, setWeekDrawerTitle] = useState<string>('');

  // 月视图日期点击弹窗（左右双栏联动）
  const [monthDayModalOpen, setMonthDayModalOpen] = useState(false);
  const [monthDayDetail, setMonthDayDetail] = useState<MonthDayResp | null>(null);
  const [monthSelectedItemId, setMonthSelectedItemId] = useState<number | null>(null);

  // 精确手机号搜索
  const [phoneSearch, setPhoneSearch] = useState<string>('');

  const dateStr = pickedDate.format('YYYY-MM-DD');

  // ─────────── 数据加载 ───────────
  const loadDay = async (d: string) => {
    if (!storeId) return;
    setLoading(true);
    try {
      const res = await dashApi<DayResp>('/api/merchant/dashboard/day', { date: d });
      setDayData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载日视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadWeek = async (d: string) => {
    if (!storeId) return;
    setLoading(true);
    try {
      const res = await dashApi<WeekResp>('/api/merchant/dashboard/week', { date: d });
      setWeekData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载周视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  const loadMonth = async (year: number, month: number) => {
    if (!storeId) return;
    setLoading(true);
    try {
      const res = await dashApi<MonthResp>('/api/merchant/dashboard/month', { year, month });
      setMonthData(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载月视图数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!storeId) return;
    if (topTab !== 'board') return;
    if (view === 'day') loadDay(dateStr);
    else if (view === 'week') loadWeek(dateStr);
    else if (view === 'month') loadMonth(pickedDate.year(), pickedDate.month() + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, topTab, view, dateStr]);

  const refresh = () => {
    if (topTab !== 'board') return;
    if (view === 'day') loadDay(dateStr);
    else if (view === 'week') loadWeek(dateStr);
    else loadMonth(pickedDate.year(), pickedDate.month() + 1);
  };

  // ─────────── 9 宫格点击 → 抽屉 ───────────
  const openSlotDrawer = async (slot_no: number) => {
    setSlotDrawerOpen(true);
    setSlotDetail(null);
    setWeekDrawerTitle('');
    try {
      const res = await dashApi<SlotDetailResp>(`/api/merchant/dashboard/slot/${dateStr}/${slot_no}`);
      setSlotDetail(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载时段订单失败');
    }
  };

  const openWeekCellDrawer = async (cell: WeekCell) => {
    setSlotDrawerOpen(true);
    setSlotDetail(null);
    const slotMap = { morning: [1, 2, 3], afternoon: [4, 5, 6], evening: [7, 8, 9] };
    const slots = slotMap[cell.period] || [];
    const periodLabel = weekData?.periods?.find(p => p.key === cell.period)?.label || cell.period;
    setWeekDrawerTitle(`${cell.date}  ${periodLabel}`);
    try {
      const results = await Promise.all(
        slots.map((s) => dashApi<SlotDetailResp>(`/api/merchant/dashboard/slot/${cell.date}/${s}`))
      );
      const merged: SlotDetailResp = {
        date: cell.date,
        slot_no: 0,
        slot_label: periodLabel,
        orders: results.flatMap(r => r.orders),
        summary: results.reduce(
          (acc, r) => ({
            appointment_count: acc.appointment_count + (r.summary?.appointment_count || 0),
            verified_count: acc.verified_count + (r.summary?.verified_count || 0),
            verified_amount: acc.verified_amount + (r.summary?.verified_amount || 0),
          }),
          { appointment_count: 0, verified_count: 0, verified_amount: 0 },
        ),
      };
      setSlotDetail(merged);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载时段订单失败');
    }
  };

  // ─────────── 月视图日期点击 → 弹窗 ───────────
  const openMonthDayModal = async (d: string) => {
    setMonthDayModalOpen(true);
    setMonthDayDetail(null);
    setMonthSelectedItemId(null);
    try {
      const res = await dashApi<MonthDayResp>('/api/merchant/dashboard/month-day', { date: d });
      if (!res.orders) {
        res.orders = [...(res.morning || []), ...(res.afternoon || [])].sort((a, b) => {
          const at = a.appointment_time || '';
          const bt = b.appointment_time || '';
          return at.localeCompare(bt);
        });
      }
      setMonthDayDetail(res);
      if (res.orders && res.orders.length > 0) setMonthSelectedItemId(res.orders[0].order_item_id);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载当日订单失败');
    }
  };

  // ─────────── 顶部搜索：精确手机号 ───────────
  const onSearchPhone = () => {
    const phone = (phoneSearch || '').trim();
    if (!phone) {
      message.warning('请输入手机号后再搜索');
      return;
    }
    if (!/^1\d{10}$/.test(phone)) {
      message.warning('请输入 11 位完整手机号（精确匹配）');
      return;
    }
    if (!dayData) {
      message.info('请先切到日视图加载数据再搜索');
      return;
    }
    // 在当日全部 top_orders 与 cells 中查找命中
    const allCells = dayData.cells || [];
    let hitSlot: number | null = null;
    for (const c of allCells) {
      const orders = c.top_orders || [];
      // top_orders 不含 phone，需通过抽屉拉取详情匹配
      // 这里先打开第一个含预约的格子提示
      if (orders.some((o) => o.customer_name)) {
        // 先按门店今天逐个打开
      }
    }
    // 简化：把匹配交由抽屉页查找——加载所有 9 段订单聚合后筛选
    (async () => {
      try {
        const all = await Promise.all(
          (dayData.cells || [])
            .filter((c) => c.appointment_count > 0)
            .map((c) => dashApi<SlotDetailResp>(`/api/merchant/dashboard/slot/${dateStr}/${c.slot_no}`))
        );
        const hit = all.flatMap((r) => r.orders).find((o) => o.customer_phone === phone);
        if (hit) {
          message.success(`找到客户 ${hit.customer_name}，时段 ${hit.slot_label}`);
          if (hit.slot_no) openSlotDrawer(hit.slot_no);
          return;
        }
        message.info('未找到该客户的预约');
      } catch (e: any) {
        message.error(e?.response?.data?.detail || '搜索失败');
      }
    })();
  };

  // ─────────── 日期切换控件 ───────────
  const dateNav = (
    <Space size={8} wrap>
      <Button icon={<LeftOutlined />} onClick={() => {
        if (view === 'day') setPickedDate(pickedDate.subtract(1, 'day'));
        else if (view === 'week') setPickedDate(pickedDate.subtract(1, 'week'));
        else setPickedDate(pickedDate.subtract(1, 'month'));
      }}>前一天</Button>
      <Button
        type={pickedDate.isSame(dayjs(), 'day') ? 'primary' : 'default'}
        onClick={() => setPickedDate(dayjs())}
      >
        今天
      </Button>
      <Text strong style={{ fontSize: 16 }}>
        {view === 'day'
          ? `${pickedDate.format('YYYY-MM-DD')} ${pickedDate.format('dddd')}`
          : view === 'week'
            ? `本周（${pickedDate.startOf('week').add(1, 'day').format('MM-DD')} ~ ${pickedDate.startOf('week').add(7, 'day').format('MM-DD')}）`
            : pickedDate.format('YYYY 年 MM 月')}
      </Text>
      <Button icon={<RightOutlined />} onClick={() => {
        if (view === 'day') setPickedDate(pickedDate.add(1, 'day'));
        else if (view === 'week') setPickedDate(pickedDate.add(1, 'week'));
        else setPickedDate(pickedDate.add(1, 'month'));
      }}>后一天</Button>
      <DatePicker
        value={pickedDate}
        onChange={(d) => d && setPickedDate(d)}
        picker={view === 'month' ? 'month' : view === 'week' ? 'week' : 'date'}
        allowClear={false}
        suffixIcon={<CalendarOutlined />}
      />
      <Button icon={<ReloadOutlined />} onClick={refresh}>刷新</Button>
    </Space>
  );

  // ─────────── 顶部搜索条 ───────────
  const searchBar = (
    <Space size={8} style={{ marginLeft: 'auto' }}>
      <input
        type="tel"
        maxLength={11}
        placeholder="输入 11 位手机号精确搜索"
        value={phoneSearch}
        onChange={(e) => setPhoneSearch(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') onSearchPhone(); }}
        style={{
          width: 220,
          padding: '4px 11px',
          height: 32,
          borderRadius: 6,
          border: '1px solid #d9d9d9',
          outline: 'none',
        }}
      />
      <Button onClick={onSearchPhone}>搜索</Button>
    </Space>
  );

  // ─────────── 日视图：9 宫格 ───────────
  const renderDayGrid = () => {
    if (!dayData) return <Empty />;
    return (
      <>
        <Row gutter={[16, 16]}>
          {dayData.cells.map((cell) => {
            const isCurrent = dayData.current_slot === cell.slot_no;
            const sc = (cell.status_code || 'pending') as StatusCode;
            const cfg = STATUS_COLOR[sc] || STATUS_COLOR.pending;
            const empty = cell.appointment_count === 0;
            const top = cell.top_orders || [];
            return (
              <Col key={cell.slot_no} xs={24} sm={12} md={8}>
                <Card
                  hoverable
                  onClick={() => openSlotDrawer(cell.slot_no)}
                  style={{
                    borderLeft: `4px solid ${cfg.color}`,
                    border: isCurrent ? `2px solid ${cfg.color}` : undefined,
                    background: isCurrent ? '#f6ffed' : undefined,
                    minHeight: 150,
                  }}
                  styles={{ body: { padding: 16 } }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 16 }}>{cell.label}</span>
                    {!empty && statusBadge(sc)}
                    {isCurrent && <Tag color="green" style={{ marginLeft: 4 }}>进行中</Tag>}
                  </div>
                  {empty ? (
                    <div style={{ height: 80 }} />
                  ) : (
                    <>
                      {top.slice(0, 2).map((o, idx) => (
                        <div key={idx} style={{ marginBottom: 4, fontSize: 13 }}>
                          <Text strong>{o.customer_name}</Text>
                          <Text type="secondary" style={{ marginLeft: 6 }}>{o.product_name}</Text>
                        </div>
                      ))}
                      {cell.appointment_count > 2 && (
                        <div style={{ fontSize: 12, color: '#1677ff', marginTop: 4 }}>
                          还有 {cell.appointment_count - 2} 条 &gt;
                        </div>
                      )}
                      <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                        预约 {cell.appointment_count} · 已核 {cell.verified_count}
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
        </Card>
      </>
    );
  };

  // ─────────── 周视图：3 行 × 7 列 = 21 格 ───────────
  const renderWeek = () => {
    if (!weekData) return <Empty />;
    const cells = weekData.cells || [];
    const periods = weekData.periods || [
      { key: 'morning', label: '上午（06:00-12:00）' },
      { key: 'afternoon', label: '下午（12:00-18:00）' },
      { key: 'evening', label: '晚上（18:00-24:00）' },
    ];
    const WEEK_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
    const weekStart = dayjs(weekData.week_start);

    return (
      <>
        <Row gutter={[8, 8]} style={{ marginBottom: 8 }}>
          <Col flex="120px" />
          {Array.from({ length: 7 }).map((_, i) => {
            const d = weekStart.add(i, 'day');
            return (
              <Col key={i} flex="1 1 0" style={{ textAlign: 'center', minWidth: 100 }}>
                <div style={{ fontWeight: 600 }}>{WEEK_LABELS[i]}</div>
                <div style={{ color: '#888', fontSize: 12 }}>{d.format('MM-DD')}</div>
              </Col>
            );
          })}
        </Row>
        {periods.map((p) => (
          <Row key={p.key} gutter={[8, 8]} style={{ marginBottom: 8 }}>
            <Col flex="120px" style={{ display: 'flex', alignItems: 'center', fontWeight: 600 }}>
              {p.label}
            </Col>
            {Array.from({ length: 7 }).map((_, i) => {
              const d = weekStart.add(i, 'day');
              const dateKey = d.format('YYYY-MM-DD');
              const cell = cells.find((c) => c.date === dateKey && c.period === p.key);
              const sc = (cell?.status_code || 'pending') as StatusCode;
              const cfg = STATUS_COLOR[sc];
              const count = cell?.appointment_count || 0;
              const empty = count === 0;
              return (
                <Col key={i} flex="1 1 0" style={{ minWidth: 100 }}>
                  <Card
                    hoverable={!empty}
                    onClick={() => {
                      if (empty || !cell) return;
                      openWeekCellDrawer(cell);
                    }}
                    styles={{ body: { padding: 12, textAlign: 'center', minHeight: 80 } }}
                    style={{
                      borderLeft: empty ? '4px solid #f0f0f0' : `4px solid ${cfg.color}`,
                      background: empty ? '#fafafa' : '#fff',
                      cursor: empty ? 'default' : 'pointer',
                    }}
                  >
                    {empty ? (
                      <Text type="secondary" style={{ fontSize: 12 }}>—</Text>
                    ) : (
                      <Badge
                        count={count}
                        showZero={false}
                        style={{ backgroundColor: cfg.color }}
                        overflowCount={99}
                      >
                        <span style={{ padding: '0 12px', fontSize: 13 }}>个预约</span>
                      </Badge>
                    )}
                  </Card>
                </Col>
              );
            })}
          </Row>
        ))}
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

  // ─────────── 月视图：标准月历 ───────────
  const renderMonth = () => {
    if (!monthData) return <Empty />;
    const firstDay = dayjs(`${monthData.year}-${String(monthData.month).padStart(2, '0')}-01`);
    const startWeekday = (firstDay.day() + 6) % 7;
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
            {cells.slice(rowIdx * 7, rowIdx * 7 + 7).map((c, cIdx) => {
              const sc = (c?.status_code || 'pending') as StatusCode;
              const cfg = STATUS_COLOR[sc];
              const has = c && c.appointment_count > 0;
              return (
                <Col key={cIdx} span={Math.floor(24 / 7)} style={{ padding: 4 }}>
                  {c ? (
                    <Card
                      size="small"
                      hoverable
                      onClick={() => openMonthDayModal(c.date)}
                      styles={{ body: { padding: 8, minHeight: 84 } }}
                      style={{
                        borderLeft: has ? `4px solid ${cfg.color}` : '4px solid #f0f0f0',
                        background: has ? '#fff' : '#fafafa',
                      }}
                    >
                      <div style={{ fontWeight: 600 }}>{dayjs(c.date).date()}</div>
                      {has ? (
                        <Badge count={c.appointment_count} style={{ backgroundColor: cfg.color }} overflowCount={99}>
                          <span style={{ padding: '0 8px', fontSize: 12 }}>个预约</span>
                        </Badge>
                      ) : (
                        <div style={{ height: 22 }} />
                      )}
                    </Card>
                  ) : (
                    <div style={{ minHeight: 84 }} />
                  )}
                </Col>
              );
            })}
          </Row>
        ))}
      </Card>
    );
  };

  // ─────────── 抽屉：取消预约 / 联系客户 ───────────
  const handleCancelOrder = (o: OrderCard) => {
    Modal.confirm({
      title: '确认取消该预约？',
      content: `客户：${o.customer_name}\n服务：${o.product_name}\n时段：${o.slot_label || ''}\n\n取消后无法恢复，请谨慎操作。`,
      okText: '确认取消',
      okButtonProps: { danger: true },
      cancelText: '不取消',
      async onOk() {
        try {
          await api.post(`/api/orders/${o.order_id}/cancel`, { reason: '商家在 PC 端取消该预约' });
          message.success('预约已取消');
          if (slotDetail) {
            setSlotDetail({
              ...slotDetail,
              orders: slotDetail.orders.filter((x) => x.order_item_id !== o.order_item_id),
              summary: {
                ...slotDetail.summary,
                appointment_count: Math.max(0, (slotDetail.summary.appointment_count || 1) - 1),
              },
            });
          }
          refresh();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '取消失败');
        }
      },
    });
  };

  const handleContact = (o: OrderCard) => {
    if (!o.customer_phone) {
      message.warning('该订单没有联系电话');
      return;
    }
    const phone = o.customer_phone;
    try { window.location.href = `tel:${phone}`; } catch (_) { /* 忽略 */ }
    navigator.clipboard?.writeText(phone).catch(() => {});
    message.success(`已复制手机号 ${phone}，可直接拨打`);
  };

  const handleGoOrderDetail = (o: OrderCard) => {
    router.push(`/merchant/orders?highlight=${o.order_id}`);
  };

  // ─────────── 抽屉/详情卡：单条预约渲染 ───────────
  const renderOrderDetailCard = (o: OrderCard, opts: { compact?: boolean } = {}) => {
    const sc = (o.status_code || 'pending') as StatusCode;
    const cfg = STATUS_COLOR[sc];
    return (
      <Card
        key={o.order_item_id}
        size={opts.compact ? 'small' : 'default'}
        style={{ marginBottom: 12, borderLeft: `4px solid ${cfg.color}` }}
        styles={{ body: { padding: opts.compact ? 12 : 16 } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <div>
            <Text strong style={{ fontSize: 15 }}>{o.customer_name}</Text>
            {o.customer_phone && (
              <Text type="secondary" style={{ marginLeft: 8 }}>📞 {o.customer_phone}</Text>
            )}
          </div>
          {statusBadge(sc)}
        </div>
        <div style={{ marginBottom: 6 }}>
          <Text type="secondary">服务：</Text>{o.product_name}
        </div>
        <div style={{ marginBottom: 6 }}>
          <Text type="secondary">时段：</Text>
          {o.appointment_time_text || ''}
          {o.slot_label && <Text type="secondary" style={{ marginLeft: 8 }}>（{o.slot_label}）</Text>}
        </div>
        {o.order_no && (
          <div style={{ marginBottom: 6 }}>
            <Text type="secondary">订单号：</Text>{o.order_no}
          </div>
        )}
        {o.notes && (
          <div style={{ marginBottom: 6, color: '#666', fontSize: 12 }}>
            <Text type="secondary">备注：</Text>{o.notes}
          </div>
        )}
        <div style={{ marginBottom: 12, color: '#52C41A' }}>
          <Text type="secondary" style={{ color: 'inherit' }}>金额：</Text>{formatYuan(o.amount)}
        </div>
        <Space wrap>
          <Tooltip title="请到手机端核销">
            <Button size="small" disabled icon={<CheckCircleOutlined />}>核销</Button>
          </Tooltip>
          <Tooltip title="请到手机端修改时段">
            <Button size="small" disabled icon={<EditOutlined />}>修改预约时间</Button>
          </Tooltip>
          <Button
            size="small"
            danger
            icon={<CloseCircleOutlined />}
            onClick={() => handleCancelOrder(o)}
            disabled={sc === 'cancelled' || sc === 'verified'}
          >
            取消预约
          </Button>
          <Button size="small" icon={<PhoneOutlined />} onClick={() => handleContact(o)}>
            联系客户
          </Button>
          <Button size="small" type="link" onClick={() => handleGoOrderDetail(o)}>
            去订单详情
          </Button>
        </Space>
      </Card>
    );
  };

  const drawerTitle = useMemo(() => {
    if (weekDrawerTitle) return weekDrawerTitle;
    if (slotDetail) return `${slotDetail.date}  ${slotDetail.slot_label}`;
    return '加载中…';
  }, [weekDrawerTitle, slotDetail]);

  // ─────────── 月视图弹窗：左右双栏 ───────────
  const renderMonthDayModal = () => {
    const orders = monthDayDetail?.orders || [];
    const selected = orders.find((o) => o.order_item_id === monthSelectedItemId) || orders[0];
    return (
      <Modal
        title={monthDayDetail ? `${monthDayDetail.date} 当日预约` : '加载中…'}
        open={monthDayModalOpen}
        onCancel={() => setMonthDayModalOpen(false)}
        footer={null}
        width={960}
        styles={{ body: { padding: 0 } }}
      >
        {!monthDayDetail ? (
          <div style={{ padding: 32, textAlign: 'center' }}><Spin /></div>
        ) : orders.length === 0 ? (
          <div style={{ padding: 32 }}><Empty description="该日暂无预约" /></div>
        ) : (
          <Row style={{ minHeight: 480 }}>
            <Col span={10} style={{ borderRight: '1px solid #f0f0f0', padding: 16, maxHeight: 600, overflow: 'auto' }}>
              <div style={{ marginBottom: 12 }}>
                <Text strong>时间轴预约列表</Text>
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>共 {orders.length} 条</Text>
              </div>
              {orders.map((o) => {
                const sc = (o.status_code || 'pending') as StatusCode;
                const cfg = STATUS_COLOR[sc];
                const isActive = o.order_item_id === selected?.order_item_id;
                return (
                  <div
                    key={o.order_item_id}
                    onClick={() => setMonthSelectedItemId(o.order_item_id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      padding: '10px 12px',
                      marginBottom: 8,
                      borderLeft: `4px solid ${cfg.color}`,
                      background: isActive ? '#e6f4ff' : '#fff',
                      border: isActive ? '1px solid #1677FF' : '1px solid #f0f0f0',
                      borderRadius: 4,
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ width: 56, color: '#666', fontWeight: 600 }}>
                      {o.appointment_time_text || ''}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>{o.customer_name}</div>
                      <div style={{ fontSize: 12, color: '#888' }}>{o.product_name}</div>
                    </div>
                    {statusBadge(sc)}
                  </div>
                );
              })}
            </Col>
            <Col span={14} style={{ padding: 16, maxHeight: 600, overflow: 'auto', background: '#fafafa' }}>
              <div style={{ marginBottom: 12 }}>
                <Text strong>预约详情</Text>
              </div>
              {selected ? renderOrderDetailCard(selected) : <Empty description="请在左侧选择一条预约" />}
              <Card size="small" style={{ marginTop: 12 }}>
                <Row gutter={16}>
                  <Col span={8}><Statistic title="预约" value={monthDayDetail.summary.appointment_count} valueStyle={{ fontSize: 16 }} /></Col>
                  <Col span={8}><Statistic title="已核" value={monthDayDetail.summary.verified_count} valueStyle={{ fontSize: 16 }} /></Col>
                  <Col span={8}><Statistic title="金额" value={formatYuan(monthDayDetail.summary.verified_amount)} valueStyle={{ fontSize: 16 }} /></Col>
                </Row>
              </Card>
            </Col>
          </Row>
        )}
      </Modal>
    );
  };

  // ─────────── Tab 内容 ───────────
  const boardTabContent = (
    <>
      <Card style={{ marginBottom: 16 }}>
        <Space size={16} wrap style={{ width: '100%' }}>
          <Tabs
            type="card"
            size="small"
            activeKey={view}
            onChange={(k) => {
              const v = k as ViewMode;
              setView(v);
              try { localStorage.setItem(DASHBOARD_VIEW_KEY, v); } catch (_) { /* 忽略 */ }
            }}
            items={[
              { key: 'day', label: '日视图' },
              { key: 'week', label: '周视图' },
              { key: 'month', label: '月视图' },
            ]}
            style={{ marginBottom: -16 }}
          />
          {dateNav}
          {searchBar}
        </Space>
      </Card>

      <Spin spinning={loading}>
        {view === 'day' && renderDayGrid()}
        {view === 'week' && renderWeek()}
        {view === 'month' && renderMonth()}
      </Spin>
    </>
  );

  const serviceGroupTabContent = (
    <Card>
      <Title level={5} style={{ marginBottom: 8 }}>服务分组日视图</Title>
      <div style={{ color: '#888', marginBottom: 16, fontSize: 13 }}>
        本视图按服务分组展示当日预约。
      </div>
      <ServiceGroupedDailyView storeId={storeId} dateStr={dateStr} dateNav={dateNav} />
    </Card>
  );

  const resourceTabContent = (
    <Card>
      <Title level={5} style={{ marginBottom: 8 }}>资源视图</Title>
      <div style={{ color: '#888', marginBottom: 16, fontSize: 13 }}>
        按资源（美容师/房间）维度查看当日预约分布。
      </div>
      <ResourceDailyView storeId={storeId} dateStr={dateStr} dateNav={dateNav} />
    </Card>
  );

  const listTabContent = (
    <Card>
      <Title level={5} style={{ marginBottom: 8 }}>列表视图</Title>
      <div style={{ color: '#888', marginBottom: 16, fontSize: 13 }}>
        平铺所有订单，支持搜索筛选。点击进入完整订单管理页。
      </div>
      <Button type="primary" onClick={() => router.push('/merchant/orders')}>
        打开订单管理列表
      </Button>
    </Card>
  );

  // ─────────── 兜底：无门店上下文 ───────────
  if (storeId === null) {
    return (
      <ConfigProvider locale={zhCN}>
        <div>
          <Title level={4}>
            <AppstoreOutlined style={{ marginRight: 8 }} />
            预约看板
          </Title>
          <div style={{ color: '#8c8c8c', padding: 24 }}>
            尚未选择门店，请先在右上角切换门店再查看预约看板。
          </div>
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider locale={zhCN}>
      <div>
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <Title level={3} style={{ margin: 0 }}>
            <AppstoreOutlined /> 预约看板
            {storeName && (
              <Text type="secondary" style={{ fontSize: 14, marginLeft: 12 }}>
                · {storeName}
              </Text>
            )}
          </Title>
        </div>

        <Tabs
          activeKey={topTab}
          onChange={(k) => {
            setTopTab(k as TopTab);
            try { localStorage.setItem(DASHBOARD_TOP_TAB_KEY, k); } catch (_) { /* 忽略 */ }
          }}
          items={TOP_TABS.map((t) => ({
            key: t.key,
            label: t.label,
            children:
              t.key === 'board' ? boardTabContent
                : t.key === 'service_group' ? serviceGroupTabContent
                : t.key === 'resource' ? resourceTabContent
                : listTabContent,
          }))}
        />

        <Drawer
          title={drawerTitle}
          open={slotDrawerOpen}
          onClose={() => { setSlotDrawerOpen(false); setWeekDrawerTitle(''); }}
          width={480}
        >
          {!slotDetail ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : (
            <>
              <Card size="small" style={{ marginBottom: 16 }}>
                <Row gutter={8}>
                  <Col span={8}><Statistic title="预约" value={slotDetail.summary.appointment_count} valueStyle={{ fontSize: 18 }} /></Col>
                  <Col span={8}><Statistic title="已核" value={slotDetail.summary.verified_count} valueStyle={{ fontSize: 18 }} /></Col>
                  <Col span={8}><Statistic title="金额" value={formatYuan(slotDetail.summary.verified_amount)} valueStyle={{ fontSize: 18 }} /></Col>
                </Row>
              </Card>
              {slotDetail.orders.length === 0
                ? <Empty description="该时段暂无预约" />
                : slotDetail.orders.map((o) => renderOrderDetailCard(o))}
            </>
          )}
        </Drawer>

        {renderMonthDayModal()}
      </div>
    </ConfigProvider>
  );
}

// ─────────────── 服务分组日视图 ───────────────
function ServiceGroupedDailyView({ storeId, dateStr, dateNav }: { storeId: number | null; dateStr: string; dateNav: React.ReactNode }) {
  const [orders, setOrders] = useState<OrderCard[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!storeId) return;
    let aborted = false;
    setLoading(true);
    (async () => {
      try {
        const res = await dashApi<MonthDayResp>('/api/merchant/dashboard/month-day', { date: dateStr });
        const all = res.orders || [...(res.morning || []), ...(res.afternoon || [])];
        if (!aborted) setOrders(all);
      } catch (e: any) {
        if (!aborted) message.error(e?.response?.data?.detail || '加载当日订单失败');
      } finally {
        if (!aborted) setLoading(false);
      }
    })();
    return () => { aborted = true; };
  }, [storeId, dateStr]);

  const grouped = useMemo(() => {
    const m: Record<string, OrderCard[]> = {};
    orders.forEach((o) => {
      const k = o.product_name || '未分类';
      if (!m[k]) m[k] = [];
      m[k].push(o);
    });
    return m;
  }, [orders]);

  return (
    <Spin spinning={loading}>
      <div style={{ marginBottom: 16 }}>{dateNav}</div>
      {Object.keys(grouped).length === 0 ? (
        <Empty description="该日暂无预约" />
      ) : (
        Object.entries(grouped).map(([service, list]) => (
          <Card key={service} size="small" style={{ marginBottom: 12 }} title={`${service}（${list.length}）`}>
            <Row gutter={[8, 8]}>
              {list.map((o) => {
                const sc = (o.status_code || 'pending') as StatusCode;
                const cfg = STATUS_COLOR[sc];
                return (
                  <Col key={o.order_item_id} xs={24} sm={12} md={8}>
                    <Card
                      size="small"
                      style={{ borderLeft: `4px solid ${cfg.color}` }}
                      styles={{ body: { padding: 8 } }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <strong>{o.customer_name}</strong>
                        {statusBadge(sc)}
                      </div>
                      <div style={{ fontSize: 12, color: '#888' }}>
                        {o.appointment_time_text || ''} · {formatYuan(o.amount)}
                      </div>
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </Card>
        ))
      )}
    </Spin>
  );
}

// ─────────────── 资源视图 ───────────────
function ResourceDailyView({ storeId, dateStr, dateNav }: { storeId: number | null; dateStr: string; dateNav: React.ReactNode }) {
  const [orders, setOrders] = useState<OrderCard[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!storeId) return;
    let aborted = false;
    setLoading(true);
    (async () => {
      try {
        const res = await dashApi<MonthDayResp>('/api/merchant/dashboard/month-day', { date: dateStr });
        const all = res.orders || [...(res.morning || []), ...(res.afternoon || [])];
        if (!aborted) setOrders(all);
      } catch (e: any) {
        if (!aborted) message.error(e?.response?.data?.detail || '加载当日订单失败');
      } finally {
        if (!aborted) setLoading(false);
      }
    })();
    return () => { aborted = true; };
  }, [storeId, dateStr]);

  return (
    <Spin spinning={loading}>
      <div style={{ marginBottom: 16 }}>{dateNav}</div>
      {orders.length === 0 ? (
        <Empty description="该日暂无预约" />
      ) : (
        <Row gutter={[8, 8]}>
          {orders.map((o) => {
            const sc = (o.status_code || 'pending') as StatusCode;
            const cfg = STATUS_COLOR[sc];
            return (
              <Col key={o.order_item_id} xs={24} sm={12} md={8}>
                <Card
                  size="small"
                  style={{ borderLeft: `4px solid ${cfg.color}` }}
                  styles={{ body: { padding: 12 } }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <strong>{o.customer_name}</strong>
                    {statusBadge(sc)}
                  </div>
                  <div style={{ fontSize: 13, color: '#555' }}>{o.product_name}</div>
                  <div style={{ fontSize: 12, color: '#888' }}>
                    {o.appointment_time_text || ''} · {o.slot_label || ''} · {formatYuan(o.amount)}
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </Spin>
  );
}
