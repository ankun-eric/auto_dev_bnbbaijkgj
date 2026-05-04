'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Calendar, Card, Tag, Typography, Space, Button, Spin, Empty, message, Drawer, Descriptions } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { ConfigProvider } from 'antd';
import { LeftOutlined, RightOutlined, CalendarOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import 'dayjs/locale/zh-cn';
import api from '@/lib/api';
import { getCurrentStoreId } from '../lib';
import DailyOrdersModal from './DailyOrdersModal';

dayjs.locale('zh-cn');

const { Title, Text } = Typography;

interface DaySummary {
  date: string;
  count: number;
  morning_count: number;
  afternoon_count: number;
  evening_count: number;
}

interface DailyAppointment {
  id: number;
  order_id: number;
  order_no?: string;
  time_slot: string;
  customer_name: string;
  customer_phone?: string;
  product_name: string;
  status: string;
  remark?: string;
  appointment_time?: string;
}

// PRD「商家 PC 后台优化 v1.1」F5：预约状态全量中文化
const STATUS_CONFIG: Record<string, { text: string; color: string }> = {
  pending: { text: '待确认', color: 'warning' },
  confirmed: { text: '已确认', color: 'processing' },
  appointed: { text: '待核销', color: 'cyan' },
  pending_use: { text: '待核销', color: 'cyan' },
  partial_used: { text: '部分核销', color: 'gold' },
  completed: { text: '已完成', color: 'success' },
  cancelled: { text: '已取消', color: 'default' },
  refunded: { text: '已退款', color: 'default' },
  refunding: { text: '退款中', color: 'red' },
};

// PRD F5：中文月份名称
const CN_MONTH_NAMES = ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];

// PRD F5：中文星期（周一开始）
const CN_WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

function getDensityColor(count: number): string {
  if (count === 0) return '#f0f0f0';
  if (count <= 2) return '#52c41a';
  if (count <= 5) return '#fa8c16';
  return '#ff4d4f';
}

function timeSlotLabel(slot: string): string {
  if (!slot) return '-';
  const map: Record<string, string> = { morning: '上午', afternoon: '下午', evening: '晚间' };
  if (map[slot]) return map[slot];
  return slot;
}

