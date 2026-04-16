'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, message, Typography, Row, Col, DatePicker, Select, Card, Statistic, Input,
} from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface RedemptionRecord {
  id: number;
  order_item_id: number;
  product_name: string;
  product_price: number;
  verification_code: string;
  total_redeem_count: number;
  used_redeem_count: number;
  fulfillment_type: string;
  user_id: number;
  order_no: string;
  created_at: string;
}

interface StoreOption {
  label: string;
  value: number;
}

const fulfillmentMap: Record<string, string> = {
  in_store: '到店服务',
  delivery: '快递配送',
  virtual: '虚拟商品',
};

export default function RedemptionsPage() {
  const [records, setRecords] = useState<RedemptionRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [storeOptions, setStoreOptions] = useState<StoreOption[]>([]);
  const [filterStore, setFilterStore] = useState<number | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [stats, setStats] = useState({ total: 0, today: 0 });

  const fetchStores = useCallback(async () => {
    try {
      const res = await get('/api/admin/merchant/stores');
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          setStoreOptions(items.map((s: any) => ({ label: String(s.store_name || s.name || ''), value: Number(s.id) })));
        }
      }
    } catch {}
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize, status: 'pending_use' };
      if (searchText) params.keyword = searchText;

      const res = await get('/api/admin/orders/unified', params);
      if (res) {
        const raw = res.items || res.list || res;
        const orders = Array.isArray(raw) ? raw : [];

        const redeemRecords: RedemptionRecord[] = [];
        for (const order of orders) {
          const items = Array.isArray(order.items) ? order.items : [];
          for (const item of items) {
            if (item.verification_code) {
              redeemRecords.push({
                id: Number(item.id),
                order_item_id: Number(item.id),
                product_name: String(item.product_name ?? ''),
                product_price: Number(item.product_price ?? 0),
                verification_code: String(item.verification_code),
                total_redeem_count: Number(item.total_redeem_count ?? 0),
                used_redeem_count: Number(item.used_redeem_count ?? 0),
                fulfillment_type: String(item.fulfillment_type ?? ''),
                user_id: Number(order.user_id ?? 0),
                order_no: String(order.order_no ?? ''),
                created_at: String(order.created_at ?? ''),
              });
            }
          }
        }

        setRecords(redeemRecords);
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? redeemRecords.length }));

        const today = dayjs().format('YYYY-MM-DD');
        const todayCount = redeemRecords.filter(r => r.created_at.startsWith(today)).length;
        setStats({ total: redeemRecords.length, today: todayCount });
      }
    } catch {
      setRecords([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [searchText, dateRange, filterStore]);

  useEffect(() => {
    fetchStores();
    fetchData();
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const columns = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 200 },
    { title: '用户ID', dataIndex: 'user_id', key: 'user_id', width: 80 },
    { title: '商品', dataIndex: 'product_name', key: 'product_name', width: 180, ellipsis: true },
    {
      title: '单价', dataIndex: 'product_price', key: 'product_price', width: 90,
      render: (v: number) => <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{v}</span>,
    },
    { title: '核销码', dataIndex: 'verification_code', key: 'verification_code', width: 120 },
    {
      title: '核销进度', key: 'progress', width: 120,
      render: (_: unknown, record: RedemptionRecord) => (
        <span>
          <Tag color={record.used_redeem_count >= record.total_redeem_count ? 'green' : 'orange'}>
            {record.used_redeem_count}/{record.total_redeem_count}
          </Tag>
        </span>
      ),
    },
    {
      title: '状态', key: 'status', width: 90,
      render: (_: unknown, record: RedemptionRecord) => {
        if (record.used_redeem_count >= record.total_redeem_count) return <Tag color="green">已完成</Tag>;
        if (record.used_redeem_count > 0) return <Tag color="blue">部分核销</Tag>;
        return <Tag color="orange">待核销</Tag>;
      },
    },
    {
      title: '类型', dataIndex: 'fulfillment_type', key: 'fulfillment_type', width: 90,
      render: (v: string) => fulfillmentMap[v] || v,
    },
    {
      title: '下单时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>核销管理</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small"><Statistic title="核销记录总数" value={stats.total} /></Card>
        </Col>
        <Col span={6}>
          <Card size="small"><Statistic title="今日核销" value={stats.today} /></Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select
            placeholder="按门店筛选"
            allowClear
            style={{ width: 160 }}
            options={storeOptions}
            value={filterStore}
            onChange={v => setFilterStore(v)}
          />
        </Col>
        <Col>
          <RangePicker value={dateRange as any} onChange={vals => setDateRange(vals as any)} />
        </Col>
        <Col>
          <Input
            placeholder="搜索订单号"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 220 }}
            allowClear
          />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1200 }}
      />
    </div>
  );
}
