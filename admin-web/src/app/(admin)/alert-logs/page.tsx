'use client';

/**
 * [PRD-FAMILY-GUARDIAN-V1] 推送记录查询 + Excel 导出
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { DownloadOutlined, SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface LogRow {
  id: number;
  guardian_user_id: number;
  guardian_nickname?: string;
  guardian_phone?: string;
  member_id: number;
  member_nickname?: string;
  report_id?: number;
  severity: string;
  abnormal_count: number;
  template_code: string;
  channel: string;
  delivery_status: string;
  pushed_at?: string;
  clicked_at?: string;
}

const CHANNELS = [
  { value: 'wechat_mp', label: '公众号' },
  { value: 'mini_subscribe', label: '小程序订阅' },
  { value: 'app_push', label: 'App 推送' },
];
const STATUSES = [
  { value: 'sent', label: '已发送', color: 'blue' },
  { value: 'delivered', label: '已送达', color: 'green' },
  { value: 'failed', label: '失败', color: 'red' },
  { value: 'clicked', label: '已点击', color: 'purple' },
];

const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/api\/?$/, '');

export default function AlertLogsPage() {
  const [form] = Form.useForm();
  const [data, setData] = useState<LogRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const fetchData = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const values = form.getFieldsValue();
      const params: any = {
        page,
        page_size: pagination.pageSize,
        channel: values.channel,
        status: values.status,
        clicked: values.clicked,
        guardian_keyword: values.guardian_keyword,
        member_keyword: values.member_keyword,
      };
      if (values.dateRange && values.dateRange.length === 2) {
        params.start_at = values.dateRange[0].toISOString();
        params.end_at = values.dateRange[1].toISOString();
      }
      const res = await get<{ items: LogRow[]; total: number }>('/api/admin/alert-logs', params);
      setData(res.items || []);
      setPagination({ current: page, pageSize: pagination.pageSize, total: res.total || 0 });
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [form, pagination.pageSize]);

  useEffect(() => {
    form.setFieldsValue({ dateRange: [dayjs().subtract(7, 'day'), dayjs()] });
    fetchData(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onExport = async () => {
    try {
      const values = form.getFieldsValue();
      const qs = new URLSearchParams();
      if (values.dateRange && values.dateRange.length === 2) {
        qs.append('start_at', values.dateRange[0].toISOString());
        qs.append('end_at', values.dateRange[1].toISOString());
      }
      if (values.channel) qs.append('channel', values.channel);
      if (values.status) qs.append('status', values.status);
      if (values.clicked !== undefined && values.clicked !== null && values.clicked !== '')
        qs.append('clicked', String(values.clicked));
      const token = localStorage.getItem('admin_token') || '';
      const resp = await fetch(`${apiBase}/api/admin/alert-logs/export?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) throw new Error('导出失败');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `family_alert_logs_${dayjs().format('YYYYMMDD_HHmmss')}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch (e: any) {
      message.error(e?.message || '导出失败');
    }
  };

  const columns = [
    {
      title: '推送时间',
      dataIndex: 'pushed_at',
      key: 'pushed_at',
      width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '',
    },
    {
      title: '守护者',
      key: 'guardian',
      width: 180,
      render: (_: any, r: LogRow) => (
        <div>
          <div>{r.guardian_nickname || `用户${r.guardian_user_id}`}</div>
          <div style={{ color: '#999', fontSize: 12 }}>{r.guardian_phone}</div>
        </div>
      ),
    },
    {
      title: '被守护者档案',
      key: 'member',
      width: 160,
      render: (_: any, r: LogRow) => r.member_nickname || `档案${r.member_id}`,
    },
    { title: '异常项数', dataIndex: 'abnormal_count', key: 'abnormal_count', width: 80 },
    {
      title: '严重程度',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (v: string) => {
        const map: Record<string, string> = { critical: 'red', warning: 'orange', info: 'blue' };
        return <Tag color={map[v] || 'default'}>{v}</Tag>;
      },
    },
    {
      title: '通道',
      dataIndex: 'channel',
      key: 'channel',
      width: 110,
      render: (v: string) => CHANNELS.find((c) => c.value === v)?.label || v,
    },
    {
      title: '状态',
      dataIndex: 'delivery_status',
      key: 'delivery_status',
      width: 100,
      render: (v: string) => {
        const opt = STATUSES.find((s) => s.value === v);
        return opt ? <Tag color={opt.color}>{opt.label}</Tag> : v;
      },
    },
    {
      title: '是否点击',
      dataIndex: 'clicked_at',
      key: 'clicked_at',
      width: 100,
      render: (v: string) => v ? <Tag color="purple">是</Tag> : <Tag>否</Tag>,
    },
  ];

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>推送记录查询</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => fetchData(1)}>刷新</Button>
          <Button type="primary" icon={<DownloadOutlined />} onClick={onExport}>导出 Excel</Button>
        </Space>
      </div>

      <Form form={form} layout="inline" style={{ marginBottom: 16 }}>
        <Form.Item name="dateRange" label="时间区间">
          <RangePicker showTime />
        </Form.Item>
        <Form.Item name="guardian_keyword" label="守护者">
          <Input placeholder="手机号/姓名" allowClear style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="member_keyword" label="被守护者">
          <Input placeholder="姓名/昵称" allowClear style={{ width: 160 }} />
        </Form.Item>
        <Form.Item name="channel" label="通道">
          <Select options={CHANNELS} allowClear style={{ width: 140 }} />
        </Form.Item>
        <Form.Item name="status" label="状态">
          <Select options={STATUSES.map((s) => ({ value: s.value, label: s.label }))} allowClear style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="clicked" label="是否点击">
          <Select
            allowClear
            options={[
              { value: true, label: '是' },
              { value: false, label: '否' },
            ]}
            style={{ width: 100 }}
          />
        </Form.Item>
        <Form.Item>
          <Button type="primary" icon={<SearchOutlined />} onClick={() => fetchData(1)}>查询</Button>
        </Form.Item>
      </Form>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: false,
          onChange: (p) => fetchData(p),
        }}
      />
    </Card>
  );
}
