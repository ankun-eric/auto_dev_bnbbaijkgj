'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Typography, Row, Col, Card, DatePicker, Radio, Space, Spin, Empty, Tag,
} from 'antd';
import { Pie, Line } from '@ant-design/charts';
import { get } from '@/lib/api';
import dayjs, { Dayjs } from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

// PRD「订单统计状态对齐」一期：
// - 撤掉旧版「今日/本月/累计」12 张大卡片
// - 顶部时间筛选器（今日/本周/本月/自定义），默认今日
// - 12 个订单状态卡片矩阵（与订单明细页 12 状态完全对齐）
// - 7 个退款状态卡片矩阵（与 RefundStatusEnum 完全对齐）
// - 销售趋势图、品类销售排行、退款原因分布保留并随时间筛选器联动

interface OrderStatusItem {
  status: string;
  label: string;
  count: number;
  amount: number;
}

interface RefundStatusItem {
  status: string;
  label: string;
  count: number;
  amount: number;
}

interface OrderStatisticsResp {
  start_at?: string | null;
  end_at?: string | null;
  summary: {
    total_orders: number;
    total_revenue: number;
    total_refund_count: number;
    total_refund_amount: number;
  };
  order_status_items: OrderStatusItem[];
  refund_status_items: RefundStatusItem[];
}

interface TrendItem {
  date: string;
  order_count: number;
  revenue: number;
  refund_amount: number;
}

interface CategorySalesRow {
  category_name: string;
  sales_count: number;
  revenue: number;
}

interface RefundReason {
  reason: string;
  count: number;
}

type RangeKey = 'today' | 'week' | 'month' | 'custom';

const ORDER_STATUS_COLORS: Record<string, string> = {
  pending_payment: '#fa8c16',
  pending_shipment: '#1890ff',
  pending_receipt: '#13c2c2',
  pending_appointment: '#722ed1',
  appointed: '#2f54eb',
  pending_use: '#eb2f96',
  partial_used: '#faad14',
  completed: '#52c41a',
  expired: '#bfbfbf',
  refunding: '#fa541c',
  refunded: '#8c8c8c',
  cancelled: '#d9d9d9',
};

const REFUND_STATUS_COLORS: Record<string, string> = {
  none: '#bfbfbf',
  applied: '#fa8c16',
  reviewing: '#1890ff',
  approved: '#52c41a',
  rejected: '#ff4d4f',
  returning: '#faad14',
  refund_success: '#722ed1',
};

function getRangeByKey(key: RangeKey, customRange: [Dayjs | null, Dayjs | null] | null): [Dayjs, Dayjs] {
  const now = dayjs();
  if (key === 'today') {
    return [now.startOf('day'), now.endOf('day')];
  }
  if (key === 'week') {
    return [now.startOf('week'), now.endOf('day')];
  }
  if (key === 'month') {
    return [now.startOf('month'), now.endOf('day')];
  }
  // custom
  const start = customRange?.[0] ?? now.startOf('day');
  const end = customRange?.[1] ?? now.endOf('day');
  return [start, end];
}

