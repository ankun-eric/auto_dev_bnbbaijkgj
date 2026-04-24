'use client';

import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Typography, Space, Spin, Alert } from 'antd';
import {
  ShoppingCartOutlined,
  ScanOutlined,
  DollarCircleOutlined,
  FileTextOutlined,
  MessageOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import api from '@/lib/api';
import { getCurrentStoreId } from '../lib';

const { Title, Text } = Typography;

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<any>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const storeId = getCurrentStoreId();
    api
      .get('/api/merchant/v1/dashboard/metrics', { params: storeId ? { store_id: storeId } : {} })
      .then((d: any) => setData(d))
      .catch(e => setError(e?.response?.data?.detail || '数据加载失败'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin />;

  return (
    <div>
      <Title level={4}>工作台</Title>
      {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="今日订单数" value={data.today_orders || 0} prefix={<ShoppingCartOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="今日核销数" value={data.today_verifications || 0} prefix={<ScanOutlined />} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="本月 GMV"
              value={data.month_gmv || 0}
              precision={2}
              prefix={<DollarCircleOutlined />}
              suffix="元"
            />
          </Card>
        </Col>
        <Col span={8} style={{ marginTop: 16 }}>
          <Card>
            <Statistic
              title="待对账金额"
              value={data.pending_settlement || 0}
              precision={2}
              prefix={<FileTextOutlined />}
              suffix="元"
            />
          </Card>
        </Col>
        <Col span={8} style={{ marginTop: 16 }}>
          <Card>
            <Statistic title="待上传附件订单数" value={data.pending_attachments || 0} prefix={<PaperClipOutlined />} />
          </Card>
        </Col>
        <Col span={8} style={{ marginTop: 16 }}>
          <Card>
            <Statistic title="未读消息" value={data.unread_messages || 0} prefix={<MessageOutlined />} />
          </Card>
        </Col>
      </Row>
      <Card style={{ marginTop: 24 }}>
        <Space direction="vertical">
          <Text strong>平台公告</Text>
          <Text type="secondary">
            欢迎使用宾尼小康商家/机构工作台。本页呈现您所属门店的经营核心指标，左侧菜单可进入各业务模块。
          </Text>
        </Space>
      </Card>
    </div>
  );
}
