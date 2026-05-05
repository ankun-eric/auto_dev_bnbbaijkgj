'use client';

// [PRD-03 客户端改期能力收口 v1.0]
// 商家端 Popover 已移除「改约」按钮，改期权 100% 归客户端。
// [PRD-05 核销动作收口手机端 v1.0]
// PC 端不允许发起核销，「核销」按钮置灰，悬浮提示「请到手机端核销」。
// 仅保留：核销（PC 置灰）/ 联系顾客 / 查看详情 三项操作。

import React from 'react';
import { Popover, Button, Space, Tooltip, message } from 'antd';
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
    <Space direction="vertical" size={4} style={{ minWidth: 160 }}>
      {/*
        [PRD-05 核销动作收口手机端 v1.0]
        PC 端任何位置不允许发起核销：核销按钮强制置灰，
        鼠标悬浮提示「请到手机端核销」。
      */}
      <Tooltip title="PC 端不允许发起核销，请到手机端 H5 / 核销小程序操作">
        <Button
          block
          type="text"
          icon={<CheckCircleOutlined />}
          disabled
        >
          核销（请到手机端）
        </Button>
      </Tooltip>
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
