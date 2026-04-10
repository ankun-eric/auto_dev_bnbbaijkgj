'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Input,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  BarChartOutlined,
  SearchOutlined,
  TeamOutlined,
  CheckCircleOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import type { Dayjs } from 'dayjs';

const { Title } = Typography;

interface StatisticsOverview {
  total_users: number;
  today_active_users: number;
  total_medication_reminders: number;
  total_checkin_items: number;
  total_user_plans: number;
  daily_trend: Array<{ date: string; count: number }>;
}

interface UserCheckinDetail {
  type: string;
  user_id: number;
  record_id: number;
  source_id: number;
  check_in_date: string;
  actual_value?: number;
  check_in_time?: string;
}

export default function StatisticsPage() {
  const [overview, setOverview] = useState<StatisticsOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [details, setDetails] = useState<UserCheckinDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [userSearch, setUserSearch] = useState('');
  const [checkDate, setCheckDate] = useState<Dayjs | null>(null);

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

  const fetchDetails = useCallback(
    async (page = 1, pageSize = 10) => {
      setDetailsLoading(true);
      try {
        const params: Record<string, unknown> = { page, page_size: pageSize };
        if (userSearch) {
          const parsed = parseInt(userSearch, 10);
          if (!isNaN(parsed)) params.user_id = parsed;
        }
        if (checkDate) params.check_date = checkDate.format('YYYY-MM-DD');

        const res = await get<{
          items?: UserCheckinDetail[];
          list?: UserCheckinDetail[];
          total?: number;
          page?: number;
          page_size?: number;
          date?: string;
        }>('/api/admin/health-plan/user-checkin-details', params);

        const items = res.items ?? res.list ?? [];
        setDetails(items);
        setPagination((prev) => ({
          ...prev,
          current: res.page ?? page,
          pageSize: res.page_size ?? pageSize,
          total: res.total ?? items.length,
        }));
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        message.error(err?.response?.data?.detail || err?.message || '加载打卡明细失败');
      } finally {
        setDetailsLoading(false);
      }
    },
    [userSearch, checkDate]
  );

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  const typeLabels: Record<string, string> = {
    medication: '用药打卡',
    checkin: '健康打卡',
    plan_task: '计划任务',
  };

  const columns = [
    { title: '用户ID', dataIndex: 'user_id', key: 'user_id', width: 100 },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      render: (v: string) => <Tag color={v === 'medication' ? 'orange' : v === 'checkin' ? 'green' : 'blue'}>{typeLabels[v] || v}</Tag>,
    },
    { title: '记录ID', dataIndex: 'record_id', key: 'record_id', width: 100 },
    { title: '来源ID', dataIndex: 'source_id', key: 'source_id', width: 100 },
    { title: '打卡日期', dataIndex: 'check_in_date', key: 'check_in_date', width: 120 },
    {
      title: '实际值',
      dataIndex: 'actual_value',
      key: 'actual_value',
      width: 100,
      render: (v: number | undefined) => v != null ? v : '-',
    },
    {
      title: '打卡时间',
      dataIndex: 'check_in_time',
      key: 'check_in_time',
      render: (v: string | undefined) => v || '-',
    },
  ];

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

      <Title level={5} style={{ marginBottom: 16 }}>用户打卡明细</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="输入用户ID"
          prefix={<SearchOutlined />}
          value={userSearch}
          onChange={(e) => setUserSearch(e.target.value)}
          onPressEnter={() => fetchDetails(1)}
          style={{ width: 200 }}
          allowClear
        />
        <DatePicker
          value={checkDate}
          onChange={(date) => setCheckDate(date)}
          placeholder="选择日期"
        />
        <Button type="primary" onClick={() => fetchDetails(1)}>
          查询
        </Button>
        <Button
          onClick={() => {
            setUserSearch('');
            setCheckDate(null);
            setTimeout(() => fetchDetails(1), 0);
          }}
        >
          重置
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={details}
        rowKey={(record) => `${record.type}-${record.record_id}`}
        loading={detailsLoading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchDetails(page, pageSize),
        }}
        scroll={{ x: 700 }}
      />
    </div>
  );
}