export default function StatisticsPage() {
  const [rangeKey, setRangeKey] = useState<RangeKey>('today');
  const [customRange, setCustomRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [loading, setLoading] = useState(false);

  const [orderStatusItems, setOrderStatusItems] = useState<OrderStatusItem[]>([]);
  const [refundStatusItems, setRefundStatusItems] = useState<RefundStatusItem[]>([]);
  const [summary, setSummary] = useState<OrderStatisticsResp['summary']>({
    total_orders: 0, total_revenue: 0, total_refund_count: 0, total_refund_amount: 0,
  });

  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [categorySales, setCategorySales] = useState<CategorySalesRow[]>([]);
  const [refundReasons, setRefundReasons] = useState<RefundReason[]>([]);

  const [startAt, endAt] = useMemo(() => {
    const [s, e] = getRangeByKey(rangeKey, customRange);
    return [s.format('YYYY-MM-DD'), e.format('YYYY-MM-DD')];
  }, [rangeKey, customRange]);

  const fetchOrderStatistics = useCallback(async () => {
    try {
      const res: OrderStatisticsResp | null = await get('/api/admin/orders/statistics', {
        start_at: startAt,
        end_at: endAt,
      });
      if (res) {
        setOrderStatusItems(Array.isArray(res.order_status_items) ? res.order_status_items : []);
        setRefundStatusItems(Array.isArray(res.refund_status_items) ? res.refund_status_items : []);
        setSummary(res.summary || { total_orders: 0, total_revenue: 0, total_refund_count: 0, total_refund_amount: 0 });
      }
    } catch {
      setOrderStatusItems([]);
      setRefundStatusItems([]);
    }
  }, [startAt, endAt]);

  const fetchTrends = useCallback(async () => {
    try {
      const res = await get('/api/admin/statistics/trends', { start_date: startAt, end_date: endAt });
      const items = res?.items || [];
      if (Array.isArray(items)) {
        setTrends(items.map((t: any) => ({
          date: String(t.date ?? ''),
          order_count: Number(t.order_count ?? t.orders ?? 0),
          revenue: Number(t.revenue ?? 0),
          refund_amount: Number(t.refund_amount ?? 0),
        })));
      }
    } catch {
      setTrends([]);
    }
  }, [startAt, endAt]);

  const fetchCategorySales = useCallback(async () => {
    try {
      const res = await get('/api/admin/products', { page: 1, page_size: 200 });
      const items = res?.items || res?.list || [];
      const catRes = await get('/api/admin/products/categories');
      const catMap = new Map<number, string>();
      if (catRes?.items && Array.isArray(catRes.items)) {
        catRes.items.forEach((c: any) => catMap.set(Number(c.id), String(c.name)));
      }
      const salesMap = new Map<string, { sales_count: number; revenue: number }>();
      if (Array.isArray(items)) {
        for (const product of items) {
          const catName = catMap.get(Number(product.category_id)) || '未分类';
          const existing = salesMap.get(catName) || { sales_count: 0, revenue: 0 };
          existing.sales_count += Number(product.sales_count ?? 0);
          existing.revenue += Number(product.sales_count ?? 0) * Number(product.sale_price ?? 0);
          salesMap.set(catName, existing);
        }
      }
      const result: CategorySalesRow[] = [];
      salesMap.forEach((v, k) => result.push({ category_name: k, ...v }));
      setCategorySales(result.sort((a, b) => b.revenue - a.revenue));
    } catch {
      setCategorySales([]);
    }
  }, []);

  const fetchRefundReasons = useCallback(async () => {
    try {
      const res = await get('/api/admin/statistics/refund-reasons');
      const items = res?.items || [];
      if (Array.isArray(items)) {
        setRefundReasons(items.map((r: any) => ({
          reason: String(r.reason ?? '未知'),
          count: Number(r.count ?? 0),
        })));
      }
    } catch {
      setRefundReasons([]);
    }
  }, []);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchOrderStatistics(),
        fetchTrends(),
        fetchCategorySales(),
        fetchRefundReasons(),
      ]);
    } finally {
      setLoading(false);
    }
  }, [fetchOrderStatistics, fetchTrends, fetchCategorySales, fetchRefundReasons]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const trendOrderData = trends.map(t => ({ date: t.date, value: t.order_count }));
  const trendRevenueData = trends.map(t => ({ date: t.date, value: Math.round(t.revenue * 100) / 100 }));
  const trendRefundData = trends.map(t => ({ date: t.date, value: Math.round(t.refund_amount * 100) / 100 }));

  const categoryPieData = categorySales
    .filter(c => c.sales_count > 0)
    .map(c => ({ type: c.category_name, value: c.sales_count }));

  const refundReasonPieData = refundReasons
    .filter(r => r.count > 0)
    .map(r => ({ type: r.reason, value: r.count }));

  const emptyPlaceholder = (
    <div style={{ textAlign: 'center', paddingTop: 120, color: '#999' }}><Empty description="暂无数据" /></div>
  );

  const renderOrderStatusCard = (item: OrderStatusItem) => (
    <Card
      size="small"
      style={{ borderTop: `3px solid ${ORDER_STATUS_COLORS[item.status] || '#1890ff'}`, height: '100%' }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
        <Tag color={ORDER_STATUS_COLORS[item.status] || 'default'} style={{ marginRight: 0 }}>
          {item.label}
        </Tag>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 }}>
        <div>
          <div style={{ fontSize: 12, color: '#999' }}>订单数</div>
          <div style={{ fontSize: 22, fontWeight: 600, color: '#262626', lineHeight: 1.2 }}>{item.count}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: '#999' }}>金额合计</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#52c41a', lineHeight: 1.2 }}>
            ¥{item.amount.toFixed(2)}
          </div>
        </div>
      </div>
    </Card>
  );

  const renderRefundStatusCard = (item: RefundStatusItem) => (
    <Card
      size="small"
      style={{ borderTop: `3px solid ${REFUND_STATUS_COLORS[item.status] || '#1890ff'}`, height: '100%' }}
      styles={{ body: { padding: '12px 16px' } }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
        <Tag color={REFUND_STATUS_COLORS[item.status] || 'default'} style={{ marginRight: 0 }}>
          {item.label}
        </Tag>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 }}>
        <div>
          <div style={{ fontSize: 12, color: '#999' }}>订单数</div>
          <div style={{ fontSize: 22, fontWeight: 600, color: '#262626', lineHeight: 1.2 }}>{item.count}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 12, color: '#999' }}>金额合计</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#fa541c', lineHeight: 1.2 }}>
            ¥{item.amount.toFixed(2)}
          </div>
        </div>
      </div>
    </Card>
  );

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>订单统计</Title>

      {/* 顶部时间筛选器 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap align="center">
          <Text strong>统计时间：</Text>
          <Radio.Group
            value={rangeKey}
            onChange={(e) => {
              const v = e.target.value as RangeKey;
              setRangeKey(v);
              if (v !== 'custom') setCustomRange(null);
            }}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="today">今日</Radio.Button>
            <Radio.Button value="week">本周</Radio.Button>
            <Radio.Button value="month">本月</Radio.Button>
            <Radio.Button value="custom">自定义</Radio.Button>
          </Radio.Group>
          {rangeKey === 'custom' && (
            <RangePicker
              value={customRange as any}
              onChange={(vals) => {
                setCustomRange(vals as any);
              }}
              allowClear={false}
            />
          )}
          <Text type="secondary" style={{ marginLeft: 12 }}>
            数据区间：{startAt} ~ {endAt}
          </Text>
        </Space>
      </Card>

      <Spin spinning={loading}>
        {/* 时间段总览（精简版） */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={12} md={6}>
            <Card size="small" styles={{ body: { padding: '12px 16px' } }}>
              <div style={{ fontSize: 12, color: '#999' }}>区间总订单数（不含已取消）</div>
              <div style={{ fontSize: 24, fontWeight: 600 }}>{summary.total_orders}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small" styles={{ body: { padding: '12px 16px' } }}>
              <div style={{ fontSize: 12, color: '#999' }}>区间总实付金额</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#52c41a' }}>¥{summary.total_revenue.toFixed(2)}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small" styles={{ body: { padding: '12px 16px' } }}>
              <div style={{ fontSize: 12, color: '#999' }}>区间退款成功单数</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#fa8c16' }}>{summary.total_refund_count}</div>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small" styles={{ body: { padding: '12px 16px' } }}>
              <div style={{ fontSize: 12, color: '#999' }}>区间退款成功金额</div>
              <div style={{ fontSize: 24, fontWeight: 600, color: '#f5222d' }}>¥{summary.total_refund_amount.toFixed(2)}</div>
            </Card>
          </Col>
        </Row>

        {/* 订单状态分布矩阵：12 个卡片 */}
        <Card size="small" title="订单状态分布（与订单明细页对齐）" style={{ marginBottom: 16 }}>
          <Row gutter={[12, 12]}>
            {orderStatusItems.map((it) => (
              <Col key={it.status} xs={24} sm={12} md={8} lg={6} xl={6}>
                {renderOrderStatusCard(it)}
              </Col>
            ))}
            {orderStatusItems.length === 0 && (
              <Col span={24}><Empty description="暂无数据" /></Col>
            )}
          </Row>
        </Card>

        {/* 退款状态分布矩阵：7 个卡片 */}
        <Card size="small" title="退款状态分布（RefundStatusEnum 全量）" style={{ marginBottom: 16 }}>
          <Row gutter={[12, 12]}>
            {refundStatusItems.map((it) => (
              <Col key={it.status} xs={24} sm={12} md={8} lg={6} xl={6}>
                {renderRefundStatusCard(it)}
              </Col>
            ))}
            {refundStatusItems.length === 0 && (
              <Col span={24}><Empty description="暂无数据" /></Col>
            )}
          </Row>
        </Card>

        {/* 销售趋势图 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={12}>
            <Card size="small" title="订单量趋势">
              <div style={{ height: 280 }}>
                {trendOrderData.length > 0
                  ? <Line data={trendOrderData} xField="date" yField="value" point={{ size: 3 }} />
                  : emptyPlaceholder}
              </div>
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="销售额趋势">
              <div style={{ height: 280 }}>
                {trendRevenueData.length > 0
                  ? <Line data={trendRevenueData} xField="date" yField="value" point={{ size: 3 }} style={{ stroke: '#52c41a' }} />
                  : emptyPlaceholder}
              </div>
            </Card>
          </Col>
        </Row>

        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={12}>
            <Card size="small" title="退款金额趋势">
              <div style={{ height: 280 }}>
                {trendRefundData.length > 0
                  ? <Line data={trendRefundData} xField="date" yField="value" point={{ size: 3 }} style={{ stroke: '#f5222d' }} />
                  : emptyPlaceholder}
              </div>
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" title="商品分类销售占比">
              <div style={{ height: 280 }}>
                {categoryPieData.length > 0
                  ? <Pie
                      data={categoryPieData}
                      angleField="value"
                      colorField="type"
                      innerRadius={0.5}
                      label={{ text: 'type', position: 'outside' }}
                      legend={{ position: 'bottom' }}
                    />
                  : emptyPlaceholder}
              </div>
            </Card>
          </Col>
        </Row>

        <Row gutter={16}>
          <Col span={12}>
            <Card size="small" title="退款原因分布">
              <div style={{ height: 280 }}>
                {refundReasonPieData.length > 0
                  ? <Pie
                      data={refundReasonPieData}
                      angleField="value"
                      colorField="type"
                      innerRadius={0.5}
                      label={{ text: 'type', position: 'outside' }}
                      legend={{ position: 'bottom' }}
                    />
                  : emptyPlaceholder}
              </div>
            </Card>
          </Col>
          <Col span={12} />
        </Row>
      </Spin>
    </div>
  );
}
