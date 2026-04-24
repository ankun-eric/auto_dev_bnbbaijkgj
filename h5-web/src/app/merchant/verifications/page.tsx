'use client';

import React, { useEffect, useState } from 'react';
import { Table, Typography, DatePicker, Space, Button, message } from 'antd';
import api from '@/lib/api';
import dayjs from 'dayjs';
import { getCurrentStoreId } from '../lib';

const { Title } = Typography;
const { RangePicker } = DatePicker;

export default function VerificationsPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  const load = async (p = 1) => {
    setLoading(true);
    try {
      const params: any = { page: p, page_size: 20 };
      const sid = getCurrentStoreId();
      if (sid) params.store_id = sid;
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD');
        params.end_date = dateRange[1].format('YYYY-MM-DD');
      }
      const res: any = await api.get('/api/merchant/v1/verifications', { params });
      setRows(res.items || []);
      setTotal(res.total || 0);
      setPage(p);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(1); }, []); // eslint-disable-line

  return (
    <div>
      <Title level={4}>核销记录</Title>
      <Space style={{ marginBottom: 16 }}>
        <RangePicker value={dateRange as any} onChange={v => setDateRange(v as any)} />
        <Button type="primary" onClick={() => load(1)}>查询</Button>
      </Space>
      <Table
        rowKey="id"
        loading={loading}
        dataSource={rows}
        pagination={{ current: page, total, pageSize: 20, onChange: p => load(p), showSizeChanger: false }}
        columns={[
          { title: '核销时间', dataIndex: 'verified_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
          { title: '订单号', dataIndex: 'order_no' },
          { title: '商品', dataIndex: 'product_name' },
          { title: '用户', dataIndex: 'user_display' },
          { title: '门店', dataIndex: 'store_name' },
          { title: '核销员', dataIndex: 'verifier_name' },
        ] as any}
      />
    </div>
  );
}
