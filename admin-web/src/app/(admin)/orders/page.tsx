'use client';

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Tabs, Tag, message,
  Typography, Descriptions, Card, Statistic, Row, Col, DatePicker, Drawer, Popconfirm,
} from 'antd';
import {
  EyeOutlined, RollbackOutlined, SearchOutlined, CheckOutlined,
  PlayCircleOutlined, StopOutlined, CarryOutOutlined,
} from '@ant-design/icons';
import { Line, Pie, Column } from '@ant-design/charts';
import { get, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

interface OrderRecord {
  id: number;
  orderNo: string;
  userId: number;
  userName: string;
  userPhone: string;
  serviceName: string;
  amount: number;
  orderStatus: string;
  paymentStatus: string;
  payMethod: string;
  remark: string;
  createdAt: string;
  raw: Record<string, unknown>;
}

const orderStatusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待确认' },
  confirmed: { color: 'blue', text: '已确认' },
  processing: { color: 'cyan', text: '服务中' },
  completed: { color: 'green', text: '已完成' },
  cancelled: { color: 'default', text: '已取消' },
};

const paymentStatusMap: Record<string, { color: string; text: string }> = {
  unpaid: { color: 'default', text: '未支付' },
  paid: { color: 'blue', text: '已支付' },
  refunded: { color: 'red', text: '已退款' },
};

const payMethodMap: Record<string, string> = {
  wechat: '微信支付',
  alipay: '支付宝',
  balance: '余额支付',
};

function mapOrder(item: Record<string, unknown>): OrderRecord {
  return {
    id: Number(item.id ?? 0),
    orderNo: String(item.order_no ?? ''),
    userId: Number(item.user_id ?? 0),
    userName: String(item.user_nickname || item.user_name || `用户#${item.user_id}`),
    userPhone: String(item.user_phone ?? ''),
    serviceName: String(item.service_name || `服务#${item.service_item_id}`),
    amount: Number(item.total_amount ?? 0),
    orderStatus: String(item.order_status ?? 'pending'),
    paymentStatus: String(item.payment_status ?? 'unpaid'),
    payMethod: payMethodMap[String(item.payment_method ?? '')] || String(item.payment_method ?? '-'),
    remark: String(item.notes ?? ''),
    createdAt: String(item.created_at ?? ''),
    raw: item,
  };
}

