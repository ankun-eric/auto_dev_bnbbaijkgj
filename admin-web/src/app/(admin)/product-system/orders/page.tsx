'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Tabs, Tag, message,
  Typography, Descriptions, Drawer, Row, Col, Card, Statistic,
  DatePicker, Select, InputNumber, Alert, Spin,
} from 'antd';
import {
  EyeOutlined, SearchOutlined, SendOutlined,
  CheckOutlined, CloseOutlined, ShoppingCartOutlined,
  DollarOutlined, UndoOutlined,
} from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

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
  appointment_data: any | null;
  appointment_time: string | null;
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
  store_name: string | null;
  created_at: string;
  updated_at: string;
}

interface SalesStats {
  today_orders: number;
  today_revenue: number;
  today_refund_amount: number;
  month_orders: number;
  month_revenue: number;
  month_refund_amount: number;
}

// PRD V2「核销订单状态体系优化」: 12 状态完整枚举 + 中文标签 + Tag 颜色
const orderStatusMap: Record<string, { color: string; text: string }> = {
  pending_payment: { color: 'orange', text: '待付款' },
  pending_shipment: { color: 'blue', text: '待发货' },
  pending_receipt: { color: 'cyan', text: '待收货' },
  pending_appointment: { color: 'purple', text: '待预约' },
  appointed: { color: 'geekblue', text: '待核销' },
  pending_use: { color: 'geekblue', text: '待核销' },
  partial_used: { color: 'gold', text: '部分核销' },
  pending_review: { color: 'purple', text: '待评价（兼容）' },
  completed: { color: 'green', text: '已完成' },
  expired: { color: 'default', text: '已过期' },
  refunding: { color: 'red', text: '退款中' },
  refunded: { color: 'default', text: '已退款' },
  cancelled: { color: 'default', text: '已取消' },
};

// PRD「我的订单与售后状态体系优化」F-09：admin 退款明细列文案与逻辑状态保持一致
// 底层 refund_status 仍保留为审计字段，但展示对齐 4 个统一文案
const refundStatusMap: Record<string, { color: string; text: string }> = {
  none: { color: 'default', text: '无' },
  applied: { color: 'orange', text: '待审核' },
  reviewing: { color: 'orange', text: '待审核' },
  approved: { color: 'processing', text: '处理中' },
  returning: { color: 'processing', text: '处理中' },
  refund_success: { color: 'green', text: '已完成' },
  rejected: { color: 'red', text: '已驳回' },
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

// PRD V2: 12 状态完整筛选下拉
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending_payment', label: '待付款' },
  { value: 'pending_shipment', label: '待发货' },
  { value: 'pending_receipt', label: '待收货' },
  { value: 'pending_appointment', label: '待预约' },
  { value: 'pending_use', label: '待核销' },
  { value: 'partial_used', label: '部分核销' },
  { value: 'completed', label: '已完成' },
  { value: 'expired', label: '已过期' },
  { value: 'refunding', label: '退款中' },
  { value: 'refunded', label: '已退款' },
  { value: 'cancelled', label: '已取消' },
];

// PRD V2: 核销码 5 态独立筛选
const redemptionCodeStatusOptions = [
  { value: '', label: '全部核销码状态' },
  { value: 'active', label: '可核销' },
  { value: 'locked', label: '已锁定' },
  { value: 'used', label: '已核销' },
  { value: 'expired', label: '已过期' },
  { value: 'refunded', label: '已退款' },
];

const payMethodOptions = [
  { value: '', label: '全部支付方式' },
  { value: 'wechat', label: '微信支付' },
  { value: 'alipay', label: '支付宝' },
  { value: 'balance', label: '余额支付' },
  { value: 'points', label: '积分兑换' },
];

