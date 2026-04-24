'use client';

import React, { useEffect, useState } from 'react';
import { Table, Typography, Button, Space, Select, DatePicker, Form, Modal, message, Tag } from 'antd';
import api from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

const basePath = typeof process !== 'undefined' ? process.env.NEXT_PUBLIC_BASE_PATH || '' : '';

const statusMap: Record<string, { text: string; color: string }> = {
  queued: { text: '排队中', color: 'blue' },
  running: { text: '处理中', color: 'processing' },
  done: { text: '已完成', color: 'green' },
  completed: { text: '已完成', color: 'green' },
  failed: { text: '失败', color: 'red' },
};

const typeNames: Record<string, string> = {
  orders: '订单列表',
  verifications: '核销记录',
  settlements: '对账明细',
  reports: '报表数据',
};

export default function DownloadsPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/exports');
      setRows(res || []);
    } catch (e: any) { message.error(e?.response?.data?.detail || '加载失败'); } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const create = async (values: any) => {
    try {
      const [start, end] = values.range || [];
      if (start && end && end.diff(start, 'day') > 366) {
        message.error('单次导出范围最多 1 年');
        return;
      }
      await api.post('/api/merchant/v1/exports', {
        task_type: values.task_type,
        task_name: `${typeNames[values.task_type] || values.task_type}_${start?.format('YYYYMMDD')}-${end?.format('YYYYMMDD')}`,
        start_date: start?.format('YYYY-MM-DD'),
        end_date: end?.format('YYYY-MM-DD'),
      });
      message.success('任务已创建');
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) { message.error(e?.response?.data?.detail || '创建失败'); }
  };

  return (
    <div>
      <Title level={4}>下载中心</Title>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => setOpen(true)}>新建导出</Button>
        <Button onClick={load}>刷新</Button>
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: '任务名', dataIndex: 'task_name' },
          { title: '类型', dataIndex: 'task_type', render: (v: string) => typeNames[v] || v },
          { title: '创建时间', dataIndex: 'created_at', render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
          { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={statusMap[v]?.color}>{statusMap[v]?.text || v}</Tag> },
          {
            title: '操作',
            render: (_: any, row: any) => (row.status === 'done' || row.status === 'completed') && row.file_url ? (
              <a href={`${basePath}${row.file_url}`} target="_blank" rel="noreferrer">下载</a>
            ) : '-',
          },
        ] as any}
      />

      <Modal title="新建导出任务" open={open} onCancel={() => setOpen(false)} onOk={() => form.submit()}>
        <Form form={form} layout="vertical" onFinish={create}>
          <Form.Item name="task_type" label="类型" rules={[{ required: true }]} initialValue="orders">
            <Select
              options={[
                { label: '订单列表', value: 'orders' },
                { label: '核销记录', value: 'verifications' },
                { label: '对账明细', value: 'settlements' },
                { label: '报表数据', value: 'reports' },
              ]}
            />
          </Form.Item>
          <Form.Item name="range" label="时间范围（≤1 年）" rules={[{ required: true }]}>
            <RangePicker />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
