'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Card,
  Col,
  DatePicker,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Button,
  message,
} from 'antd';
import {
  BarChartOutlined,
  TeamOutlined,
  CheckCircleOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface StatisticsOverview {
  total_users: number;
  today_active_users: number;
  total_medication_reminders: number;
  total_checkin_items: number;
  total_user_plans: number;
  daily_trend: Array<{ date: string; count: number }>;
}

interface DailyDetail {
  name: string;
  type: string;
  is_completed: boolean;
  check_time: string | null;
}

interface DailySummaryItem {
  date: string;
  total_expected: number;
  total_completed: number;
  completion_rate: number;
  details: DailyDetail[];
}

interface UserOption {
  id: number;
  phone: string | null;
  nickname: string | null;
}

export default function StatisticsPage() {
  const [overview, setOverview] = useState<StatisticsOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [dailyData, setDailyData] = useState<DailySummaryItem[]>([]);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [users, setUsers] = useState<UserOption[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | undefined>(undefined);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);

  const fetchOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const res = await get<StatisticsOverview>('/api/admin/health-plan/checkin-statistics');
      setOverview(res);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载统计概览失败');
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const fetchDailySummary = useCallback(async () => {
    setDailyLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (selectedUserId) params.user_id = selectedUserId;
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD');
        params.end_date = dateRange[1].format('YYYY-MM-DD');
      }
      const res = await get<{ daily_data: DailySummaryItem[]; users: UserOption[] }>(
        '/api/admin/health-plan/user-daily-summary',
        params,
      );
      setDailyData(res.daily_data ?? []);
      if (res.users) setUsers(res.users);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载每日汇总失败');
    } finally {
      setDailyLoading(false);
    }
  }, [selectedUserId, dateRange]);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    fetchDailySummary();
  }, [fetchDailySummary]);

  const typeLabels: Record<string, string> = {
    medication: '用药打卡',
    checkin: '健康打卡',
    plan_task: '计划任务',
  };

  const summaryColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '应打卡数', dataIndex: 'total_expected', key: 'total_expected', width: 110 },
    { title: '已完成数', dataIndex: 'total_completed', key: 'total_completed', width: 110 },
    {
      title: '完成率',
      dataIndex: 'completion_rate',
      key: 'completion_rate',
      width: 110,
      render: (v: number) => {
        const color = v >= 80 ? 'green' : v >= 50 ? 'orange' : 'red';
        return <Tag color={color}>{v}%</Tag>;
      },
    },
    {
      title: '明细条数',
      key: 'detail_count',
      width: 100,
      render: (_: unknown, record: DailySummaryItem) => record.details.length,
    },
  ];

  const detailColumns = [
    { title: '项目名称', dataIndex: 'name', key: 'name' },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (v: string) => (
        <Tag color={v === 'medication' ? 'orange' : v === 'checkin' ? 'green' : 'blue'}>
          {typeLabels[v] || v}
        </Tag>
      ),
    },
    {
      title: '是否完成',
      dataIndex: 'is_completed',
      key: 'is_completed',
      width: 100,
      render: (v: boolean) => (
        <Tag color={v ? 'green' : 'default'}>{v ? '已完成' : '未完成'}</Tag>
      ),
    },
    {
      title: '打卡时间',
      dataIndex: 'check_time',
      key: 'check_time',
      width: 180,
      render: (v: string | null) => v || '-',
    },
  ];

  const expandedRowRender = (record: DailySummaryItem) => (
    <Table
      columns={detailColumns}
      dataSource={record.details}
      rowKey={(item, index) => `${record.date}-${item.type}-${item.name}-${index}`}
      pagination={false}
      size="small"
    />
  );

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <BarChartOutlined style={{ marginRight: 8, color: '#52c41a' }} />
        打卡数据统计
      </Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={8}>
          <Card loading={overviewLoading}>
            <Statistic
              title="今日活跃用户"
              value={overview?.today_active_users ?? 0}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card loading={overviewLoading}>
            <Statistic
              title="总用户数"
              value={overview?.total_users ?? 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card loading={overviewLoading}>
            <Statistic
              title="活跃计划数"
              value={overview?.total_user_plans ?? 0}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12}>
          <Card loading={overviewLoading}>
            <Statistic
              title="用药提醒数"
              value={overview?.total_medication_reminders ?? 0}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12}>
          <Card loading={overviewLoading}>
            <Statistic
              title="打卡项数"
              value={overview?.total_checkin_items ?? 0}
              valueStyle={{ color: '#13c2c2' }}
            />
          </Card>
        </Col>
      </Row>

      {overview?.daily_trend && overview.daily_trend.length > 0 && (
        <Card title="每日打卡趋势" size="small" style={{ marginBottom: 24 }}>
          <Space wrap>
            {overview.daily_trend.map((d, i) => (
              <Tag key={i} color="blue">
                {d.date}: {d.count} 次
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      <Title level={5} style={{ marginBottom: 16 }}>每日打卡汇总</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          showSearch
          allowClear
          placeholder="选择用户"
          value={selectedUserId}
          onChange={(val) => setSelectedUserId(val)}
          style={{ width: 240 }}
          filterOption={(input, option) =>
            (option?.label as string ?? '').toLowerCase().includes(input.toLowerCase())
          }
          options={users.map((u) => ({
            label: `${u.nickname || '未设置昵称'} (${u.phone || u.id})`,
            value: u.id,
          }))}
        />
        <RangePicker
          value={dateRange}
          onChange={(dates) => {
            setDateRange(dates as [Dayjs, Dayjs] | null);
          }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchDailySummary()}>
          查询
        </Button>
        <Button
          onClick={() => {
            setSelectedUserId(undefined);
            setDateRange(null);
          }}
        >
          重置
        </Button>
      </Space>

      <Table
        columns={summaryColumns}
        dataSource={dailyData}
        rowKey="date"
        loading={dailyLoading}
        expandable={{ expandedRowRender }}
        pagination={false}
        scroll={{ x: 600 }}
      />
    </div>
  );
}