// PRD「我的订单与售后状态体系优化」F-09/F-10：
// admin 退款流程筛选 — 4 个统一逻辑状态，与客户端、H5 完全一致
// 待审核 / 处理中 / 已完成 / 已驳回
const refundStatusOptions = [
  { value: '', label: '全部售后' },
  { value: 'pending', label: '待审核' },
  { value: 'processing', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'rejected', label: '已驳回' },
];

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
        appointment_data: it.appointment_data ?? null,
        appointment_time: it.appointment_time ? String(it.appointment_time) : null,
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
    store_name: raw.store_name ? String(raw.store_name) : null,
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

  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPayMethod, setFilterPayMethod] = useState('');
  const [filterRefundStatus, setFilterRefundStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  // PRD V2: 核销码 5 态独立筛选
  const [filterRedemptionCodeStatus, setFilterRedemptionCodeStatus] = useState('');
  const [amountMin, setAmountMin] = useState<number | null>(null);
  const [amountMax, setAmountMax] = useState<number | null>(null);
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);

  const [statsData, setStatsData] = useState<SalesStats>({
    today_orders: 0, today_revenue: 0, today_refund_amount: 0,
    month_orders: 0, month_revenue: 0, month_refund_amount: 0,
  });

  const [drawerVisible, setDrawerVisible] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<UnifiedOrder | null>(null);

  const [shipVisible, setShipVisible] = useState(false);
  const [shipForm] = Form.useForm();

  const [refundApproveVisible, setRefundApproveVisible] = useState(false);
  const [refundRejectVisible, setRefundRejectVisible] = useState(false);
  const [refundForm] = Form.useForm();

  const [refundDetail, setRefundDetail] = useState<any>(null);
  const [refundDetailLoading, setRefundDetailLoading] = useState(false);

  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const fetchCategories = useCallback(async () => {
    try {
      const res = await get('/api/admin/products/categories');
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          setCategories(items.map((c: any) => ({ id: Number(c.id), name: String(c.name) })));
        }
      }
    } catch {}
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await get('/api/admin/statistics/sales');
      if (res) {
        setStatsData({
          today_orders: Number(res.today_orders ?? 0),
          today_revenue: Number(res.today_revenue ?? 0),
          today_refund_amount: Number(res.today_refund_amount ?? 0),
          month_orders: Number(res.month_orders ?? 0),
          month_revenue: Number(res.month_revenue ?? 0),
          month_refund_amount: Number(res.month_refund_amount ?? 0),
        });
      }
    } catch {}
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');
      if (filterStatus) params.status = filterStatus;
      if (filterPayMethod) params.payment_method = filterPayMethod;
      // PRD F-09：4 个统一逻辑值（pending/processing/completed/rejected）走新参数 aftersales_status
      if (filterRefundStatus) params.aftersales_status = filterRefundStatus;
      if (filterCategory) params.category_id = filterCategory;
      if (filterRedemptionCodeStatus) params.redemption_code_status = filterRedemptionCodeStatus;
      if (amountMin !== null) params.amount_min = amountMin;
      if (amountMax !== null) params.amount_max = amountMax;

      const tab = activeTabRef.current;
      // PRD F-09：admin 退款申请 Tab 改为按"待审核"逻辑筛选
      if (tab === 'refund') {
        params.aftersales_status = 'pending';
      } else if (tab === 'pending_review') {
        params.status = 'pending_review';
      } else if (tab === 'pending_use') {
        // [PRD 订单状态机简化方案 v1.0] 合并 appointed + pending_use 同时按预约日升序
        params.status = 'appointed,pending_use';
        params.sort_by = 'appointment_time';
        params.sort_order = 'asc';
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
  }, [searchText, dateRange, filterStatus, filterPayMethod, filterRefundStatus, filterCategory, filterRedemptionCodeStatus, amountMin, amountMax]);

  useEffect(() => {
    fetchCategories();
    fetchStats();
  }, []);

  useEffect(() => {
    fetchData(1, pagination.pageSize);
  }, [activeTab]);

  const handleSearch = () => {
    fetchData(1, pagination.pageSize);
  };

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
        refund_amount: values.refund_amount,
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

  const fetchRefundDetail = async (orderId: number) => {
    setRefundDetailLoading(true);
    try {
      const res = await get(`/api/admin/orders/unified/${orderId}/refund-detail`);
      setRefundDetail(res);
    } catch {
      setRefundDetail(null);
    } finally {
      setRefundDetailLoading(false);
    }
  };

  // PRD V2: admin 端按 12 状态完整展示，外加 "全部" / "退款申请" 工作流入口
  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'pending_payment', label: '待付款' },
    { key: 'pending_shipment', label: '待发货' },
    { key: 'pending_receipt', label: '待收货' },
    { key: 'pending_appointment', label: '待预约' },
    { key: 'pending_use', label: '待核销' },
    { key: 'partial_used', label: '部分核销' },
    { key: 'completed', label: '已完成' },
    { key: 'expired', label: '已过期' },
    { key: 'refunding', label: '退款中' },
    { key: 'refunded', label: '已退款' },
    { key: 'cancelled', label: '已取消' },
    { key: 'refund', label: '退款申请' },
  ];

  const renderStatusTag = (record: UnifiedOrder) => {
    if (record.status === 'cancelled' && record.refund_status === 'refund_success') {
      return <Tag color="default">已取消（已退款）</Tag>;
    }
    if (record.status === 'appointed' || record.status === 'pending_use') {
      // [PRD 订单状态机简化方案 v1.0] 待核销 Tag 文案带预约日期
      const apptItem = record.items?.find(it => it.appointment_time);
      const apptDate = apptItem?.appointment_time;
      if (apptDate) {
        const d = new Date(apptDate);
        return <Tag color="geekblue">{`待核销（预约 ${d.getMonth() + 1}月${d.getDate()}日）`}</Tag>;
      }
      return <Tag color="geekblue">待核销</Tag>;
    }
    const s = orderStatusMap[record.status] || { color: 'default', text: record.status };
    return <Tag color={s.color}>{s.text}</Tag>;
  };

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
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v ?? 0}</span>,
    },
    {
      title: '实付', dataIndex: 'paid_amount', key: 'paid_amount', width: 100,
      render: (v: number) => <span>¥{v ?? 0}</span>,
    },
    {
      title: '订单状态', key: 'status', width: 130,
      render: (_: unknown, record: UnifiedOrder) => renderStatusTag(record),
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
                onClick={() => { setCurrentOrder(record); refundForm.resetFields(); fetchRefundDetail(record.id); setRefundApproveVisible(true); }}>
                批准退款
              </Button>
              <Button type="link" size="small" danger icon={<CloseOutlined />}
                onClick={() => { setCurrentOrder(record); refundForm.resetFields(); fetchRefundDetail(record.id); setRefundRejectVisible(true); }}>
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
      <Title level={4} style={{ marginBottom: 16 }}>订单明细</Title>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="今日订单数" value={statsData.today_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="今日成交金额" value={statsData.today_revenue} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="今日退款金额" value={statsData.today_refund_amount} precision={2} prefix="¥" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="本月订单数" value={statsData.month_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="本月成交金额" value={statsData.month_revenue} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="本月退款金额" value={statsData.month_refund_amount} precision={2} prefix="¥" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>

      {/* 查询条件 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={[16, 12]}>
          <Col span={6}>
            <Input
              placeholder="订单号 / 用户昵称 / 手机号"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              onPressEnter={handleSearch}
              allowClear
            />
          </Col>
          <Col span={6}>
            <RangePicker
              style={{ width: '100%' }}
              placeholder={['下单开始时间', '下单结束时间']}
              value={dateRange as any}
              onChange={vals => setDateRange(vals as any)}
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              value={filterStatus}
              onChange={v => setFilterStatus(v)}
              options={statusOptions}
              placeholder="订单状态"
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              value={filterPayMethod}
              onChange={v => setFilterPayMethod(v)}
              options={payMethodOptions}
              placeholder="支付方式"
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              value={filterRefundStatus}
              onChange={v => setFilterRefundStatus(v)}
              options={refundStatusOptions}
              placeholder="退款流程"
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              value={filterRedemptionCodeStatus}
              onChange={v => setFilterRedemptionCodeStatus(v)}
              options={redemptionCodeStatusOptions}
              placeholder="核销码状态"
            />
          </Col>
          <Col span={4}>
            <Select
              style={{ width: '100%' }}
              value={filterCategory}
              onChange={v => setFilterCategory(v)}
              placeholder="商品分类"
              allowClear
              onClear={() => setFilterCategory('')}
            >
              <Select.Option value="">全部分类</Select.Option>
              {categories.map(c => (
                <Select.Option key={c.id} value={String(c.id)}>{c.name}</Select.Option>
              ))}
            </Select>
          </Col>
          <Col span={4}>
            <Space.Compact style={{ width: '100%' }}>
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最低金额"
                min={0}
                value={amountMin}
                onChange={v => setAmountMin(v)}
              />
              <InputNumber
                style={{ width: '50%' }}
                placeholder="最高金额"
                min={0}
                value={amountMax}
                onChange={v => setAmountMax(v)}
              />
            </Space.Compact>
          </Col>
          <Col span={4}>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>搜索</Button>
          </Col>
        </Row>
      </Card>

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
              <Descriptions.Item label="总金额"><span style={{ color: '#f5222d' }}>¥{currentOrder.total_amount ?? 0}</span></Descriptions.Item>
              <Descriptions.Item label="实付金额">¥{currentOrder.paid_amount ?? 0}</Descriptions.Item>
              <Descriptions.Item label="积分抵扣">{currentOrder.points_deduction}</Descriptions.Item>
              <Descriptions.Item label="优惠券抵扣">¥{currentOrder.coupon_discount ?? 0}</Descriptions.Item>
              <Descriptions.Item label="支付方式">{currentOrder.payment_method ? (payMethodMap[currentOrder.payment_method] || currentOrder.payment_method) : '-'}</Descriptions.Item>
              <Descriptions.Item label="订单状态">
                {renderStatusTag(currentOrder)}
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

            {currentOrder?.items?.some((item: any) => item.appointment_time) && (
              <Card size="small" title="预约信息" style={{ marginTop: 16 }}>
                <Descriptions column={2} size="small">
                  {currentOrder.store_name && (
                    <Descriptions.Item label="关联门店" span={2}>
                      {currentOrder.store_name}
                    </Descriptions.Item>
                  )}
                  {currentOrder.items.filter((item: any) => item.appointment_time).map((item: any, idx: number) => (
                    <React.Fragment key={idx}>
                      <Descriptions.Item label="预约日期" span={1}>
                        {item.appointment_time ? new Date(item.appointment_time).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }) : '-'}
                      </Descriptions.Item>
                      <Descriptions.Item label="预约时段" span={1}>
                        {item.appointment_data?.time_slot || (item.appointment_time ? new Date(item.appointment_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '-')}
                      </Descriptions.Item>
                      <Descriptions.Item label="预约状态" span={1}>
                        <Tag color={currentOrder.status === 'completed' ? 'green' : currentOrder.status === 'cancelled' ? 'red' : 'blue'}>
                          {currentOrder.status === 'completed' ? '已完成'
                            : currentOrder.status === 'cancelled' ? '已取消'
                            : (currentOrder.status === 'pending_use' || currentOrder.status === 'appointed') ? '待核销'
                            : currentOrder.status === 'pending_appointment' ? '待预约'
                            : '待支付'}
                        </Tag>
                      </Descriptions.Item>
                      {item.appointment_data?.note && (
                        <Descriptions.Item label="预约备注" span={1}>
                          {item.appointment_data.note}
                        </Descriptions.Item>
                      )}
                    </React.Fragment>
                  ))}
                </Descriptions>
              </Card>
            )}

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
            <div>金额: ¥{currentOrder.paid_amount ?? 0}</div>
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
        onCancel={() => { setRefundApproveVisible(false); setRefundDetail(null); }}
        destroyOnClose
        width={560}
      >
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
            <div>订单号: {currentOrder.order_no}</div>
            <div>实付: ¥{currentOrder.paid_amount ?? 0}</div>
          </div>
        )}
        {refundDetailLoading ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}><Spin tip="加载核销详情..." /></div>
        ) : refundDetail?.has_redemption ? (
          <div style={{ marginBottom: 16 }}>
            <Alert
              type="warning"
              showIcon
              message="核销情况（该订单已发生核销）"
              description={
                <div>
                  <div style={{ marginBottom: 8, fontWeight: 600 }}>
                    核销进度: {refundDetail.used_count ?? 0} / {refundDetail.total_count ?? 0} 次
                    {refundDetail.total_count > 0 && (
                      <span> ({Math.round(((refundDetail.used_count ?? 0) / refundDetail.total_count) * 100)}%)</span>
                    )}
                  </div>
                  {Array.isArray(refundDetail.redemption_records) && refundDetail.redemption_records.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>核销明细:</div>
                      {refundDetail.redemption_records.map((r: any, idx: number) => (
                        <div key={idx} style={{ color: '#595959', lineHeight: '22px' }}>
                          ⓘ {r.redeemed_at ? dayjs(r.redeemed_at).format('YYYY-MM-DD HH:mm') : '-'}　{r.store_name || '-'}　{r.operator_name || '-'}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              }
            />
          </div>
        ) : null}
        <Form form={refundForm} layout="vertical" initialValues={{ refund_amount: currentOrder?.paid_amount ?? 0 }}>
          <Form.Item
            label="审核退款金额"
            name="refund_amount"
            rules={[{ required: true, message: '请输入退款金额' }]}
          >
            <InputNumber
              style={{ width: '100%' }}
              min={0}
              max={currentOrder?.paid_amount ?? 0}
              precision={2}
              prefix="¥"
              placeholder="请输入退款金额"
            />
          </Form.Item>
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
        onCancel={() => { setRefundRejectVisible(false); setRefundDetail(null); }}
        destroyOnClose
        width={560}
      >
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#fff7e6', borderRadius: 8 }}>
            <div>订单号: {currentOrder.order_no}</div>
            <div>实付: ¥{currentOrder.paid_amount ?? 0}</div>
          </div>
        )}
        {refundDetailLoading ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}><Spin tip="加载核销详情..." /></div>
        ) : refundDetail?.has_redemption ? (
          <div style={{ marginBottom: 16 }}>
            <Alert
              type="warning"
              showIcon
              message="核销情况（该订单已发生核销）"
              description={
                <div>
                  <div style={{ marginBottom: 8, fontWeight: 600 }}>
                    核销进度: {refundDetail.used_count ?? 0} / {refundDetail.total_count ?? 0} 次
                    {refundDetail.total_count > 0 && (
                      <span> ({Math.round(((refundDetail.used_count ?? 0) / refundDetail.total_count) * 100)}%)</span>
                    )}
                  </div>
                  {Array.isArray(refundDetail.redemption_records) && refundDetail.redemption_records.length > 0 && (
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>核销明细:</div>
                      {refundDetail.redemption_records.map((r: any, idx: number) => (
                        <div key={idx} style={{ color: '#595959', lineHeight: '22px' }}>
                          ⓘ {r.redeemed_at ? dayjs(r.redeemed_at).format('YYYY-MM-DD HH:mm') : '-'}　{r.store_name || '-'}　{r.operator_name || '-'}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              }
            />
          </div>
        ) : null}
        <Form form={refundForm} layout="vertical">
          <Form.Item label="拒绝原因" name="admin_notes" rules={[{ required: true, message: '请输入拒绝原因' }]}>
            <TextArea rows={3} placeholder="请输入拒绝原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
