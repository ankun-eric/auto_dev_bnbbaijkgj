'use client';

import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Typography, Radio, Statistic, Table, message, Space } from 'antd';
import api from '@/lib/api';

const { Title } = Typography;

export default function ReportsPage() {
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('day');
  const [dim, setDim] = useState<'merchant' | 'store'>('merchant');
  const [data, setData] = useState<any>({});
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/reports', { params: { period, dim } });
      setData(res || {});
    } catch (e: any) { message.error(e?.response?.data?.detail || '加载失败'); } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [period, dim]);

  return (
    <div>
      <Title level={4}>报表分析</Title>
      <Space style={{ marginBottom: 16 }}>
        <Radio.Group value={period} onChange={e => setPeriod(e.target.value)}>
          <Radio.Button value="day">日</Radio.Button>
          <Radio.Button value="week">周</Radio.Button>
          <Radio.Button value="month">月</Radio.Button>
        </Radio.Group>
        <Radio.Group value={dim} onChange={e => setDim(e.target.value)}>
          <Radio.Button value="merchant">机构维度</Radio.Button>
          <Radio.Button value="store">门店维度</Radio.Button>
        </Radio.Group>
      </Space>
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="订单数" value={data.total_orders || 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="核销数" value={data.total_verifications || 0} /></Card></Col>
        <Col span={6}><Card><Statistic title="GMV" value={data.total_gmv || 0} precision={2} suffix="元" /></Card></Col>
        <Col span={6}><Card><Statistic title="TOP商品数" value={(data.top_products || []).length} /></Card></Col>
      </Row>
      <Card title="趋势数据" style={{ marginTop: 16 }} loading={loading}>
        <Table
          rowKey={(r: any) => r.label}
          dataSource={data.series || []}
          pagination={false}
          columns={[
            { title: '时间', dataIndex: 'label' },
            { title: '订单数', dataIndex: 'orders' },
            { title: '核销数', dataIndex: 'verifications' },
            { title: 'GMV', dataIndex: 'gmv', render: (v: number) => `¥${(v || 0).toFixed(2)}` },
          ]}
        />
      </Card>
      <Card title="TOP 商品" style={{ marginTop: 16 }}>
        <Table
          rowKey={(r: any, i?: number) => `${r.name}_${i}`}
          dataSource={data.top_products || []}
          pagination={false}
          columns={[
            { title: '商品', dataIndex: 'name' },
            { title: '订单数', dataIndex: 'count' },
            { title: 'GMV', dataIndex: 'gmv', render: (v: number) => `¥${(v || 0).toFixed(2)}` },
          ]}
        />
      </Card>
    </div>
  );
}
