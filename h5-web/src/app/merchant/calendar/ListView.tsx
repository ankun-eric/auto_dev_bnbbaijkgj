'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Card, Table, Tag, Dropdown, Button, message, Spin } from 'antd';
import { MoreOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';
import type { CalendarFilters, ListItem } from './types';
import { STATUS_CONFIG } from './types';

// [PRD-03 客户端改期能力收口 v1.0]
// 商家端列表视图的「改约」操作菜单已移除，改期权 100% 归客户端。

interface ListViewProps {
  storeId: number | null;
  currentDate: Dayjs;
  filters: CalendarFilters;
  onChanged?: () => void;
}

export default function ListView({
  storeId,
  currentDate,
  filters,
  onChanged,
}: ListViewProps) {
  const [items, setItems] = useState<ListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  // 默认按周加载
  const start = currentDate.subtract(currentDate.day() === 0 ? 6 : currentDate.day() - 1, 'day');
  const end = start.add(6, 'day');

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const params: any = {
        store_id: storeId,
        start_date: start.format('YYYY-MM-DD'),
        end_date: end.format('YYYY-MM-DD'),
        page,
        page_size: pageSize,
      };
      if (filters.product_ids?.length) params.product_ids = filters.product_ids;
      if (filters.staff_ids?.length) params.staff_ids = filters.staff_ids;
      if (filters.statuses?.length) params.statuses = filters.statuses;
      if (filters.sources?.length) params.sources = filters.sources;
      if (filters.q) params.q = filters.q;
      const res: any = await api.get('/api/merchant/calendar/list', { params });
      setItems(res?.items || []);
      setTotal(res?.total || 0);
    } catch {
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, currentDate.format('YYYY-MM-DD'), JSON.stringify(filters), page, pageSize]);

  useEffect(() => {
    load();
  }, [load]);

  const handleNotify = async (record: ListItem) => {
    if (!storeId) return;
    try {
      const res: any = await api.post(
        `/api/merchant/booking/${record.order_item_id}/notify`,
        { scene: 'contact_customer' },
        { params: { store_id: storeId } }
      );
      if (res?.result === 'no_subscribe') {
        message.warning('顾客未授权订阅消息');
      } else {
        message.success('通知已发送');
      }
      onChanged?.();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '通知失败');
    }
  };

  const columns = [
    { title: '日期', dataIndex: 'appointment_date', key: 'date', width: 110 },
    { title: '时间', dataIndex: 'appointment_time', key: 'time', width: 80 },
    { title: '顾客', dataIndex: 'customer_nickname', key: 'customer', width: 100 },
    {
      title: '电话',
      dataIndex: 'customer_phone',
      key: 'phone',
      width: 120,
      render: (v: string | null) => v || '-',
    },
    { title: '项目', dataIndex: 'product_name', key: 'product', width: 200 },
    {
      title: '员工',
      dataIndex: 'staff_name',
      key: 'staff',
      width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (v: keyof typeof STATUS_CONFIG) => {
        const cfg = STATUS_CONFIG[v];
        return cfg ? <Tag color={cfg.color}>{cfg.text}</Tag> : <Tag>{v}</Tag>;
      },
    },
    {
      title: '金额',
      dataIndex: 'amount',
      key: 'amount',
      width: 100,
      render: (v: number) => `¥${v}`,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (v: string | null) => v || '-',
    },
    {
      title: '操作',
      key: 'op',
      fixed: 'right' as const,
      width: 80,
      render: (_: unknown, record: ListItem) => (
        <Dropdown
          menu={{
            items: [
              {
                // [PRD-05 核销动作收口手机端 v1.0]
                // PC 端任何位置不允许发起核销，菜单项强制置灰并提示「请到手机端核销」。
                key: 'verify',
                label: '核销（请到手机端）',
                disabled: true,
                title: '请到手机端 H5 / 核销小程序发起核销',
              },
              // [PRD-03 客户端改期能力收口 v1.0] 商家端「改约」菜单项已删除
              {
                key: 'notify',
                label: '联系顾客',
                onClick: () => handleNotify(record),
              },
              {
                key: 'detail',
                label: '查看详情',
                onClick: () =>
                  (window.location.href = `/merchant/orders?highlight=${record.order_id}`),
              },
            ],
          }}
          trigger={['click']}
        >
          <Button type="text" icon={<MoreOutlined />} />
        </Dropdown>
      ),
    },
  ];

  return (
    <Card>
      <Spin spinning={loading}>
        <Table
          rowKey="order_item_id"
          dataSource={items}
          columns={columns}
          scroll={{ x: 1100 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Spin>
    </Card>
  );
}
