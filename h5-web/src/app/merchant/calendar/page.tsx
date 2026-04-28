'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Calendar, Badge, Card, Tag, Table, Typography, Space, Button, Spin, Empty, message } from 'antd';
import { LeftOutlined, RightOutlined, CalendarOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import api from '@/lib/api';
import { getCurrentStoreId } from '../lib';

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
  time_slot: string;
  customer_name: string;
  product_name: string;
  status: string;
}

const STATUS_CONFIG: Record<string, { text: string; color: string }> = {
  pending: { text: '待确认', color: 'warning' },
  confirmed: { text: '已确认', color: 'processing' },
  completed: { text: '已完成', color: 'success' },
  cancelled: { text: '已取消', color: 'default' },
};

function getDensityColor(count: number): string {
  if (count === 0) return '#f0f0f0';
  if (count <= 2) return '#52c41a';
  if (count <= 5) return '#fa8c16';
  return '#ff4d4f';
}

export default function CalendarPCPage() {
  const [currentMonth, setCurrentMonth] = useState<Dayjs>(dayjs());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [monthlySummary, setMonthlySummary] = useState<Record<string, DaySummary>>({});
  const [dailyList, setDailyList] = useState<DailyAppointment[]>([]);
  const [loadingMonthly, setLoadingMonthly] = useState(false);
  const [loadingDaily, setLoadingDaily] = useState(false);

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

  const dateCellRender = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD');
    const summary = monthlySummary[dateStr];
    if (!summary || summary.count === 0) return null;
    return (
      <div>
        <div style={{ fontSize: 12, color: '#fa541c', fontWeight: 600 }}>{summary.count}单</div>
        <div style={{ display: 'flex', gap: 3, marginTop: 2 }}>
          {[
            { label: '上午', count: summary.morning_count },
            { label: '下午', count: summary.afternoon_count },
            { label: '晚间', count: summary.evening_count },
          ].map(slot => (
            <div
              key={slot.label}
              title={`${slot.label}: ${slot.count}单`}
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

  const columns = [
    {
      title: '预约时段',
      dataIndex: 'time_slot',
      key: 'time_slot',
      width: 150,
    },
    {
      title: '客户姓名',
      dataIndex: 'customer_name',
      key: 'customer_name',
      width: 120,
    },
    {
      title: '商品名称',
      dataIndex: 'product_name',
      key: 'product_name',
    },
    {
      title: '预约状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: string) => {
        const cfg = STATUS_CONFIG[s] || { text: s, color: 'default' };
        return <Tag color={cfg.color}>{cfg.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, row: DailyAppointment) => (
        <Button type="link" size="small" onClick={() => window.location.href = `/merchant/orders?highlight=${row.order_id}`}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}><CalendarOutlined style={{ marginRight: 8 }} />预约日历</Title>

      {/* Density legend */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
        <Text type="secondary">热力色块：</Text>
        {[
          { label: '低密度(0-2)', color: '#52c41a' },
          { label: '中密度(3-5)', color: '#fa8c16' },
          { label: '高密度(6+)', color: '#ff4d4f' },
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
            onSelect={(date) => {
              setSelectedDate(date.format('YYYY-MM-DD'));
              setCurrentMonth(date);
            }}
            onPanelChange={(date) => {
              setCurrentMonth(date);
              setSelectedDate(null);
            }}
            cellRender={(current, info) => {
              if (info.type === 'date') return dateCellRender(current as Dayjs);
              return null;
            }}
          />
        </Card>
      </Spin>

      {selectedDate && (
        <Card title={`${selectedDate} 预约列表`} style={{ marginTop: 16 }}>
          <Table
            rowKey={(r) => r.id || r.order_id}
            loading={loadingDaily}
            dataSource={dailyList}
            columns={columns}
            pagination={false}
            locale={{ emptyText: <Empty description="当天无预约" /> }}
          />
        </Card>
      )}
    </div>
  );
}
