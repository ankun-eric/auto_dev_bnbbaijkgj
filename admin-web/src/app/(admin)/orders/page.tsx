'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, InputNumber, Tabs, Tag, message, Typography, Descriptions, Popconfirm } from 'antd';
import { EyeOutlined, RollbackOutlined, SearchOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface OrderRecord {
  id: string;
  userId: number;
  userName: string;
  userPhone: string;
  serviceName: string;
  amount: number;
  status: string;
  payMethod: string;
  remark: string;
  createdAt: string;
  paidAt?: string;
  completedAt?: string;
}

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待支付' },
  paid: { color: 'blue', text: '已支付' },
  processing: { color: 'cyan', text: '服务中' },
  completed: { color: 'green', text: '已完成' },
  refunding: { color: 'gold', text: '退款中' },
  refunded: { color: 'red', text: '已退款' },
  cancelled: { color: 'default', text: '已取消' },
};

const mockOrders: OrderRecord[] = [
  { id: 'ORD20260327001', userId: 1, userName: '张三', userPhone: '138****1234', serviceName: 'AI智能问诊', amount: 9.9, status: 'paid', payMethod: '微信支付', remark: '', createdAt: '2026-03-27 10:30:00', paidAt: '2026-03-27 10:31:00' },
  { id: 'ORD20260327002', userId: 2, userName: '李四', userPhone: '139****5678', serviceName: '个性化营养方案', amount: 299, status: 'completed', payMethod: '支付宝', remark: '', createdAt: '2026-03-27 09:15:00', paidAt: '2026-03-27 09:16:00', completedAt: '2026-03-27 11:00:00' },
  { id: 'ORD20260327003', userId: 3, userName: '王五', userPhone: '137****9012', serviceName: '体检报告解读', amount: 49, status: 'paid', payMethod: '微信支付', remark: '', createdAt: '2026-03-27 08:42:00', paidAt: '2026-03-27 08:43:00' },
  { id: 'ORD20260326004', userId: 4, userName: '赵六', userPhone: '136****3456', serviceName: '中医体质辨识', amount: 199, status: 'refunded', payMethod: '微信支付', remark: '用户申请退款', createdAt: '2026-03-26 18:20:00', paidAt: '2026-03-26 18:21:00' },
  { id: 'ORD20260326005', userId: 5, userName: '孙七', userPhone: '135****7890', serviceName: '心理健康评估', amount: 149, status: 'completed', payMethod: '支付宝', remark: '', createdAt: '2026-03-26 16:05:00', paidAt: '2026-03-26 16:06:00', completedAt: '2026-03-26 18:30:00' },
  { id: 'ORD20260326006', userId: 6, userName: '周八', userPhone: '188****2345', serviceName: '深度健康咨询', amount: 99, status: 'pending', payMethod: '', remark: '', createdAt: '2026-03-26 14:00:00' },
  { id: 'ORD20260325007', userId: 7, userName: '吴九', userPhone: '199****6789', serviceName: 'AI智能问诊', amount: 9.9, status: 'refunding', payMethod: '微信支付', remark: '服务未响应', createdAt: '2026-03-25 20:10:00', paidAt: '2026-03-25 20:11:00' },
  { id: 'ORD20260325008', userId: 8, userName: '郑十', userPhone: '177****0123', serviceName: '个性化营养方案', amount: 299, status: 'processing', payMethod: '支付宝', remark: '', createdAt: '2026-03-25 15:30:00', paidAt: '2026-03-25 15:31:00' },
];

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderRecord[]>(mockOrders);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockOrders.length });
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
      const res = await get('/api/admin/orders', { page, pageSize, status: activeTab === 'all' ? '' : activeTab, search: searchText });
      if (res.code === 0 && res.data) {
        setOrders(res.data.list || res.data);
        setPagination((prev) => ({ ...prev, current: page, total: res.data.total || res.data.length }));
      }
    } catch {
      let filtered = mockOrders;
      if (activeTab !== 'all') filtered = filtered.filter((o) => o.status === activeTab);
      if (searchText) filtered = filtered.filter((o) => o.id.includes(searchText) || o.userName.includes(searchText));
      setOrders(filtered);
      setPagination((prev) => ({ ...prev, current: page, total: filtered.length }));
    } finally {
      setLoading(false);
    }
  };

  const handleRefund = async () => {
    try {
      const values = await refundForm.validateFields();
      try {
        await post(`/api/admin/orders/${currentOrder?.id}/refund`, values);
      } catch {}
      setOrders((prev) => prev.map((o) => (o.id === currentOrder?.id ? { ...o, status: 'refunded', remark: values.reason } : o)));
      message.success('退款处理成功');
      setRefundVisible(false);
      refundForm.resetFields();
    } catch {}
  };

  const tabItems = [
    { key: 'all', label: `全部 (${mockOrders.length})` },
    { key: 'pending', label: `待支付 (${mockOrders.filter((o) => o.status === 'pending').length})` },
    { key: 'paid', label: `已支付 (${mockOrders.filter((o) => o.status === 'paid').length})` },
    { key: 'processing', label: `服务中 (${mockOrders.filter((o) => o.status === 'processing').length})` },
    { key: 'completed', label: `已完成 (${mockOrders.filter((o) => o.status === 'completed').length})` },
    { key: 'refunding', label: `退款中 (${mockOrders.filter((o) => o.status === 'refunding').length})` },
    { key: 'refunded', label: `已退款 (${mockOrders.filter((o) => o.status === 'refunded').length})` },
  ];

  const columns = [
    { title: '订单号', dataIndex: 'id', key: 'id', width: 170 },
    { title: '用户', dataIndex: 'userName', key: 'userName', width: 80 },
    { title: '服务', dataIndex: 'serviceName', key: 'serviceName', width: 150 },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v.toFixed(2)}</span>,
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
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: OrderRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentOrder(record); setDetailVisible(true); }}>
            详情
          </Button>
          {(record.status === 'paid' || record.status === 'refunding') && (
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
          placeholder="搜索订单号/用户"
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
        rowKey="id"
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
            <Descriptions.Item label="订单号">{currentOrder.id}</Descriptions.Item>
            <Descriptions.Item label="用户">{currentOrder.userName}</Descriptions.Item>
            <Descriptions.Item label="手机号">{currentOrder.userPhone}</Descriptions.Item>
            <Descriptions.Item label="服务">{currentOrder.serviceName}</Descriptions.Item>
            <Descriptions.Item label="金额"><span style={{ color: '#f5222d' }}>¥{currentOrder.amount.toFixed(2)}</span></Descriptions.Item>
            <Descriptions.Item label="支付方式">{currentOrder.payMethod || '-'}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusMap[currentOrder.status]?.color}>{statusMap[currentOrder.status]?.text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="下单时间">{dayjs(currentOrder.createdAt).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
            {currentOrder.paidAt && <Descriptions.Item label="支付时间">{dayjs(currentOrder.paidAt).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>}
            {currentOrder.completedAt && <Descriptions.Item label="完成时间">{dayjs(currentOrder.completedAt).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>}
            <Descriptions.Item label="备注" span={2}>{currentOrder.remark || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      <Modal title="退款处理" open={refundVisible} onOk={handleRefund} onCancel={() => setRefundVisible(false)} destroyOnClose>
        <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
          <div>订单号: {currentOrder?.id}</div>
          <div>金额: ¥{currentOrder?.amount.toFixed(2)}</div>
          <div>用户: {currentOrder?.userName}</div>
        </div>
        <Form form={refundForm} layout="vertical">
          <Form.Item label="退款原因" name="reason" rules={[{ required: true, message: '请输入退款原因' }]}>
            <TextArea rows={3} placeholder="请输入退款原因" />
          </Form.Item>
          <Form.Item label="退款金额" name="refundAmount" initialValue={currentOrder?.amount}>
            <InputNumber min={0} max={currentOrder?.amount} style={{ width: '100%' }} prefix="¥" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
