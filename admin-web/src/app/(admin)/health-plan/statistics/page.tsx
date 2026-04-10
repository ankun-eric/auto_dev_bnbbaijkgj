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
import dayjs, { Dayjs } from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface StatisticsOverview {
  active_users: number;
  average_completion_rate: number;
  plan_participation: Array<{ plan_name: string; user_count: number }>;
}

interface UserCheckinDetail {
  user_id: number;
  username: string;
  nickname?: string;
  plan_name: string;
  plan_type?: string;
  total_tasks: number;
  completed_tasks: number;
  completion_rate: number;
}

export default function StatisticsPage() {
  const [overview, setOverview] = useState<StatisticsOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [details, setDetails] = useState<UserCheckinDetail[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [userSearch, setUserSearch] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);

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
        if (userSearch) params.user_search = userSearch;
        if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
        if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');

        const res = await get<{
          items?: UserCheckinDetail[];
          list?: UserCheckinDetail[];
          total?: number;
          page?: number;
          page_size?: number;
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
    [userSearch, dateRange]
  );

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    fetchDetails();
  }, [fetchDetails]);

  const getCompletionColor = (rate: number) => {
    if (rate >= 80) return 'green';
    if (rate >= 50) return 'orange';
    return 'red';
  };

  const columns = [
    {
      title: '用户',
      key: 'user',
      width: 130,
      render: (_: unknown, record: UserCheckinDetail) => record.nickname || record.username || `用户${record.user_id}`,
    },
    { title: '计划名称', dataIndex: 'plan_name', key: 'plan_name' },
    {
      title: '计划类型',
      dataIndex: 'plan_type',
      key: 'plan_type',
      width: 100,
      render: (v: string | undefined) => v || '-',
    },
    { title: '总任务数', dataIndex: 'total_tasks', key: 'total_tasks', width: 100 },
    { title: '完成数', dataIndex: 'completed_tasks', key: 'completed_tasks', width: 90 },
    {
      title: '完成率',
      dataIndex: 'completion_rate',
      key: 'completion_rate',
      width: 100,
      sorter: (a: UserCheckinDetail, b: UserCheckinDetail) => a.completion_rate - b.completion_rate,
      render: (v: number) => <Tag color={getCompletionColor(v)}>{v.toFixed(1)}%</Tag>,
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
              title="活跃用户数"
              value={overview?.active_users ?? 0}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card loading={overviewLoading}>
            <Statistic
              title="平均完成率"
              value={overview?.average_completion_rate ?? 0}
              precision={1}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card loading={overviewLoading}>
            <Statistic
              title="参与计划数"
              value={overview?.plan_participation?.length ?? 0}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {overview?.plan_participation && overview.plan_participation.length > 0 && (
        <Card title="各计划参与人数" size="small" style={{ marginBottom: 24 }}>
          <Space wrap>
            {overview.plan_participation.map((p, i) => (
              <Tag key={i} color="blue">
                {p.plan_name}: {p.user_count} 人
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      <Title level={5} style={{ marginBottom: 16 }}>用户打卡明细</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索用户名/昵称"
          prefix={<SearchOutlined />}
          value={userSearch}
          onChange={(e) => setUserSearch(e.target.value)}
          onPressEnter={() => fetchDetails(1)}
          style={{ width: 200 }}
          allowClear
        />
        <RangePicker
          value={dateRange as [Dayjs, Dayjs] | null}
          onChange={(dates) => setDateRange(dates as [Dayjs | null, Dayjs | null] | null)}
        />
        <Button type="primary" onClick={() => fetchDetails(1)}>
          查询
        </Button>
        <Button
          onClick={() => {
            setUserSearch('');
            setDateRange(null);
            setTimeout(() => fetchDetails(1), 0);
          }}
        >
          重置
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={details}
        rowKey={(record) => `${record.user_id}-${record.plan_name}`}
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
