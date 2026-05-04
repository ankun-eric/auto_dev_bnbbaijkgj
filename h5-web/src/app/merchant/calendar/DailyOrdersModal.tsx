'use client';

/**
 * 预约日历「当日订单弹窗」（PC 端） — PRD「当日订单弹窗」v1.0
 *
 * 触发：点击日历中订单数 ≥ 1 的日期单元格
 * 内容：
 *   - 标题：YYYY年M月D日 周X · 当日订单（共 N 单）
 *   - Tab：全部 / 待核销 / 已核销 / 已取消 / 已退款（含计数）
 *   - 表格：时段 / 客户 / 服务项目 / 状态 / 操作
 *   - 行就地展开详情：客户备注 / 服务地点 / 客户手机号(拨号+复制) / 核销状态 /
 *                    核销时间(verified) / 核销码(verified) / 取消时间(cancelled) /
 *                    退款时间(refunded) / 取消/退款原因
 *   - 关闭：右上角 × + 点击遮罩 + ESC
 */
import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { Modal, Tabs, Table, Tag, Button, Space, Empty, Spin, message, Descriptions, Typography } from 'antd';
import {
  PhoneOutlined,
  CopyOutlined,
  EyeOutlined,
  DownOutlined,
  UpOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '@/lib/api';

const { Text } = Typography;

export type DailyOrderStatus = 'pending' | 'verified' | 'cancelled' | 'refunded' | 'other';

export interface DailyOrder {
  order_id: number;
  order_item_id: number;
  order_no?: string;
  time_slot?: string;
  appointment_time?: string;
  customer_nickname?: string;
  customer_phone?: string;
  service_name?: string;
  service_location?: string;
  status: DailyOrderStatus;
  remark?: string;
  verify_time?: string;
  verify_code?: string;
  cancel_time?: string;
  cancel_reason?: string;
  refund_time?: string;
  refund_reason?: string;
}

interface DailyOrdersResponseData {
  date: string;
  total: number;
  by_status: { pending: number; verified: number; cancelled: number; refunded: number };
  orders: DailyOrder[];
}

interface DailyOrdersModalProps {
  open: boolean;
  date: string | null;
  storeId?: number | null;
  onClose: () => void;
}

const STATUS_TAG: Record<DailyOrderStatus, { text: string; color: string }> = {
  pending: { text: '待核销', color: 'orange' },
  verified: { text: '已核销', color: 'green' },
  cancelled: { text: '已取消', color: 'red' },
  refunded: { text: '已退款', color: 'magenta' },
  other: { text: '其它', color: 'default' },
};

const WEEKDAY_CN = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

function formatDateTitle(date: string | null, total: number): string {
  if (!date) return '当日订单';
  const d = dayjs(date);
  if (!d.isValid()) return `${date} · 当日订单（共 ${total} 单）`;
  return `${d.year()}年${d.month() + 1}月${d.date()}日 ${WEEKDAY_CN[d.day()]} · 当日订单（共 ${total} 单）`;
}

function formatDateTimeStr(s?: string | null): string {
  if (!s) return '—';
  const d = dayjs(s);
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm:ss') : s;
}

function formatPhone(p?: string): string {
  if (!p) return '—';
  const digits = p.replace(/\D/g, '');
  if (digits.length === 11) return `${digits.slice(0, 3)} ${digits.slice(3, 7)} ${digits.slice(7)}`;
  return p;
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    // 降级到 execCommand
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export default function DailyOrdersModal({ open, date, storeId, onClose }: DailyOrdersModalProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<DailyOrdersResponseData | null>(null);
  const [activeTab, setActiveTab] = useState<DailyOrderStatus | 'all'>('all');
  const [expandedKey, setExpandedKey] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    if (!open || !date) return;
    setLoading(true);
    try {
      const params: Record<string, unknown> = { date };
      if (storeId) params.store_id = storeId;
      const res = await api.get('/api/merchant/calendar/daily-orders', { params });
      const payload = (res?.data ?? res) as DailyOrdersResponseData;
      setData(payload);
    } catch {
      setData(null);
      message.error('加载失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [open, date, storeId]);

  useEffect(() => {
    if (open) {
      setActiveTab('all');
      setExpandedKey(null);
      loadData();
    } else {
      setData(null);
      setExpandedKey(null);
    }
  }, [open, loadData]);

  const handleTabChange = (key: string) => {
    setActiveTab(key as DailyOrderStatus | 'all');
    setExpandedKey(null);
  };

  const filteredOrders = useMemo(() => {
    if (!data) return [];
    if (activeTab === 'all') return data.orders;
    return data.orders.filter((o) => o.status === activeTab);
  }, [data, activeTab]);

  const total = data?.total ?? 0;
  const counts = data?.by_status ?? { pending: 0, verified: 0, cancelled: 0, refunded: 0 };

  const handlePhoneCall = (phone?: string, orderNo?: string) => {
    if (!phone) return;
    // 仅做埋点占位 + 拨号 tel:
    try {
      // eslint-disable-next-line no-console
      console.info('[track] calendar_daily_phone_call', { order_no: orderNo, phone_len: phone.length });
    } catch {}
    const digits = phone.replace(/\D/g, '');
    window.location.href = `tel:${digits}`;
  };

  const handleCopyPhone = async (phone?: string, orderNo?: string) => {
    if (!phone) return;
    const ok = await copyToClipboard(phone.replace(/\D/g, ''));
    if (ok) {
      message.success('已复制到剪贴板');
      try {
        // eslint-disable-next-line no-console
        console.info('[track] calendar_daily_phone_copy', { order_no: orderNo });
      } catch {}
    } else {
      message.warning('复制失败，请手动选取');
    }
  };

  const handleExpandToggle = (orderItemId: number) => {
    setExpandedKey((cur) => (cur === orderItemId ? null : orderItemId));
  };

  const handleViewFullOrder = (order: DailyOrder) => {
    try {
      // eslint-disable-next-line no-console
      console.info('[track] calendar_daily_view_full_order', { order_no: order.order_no });
    } catch {}
    window.location.href = `/merchant/orders?highlight=${order.order_id}`;
  };

  const renderDetail = (order: DailyOrder) => {
    const isVerified = order.status === 'verified';
    const isCancelled = order.status === 'cancelled';
    const isRefunded = order.status === 'refunded';
    const cfg = STATUS_TAG[order.status];
    return (
      <div style={{ background: '#fafbfc', padding: 16, borderRadius: 6, border: '1px solid #f0f0f0' }}>
        <Descriptions column={1} size="small" labelStyle={{ width: 110, color: '#8c8c8c' }}>
          <Descriptions.Item label="客户备注">{order.remark || '—'}</Descriptions.Item>
          <Descriptions.Item label="服务地点">{order.service_location || '—'}</Descriptions.Item>
          <Descriptions.Item label="客户手机号">
            <Space size={8} wrap>
              <Text style={{ fontFamily: 'Menlo, Consolas, monospace', fontSize: 14 }}>
                {formatPhone(order.customer_phone)}
              </Text>
              <Button
                size="small"
                icon={<PhoneOutlined />}
                onClick={() => handlePhoneCall(order.customer_phone, order.order_no)}
                disabled={!order.customer_phone}
              >
                拨打
              </Button>
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={() => handleCopyPhone(order.customer_phone, order.order_no)}
                disabled={!order.customer_phone}
              >
                复制
              </Button>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="核销状态">
            <Tag color={cfg.color}>{cfg.text}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="核销时间">
            {isVerified ? formatDateTimeStr(order.verify_time) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="核销码">
            {isVerified ? (
              <Text code style={{ fontSize: 13 }}>
                {order.verify_code || '—'}
              </Text>
            ) : (
              '—'
            )}
          </Descriptions.Item>
          {isCancelled && (
            <>
              <Descriptions.Item label="取消时间">{formatDateTimeStr(order.cancel_time)}</Descriptions.Item>
              {order.cancel_reason && (
                <Descriptions.Item label="取消原因">{order.cancel_reason}</Descriptions.Item>
              )}
            </>
          )}
          {isRefunded && (
            <>
              <Descriptions.Item label="退款时间">{formatDateTimeStr(order.refund_time)}</Descriptions.Item>
              {order.refund_reason && (
                <Descriptions.Item label="退款原因">{order.refund_reason}</Descriptions.Item>
              )}
            </>
          )}
        </Descriptions>
        <div style={{ marginTop: 12, textAlign: 'right' }}>
          <Button type="primary" icon={<EyeOutlined />} onClick={() => handleViewFullOrder(order)}>
            查看完整订单
          </Button>
        </div>
      </div>
    );
  };

  const columns = [
    {
      title: '时段',
      dataIndex: 'time_slot',
      key: 'time_slot',
      width: 130,
      render: (v: string) => v || '—',
    },
    {
      title: '客户',
      dataIndex: 'customer_nickname',
      key: 'customer_nickname',
      width: 120,
      render: (v: string) => v || '—',
    },
    {
      title: '服务项目',
      dataIndex: 'service_name',
      key: 'service_name',
      ellipsis: true,
      render: (v: string) => v || '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: DailyOrderStatus) => {
        const cfg = STATUS_TAG[s] || STATUS_TAG.other;
        return <Tag color={cfg.color}>{cfg.text}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 130,
      render: (_: unknown, record: DailyOrder) => (
        <Space size={4}>
          <Button
            size="small"
            type="link"
            icon={expandedKey === record.order_item_id ? <UpOutlined /> : <DownOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              handleExpandToggle(record.order_item_id);
            }}
          >
            {expandedKey === record.order_item_id ? '收起' : '展开'}
          </Button>
          <Button
            size="small"
            type="link"
            onClick={(e) => {
              e.stopPropagation();
              handleViewFullOrder(record);
            }}
          >
            完整订单
          </Button>
        </Space>
      ),
    },
  ];

  const tabItems = [
    { key: 'all', label: `全部(${total})` },
    { key: 'pending', label: `待核销(${counts.pending})` },
    { key: 'verified', label: `已核销(${counts.verified})` },
    { key: 'cancelled', label: `已取消(${counts.cancelled})` },
    { key: 'refunded', label: `已退款(${counts.refunded})` },
  ];

  return (
    <Modal
      title={formatDateTitle(date, total)}
      open={open}
      onCancel={onClose}
      width={920}
      maskClosable={true}
      keyboard={true}
      footer={null}
      destroyOnClose
      styles={{ body: { maxHeight: 'calc(80vh - 110px)', overflowY: 'auto' } }}
    >
      <Tabs activeKey={activeTab} items={tabItems} onChange={handleTabChange} />
      <Spin spinning={loading}>
        {filteredOrders.length === 0 ? (
          <div style={{ padding: '48px 0' }}>
            <Empty description="该状态下暂无记录" />
          </div>
        ) : (
          <Table
            rowKey="order_item_id"
            dataSource={filteredOrders}
            columns={columns}
            pagination={false}
            size="middle"
            onRow={(record) => ({
              onClick: () => handleExpandToggle(record.order_item_id),
              style: { cursor: 'pointer' },
            })}
            expandable={{
              expandedRowKeys: expandedKey ? [expandedKey] : [],
              showExpandColumn: false,
              expandedRowRender: (record) => renderDetail(record),
            }}
          />
        )}
      </Spin>
    </Modal>
  );
}
