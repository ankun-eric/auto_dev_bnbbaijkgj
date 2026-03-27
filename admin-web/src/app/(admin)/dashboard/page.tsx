'use client';

import React, { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Typography, Spin } from 'antd';
import {
  UserOutlined,
  ShoppingCartOutlined,
  RobotOutlined,
  DollarOutlined,
  ArrowUpOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface DashboardData {
  totalUsers: number;
  todayOrders: number;
  aiCalls: number;
  totalRevenue: number;
  userGrowth: { date: string; count: number }[];
  orderTrend: { date: string; count: number }[];
  recentOrders: any[];
}

const defaultData: DashboardData = {
  totalUsers: 12856,
  todayOrders: 328,
  aiCalls: 15672,
  totalRevenue: 298650,
  userGrowth: [
    { date: '03-21', count: 120 },
    { date: '03-22', count: 185 },
    { date: '03-23', count: 156 },
    { date: '03-24', count: 210 },
    { date: '03-25', count: 198 },
    { date: '03-26', count: 245 },
    { date: '03-27', count: 280 },
  ],
  orderTrend: [
    { date: '03-21', count: 45 },
    { date: '03-22', count: 62 },
    { date: '03-23', count: 58 },
    { date: '03-24', count: 73 },
    { date: '03-25', count: 68 },
    { date: '03-26', count: 85 },
    { date: '03-27', count: 92 },
  ],
  recentOrders: [
    { id: 'ORD20260327001', user: '张三', service: 'AI健康咨询', amount: 99, status: 'paid', time: '2026-03-27 10:30' },
    { id: 'ORD20260327002', user: '李四', service: '营养方案定制', amount: 299, status: 'completed', time: '2026-03-27 09:15' },
    { id: 'ORD20260327003', user: '王五', service: '体检报告解读', amount: 49, status: 'paid', time: '2026-03-27 08:42' },
    { id: 'ORD20260326004', user: '赵六', service: '中医体质辨识', amount: 199, status: 'refunded', time: '2026-03-26 18:20' },
    { id: 'ORD20260326005', user: '孙七', service: '心理健康评估', amount: 149, status: 'completed', time: '2026-03-26 16:05' },
  ],
};

const statusMap: Record<string, { color: string; text: string }> = {
  paid: { color: 'blue', text: '已支付' },
  completed: { color: 'green', text: '已完成' },
  refunded: { color: 'red', text: '已退款' },
  pending: { color: 'orange', text: '待支付' },
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData>(defaultData);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/dashboard');
      if (res) {
        setData(res.data || res);
      }
    } catch {
      // Use default mock data
    } finally {
      setLoading(false);
    }
  };

  const statCards = [
    {
      title: '总用户数',
      value: data.totalUsers,
      icon: <UserOutlined />,
      color: '#52c41a',
      bg: 'linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%)',
    },
    {
      title: '今日订单',
      value: data.todayOrders,
      icon: <ShoppingCartOutlined />,
      color: '#13c2c2',
      bg: 'linear-gradient(135deg, #e6fffb 0%, #b5f5ec 100%)',
    },
    {
      title: 'AI调用次数',
      value: data.aiCalls,
      icon: <RobotOutlined />,
      color: '#1890ff',
      bg: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)',
    },
    {
      title: '总收入 (元)',
      value: data.totalRevenue,
      icon: <DollarOutlined />,
      color: '#faad14',
      bg: 'linear-gradient(135deg, #fffbe6 0%, #ffe58f 100%)',
    },
  ];

  const orderColumns = [
    { title: '订单号', dataIndex: 'id', key: 'id', width: 180 },
    { title: '用户', dataIndex: 'user', key: 'user', width: 100 },
    { title: '服务', dataIndex: 'service', key: 'service' },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      render: (v: number) => `¥${v.toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        const s = statusMap[v] || { color: 'default', text: v };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    { title: '时间', dataIndex: 'time', key: 'time', width: 180 },
  ];

  const maxGrowth = Math.max(...data.userGrowth.map((d) => d.count));
  const maxOrder = Math.max(...data.orderTrend.map((d) => d.count));

  return (
    <Spin spinning={loading}>
      <Title level={4} style={{ marginBottom: 24 }}>
        数据概览
      </Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {statCards.map((card, idx) => (
          <Col xs={24} sm={12} lg={6} key={idx}>
            <div className="stat-card" style={{ background: card.bg }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ color: '#666', fontSize: 14, marginBottom: 8 }}>{card.title}</div>
                  <Statistic
                    value={card.value}
                    valueStyle={{ color: card.color, fontSize: 28, fontWeight: 600 }}
                    prefix={card.title === '总收入 (元)' ? '¥' : undefined}
                    suffix={
                      <span style={{ fontSize: 14, color: '#52c41a', marginLeft: 8 }}>
                        <ArrowUpOutlined /> 12%
                      </span>
                    }
                  />
                </div>
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 12,
                    background: `${card.color}20`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 24,
                    color: card.color,
                  }}
                >
                  {card.icon}
                </div>
              </div>
            </div>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="用户增长趋势" size="small" style={{ borderRadius: 12 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 200, padding: '16px 0' }}>
              {data.userGrowth.map((item, idx) => (
                <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 12, color: '#666' }}>{item.count}</span>
                  <div
                    style={{
                      width: '100%',
                      maxWidth: 40,
                      height: `${(item.count / maxGrowth) * 140}px`,
                      background: 'linear-gradient(180deg, #52c41a 0%, #95de64 100%)',
                      borderRadius: '4px 4px 0 0',
                      transition: 'height 0.5s',
                    }}
                  />
                  <span style={{ fontSize: 11, color: '#999' }}>{item.date}</span>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="订单量趋势" size="small" style={{ borderRadius: 12 }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 200, padding: '16px 0' }}>
              {data.orderTrend.map((item, idx) => (
                <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                  <span style={{ fontSize: 12, color: '#666' }}>{item.count}</span>
                  <div
                    style={{
                      width: '100%',
                      maxWidth: 40,
                      height: `${(item.count / maxOrder) * 140}px`,
                      background: 'linear-gradient(180deg, #13c2c2 0%, #87e8de 100%)',
                      borderRadius: '4px 4px 0 0',
                      transition: 'height 0.5s',
                    }}
                  />
                  <span style={{ fontSize: 11, color: '#999' }}>{item.date}</span>
                </div>
              ))}
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="最近订单" size="small" style={{ borderRadius: 12 }}>
        <Table
          columns={orderColumns}
          dataSource={data.recentOrders}
          rowKey="id"
          pagination={false}
          size="middle"
        />
      </Card>
    </Spin>
  );
}
