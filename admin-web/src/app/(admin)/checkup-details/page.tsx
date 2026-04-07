'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Input, Button, Space, Select, DatePicker, Tag, Card,
  Statistic, Row, Col, Tooltip, Drawer, Avatar, Image, Descriptions, message,
} from 'antd';
import {
  SearchOutlined, ReloadOutlined, FileSearchOutlined, PlusCircleOutlined,
  WarningOutlined, CalendarOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const REPORT_TYPE_OPTIONS = [
  { label: '血常规', value: '血常规' },
  { label: '肝功能', value: '肝功能' },
  { label: '综合体检', value: '综合体检' },
  { label: '尿常规', value: '尿常规' },
  { label: '血脂', value: '血脂' },
  { label: '血糖', value: '血糖' },
  { label: '肾功能', value: '肾功能' },
  { label: '甲状腺功能', value: '甲状腺功能' },
];

const REPORT_TYPE_COLORS: Record<string, string> = {
  '血常规': 'blue',
  '肝功能': 'green',
  '综合体检': 'purple',
  '尿常规': 'cyan',
  '血脂': 'orange',
  '血糖': 'gold',
  '肾功能': 'magenta',
  '甲状腺功能': 'geekblue',
};

const STATUS_OPTIONS = [
  { label: '正常', value: 'normal' },
  { label: '异常', value: 'abnormal' },
];

interface CheckupDetail {
  id: number;
  created_at: string;
  user_nickname: string;
  user_phone: string;
  user_avatar: string;
  report_type: string;
  abnormal_count: number;
  summary: string;
  status: string;
  provider_name: string;
  original_image_url: string;
  ocr_raw_text: string;
  ai_structured_result: any;
  abnormal_items: any[];
}

interface ListResponse {
  items: CheckupDetail[];
  total: number;
  page: number;
  page_size: number;
}

interface StatsData {
  total_reports: number;
  today_new: number;
  abnormal_reports: number;
  month_reports: number;
}

function maskPhone(phone: string): string {
  if (!phone || phone.length < 7) return phone || '-';
  return phone.slice(0, 3) + '****' + phone.slice(-4);
}

export default function CheckupDetailsPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<CheckupDetail[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [stats, setStats] = useState<StatsData>({ total_reports: 0, today_new: 0, abnormal_reports: 0, month_reports: 0 });

  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [keyword, setKeyword] = useState('');
  const [reportType, setReportType] = useState<string | undefined>(undefined);
  const [status, setStatus] = useState<string | undefined>(undefined);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<CheckupDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await get<StatsData>('/api/admin/checkup-details/statistics');
      setStats(res);
    } catch {
      // ignore
    }
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');
      if (keyword) params.keyword = keyword;
      if (reportType) params.report_type = reportType;
      if (status) params.status = status;

      const res = await get<ListResponse>('/api/admin/checkup-details', params);
      setData(res.items || []);
      setPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取体检报告解读明细失败');
    } finally {
      setLoading(false);
    }
  }, [dateRange, keyword, reportType, status]);

  useEffect(() => {
    fetchData();
    fetchStats();
  }, [fetchData, fetchStats]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

  const handleReset = () => {
    setDateRange(null);
    setKeyword('');
    setReportType(undefined);
    setStatus(undefined);
  };

  const handleViewDetail = async (record: CheckupDetail) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const res = await get<CheckupDetail>(`/api/admin/checkup-details/${record.id}`);
      setDetail(res);
    } catch {
      message.error('获取详情失败');
      setDetail(record);
    } finally {
      setDetailLoading(false);
    }
  };

  const columns = [
    {
      title: '解读时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '关联用户',
      key: 'user',
      width: 160,
      render: (_: any, record: CheckupDetail) => (
        <Space>
          <span>{record.user_nickname || '-'}</span>
          <Text type="secondary">{maskPhone(record.user_phone)}</Text>
        </Space>
      ),
    },
    {
      title: '报告类型',
      dataIndex: 'report_type',
      key: 'report_type',
      width: 110,
      render: (v: string) => <Tag color={REPORT_TYPE_COLORS[v] || 'default'}>{v || '-'}</Tag>,
    },
    {
      title: '异常指标数',
      dataIndex: 'abnormal_count',
      key: 'abnormal_count',
      width: 100,
      render: (v: number) => (
        <span style={{ color: v > 0 ? '#ff4d4f' : undefined, fontWeight: v > 0 ? 600 : undefined }}>
          {v ?? 0}
        </span>
      ),
    },
    {
      title: '解读摘要',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v && v.length > 30 ? v.slice(0, 30) + '...' : v || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: '识别状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        if (v === 'normal') return <Tag color="green">正常</Tag>;
        if (v === 'abnormal') return <Tag color="red">异常</Tag>;
        return <Tag>{v || '-'}</Tag>;
      },
    },
    {
      title: '使用厂商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 100,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: CheckupDetail) => (
        <Button type="link" size="small" onClick={() => handleViewDetail(record)}>
          详情
        </Button>
      ),
    },
  ];

  const abnormalColumns = [
    { title: '指标名', dataIndex: 'name', key: 'name', width: 120 },
    { title: '实际值', dataIndex: 'value', key: 'value', width: 100 },
    { title: '参考范围', dataIndex: 'reference_range', key: 'reference_range', width: 120 },
    { title: '异常说明', dataIndex: 'description', key: 'description' },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>体检报告解读明细</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总报告数"
              value={stats.total_reports}
              prefix={<FileSearchOutlined style={{ color: '#1890ff' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日新增"
              value={stats.today_new}
              prefix={<PlusCircleOutlined style={{ color: '#52c41a' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="异常报告数"
              value={stats.abnormal_reports}
              prefix={<WarningOutlined style={{ color: '#ff4d4f' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本月解读数"
              value={stats.month_reports}
              prefix={<CalendarOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col>
          <RangePicker
            value={dateRange as any}
            onChange={(dates) => setDateRange(dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
          />
        </Col>
        <Col>
          <Input
            placeholder="手机号或昵称搜索"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 200 }}
            allowClear
          />
        </Col>
        <Col>
          <Select
            placeholder="报告类型"
            value={reportType}
            onChange={(v) => setReportType(v)}
            allowClear
            style={{ width: 140 }}
            options={REPORT_TYPE_OPTIONS}
          />
        </Col>
        <Col>
          <Select
            placeholder="状态"
            value={status}
            onChange={(v) => setStatus(v)}
            allowClear
            style={{ width: 120 }}
            options={STATUS_OPTIONS}
          />
        </Col>
        <Col>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>搜索</Button>
            <Button icon={<ReloadOutlined />} onClick={() => { handleReset(); setTimeout(() => fetchData(1, pagination.pageSize), 0); }}>重置</Button>
          </Space>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1100 }}
      />

      <Drawer
        title="体检报告解读详情"
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setDetail(null); }}
        width={700}
        loading={detailLoading}
      >
        {detail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <Card size="small" title="用户信息">
              <Space>
                <Avatar src={detail.user_avatar} size={48}>{detail.user_nickname?.[0]}</Avatar>
                <div>
                  <div><Text strong>{detail.user_nickname || '-'}</Text></div>
                  <div><Text type="secondary">{detail.user_phone || '-'}</Text></div>
                </div>
              </Space>
            </Card>

            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="解读时间">
                {detail.created_at ? dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="报告类型">
                <Tag color={REPORT_TYPE_COLORS[detail.report_type] || 'default'}>{detail.report_type}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="识别状态">
                {detail.status === 'normal' ? <Tag color="green">正常</Tag> : <Tag color="red">异常</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="使用厂商">{detail.provider_name || '-'}</Descriptions.Item>
            </Descriptions>

            {detail.original_image_url && (
              <Card size="small" title="原始图片">
                <Image
                  src={detail.original_image_url}
                  style={{ maxWidth: '100%', maxHeight: 300 }}
                  fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN4kNMRdQAAAABJRU5ErkJggg=="
                />
              </Card>
            )}

            <Card size="small" title="OCR原始文字">
              <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, maxHeight: 200, overflow: 'auto', margin: 0 }}>
                {detail.ocr_raw_text || '暂无'}
              </pre>
            </Card>

            <Card size="small" title="AI结构化分析">
              <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, maxHeight: 300, overflow: 'auto', margin: 0 }}>
                {detail.ai_structured_result ? JSON.stringify(detail.ai_structured_result, null, 2) : '暂无'}
              </pre>
            </Card>

            {detail.abnormal_items && detail.abnormal_items.length > 0 && (
              <Card size="small" title="异常指标列表">
                <Table
                  dataSource={detail.abnormal_items}
                  columns={abnormalColumns}
                  rowKey={(_, idx) => String(idx)}
                  pagination={false}
                  size="small"
                />
              </Card>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
