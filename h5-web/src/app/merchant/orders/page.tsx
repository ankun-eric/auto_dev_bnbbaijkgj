'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Input, Space, Button, DatePicker, Tag, Typography, Modal, Upload, Form, InputNumber, message, Popconfirm, Select,
} from 'antd';
import { SearchOutlined, PaperClipOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import api from '@/lib/api';
import dayjs from 'dayjs';
import { getCurrentStoreId } from '../lib';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface OrderRow {
  order_id: number;
  order_no: string;
  user_display: string;
  product_name: string;
  created_at: string;
  appointment_time?: string;
  store_id?: number;
  store_name?: string;
  status: string;
  amount: number;
  attachment_count: number;
}

const statusMap: Record<string, { text: string; color: string }> = {
  pending_payment: { text: '待支付', color: 'orange' },
  paid: { text: '已支付', color: 'blue' },
  redeemed: { text: '已核销', color: 'green' },
  cancelled: { text: '已取消', color: 'default' },
  refunded: { text: '已退款', color: 'red' },
  completed: { text: '已完成', color: 'green' },
};

export default function OrdersPage() {
  const [rows, setRows] = useState<OrderRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  const [attachOpen, setAttachOpen] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<OrderRow | null>(null);
  const [attachments, setAttachments] = useState<any[]>([]);
  const [uploadForm] = Form.useForm();

  const load = useCallback(async (p: number = page) => {
    setLoading(true);
    try {
      const storeId = getCurrentStoreId();
      const params: any = {
        page: p,
        page_size: 20,
        keyword: keyword || undefined,
        status: status || undefined,
      };
      if (storeId) params.store_id = storeId;
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD');
        params.end_date = dateRange[1].format('YYYY-MM-DD');
      }
      const res: any = await api.get('/api/merchant/v1/orders', { params });
      setRows(res.items || []);
      setTotal(res.total || 0);
      setPage(p);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, status, dateRange, page]);

  useEffect(() => { load(1); }, []); // eslint-disable-line

  const openAttach = async (row: OrderRow) => {
    setCurrentOrder(row);
    setAttachOpen(true);
    try {
      const res: any = await api.get(`/api/merchant/v1/orders/${row.order_id}/attachments`);
      setAttachments(res || []);
    } catch { setAttachments([]); }
  };

  const doUpload = async (values: any) => {
    if (!currentOrder) return;
    try {
      await api.post(`/api/merchant/v1/orders/${currentOrder.order_id}/attachments`, {
        file_url: values.file_url,
        file_name: values.file_name,
        file_type: values.file_type,
        file_size: values.file_size || 0,
      });
      message.success('附件已上传');
      uploadForm.resetFields();
      openAttach(currentOrder);
      load(page);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
    }
  };

  const deleteAttach = async (attId: number) => {
    if (!currentOrder) return;
    try {
      await api.delete(`/api/merchant/v1/orders/${currentOrder.order_id}/attachments/${attId}`);
      message.success('已删除');
      openAttach(currentOrder);
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败'); }
  };

  const columns = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 180 },
    { title: '用户', dataIndex: 'user_display', key: 'user_display', width: 130 },
    { title: '商品', dataIndex: 'product_name', key: 'product_name' },
    { title: '下单时间', dataIndex: 'created_at', key: 'created_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
    { title: '门店', dataIndex: 'store_name', key: 'store_name', width: 140 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={statusMap[s]?.color || 'default'}>{statusMap[s]?.text || s}</Tag>,
    },
    { title: '金额', dataIndex: 'amount', key: 'amount', width: 90, render: (v: number) => `¥${v || 0}` },
    { title: '附件', dataIndex: 'attachment_count', key: 'attachment_count', width: 70 },
    {
      title: '操作', key: 'ops', width: 140,
      render: (_: any, row: OrderRow) => (
        <Space>
          <Button size="small" icon={<PaperClipOutlined />} onClick={() => openAttach(row)}>附件</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>订单管理</Title>
      <Space wrap style={{ marginBottom: 16 }}>
        <Input
          placeholder="订单号/商品名"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="状态"
          value={status}
          onChange={setStatus}
          style={{ width: 120 }}
          allowClear
          options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.text }))}
        />
        <RangePicker value={dateRange as any} onChange={v => setDateRange(v as any)} />
        <Button type="primary" onClick={() => load(1)}>查询</Button>
      </Space>
      <Table
        rowKey="order_id"
        loading={loading}
        dataSource={rows}
        columns={columns as any}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: p => load(p),
          showSizeChanger: false,
        }}
      />

      <Modal
        title={`订单附件 - ${currentOrder?.order_no || ''}`}
        open={attachOpen}
        onCancel={() => setAttachOpen(false)}
        footer={null}
        width={720}
      >
        <Table
          size="small"
          rowKey="id"
          dataSource={attachments}
          pagination={false}
          columns={[
            { title: '文件名', dataIndex: 'file_name' },
            { title: '类型', dataIndex: 'file_type', width: 80 },
            { title: '大小', dataIndex: 'file_size', width: 100, render: (v: number) => v ? `${(v / 1024).toFixed(1)}KB` : '-' },
            { title: '上传时间', dataIndex: 'created_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            {
              title: '操作', width: 160, render: (_: any, att: any) => (
                <Space>
                  <a href={att.file_url} target="_blank" rel="noreferrer"><DownloadOutlined /> 下载</a>
                  <Popconfirm title="确定删除?" onConfirm={() => deleteAttach(att.id)}>
                    <a>删除</a>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
        <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 8 }}>
          <Typography.Text strong>上传附件（单文件≤20MB，最多 5 个）</Typography.Text>
          <Form form={uploadForm} layout="vertical" onFinish={doUpload} style={{ marginTop: 12 }}>
            <Form.Item name="file_url" label="文件URL" rules={[{ required: true, message: '请输入文件URL' }]}>
              <Input placeholder="上传到OSS后粘贴URL，或使用对接的上传组件" />
            </Form.Item>
            <Space>
              <Form.Item name="file_name" label="文件名" rules={[{ required: true }]}>
                <Input placeholder="report.pdf" />
              </Form.Item>
              <Form.Item name="file_type" label="类型" rules={[{ required: true }]} initialValue="pdf">
                <Select style={{ width: 120 }} options={[{ value: 'image', label: '图片' }, { value: 'pdf', label: 'PDF' }]} />
              </Form.Item>
              <Form.Item name="file_size" label="大小(字节)">
                <InputNumber min={0} max={20 * 1024 * 1024} />
              </Form.Item>
            </Space>
            <Button type="primary" htmlType="submit" icon={<UploadOutlined />}>提交附件</Button>
          </Form>
        </div>
      </Modal>
    </div>
  );
}