function displayStatus(order: OrderRecord) {
  if (order.paymentStatus === 'refunded') return { color: 'red', text: '已退款' };
  const s = orderStatusMap[order.orderStatus];
  if (s) return s;
  return { color: 'default', text: order.orderStatus };
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<OrderRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  const [drawerVisible, setDrawerVisible] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<OrderRecord | null>(null);

  const [cancelVisible, setCancelVisible] = useState(false);
  const [cancelForm] = Form.useForm();

  const [refundVisible, setRefundVisible] = useState(false);
  const [refundForm] = Form.useForm();

  const [statistics, setStatistics] = useState<Record<string, any>>({});
  const [trends, setTrends] = useState<any[]>([]);
  const [trendDays, setTrendDays] = useState(7);
  const [distribution, setDistribution] = useState<{ category: any[]; status: any[] }>({ category: [], status: [] });

  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;
      if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
      if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');

      const tab = activeTabRef.current;
      if (tab === 'paid') {
        params.payment_status = 'paid';
      } else if (tab === 'refunded') {
        params.payment_status = 'refunded';
      } else if (tab === 'processing') {
        params.order_status = 'confirmed,processing';
      } else if (tab !== 'all') {
        params.order_status = tab;
      }

      const res = await get('/api/admin/orders', params);
      if (res) {
        const raw = res.items || res.list || res;
        const items = Array.isArray(raw) ? raw.map((r: Record<string, unknown>) => mapOrder(r)) : [];
        setOrders(items);
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? items.length }));
      }
    } catch {
      setOrders([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载订单数据失败');
    } finally {
      setLoading(false);
    }
  }, [searchText, dateRange]);

  const fetchStatistics = useCallback(async () => {
    try {
      const res = await get('/api/admin/orders/statistics');
      if (res) setStatistics(res);
    } catch {}
  }, []);

  const fetchTrends = useCallback(async (days: number) => {
    try {
      const res = await get('/api/admin/orders/trends', { days });
      if (res) {
        const raw = res.items || res.list || res;
        setTrends(Array.isArray(raw) ? raw : []);
      }
    } catch {}
  }, []);

  const fetchDistribution = useCallback(async () => {
    try {
      const res = await get('/api/admin/orders/distribution');
      if (res) {
        setDistribution({
          category: Array.isArray(res.category) ? res.category : [],
          status: Array.isArray(res.status) ? res.status : [],
        });
      }
    } catch {}
  }, []);

  useEffect(() => {
    fetchData(1, pagination.pageSize);
  }, [activeTab]);

  useEffect(() => {
    fetchStatistics();
    fetchTrends(trendDays);
    fetchDistribution();
  }, []);

  useEffect(() => {
    fetchTrends(trendDays);
  }, [trendDays]);

  const handleAction = async (order: OrderRecord, action: string, body?: Record<string, unknown>) => {
    try {
      await put(`/api/admin/orders/${order.id}/${action}`, body);
      message.success('操作成功');
      fetchData(pagination.current, pagination.pageSize);
      fetchStatistics();
    } catch {
      message.error('操作失败');
    }
  };

  const handleCancel = async () => {
    if (!currentOrder) return;
    try {
      const values = await cancelForm.validateFields();
      await put(`/api/admin/orders/${currentOrder.id}/cancel`, { reason: values.reason });
      message.success('取消成功');
      setCancelVisible(false);
      cancelForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
      fetchStatistics();
    } catch {
      message.error('取消失败');
    }
  };

  const handleRefund = async () => {
    if (!currentOrder) return;
    try {
      const values = await refundForm.validateFields();
      await put(`/api/admin/orders/${currentOrder.id}/refund`, {
        reason: values.reason,
        refund_amount: values.refund_amount,
      });
      message.success('退款处理成功');
      setRefundVisible(false);
      refundForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
      fetchStatistics();
    } catch {
      message.error('退款处理失败');
    }
  };

  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'pending', label: '待确认' },
    { key: 'paid', label: '已支付' },
    { key: 'processing', label: '服务中' },
    { key: 'completed', label: '已完成' },
    { key: 'refunded', label: '已退款' },
  ];

  const orderTrendData = trends.map(t => ({
    date: String(t.date ?? ''),
    value: Number(t.order_count ?? t.count ?? 0),
  }));

  const amountTrendData = trends.map(t => ({
    date: String(t.date ?? ''),
    value: Number(t.total_amount ?? t.amount ?? 0),
  }));

  const lineConfig = (data: any[], yLabel: string) => ({
    data,
    xField: 'date',
    yField: 'value',
    smooth: true,
    point: { size: 3 },
    axis: { y: { title: yLabel } },
    style: { lineWidth: 2 },
  });

  const pieData = distribution.category.map(c => ({
    type: String(c.name ?? c.category ?? c.type ?? ''),
    value: Number(c.count ?? c.value ?? 0),
  }));

  const columnData = distribution.status.map(s => ({
    type: String(s.name ?? s.status ?? s.type ?? ''),
    value: Number(s.count ?? s.value ?? 0),
  }));

  const columns = [
    { title: '订单号', dataIndex: 'orderNo', key: 'orderNo', width: 180 },
    { title: '用户', dataIndex: 'userName', key: 'userName', width: 110 },
    { title: '手机号', dataIndex: 'userPhone', key: 'userPhone', width: 130 },
    { title: '服务', dataIndex: 'serviceName', key: 'serviceName', width: 150 },
    {
      title: '金额', dataIndex: 'amount', key: 'amount', width: 100,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{(v ?? 0).toFixed(2)}</span>,
    },
    {
      title: '状态', key: 'status', width: 90,
      render: (_: unknown, record: OrderRecord) => {
        const s = displayStatus(record);
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '下单时间', dataIndex: 'createdAt', key: 'createdAt', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作', key: 'action', width: 260, fixed: 'right' as const,
      render: (_: unknown, record: OrderRecord) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentOrder(record); setDrawerVisible(true); }}>详情</Button>
          {record.orderStatus === 'pending' && record.paymentStatus === 'paid' && (
            <Popconfirm title="确认此订单？" onConfirm={() => handleAction(record, 'confirm')}>
              <Button type="link" size="small" icon={<CheckOutlined />}>确认</Button>
            </Popconfirm>
          )}
          {record.orderStatus === 'confirmed' && (
            <Popconfirm title="开始服务？" onConfirm={() => handleAction(record, 'start-service')}>
              <Button type="link" size="small" icon={<PlayCircleOutlined />}>开始服务</Button>
            </Popconfirm>
          )}
          {record.orderStatus === 'processing' && (
            <Popconfirm title="确认完成？" onConfirm={() => handleAction(record, 'complete')}>
              <Button type="link" size="small" icon={<CarryOutOutlined />}>完成</Button>
            </Popconfirm>
          )}
          {!['completed', 'cancelled'].includes(record.orderStatus) && record.paymentStatus !== 'refunded' && (
            <Button type="link" size="small" danger icon={<StopOutlined />}
              onClick={() => { setCurrentOrder(record); cancelForm.resetFields(); setCancelVisible(true); }}>
              取消
            </Button>
          )}
          {record.paymentStatus === 'paid' && record.orderStatus !== 'cancelled' && (
            <Button type="link" size="small" danger icon={<RollbackOutlined />}
              onClick={() => {
                setCurrentOrder(record);
                refundForm.resetFields();
                refundForm.setFieldsValue({ refund_amount: record.amount });
                setRefundVisible(true);
              }}>
              退款
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>订单管理</Title>

      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card size="small"><Statistic title="今日订单数" value={statistics.today_orders ?? 0} /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="今日成交金额" value={statistics.today_amount ?? 0} precision={2} prefix="¥" /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="本月订单数" value={statistics.month_orders ?? 0} /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="本月成交金额" value={statistics.month_amount ?? 0} precision={2} prefix="¥" /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="订单总数" value={statistics.total_orders ?? 0} /></Card>
        </Col>
        <Col span={4}>
          <Card size="small"><Statistic title="累计总金额" value={statistics.total_amount ?? 0} precision={2} prefix="¥" /></Card>
        </Col>
      </Row>

      {/* Charts 2x2 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card
            size="small"
            title="订单量趋势"
            extra={
              <Space>
                <Button size="small" type={trendDays === 7 ? 'primary' : 'default'} onClick={() => setTrendDays(7)}>7天</Button>
                <Button size="small" type={trendDays === 30 ? 'primary' : 'default'} onClick={() => setTrendDays(30)}>30天</Button>
              </Space>
            }
          >
            <div style={{ height: 260 }}>
              {orderTrendData.length > 0 ? <Line {...lineConfig(orderTrendData, '订单数')} /> : <div style={{ textAlign: 'center', paddingTop: 100, color: '#999' }}>暂无数据</div>}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card
            size="small"
            title="成交金额趋势"
            extra={
              <Space>
                <Button size="small" type={trendDays === 7 ? 'primary' : 'default'} onClick={() => setTrendDays(7)}>7天</Button>
                <Button size="small" type={trendDays === 30 ? 'primary' : 'default'} onClick={() => setTrendDays(30)}>30天</Button>
              </Space>
            }
          >
            <div style={{ height: 260 }}>
              {amountTrendData.length > 0 ? <Line {...lineConfig(amountTrendData, '金额(¥)')} /> : <div style={{ textAlign: 'center', paddingTop: 100, color: '#999' }}>暂无数据</div>}
            </div>
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card size="small" title="服务分类占比">
            <div style={{ height: 260 }}>
              {pieData.length > 0
                ? <Pie data={pieData} angleField="value" colorField="type" innerRadius={0.5} label={{ text: 'type', position: 'outside' }} legend={{ position: 'bottom' }} />
                : <div style={{ textAlign: 'center', paddingTop: 100, color: '#999' }}>暂无数据</div>}
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="订单状态分布">
            <div style={{ height: 260 }}>
              {columnData.length > 0
                ? <Column data={columnData} xField="type" yField="value" colorField="type" />
                : <div style={{ textAlign: 'center', paddingTop: 100, color: '#999' }}>暂无数据</div>}
            </div>
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索订单号/用户昵称/手机号"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          onPressEnter={() => fetchData(1, pagination.pageSize)}
          style={{ width: 280 }}
          allowClear
        />
        <RangePicker
          value={dateRange as any}
          onChange={(vals) => setDateRange(vals as any)}
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
        scroll={{ x: 1300 }}
      />

      {/* Detail Drawer */}
      <Drawer
        title="订单详情"
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        width={560}
      >
        {currentOrder && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="订单号">{currentOrder.orderNo}</Descriptions.Item>
            <Descriptions.Item label="用户">{currentOrder.userName}</Descriptions.Item>
            <Descriptions.Item label="手机号">{currentOrder.userPhone || '-'}</Descriptions.Item>
            <Descriptions.Item label="服务">{currentOrder.serviceName}</Descriptions.Item>
            <Descriptions.Item label="金额"><span style={{ color: '#f5222d' }}>¥{(currentOrder.amount ?? 0).toFixed(2)}</span></Descriptions.Item>
            <Descriptions.Item label="支付方式">{currentOrder.payMethod || '-'}</Descriptions.Item>
            <Descriptions.Item label="订单状态">
              {(() => { const s = displayStatus(currentOrder); return <Tag color={s.color}>{s.text}</Tag>; })()}
            </Descriptions.Item>
            <Descriptions.Item label="下单时间">{currentOrder.createdAt ? dayjs(currentOrder.createdAt).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
            <Descriptions.Item label="备注" span={2}>{currentOrder.remark || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>

      {/* Cancel Modal */}
      <Modal title="取消订单" open={cancelVisible} onOk={handleCancel} onCancel={() => setCancelVisible(false)} destroyOnClose>
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#fff7e6', borderRadius: 8 }}>
            <div>订单号: {currentOrder.orderNo}</div>
            <div>用户: {currentOrder.userName}</div>
          </div>
        )}
        <Form form={cancelForm} layout="vertical">
          <Form.Item label="取消原因" name="reason" rules={[{ required: true, message: '请输入取消原因' }]}>
            <TextArea rows={3} placeholder="请输入取消原因" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Refund Modal */}
      <Modal title="退款处理" open={refundVisible} onOk={handleRefund} onCancel={() => setRefundVisible(false)} destroyOnClose>
        {currentOrder && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
            <div>订单号: {currentOrder.orderNo}</div>
            <div>金额: ¥{(currentOrder.amount ?? 0).toFixed(2)}</div>
            <div>用户: {currentOrder.userName}</div>
          </div>
        )}
        <Form form={refundForm} layout="vertical">
          <Form.Item label="退款金额" name="refund_amount" rules={[{ required: true, message: '请输入退款金额' }]}>
            <InputNumber min={0.01} max={currentOrder?.amount} step={0.01} style={{ width: '100%' }} precision={2} prefix="¥" />
          </Form.Item>
          <Form.Item label="退款原因" name="reason" rules={[{ required: true, message: '请输入退款原因' }]}>
            <TextArea rows={3} placeholder="请输入退款原因" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
