'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Tabs, Tag, message,
  Typography, Descriptions, Drawer, Popconfirm, Row, Col,
} from 'antd';
import {
  EyeOutlined, SearchOutlined, SendOutlined,
  CheckOutlined, CloseOutlined,
} from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface OrderItem {
  id: number;
  product_id: number;
  product_name: string;
  product_image: string | null;
  product_price: number;
  quantity: number;
  subtotal: number;
  fulfillment_type: string;
  verification_code: string | null;
  total_redeem_count: number;
  used_redeem_count: number;
}

interface UnifiedOrder {
  id: number;
  order_no: string;
  user_id: number;
  total_amount: number;
  paid_amount: number;
  points_deduction: number;
  payment_method: string | null;
  coupon_id: number | null;
  coupon_discount: number;
  status: string;
  refund_status: string;
  shipping_info: any;
  tracking_number: string | null;
  tracking_company: string | null;
  notes: string | null;
  paid_at: string | null;
  shipped_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

const orderStatusMap: Record<string, { color: string; text: string }> = {
  pending_payment: { color: 'orange', text: '待付款' },
  pending_shipment: { color: 'blue', text: '待发货' },
  pending_receipt: { color: 'cyan', text: '待收货' },
  pending_use: { color: 'geekblue', text: '待使用' },
  pending_review: { color: 'purple', text: '待评价' },
  completed: { color: 'green', text: '已完成' },
  cancelled: { color: 'default', text: '已取消' },
};

const refundStatusMap: Record<string, { color: string; text: string }> = {
  none: { color: 'default', text: '无' },
  applied: { color: 'orange', text: '退款申请中' },
  approved: { color: 'green', text: '退款已批准' },
  rejected: { color: 'red', text: '退款已拒绝' },
};

const fulfillmentMap: Record<string, string> = {
  in_store: '到店',
  delivery: '快递',
  virtual: '虚拟',
};

const payMethodMap: Record<string, string> = {
  wechat: '微信支付',
  alipay: '支付宝',
  balance: '余额支付',
  points: '积分兑换',
};

function mapOrder(raw: Record<string, unknown>): UnifiedOrder {
  const items = Array.isArray(raw.items)
    ? raw.items.map((it: any) => ({
        id: Number(it.id),
        product_id: Number(it.product_id),
        product_name: String(it.product_name ?? ''),
        product_image: it.product_image ? String(it.product_image) : null,
        product_price: Number(it.product_price ?? 0),
        quantity: Number(it.quantity ?? 1),
        subtotal: Number(it.subtotal ?? 0),
        fulfillment_type: String(it.fulfillment_type ?? ''),
        verification_code: it.verification_code ? String(it.verification_code) : null,
        total_redeem_count: Number(it.total_redeem_count ?? 0),
        used_redeem_count: Number(it.used_redeem_count ?? 0),
      }))
    : [];

  return {
    id: Number(raw.id),
    order_no: String(raw.order_no ?? ''),
    user_id: Number(raw.user_id ?? 0),
    total_amount: Number(raw.total_amount ?? 0),
    paid_amount: Number(raw.paid_amount ?? 0),
    points_deduction: Number(raw.points_deduction ?? 0),
    payment_method: raw.payment_method ? String(raw.payment_method) : null,
    coupon_id: raw.coupon_id ? Number(raw.coupon_id) : null,
    coupon_discount: Number(raw.coupon_discount ?? 0),
    status: String(raw.status ?? ''),
    refund_status: String(raw.refund_status ?? 'none'),
    shipping_info: raw.shipping_info,
    tracking_number: raw.tracking_number ? String(raw.tracking_number) : null,
    tracking_company: raw.tracking_company ? String(raw.tracking_company) : null,
    notes: raw.notes ? String(raw.notes) : null,
    paid_at: raw.paid_at ? String(raw.paid_at) : null,
    shipped_at: raw.shipped_at ? String(raw.shipped_at) : null,
    completed_at: raw.completed_at ? String(raw.completed_at) : null,
    cancelled_at: raw.cancelled_at ? String(raw.cancelled_at) : null,
    cancel_reason: raw.cancel_reason ? String(raw.cancel_reason) : null,
    items,
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
  };
}

export default function UnifiedOrdersPage() {
  const [orders, setOrders] = useState<UnifiedOrder[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  const [drawerVisible, setDrawerVisible] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<UnifiedOrder | null>(null);

  const [shipVisible, setShipVisible] = useState(false);
  const [shipForm] = Form.useForm();

  const [refundApproveVisible, setRefundApproveVisible] = useState(false);
  const [refundRejectVisible, setRefundRejectVisible] = useState(false);
  const [refundForm] = Form.useForm();

  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;

      const tab = activeTabRef.current;
      if (tab === 'refund') {
        params.refund_status = 'applied';
      } else if (tab !== 'all') {
        params.status = tab;
      }

      const res = await get('/api/admin/orders/unified', params);
      if (res) {
        const raw = res.items || res.list || res;
        const items = Array.isArray(raw) ? raw.map((r: Record<string, unknown>) => mapOrder(r)) : [];
        setOrders(items);
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? items.length }));
      }
    } catch {
      setOrders([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载订单失败');
    } finally {
      setLoading(false);
    }
  }, [searchText]);

  useEffect(() => {
    fetchData(1, pagination.pageSize);
  }, [activeTab]);

  const handleShip = async () => {
    if (!currentOrder) return;
    try {
      const values = await shipForm.validateFields();
      await post(`/api/admin/orders/unified/${currentOrder.id}/ship`, {
        tracking_company: values.tracking_company,
        tracking_number: values.tracking_number,
      });
      message.success('发货成功');
      setShipVisible(false);
      shipForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '发货失败');
    }
  };

  const handleRefundApprove = async () => {
    if (!currentOrder) return;
    try {
      const values = await refundForm.validateFields();
      await post(`/api/admin/orders/unified/${currentOrder.id}/refund/approve`, {
        admin_notes: values.admin_notes || '',
      });
      message.success('退款已批准');
      setRefundApproveVisible(false);
      refundForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleRefundReject = async () => {
    if (!currentOrder) return;
    try {
      const values = await refundForm.validateFields();
      await post(`/api/admin/orders/unified/${currentOrder.id}/refund/reject`, {
        admin_notes: values.admin_notes || '',
      });
      message.success('退款已拒绝');
      setRefundRejectVisible(false);
      refundForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'pending_payment', label: '待付款' },
    { key: 'pending_shipment', label: '待发货' },
    { key: 'pending_receipt', label: '待收货' },
    { key: 'pending_use', label: '待使用' },
    { key: 'completed', label: '已完成' },
    { key: 'cancelled', label: '已取消' },
    { key: 'refund', label: '退款申请' },
  ];

  const columns = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 200 },
    { title: '用户ID', dataIndex: 'user_id', key: 'user_id', width: 80 },
    {
      title: '商品', key: 'products', width: 200, ellipsis: true,
      render: (_: unknown, record: UnifiedOrder) =>
        record.items.map(it => it.product_name).join(', ') || '-',
    },
    {
      title: '总金额', dataIndex: 'total_amount', key: 'total_amount', width: 100,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{(v ?? 0).toFixed(2)}</span>,
    },
    {
      title: '实付', dataIndex: 'paid_amount', key: 'paid_amount', width: 100,
      render: (v: number) => <span>¥{(v ?? 0).toFixed(2)}</span>,
    },
    {
      title: '订单状态', key: 'status', width: 100,
      render: (_: unknown, record: UnifiedOrder) => {
        const s = orderStatusMap[record.status] || { color: 'default', text: record.status };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '退款状态', dataIndex: 'refund_status', key: 'refund_status', width: 110,
      render: (v: string) => {
        if (v === 'none') return '-';
        const s = refundStatusMap[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '下单时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作', key: 'action', width: 260, fixed: 'right' as const,
      render: (_: unknown, record: UnifiedOrder) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentOrder(record); setDrawerVisible(true); }}>详情</Button>
          {record.status === 'pending_shipment' && (
            <Button type="link" size="small" icon={<SendOutlined />}
              onClick={() => { setCurrentOrder(record); shipForm.resetFields(); setShipVisible(true); }}>
              发货
            </Button>
          )}
          {record.refund_status === 'applied' && (
            <>
              <Button type="link" size="small" icon={<CheckOutlined />} style={{ color: '#52c41a' }}
                onClick={() => { setCurrentOrder(record); refundForm.resetFields(); setRefundApproveVisible(true); }}>
                批准退款
              </Button>
              <Button type="link" size="small" danger icon={<CloseOutlined />}
                onClick={() => { setCurrentOrder(record); refundForm.resetFields(); setRefundRejectVisible(true); }}>
                拒绝退款
              </Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>统一订单管理</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索订单号"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          onPressEnter={() => fetchData(1, pagination.pageSize)}
          style={{ width: 280 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchData(1, pagination.pageSize)}>搜索</Button>
      </Space>

      <Tabs
        activeKey={activeTab}
        onChange={key => setActiveTab(key)}
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
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1400 }}
      />

      {/* 订单详情 Drawer */}
      <Drawer
        title="订单详情"
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        width={640}
      >
        {currentOrder && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="订单号">{currentOrder.order_no}</Descriptions.Item>
              <Descriptions.Item label="用户ID">{currentOrder.user_id}</Descriptions.Item>
              <Descriptions.Item label="总金额"><span style={{ color: '#f5222d' }}>¥{(currentOrder.total_amount ?? 0).toFixed(2)}</span></Descriptions.Item>
              <Descriptions.Item label="实付金额">¥{(currentOrder.paid_amount ?? 0).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="积分抵扣">{currentOrder.points_deduction}</Descriptions.Item>
              <Descriptions.Item label="优惠券抵扣">¥{(currentOrder.coupon_discount ?? 0).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="支付方式">{currentOrder.payment_method ? (payMethodMap[currentOrder.payment_method] || currentOrder.payment_method) : '-'}</Descriptions.Item>
              <Descriptions.Item label="订单状态">
                {(() => { const s = orderStatusMap[currentOrder.status] || { color: 'default', text: currentOrder.status }; return <Tag color={s.color}>{s.text}</Tag>; })()}
              </Descriptions.Item>
              <Descriptions.Item label="退款状态">
                {(() => { const s = refundStatusMap[currentOrder.refund_status] || { color: 'default', text: currentOrder.refund_status }; return <Tag color={s.color}>{s.text}</Tag>; })()}
              </Descriptions.Item>
              <Descriptions.Item label="下单时间">{currentOrder.created_at ? dayjs(currentOrder.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
              {currentOrder.paid_at && <Descriptions.Item label="支付时间">{dayjs(currentOrder.paid_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>}
              {currentOrder.shipped_at && <Descriptions.Item label="发货时间">{dayjs(currentOrder.shipped_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>}
              {currentOrder.tracking_company && <Descriptions.Item label="快递公司">{currentOrder.tracking_company}</Descriptions.Item>}
              {currentOrder.tracking_number && <Descriptions.Item label="快递单号">{currentOrder.tracking_number}</Descriptions.Item>}
              {currentOrder.cancel_reason && <Descriptions.Item label="取消原因" span={2}>{currentOrder.cancel_reason}</Descriptions.Item>}
              <Descriptions.Item label="备注" span={2}>{currentOrder.notes || '-'}</Descriptions.Item>
            </Descriptions>

            <Title level={5} style={{ marginTop: 24, marginBottom: 12 }}>商品明细</Title>
            <Table
              dataSource={currentOrder.items}
              rowKey="id"
              pagination={false}
              size="small"
              columns={[
                {
                  title: '商品', key: 'product', width: 200,
                  render: (_: unknown, item: OrderItem) => (
                    <Space>
                      {item.product_image && <img src={item.product_image} alt="" style={{ width: 32, height: 32, objectFit: 'cover', borderRadius: 4 }} />}
                      {item.product_name}
                    </Space>
                  ),
                },
                { title: '单价', dataIndex: 'product_price', key: 'product_price', width: 80, render: (v: number) => `¥${v}` },
                { title: '数量', dataIndex: 'quantity', key: 'quantity', width: 60 },
                { title: '小计', dataIndex: 'subtotal', key: 'subtotal', width: 80, render: (v: number) => `¥${v}` },
                { title: '类型', dataIndex: 'fulfillment_type', key: 'fulfillment_type', width: 70, render: (v: string) => fulfillmentMap[v] || v },
                {
                  title: '核销', key: 'redeem', width: 100,
                  render: (_: unknown, item: OrderItem) => item.verification_code
                    ? <span>{item.used_redeem_count}/{item.total_redeem_count}</span>
                    : '-',
                },
              ]}
            />
          </>
        )}
      </Drawer>

      {/* 发货弹窗 */}
      <Modal
        title="发货"
        open={shipVisible}
        onOk={handleShip}
        onCancel={() => setShipVisible(false)}
        destroyOnClose
      >
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#e6f7ff', borderRadius: 8 }}>
            <div>订单号: {currentOrder.order_no}</div>
            <div>金额: ¥{(currentOrder.paid_amount ?? 0).toFixed(2)}</div>
          </div>
        )}
        <Form form={shipForm} layout="vertical">
          <Form.Item label="快递公司" name="tracking_company" rules={[{ required: true, message: '请输入快递公司' }]}>
            <Input placeholder="如：顺丰速运、中通快递" />
          </Form.Item>
          <Form.Item label="快递单号" name="tracking_number" rules={[{ required: true, message: '请输入快递单号' }]}>
            <Input placeholder="请输入快递单号" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批准退款弹窗 */}
      <Modal
        title="批准退款"
        open={refundApproveVisible}
        onOk={handleRefundApprove}
        onCancel={() => setRefundApproveVisible(false)}
        destroyOnClose
      >
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
            <div>订单号: {currentOrder.order_no}</div>
            <div>实付: ¥{(currentOrder.paid_amount ?? 0).toFixed(2)}</div>
          </div>
        )}
        <Form form={refundForm} layout="vertical">
          <Form.Item label="审核备注" name="admin_notes">
            <TextArea rows={3} placeholder="请输入审核备注（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 拒绝退款弹窗 */}
      <Modal
        title="拒绝退款"
        open={refundRejectVisible}
        onOk={handleRefundReject}
        onCancel={() => setRefundRejectVisible(false)}
        destroyOnClose
      >
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#fff7e6', borderRadius: 8 }}>
            <div>订单号: {currentOrder.order_no}</div>
            <div>实付: ¥{(currentOrder.paid_amount ?? 0).toFixed(2)}</div>
          </div>
        )}
        <Form form={refundForm} layout="vertical">
          <Form.Item label="拒绝原因" name="admin_notes" rules={[{ required: true, message: '请输入拒绝原因' }]}>
            <TextArea rows={3} placeholder="请输入拒绝原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
