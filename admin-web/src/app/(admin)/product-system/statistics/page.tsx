'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Row, Col, Card, Statistic, DatePicker, Button, Space, message,
  Input, Select, InputNumber,
} from 'antd';
import {
  ShoppingCartOutlined, DollarOutlined, SearchOutlined, UndoOutlined,
} from '@ant-design/icons';
import { Column, Pie, Line } from '@ant-design/charts';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface FullStats {
  today_orders: number;
  today_revenue: number;
  today_refund_count: number;
  today_refund_amount: number;
  month_orders: number;
  month_revenue: number;
  month_refund_count: number;
  month_refund_amount: number;
  total_orders: number;
  total_revenue: number;
  total_refund_count: number;
  total_refund_amount: number;
}

interface TrendItem {
  date: string;
  orders: number;
  revenue: number;
  refund_amount: number;
}

interface CategorySales {
  category_name: string;
  sales_count: number;
  revenue: number;
}

interface StatusDist {
  status: string;
  count: number;
}

interface RefundReason {
  reason: string;
  count: number;
}

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending_payment', label: '待付款' },
  { value: 'pending_shipment', label: '待发货' },
  { value: 'pending_receipt', label: '待收货' },
  { value: 'pending_use', label: '待使用' },
  { value: 'completed', label: '已完成' },
  { value: 'pending_review', label: '待评价' },
  { value: 'cancelled', label: '已取消' },
];

const payMethodOptions = [
  { value: '', label: '全部支付方式' },
  { value: 'wechat', label: '微信支付' },
  { value: 'alipay', label: '支付宝' },
  { value: 'balance', label: '余额支付' },
  { value: 'points', label: '积分兑换' },
];

const refundStatusOptions = [
  { value: '', label: '全部退款状态' },
  { value: 'none', label: '无退款' },
  { value: 'applied', label: '退款申请中' },
  { value: 'approved', label: '退款已批准' },
  { value: 'rejected', label: '退款已拒绝' },
  { value: 'refund_success', label: '退款成功' },
];

const statusLabelMap: Record<string, string> = {
  pending_payment: '待付款',
  pending_shipment: '待发货',
  pending_receipt: '待收货',
  pending_use: '待使用',
  pending_review: '待评价',
  completed: '已完成',
  cancelled: '已取消',
};