export default function CalendarPCPage() {
  const [currentMonth, setCurrentMonth] = useState<Dayjs>(dayjs());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [monthlySummary, setMonthlySummary] = useState<Record<string, DaySummary>>({});
  const [dailyList, setDailyList] = useState<DailyAppointment[]>([]);
  const [loadingMonthly, setLoadingMonthly] = useState(false);
  const [loadingDaily, setLoadingDaily] = useState(false);

  // PRD F6：右侧侧滑面板状态
  const [panelOpen, setPanelOpen] = useState(false);
  const [currentAppt, setCurrentAppt] = useState<DailyAppointment | null>(null);

  // PRD「当日订单弹窗」v1.0：点击日期单元格触发的当日订单弹窗
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupDate, setPopupDate] = useState<string | null>(null);

  const monthStr = useMemo(() => currentMonth.format('YYYY-MM'), [currentMonth]);

  const loadMonthly = useCallback(async () => {
    setLoadingMonthly(true);
    try {
      const params: any = { month: monthStr };
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/calendar/monthly', { params });
      const map: Record<string, DaySummary> = {};
      (res?.days || res || []).forEach((d: DaySummary) => {
        map[d.date] = d;
      });
      setMonthlySummary(map);
    } catch {
      setMonthlySummary({});
    } finally {
      setLoadingMonthly(false);
    }
  }, [monthStr]);

  const loadDaily = useCallback(async (date: string) => {
    setLoadingDaily(true);
    try {
      const params: any = { date };
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      const res: any = await api.get('/api/merchant/calendar/daily', { params });
      setDailyList(res?.appointments || res?.items || res || []);
    } catch {
      setDailyList([]);
    } finally {
      setLoadingDaily(false);
    }
  }, []);

  useEffect(() => { loadMonthly(); }, [loadMonthly]);

  useEffect(() => {
    if (selectedDate) loadDaily(selectedDate);
  }, [selectedDate, loadDaily]);

  // PRD F6：ESC 关闭面板（Drawer 默认已支持，但额外保证）
  useEffect(() => {
    if (!panelOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setPanelOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [panelOpen]);

  const dateCellRender = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD');
    const summary = monthlySummary[dateStr];
    if (!summary || summary.count === 0) return null;
    // PRD「当日订单弹窗」v1.0 F-01：徽标作为可视入口提示
    return (
      <div
        title="点击查看当日订单详情"
        style={{ cursor: 'pointer' }}
      >
        <div style={{ fontSize: 12, color: '#fa541c', fontWeight: 600 }}>共 {summary.count} 个预约</div>
        <div style={{ display: 'flex', gap: 3, marginTop: 2 }}>
          {[
            { label: '上午', count: summary.morning_count },
            { label: '下午', count: summary.afternoon_count },
            { label: '晚间', count: summary.evening_count },
          ].map(slot => (
            <div
              key={slot.label}
              title={`${slot.label}：${slot.count} 个`}
              style={{
                width: 18,
                height: 8,
                borderRadius: 2,
                background: getDensityColor(slot.count),
              }}
            />
          ))}
        </div>
      </div>
    );
  };

  // PRD「当日订单弹窗」v1.0 F-01：点击日期单元格触发当日订单弹窗
  // 业务规则：仅当 summary.count ≥ 1 时才打开弹窗；0 单的日期点击无响应
  const handleCellClick = useCallback((date: Dayjs) => {
    const dateStr = date.format('YYYY-MM-DD');
    const summary = monthlySummary[dateStr];
    if (!summary || summary.count === 0) {
      // 仍然保留旧行为：选中该日期，但不打开弹窗
      setSelectedDate(dateStr);
      setCurrentMonth(date);
      return;
    }
    setPopupDate(dateStr);
    setPopupOpen(true);
    // 同时同步选中状态，让旧的卡片列表也跟着更新（向后兼容）
    setSelectedDate(dateStr);
    setCurrentMonth(date);
    try {
      // eslint-disable-next-line no-console
      console.info('[track] calendar_daily_popup_open', { date: dateStr, order_count: summary.count, terminal: 'pc' });
    } catch {}
  }, [monthlySummary]);

  // PRD F6：点击预约打开右侧侧滑面板
  const openPanel = (appt: DailyAppointment) => {
    setCurrentAppt(appt);
    setPanelOpen(true);
  };

  const goToOrderDetail = () => {
    if (!currentAppt) return;
    window.location.href = `/merchant/orders?highlight=${currentAppt.order_id}`;
  };

  // PRD F5：自定义日历头部（去年份选择器 + 中文月份 + 中文左右切换）
  const headerRender = ({ value, onChange }: any) => {
    const currentVal = value as Dayjs;
    const monthIdx = currentVal.month();
    const year = currentVal.year();
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 16,
          padding: '12px 0',
        }}
      >
        <Button
          type="text"
          icon={<LeftOutlined />}
          onClick={() => {
            const next = currentVal.subtract(1, 'month');
            onChange(next);
            setCurrentMonth(next);
            setSelectedDate(null);
          }}
        >
          上月
        </Button>
        <Text strong style={{ fontSize: 18, minWidth: 130, textAlign: 'center', display: 'inline-block' }}>
          {year} 年 {CN_MONTH_NAMES[monthIdx]}
        </Text>
        <Button
          type="text"
          onClick={() => {
            const next = currentVal.add(1, 'month');
            onChange(next);
            setCurrentMonth(next);
            setSelectedDate(null);
          }}
        >
          下月 <RightOutlined />
        </Button>
      </div>
    );
  };

  return (
    <ConfigProvider locale={zhCN}>
      <div>
        <Title level={4}><CalendarOutlined style={{ marginRight: 8 }} />预约日历</Title>

        {/* 热力色块图例 */}
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
          <Text type="secondary">热力色块：</Text>
          {[
            { label: '低密度（0-2 个）', color: '#52c41a' },
            { label: '中密度（3-5 个）', color: '#fa8c16' },
            { label: '高密度（6 个以上）', color: '#ff4d4f' },
          ].map(item => (
            <Space key={item.label} size={4}>
              <div style={{ width: 18, height: 10, borderRadius: 2, background: item.color }} />
              <Text type="secondary" style={{ fontSize: 12 }}>{item.label}</Text>
            </Space>
          ))}
        </div>

        <Spin spinning={loadingMonthly}>
          <Card>
            <Calendar
              value={currentMonth}
              headerRender={headerRender}
              onSelect={(date) => handleCellClick(date as Dayjs)}
              onPanelChange={(date) => {
                setCurrentMonth(date);
                setSelectedDate(null);
              }}
              cellRender={(current, info) => {
                if (info.type === 'date') return dateCellRender(current as Dayjs);
                return null;
              }}
            />
            {/* PRD F5：中文星期标题（覆盖默认） */}
            <style jsx global>{`
              .ant-picker-content thead th {
                font-weight: 600 !important;
              }
              /* 把日历内部默认英文 Mo/Tu... 替换为中文 */
              .ant-picker-content thead th:nth-child(1)::before { content: '周日'; }
              .ant-picker-content thead th:nth-child(2)::before { content: '周一'; }
              .ant-picker-content thead th:nth-child(3)::before { content: '周二'; }
              .ant-picker-content thead th:nth-child(4)::before { content: '周三'; }
              .ant-picker-content thead th:nth-child(5)::before { content: '周四'; }
              .ant-picker-content thead th:nth-child(6)::before { content: '周五'; }
              .ant-picker-content thead th:nth-child(7)::before { content: '周六'; }
              .ant-picker-content thead th { font-size: 0; }
              .ant-picker-content thead th::before { font-size: 14px; }
            `}</style>
          </Card>
        </Spin>

        {selectedDate && (
          <Card title={`${selectedDate} 当日预约（共 ${dailyList.length} 个）`} style={{ marginTop: 16 }}>
            <Spin spinning={loadingDaily}>
              {dailyList.length === 0 ? (
                <Empty description="当天无预约" />
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                  {dailyList.map((appt) => {
                    const cfg = STATUS_CONFIG[appt.status] || { text: appt.status, color: 'default' };
                    return (
                      <div
                        key={appt.id || appt.order_id}
                        onClick={() => openPanel(appt)}
                        style={{
                          padding: 14,
                          border: '1px solid #f0f0f0',
                          borderRadius: 8,
                          cursor: 'pointer',
                          background: '#fff',
                          transition: 'all 0.2s',
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#1677ff'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(22,119,255,0.15)'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#f0f0f0'; e.currentTarget.style.boxShadow = 'none'; }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <Text strong>{appt.customer_name || '匿名客户'}</Text>
                          <Tag color={cfg.color}>{cfg.text}</Tag>
                        </div>
                        <div style={{ fontSize: 13, color: '#595959', marginBottom: 4 }}>
                          {appt.product_name || '-'}
                        </div>
                        <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                          预约时段：{timeSlotLabel(appt.time_slot)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Spin>
          </Card>
        )}

        {/* PRD F6：右侧侧滑面板 — 宽度 400px，仅展示 + 一个跳转按钮 */}
        <Drawer
          title="预约详情"
          placement="right"
          width={400}
          open={panelOpen}
          onClose={() => setPanelOpen(false)}
          maskClosable={true}
          keyboard={true}
          footer={
            <div style={{ textAlign: 'right' }}>
              <Button type="primary" block size="large" onClick={goToOrderDetail}>
                查看订单详情
              </Button>
            </div>
          }
        >
          {currentAppt && (
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="预约人">{currentAppt.customer_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="电话">{currentAppt.customer_phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="预约项目">{currentAppt.product_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="预约时间">
                {currentAppt.appointment_time
                  ? dayjs(currentAppt.appointment_time).format('YYYY-MM-DD HH:mm')
                  : `${selectedDate || ''} ${timeSlotLabel(currentAppt.time_slot)}`}
              </Descriptions.Item>
              <Descriptions.Item label="备注">{currentAppt.remark || '-'}</Descriptions.Item>
              <Descriptions.Item label="订单号">
                <code style={{ fontSize: 12 }}>{currentAppt.order_no || `#${currentAppt.order_id}`}</code>
              </Descriptions.Item>
              <Descriptions.Item label="预约状态">
                <Tag color={(STATUS_CONFIG[currentAppt.status] || { color: 'default' }).color}>
                  {(STATUS_CONFIG[currentAppt.status] || { text: currentAppt.status }).text}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          )}
        </Drawer>

        {/* PRD「当日订单弹窗」v1.0：日历点击日期触发的当日订单弹窗 */}
        <DailyOrdersModal
          open={popupOpen}
          date={popupDate}
          storeId={getCurrentStoreId() ?? null}
          onClose={() => setPopupOpen(false)}
        />
      </div>
    </ConfigProvider>
  );
}
