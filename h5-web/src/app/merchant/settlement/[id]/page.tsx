'use client';

import React, { useEffect, useState } from 'react';
import { Card, Descriptions, Table, Typography, Tag, Space, Button, message } from 'antd';
import api from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import dayjs from 'dayjs';

const { Title } = Typography;

export default function SettlementDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params?.id;
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (!id) return;
    api.get(`/api/merchant/v1/settlements/${id}`).then(setData).catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'));
  }, [id]);

  if (!data) return null;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button onClick={() => router.back()}>返回</Button>
        <Button onClick={() => window.print()}>打印</Button>
      </Space>
      <Title level={4}>对账单详情 - {data.statement_no}</Title>
      <Card>
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="账单号">{data.statement_no}</Descriptions.Item>
          <Descriptions.Item label="周期">{data.period_start} ~ {data.period_end}</Descriptions.Item>
          <Descriptions.Item label="维度">{data.dim === 'merchant' ? '机构合并' : '门店'}</Descriptions.Item>
          <Descriptions.Item label="门店ID">{data.store_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="订单数">{data.order_count}</Descriptions.Item>
          <Descriptions.Item label="订单总额">¥{(data.total_amount || 0).toFixed(2)}</Descriptions.Item>
          <Descriptions.Item label="应结金额">¥{(data.settlement_amount || 0).toFixed(2)}</Descriptions.Item>
          <Descriptions.Item label="状态"><Tag>{data.status}</Tag></Descriptions.Item>
          <Descriptions.Item label="确认时间">{data.confirmed_at && dayjs(data.confirmed_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
          <Descriptions.Item label="结清时间">{data.settled_at && dayjs(data.settled_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
