'use client';

/**
 * [2026-05-05 订单页地址导航按钮 PRD v1.0] 通用「导航」按钮
 *
 * 用于下单页（checkout）与订单明细页（unified-order/[id]）所有地址展示行的右侧。
 * 视觉风格与商家详情页/ContactStoreModal 的"导航"按钮保持一致（绿色 #52c41a）。
 *
 * 行为：
 *   - 点击后弹出 MapNavSheet 选择地图 App
 *   - 有经纬度 → 直接路线规划
 *   - 无经纬度 → 用文字地址作为关键词调起地图（PRD F-08）
 *   - 500ms 防抖（PRD E-09）
 */

import React, { useState, useRef, useCallback } from 'react';
import MapNavSheet, { MapNavTarget } from './MapNavSheet';

interface Props {
  /** 目的地名称（门店名 / 收件人姓名 / 默认"目的地"） */
  name: string;
  /** 文字地址（无经纬度时作为关键词使用） */
  address?: string;
  /** GCJ-02 高德坐标系经度（可选） */
  lng?: number | null;
  /** GCJ-02 高德坐标系纬度（可选） */
  lat?: number | null;
  /** 自定义内联样式（用于尺寸微调） */
  style?: React.CSSProperties;
  /** 调试/无障碍 label */
  ariaLabel?: string;
}

export default function AddressNavButton({
  name,
  address,
  lat,
  lng,
  style,
  ariaLabel,
}: Props) {
  const [visible, setVisible] = useState(false);
  const lastClickRef = useRef<number>(0);

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      // 防止冒泡触发外层卡片点击事件（如 checkout 页门店卡片本身有 onClick）
      e.stopPropagation();
      const now = Date.now();
      if (now - lastClickRef.current < 500) return;
      lastClickRef.current = now;
      setVisible(true);
    },
    [],
  );

  const target: MapNavTarget = {
    name: name || '目的地',
    address: address || undefined,
    lat: lat ?? null,
    lng: lng ?? null,
  };

  return (
    <>
      <div
        role="button"
        aria-label={ariaLabel || '导航'}
        onClick={handleClick}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          background: '#52c41a15',
          color: '#52c41a',
          padding: '6px 12px',
          borderRadius: 16,
          fontSize: 12,
          fontWeight: 600,
          flexShrink: 0,
          cursor: 'pointer',
          userSelect: 'none',
          ...style,
        }}
      >
        <span aria-hidden="true">📍</span>
        <span>导航</span>
      </div>
      <MapNavSheet visible={visible} target={target} onClose={() => setVisible(false)} />
    </>
  );
}
