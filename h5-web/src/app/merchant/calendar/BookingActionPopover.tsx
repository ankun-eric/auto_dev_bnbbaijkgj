'use client';

// [PRD-03 客户端改期能力收口 v1.0]
// 商家端 Popover 已移除「改约」按钮，改期权 100% 归客户端。
// 仅保留：核销 / 联系顾客 / 查看详情 三项操作。

import React from 'react';
import { Popover, Button, Space, message } from 'antd';
import {
  CheckCircleOutlined,
  PhoneOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import api from '@/lib/api';
import type { ItemCard } from './types';

interface ActionPopoverProps {
  storeId: number | null;
  card: ItemCard;
  children: React.ReactNode;
  onChanged?: () => void;
}

export default function BookingActionPopover({
  storeId,
  card,
  children,
  onChanged,
}: ActionPopoverProps) {
  const goToDetail = () => {
    window.location.href = `/merchant/orders?highlight=${card.order_id}`;
  };

  const handleVerify = () => {
    window.location.href = `/merchant/verifications?order=${card.order_id}`;
  };

  const handleNotify = async () => {
    if (!storeId) return;
    try {
      const res: any = await api.post(
        `/api/merchant/booking/${card.order_item_id}/notify`,
        { scene: 'contact_customer' },
        { params: { store_id: storeId } }
      );
      if (res?.result === 'success') {
        message.success('通知已发送');
      } else if (res?.result === 'no_subscribe') {
        message.warning('顾客未授权订阅消息，请直接拨打电话');
      } else {
        message.error('通知发送失败');
      }
      onChanged?.();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '通知失败');
    }
  };

  const content = (
    <Space direction="vertical" size={4} style={{ minWidth: 140 }}>
      <Button
        block
        type="text"
        icon={<CheckCircleOutlined />}
        onClick={handleVerify}
        disabled={card.status !== 'pending'}
      >
        核销
      </Button>
      {/* [PRD-03 客户端改期能力收口 v1.0] 商家端「改约」按钮已删除 */}
      <Button block type="text" icon={<PhoneOutlined />} onClick={handleNotify}>
        联系顾客
      </Button>
      <Button block type="text" icon={<EyeOutlined />} onClick={goToDetail}>
        查看详情
      </Button>
    </Space>
  );

  return (
    <Popover content={content} trigger="click" placement="rightTop">
      {children}
    </Popover>
  );
}