export default function StatisticsPage() {
  const [stats, setStats] = useState<FullStats>({
    today_orders: 0, today_revenue: 0, today_refund_count: 0, today_refund_amount: 0,
    month_orders: 0, month_revenue: 0, month_refund_count: 0, month_refund_amount: 0,
    total_orders: 0, total_revenue: 0, total_refund_count: 0, total_refund_amount: 0,
  });
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [categorySales, setCategorySales] = useState<CategorySales[]>([]);
  const [statusDist, setStatusDist] = useState<StatusDist[]>([]);
  const [refundReasons, setRefundReasons] = useState<RefundReason[]>([]);
  const [categories, setCategories] = useState<{ id: number; name: string }[]>([]);

  const [searchText, setSearchText] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterPayMethod, setFilterPayMethod] = useState('');
  const [filterRefundStatus, setFilterRefundStatus] = useState('');
  const [filterCategory, setFilterCategory] = useState<string>('');
  const [amountMin, setAmountMin] = useState<number | null>(null);
  const [amountMax, setAmountMax] = useState<number | null>(null);

  const buildParams = useCallback(() => {
    const params: Record<string, unknown> = {};
    if (searchText) params.keyword = searchText;
    if (dateRange?.[0]) params.start_date = dateRange[0].format('YYYY-MM-DD');
    if (dateRange?.[1]) params.end_date = dateRange[1].format('YYYY-MM-DD');
    if (filterStatus) params.status = filterStatus;
    if (filterPayMethod) params.payment_method = filterPayMethod;
    if (filterRefundStatus) params.refund_status = filterRefundStatus;
    if (filterCategory) params.category_id = filterCategory;
    if (amountMin !== null) params.amount_min = amountMin;
    if (amountMax !== null) params.amount_max = amountMax;
    return params;
  }, [searchText, dateRange, filterStatus, filterPayMethod, filterRefundStatus, filterCategory, amountMin, amountMax]);

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
      const params = buildParams();
      const res = await get('/api/admin/statistics/sales', params);
      if (res) {
        setStats({
          today_orders: Number(res.today_orders ?? 0),
          today_revenue: Number(res.today_revenue ?? 0),
          today_refund_count: Number(res.today_refund_count ?? 0),
          today_refund_amount: Number(res.today_refund_amount ?? 0),
          month_orders: Number(res.month_orders ?? 0),
          month_revenue: Number(res.month_revenue ?? 0),
          month_refund_count: Number(res.month_refund_count ?? 0),
          month_refund_amount: Number(res.month_refund_amount ?? 0),
          total_orders: Number(res.total_orders ?? 0),
          total_revenue: Number(res.total_revenue ?? 0),
          total_refund_count: Number(res.total_refund_count ?? 0),
          total_refund_amount: Number(res.total_refund_amount ?? 0),
        });
      }
    } catch {}
  }, [buildParams]);

  const fetchTrends = useCallback(async () => {
    try {
      const params = buildParams();
      const res = await get('/api/admin/statistics/trends', params);
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          setTrends(items.map((t: any) => ({
            date: String(t.date ?? ''),
            orders: Number(t.orders ?? 0),
            revenue: Number(t.revenue ?? 0),
            refund_amount: Number(t.refund_amount ?? 0),
          })));
        }
      }
    } catch {}
  }, [buildParams]);

  const fetchCategorySales = useCallback(async () => {
    try {
      const params = buildParams();
      const res = await get('/api/admin/products', { page: 1, page_size: 100, ...params });
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          const catRes = await get('/api/admin/products/categories');
          const catMap = new Map<number, string>();
          if (catRes?.items && Array.isArray(catRes.items)) {
            catRes.items.forEach((c: any) => catMap.set(Number(c.id), String(c.name)));
          }

          const salesMap = new Map<string, { sales_count: number; revenue: number }>();
          for (const product of items) {
            const catName = catMap.get(Number(product.category_id)) || '未分类';
            const existing = salesMap.get(catName) || { sales_count: 0, revenue: 0 };
            existing.sales_count += Number(product.sales_count ?? 0);
            existing.revenue += Number(product.sales_count ?? 0) * Number(product.sale_price ?? 0);
            salesMap.set(catName, existing);
          }

          const result: CategorySales[] = [];
          salesMap.forEach((v, k) => {
            result.push({ category_name: k, ...v });
          });
          setCategorySales(result.sort((a, b) => b.revenue - a.revenue));
        }
      }
    } catch {}
  }, [buildParams]);

  const fetchStatusDist = useCallback(async () => {
    try {
      const params = buildParams();
      const res = await get('/api/admin/orders/unified', { ...params, page: 1, page_size: 1000 });
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          const countMap = new Map<string, number>();
          items.forEach((o: any) => {
            const st = String(o.status ?? 'unknown');
            countMap.set(st, (countMap.get(st) || 0) + 1);
          });
          const result: StatusDist[] = [];
          countMap.forEach((count, status) => {
            result.push({ status, count });
          });
          setStatusDist(result);
        }
      }
    } catch {}
  }, [buildParams]);

  const fetchRefundReasons = useCallback(async () => {
    try {
      const params = buildParams();
      const res = await get('/api/admin/statistics/refund-reasons', params);
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          setRefundReasons(items.map((r: any) => ({
            reason: String(r.reason ?? '未知'),
            count: Number(r.count ?? 0),
          })));
        }
      }
    } catch {}
  }, [buildParams]);

  const fetchAllData = useCallback(() => {
    fetchStats();
    fetchTrends();
    fetchCategorySales();
    fetchStatusDist();
    fetchRefundReasons();
  }, [fetchStats, fetchTrends, fetchCategorySales, fetchStatusDist, fetchRefundReasons]);

  useEffect(() => {
    fetchCategories();
    fetchAllData();
  }, []);

  const handleSearch = () => {
    fetchAllData();
  };

  const orderTrendData = trends.map(t => ({ date: t.date, value: t.orders }));
  const revenueTrendData = trends.map(t => ({ date: t.date, value: Math.round(t.revenue * 100) / 100 }));
  const refundTrendData = trends.map(t => ({ date: t.date, value: Math.round(t.refund_amount * 100) / 100 }));

  const categoryPieData = categorySales
    .filter(c => c.sales_count > 0)
    .map(c => ({ type: c.category_name, value: c.sales_count }));

  const statusBarData = statusDist.map(s => ({
    type: statusLabelMap[s.status] || s.status,
    value: s.count,
  }));

  const refundReasonPieData = refundReasons
    .filter(r => r.count > 0)
    .map(r => ({ type: r.reason, value: r.count }));

  const emptyPlaceholder = (
    <div style={{ textAlign: 'center', paddingTop: 120, color: '#999' }}>暂无数据</div>
  );

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>订单统计</Title>

      {/* 12张统计卡片 - 三行四列 */}
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日订单数" value={stats.today_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日成交金额" value={stats.today_revenue} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日退款单数" value={stats.today_refund_count} prefix={<UndoOutlined />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日退款金额" value={stats.today_refund_amount} precision={2} prefix="¥" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="本月订单数" value={stats.month_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="本月成交金额" value={stats.month_revenue} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="本月退款单数" value={stats.month_refund_count} prefix={<UndoOutlined />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="本月退款金额" value={stats.month_refund_amount} precision={2} prefix="¥" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="累计订单数" value={stats.total_orders} prefix={<ShoppingCartOutlined />} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="累计成交金额" value={stats.total_revenue} precision={2} prefix={<DollarOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="累计退款单数" value={stats.total_refund_count} prefix={<UndoOutlined />} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="累计退款金额" value={stats.total_refund_amount} precision={2} prefix="¥" valueStyle={{ color: '#f5222d' }} />
          </Card>
        </Col>
      </Row>

      {/* 查询条件 */}
      <Card size="small" style={{ marginBottom: 24 }}>
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
              placeholder="退款状态"
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
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>查询</Button>
          </Col>
        </Row>
      </Card>

      {/* 6张图表 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card size="small" title="订单量趋势">
            <div style={{ height: 320 }}>
              {orderTrendData.length > 0
                ? <Line
                    data={orderTrendData}
                    xField="date"
                    yField="value"
                    point={{ size: 3 }}
                    axis={{ y: { title: '订单数' } }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="成交金额趋势">
            <div style={{ height: 320 }}>
              {revenueTrendData.length > 0
                ? <Line
                    data={revenueTrendData}
                    xField="date"
                    yField="value"
                    point={{ size: 3 }}
                    axis={{ y: { title: '金额 (¥)' } }}
                    style={{ stroke: '#52c41a' }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card size="small" title="退款金额趋势">
            <div style={{ height: 320 }}>
              {refundTrendData.length > 0
                ? <Line
                    data={refundTrendData}
                    xField="date"
                    yField="value"
                    point={{ size: 3 }}
                    axis={{ y: { title: '金额 (¥)' } }}
                    style={{ stroke: '#f5222d' }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="商品分类占比">
            <div style={{ height: 320 }}>
              {categoryPieData.length > 0
                ? <Pie
                    data={categoryPieData}
                    angleField="value"
                    colorField="type"
                    innerRadius={0.5}
                    label={{ text: 'type', position: 'outside' }}
                    legend={{ position: 'bottom' }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" title="订单状态分布">
            <div style={{ height: 320 }}>
              {statusBarData.length > 0
                ? <Column
                    data={statusBarData}
                    xField="type"
                    yField="value"
                    colorField="type"
                    axis={{ y: { title: '数量' } }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="退款原因分布">
            <div style={{ height: 320 }}>
              {refundReasonPieData.length > 0
                ? <Pie
                    data={refundReasonPieData}
                    angleField="value"
                    colorField="type"
                    innerRadius={0.5}
                    label={{ text: 'type', position: 'outside' }}
                    legend={{ position: 'bottom' }}
                  />
                : emptyPlaceholder
              }
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
