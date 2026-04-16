'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Row, Col, Card, Statistic, DatePicker, Button, Space, message,
} from 'antd';
import {
  ShoppingCartOutlined, DollarOutlined, ShopOutlined,
} from '@ant-design/icons';
import { Column, Pie, Line } from '@ant-design/charts';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface SalesStats {
  total_orders: number;
  total_revenue: number;
  total_products_sold: number;
}

interface CategorySales {
  category_name: string;
  sales_count: number;
  revenue: number;
}

export default function StatisticsPage() {
  const [stats, setStats] = useState<SalesStats>({ total_orders: 0, total_revenue: 0, total_products_sold: 0 });
  const [todayStats, setTodayStats] = useState<SalesStats>({ total_orders: 0, total_revenue: 0, total_products_sold: 0 });
  const [monthStats, setMonthStats] = useState<SalesStats>({ total_orders: 0, total_revenue: 0, total_products_sold: 0 });
  const [categorySales, setCategorySales] = useState<CategorySales[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [rangeStats, setRangeStats] = useState<SalesStats | null>(null);

  const fetchAllStats = useCallback(async () => {
    try {
      const res = await get('/api/admin/statistics/sales');
      if (res) {
        setStats({
          total_orders: Number(res.total_orders ?? 0),
          total_revenue: Number(res.total_revenue ?? 0),
          total_products_sold: Number(res.total_products_sold ?? 0),
        });
      }
    } catch {}
  }, []);

  const fetchTodayStats = useCallback(async () => {
    try {
      const today = dayjs().format('YYYY-MM-DD');
      const res = await get('/api/admin/statistics/sales', {
        start_date: today,
        end_date: `${today}T23:59:59`,
      });
      if (res) {
        setTodayStats({
          total_orders: Number(res.total_orders ?? 0),
          total_revenue: Number(res.total_revenue ?? 0),
          total_products_sold: Number(res.total_products_sold ?? 0),
        });
      }
    } catch {}
  }, []);

  const fetchMonthStats = useCallback(async () => {
    try {
      const monthStart = dayjs().startOf('month').format('YYYY-MM-DD');
      const monthEnd = dayjs().endOf('month').format('YYYY-MM-DD');
      const res = await get('/api/admin/statistics/sales', {
        start_date: monthStart,
        end_date: monthEnd,
      });
      if (res) {
        setMonthStats({
          total_orders: Number(res.total_orders ?? 0),
          total_revenue: Number(res.total_revenue ?? 0),
          total_products_sold: Number(res.total_products_sold ?? 0),
        });
      }
    } catch {}
  }, []);

  const fetchCategorySales = useCallback(async () => {
    try {
      const res = await get('/api/admin/products', { page: 1, page_size: 100 });
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
  }, []);

  useEffect(() => {
    fetchAllStats();
    fetchTodayStats();
    fetchMonthStats();
    fetchCategorySales();
  }, []);

  const handleRangeSearch = async () => {
    if (!dateRange?.[0] || !dateRange?.[1]) {
      message.warning('请选择日期范围');
      return;
    }
    try {
      const res = await get('/api/admin/statistics/sales', {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      });
      if (res) {
        setRangeStats({
          total_orders: Number(res.total_orders ?? 0),
          total_revenue: Number(res.total_revenue ?? 0),
          total_products_sold: Number(res.total_products_sold ?? 0),
        });
      }
    } catch {
      message.error('查询失败');
    }
  };

  const pieData = categorySales
    .filter(c => c.sales_count > 0)
    .map(c => ({
      type: c.category_name,
      value: c.sales_count,
    }));

  const revenueBarData = categorySales
    .filter(c => c.revenue > 0)
    .map(c => ({
      type: c.category_name,
      value: Math.round(c.revenue * 100) / 100,
    }));

  const salesBarData = categorySales
    .filter(c => c.sales_count > 0)
    .map(c => ({
      type: c.category_name,
      value: c.sales_count,
    }));

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数据统计</Title>

      {/* 总览卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card size="small">
            <Statistic title="今日订单" value={todayStats.total_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="今日收入" value={todayStats.total_revenue} precision={2} prefix="¥" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="本月订单" value={monthStats.total_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="本月收入" value={monthStats.total_revenue} precision={2} prefix="¥" />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="累计订单" value={stats.total_orders} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card size="small">
            <Statistic title="累计收入" value={stats.total_revenue} precision={2} prefix={<DollarOutlined />} />
          </Card>
        </Col>
      </Row>

      {/* 自定义日期范围查询 */}
      <Card size="small" title="按时间段查询" style={{ marginBottom: 24 }}>
        <Space style={{ marginBottom: 16 }}>
          <RangePicker value={dateRange as any} onChange={vals => setDateRange(vals as any)} />
          <Button type="primary" onClick={handleRangeSearch}>查询</Button>
        </Space>
        {rangeStats && (
          <Row gutter={16}>
            <Col span={8}>
              <Statistic title="订单数" value={rangeStats.total_orders} />
            </Col>
            <Col span={8}>
              <Statistic title="销售额" value={rangeStats.total_revenue} precision={2} prefix="¥" />
            </Col>
            <Col span={8}>
              <Statistic title="售出商品数" value={rangeStats.total_products_sold} />
            </Col>
          </Row>
        )}
      </Card>

      {/* 图表 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card size="small" title="各分类销售占比">
            <div style={{ height: 320 }}>
              {pieData.length > 0
                ? <Pie
                    data={pieData}
                    angleField="value"
                    colorField="type"
                    innerRadius={0.5}
                    label={{ text: 'type', position: 'outside' }}
                    legend={{ position: 'bottom' }}
                  />
                : <div style={{ textAlign: 'center', paddingTop: 120, color: '#999' }}>暂无数据</div>
              }
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="各分类销售额">
            <div style={{ height: 320 }}>
              {revenueBarData.length > 0
                ? <Column
                    data={revenueBarData}
                    xField="type"
                    yField="value"
                    colorField="type"
                    axis={{ y: { title: '金额 (¥)' } }}
                  />
                : <div style={{ textAlign: 'center', paddingTop: 120, color: '#999' }}>暂无数据</div>
              }
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card size="small" title="各分类销量">
            <div style={{ height: 320 }}>
              {salesBarData.length > 0
                ? <Column
                    data={salesBarData}
                    xField="type"
                    yField="value"
                    colorField="type"
                    axis={{ y: { title: '销量' } }}
                  />
                : <div style={{ textAlign: 'center', paddingTop: 120, color: '#999' }}>暂无数据</div>
              }
            </div>
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="总体数据">
            <Row gutter={[16, 24]} style={{ padding: '24px 0' }}>
              <Col span={8}>
                <Statistic title="总订单数" value={stats.total_orders} valueStyle={{ color: '#1890ff' }} />
              </Col>
              <Col span={8}>
                <Statistic title="总销售额" value={stats.total_revenue} precision={2} prefix="¥" valueStyle={{ color: '#52c41a' }} />
              </Col>
              <Col span={8}>
                <Statistic title="售出商品总量" value={stats.total_products_sold} valueStyle={{ color: '#faad14' }} />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
