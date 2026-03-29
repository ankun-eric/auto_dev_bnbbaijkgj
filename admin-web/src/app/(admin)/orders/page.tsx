'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Tabs, Tag, message, Typography, Descriptions } from 'antd';
import { EyeOutlined, RollbackOutlined, SearchOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface OrderRecord {
  orderId: number;
  orderNo: string;
  userId: number;
  userName: string;
  serviceName: string;
  amount: number;
  status: string;
  payMethod: string;
  remark: string;
  createdAt: string;
}

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待支付' },
  paid: { color: 'blue', text: '已支付' },
  processing: { color: 'cyan', text: '服务中' },
  completed: { color: 'green', text: '已完成' },
  refunded: { color: 'red', text: '已退款' },
  cancelled: { color: 'default', text: '已取消' },
};

const payMethodMap: Record<string, string> = {
  wechat: '微信支付',
  alipay: '支付宝',
  balance: '余额支付',
};

function deriveStatus(item: Record<string, unknown>): string {
  const ps = String(item.payment_status ?? '');
  const os = String(item.order_status ?? '');
  if (ps === 'refunded') return 'refunded';
  if (os === 'completed') return 'completed';
  if (os === 'cancelled') return 'cancelled';
  if (os === 'processing' || os === 'confirmed') return 'processing';
  if (ps === 'paid') return 'paid';
  return 'pending';
}

function mapOrder(item: Record<string, unknown>): OrderRecord {
  return {
    orderId: Number(item.id ?? 0),
    orderNo: String(item.order_no ?? ''),
    userId: Number(item.user_id ?? 0),
    userName: `用户#${item.user_id}`,
    serviceName: `服务#${item.service_item_id}`,
    amount: Number(item.total_amount ?? 0),
    status: deriveStatus(item),
    payMethod: payMethodMap[String(item.payment_method ?? '')] || String(item.payment_method ?? '-'),
    remark: String(item.notes ?? ''),
    createdAt: String(item.created_at ?? ''),
  };
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [detailVisible, setDetailVisible] = useState(false);
  const [refundVisible, setRefundVisible] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<OrderRecord | null>(null);
  const [refundForm] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;
      if (activeTab !== 'all') {
        if (activeTab === 'paid' || activeTab === 'refunded') {
          params.payment_status = activeTab;
        } else {
          params.order_status = activeTab;
        }
      }
      const res = await get('/api/admin/orders', params);
      if (res) {
        const raw = res.items || res.list || res;
        const items = Array.isArray(raw) ? raw.map((r: Record<string, unknown>) => mapOrder(r)) : [];
        setOrders(items);
        setPagination((prev) => ({ ...prev, current: page, total: res.total ?? items.length }));
      }
    } catch {
      setOrders([]);
      setPagination((prev) => ({ ...prev, current: page, total: 0 }));
      message.error('加载订单数据失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRefund = async () => {
    if (!currentOrder) return;
    try {
      const values = await refundForm.validateFields();
      await put(`/api/admin/orders/${currentOrder.orderId}/refund`);
      message.success('退款处理成功');
      setRefundVisible(false);
      refundForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('退款处理失败');
    }
  };

  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'pending', label: '待支付' },
    { key: 'paid', label: '已支付' },
    { key: 'processing', label: '服务中' },
    { key: 'completed', label: '已完成' },
    { key: 'refunded', label: '已退款' },
  ];

  const columns = [
    { title: '订单号', dataIndex: 'orderNo', key: 'orderNo', width: 170 },
    { title: '用户', dataIndex: 'userName', key: 'userName', width: 100 },
    { title: '服务', dataIndex: 'serviceName', key: 'serviceName', width: 150 },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{(v ?? 0).toFixed(2)}</span>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: string) => {
        const s = statusMap[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '下单时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: unknown, record: OrderRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentOrder(record); setDetailVisible(true); }}>
            详情
          </Button>
          {record.status === 'paid' && (
            <Button type="link" size="small" danger icon={<RollbackOutlined />} onClick={() => { setCurrentOrder(record); setRefundVisible(true); refundForm.resetFields(); }}>
              退款
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>订单管理</Title>

      <Space style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索订单号"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          onPressEnter={() => fetchData(1)}
          style={{ width: 250 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchData(1)}>搜索</Button>
      </Space>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => { setActiveTab(key); setTimeout(() => fetchData(1), 0); }}
        items={tabItems}
      />

      <Table
        columns={columns}
        dataSource={orders}
        rowKey="orderId"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1000 }}
      />

      <Modal title="订单详情" open={detailVisible} onCancel={() => setDetailVisible(false)} footer={null} width={640}>
        {currentOrder && (
          <Descriptions column={2} bordered size="small" style={{ marginTop: 16 }}>
            <Descriptions.Item label="订单号">{currentOrder.orderNo}</Descriptions.Item>
            <Descriptions.Item label="用户">{currentOrder.userName}</Descriptions.Item>
            <Descriptions.Item label="金额"><span style={{ color: '#f5222d' }}>¥{(currentOrder.amount ?? 0).toFixed(2)}</span></Descriptions.Item>
            <Descriptions.Item label="支付方式">{currentOrder.payMethod || '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusMap[currentOrder.status]?.color}>{statusMap[currentOrder.status]?.text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="下单时间">{currentOrder.createdAt ? dayjs(currentOrder.createdAt).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
            <Descriptions.Item label="备注" span={2}>{currentOrder.remark || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal title="退款处理" open={refundVisible} onOk={handleRefund} onCancel={() => setRefundVisible(false)} destroyOnClose>
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
            <div>订单号: {currentOrder.orderNo}</div>
            <div>金额: ¥{(currentOrder.amount ?? 0).toFixed(2)}</div>
            <div>用户: {currentOrder.userName}</div>
          </div>
        )}
        <Form form={refundForm} layout="vertical">
          <Form.Item label="退款原因" name="reason" rules={[{ required: true, message: '请输入退款原因' }]}>
            <TextArea rows={3} placeholder="请输入退款原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
