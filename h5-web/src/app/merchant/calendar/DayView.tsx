'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Card, Spin, Tag, Empty, Typography } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';
import type { CalendarFilters, ItemCard } from './types';
import { STATUS_CONFIG } from './types';
import BookingActionPopover from './BookingActionPopover';

const { Text } = Typography;

// [PRD-03 客户端改期能力收口 v1.0] 商家端「改约」入口已移除
interface DayViewProps {
  storeId: number | null;
  currentDate: Dayjs;
  filters: CalendarFilters;
  onChanged?: () => void;
}

// 30 分钟粒度，9:00 ~ 20:00 共 22 行
const TIME_SLOTS: string[] = (() => {
  const slots: string[] = [];
  for (let h = 9; h < 20; h++) {
    slots.push(`${String(h).padStart(2, '0')}:00`);
    slots.push(`${String(h).padStart(2, '0')}:30`);
  }
  return slots;
})();

function timeKey(t?: string | null): string {
  if (!t) return '';
  const d = dayjs(t);
  if (!d.isValid()) return '';
  const m = d.minute();
  const half = m >= 30 ? '30' : '00';
  return `${String(d.hour()).padStart(2, '0')}:${half}`;
}

export default function DayView({
  storeId,
  currentDate,
  filters,
  onChanged,
}: DayViewProps) {
  const [items, setItems] = useState<ItemCard[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const ds = currentDate.format('YYYY-MM-DD');
      const params: any = {
        store_id: storeId,
        start_date: ds,
        end_date: ds,
        group_by: 'service',
      };
      if (filters.product_ids?.length) params.product_ids = filters.product_ids;
      if (filters.staff_ids?.length) params.staff_ids = filters.staff_ids;
      if (filters.statuses?.length) params.statuses = filters.statuses;
      if (filters.sources?.length) params.sources = filters.sources;
      if (filters.q) params.q = filters.q;
      const res: any = await api.get('/api/merchant/calendar/items', { params });
      setItems(res?.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId, currentDate.format('YYYY-MM-DD'), JSON.stringify(filters)]);

  useEffect(() => {
    load();
  }, [load]);

  // 按服务项目分组
  const products = useMemo(() => {
    const map = new Map<string, { id?: number; name: string }>();
    items.forEach((it) => {
      const key = String(it.product_id ?? it.product_name ?? '其它');
      if (!map.has(key)) {
        map.set(key, { id: it.product_id ?? undefined, name: it.product_name || '未命名服务' });
      }
    });
    return Array.from(map.values());
  }, [items]);

  // 二维 grid: time_slot × product_id
  const cellMap = useMemo(() => {
    const m: Record<string, ItemCard[]> = {};
    items.forEach((it) => {
      const t = timeKey(it.appointment_time);
      const p = String(it.product_id ?? it.product_name ?? '其它');
      const k = `${t}|${p}`;
      m[k] = m[k] || [];
      m[k].push(it);
    });
    return m;
  }, [items]);

  return (
    <Spin spinning={loading}>
      <Card title={`${currentDate.format('YYYY 年 M 月 D 日')}（${items.length} 个预约）`}>
        {products.length === 0 ? (
          <Empty description="当天暂无预约" />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: `80px repeat(${products.length}, minmax(160px, 1fr))`,
                border: '1px solid #f0f0f0',
                borderRadius: 6,
              }}
            >
              {/* 表头 */}
              <div style={{ padding: 8, background: '#fafafa', borderBottom: '1px solid #f0f0f0', borderRight: '1px solid #f0f0f0' }}>
                <Text strong>时段</Text>
              </div>
              {products.map((p) => (
                <div
                  key={String(p.id ?? p.name)}
                  style={{ padding: 8, background: '#fafafa', borderBottom: '1px solid #f0f0f0', borderRight: '1px solid #f0f0f0' }}
                >
                  <Text strong>{p.name}</Text>
                </div>
              ))}
              {/* 行 */}
              {TIME_SLOTS.map((t) => (
                <React.Fragment key={t}>
                  <div
                    style={{
                      padding: 8,
                      borderBottom: '1px solid #f5f5f5',
                      borderRight: '1px solid #f0f0f0',
                      background: '#fafafa',
                      fontSize: 12,
                      color: '#595959',
                    }}
                  >
                    {t}
                  </div>
                  {products.map((p) => {
                    const k = `${t}|${String(p.id ?? p.name)}`;
                    const cardList = cellMap[k] || [];
                    return (
                      <div
                        key={k}
                        style={{
                          padding: 4,
                          borderBottom: '1px solid #f5f5f5',
                          borderRight: '1px solid #f0f0f0',
                          minHeight: 36,
                        }}
                      >
                        {cardList.map((card) => {
                          const cfg = STATUS_CONFIG[card.status];
                          return (
                            <BookingActionPopover
                              key={card.order_item_id}
                              storeId={storeId}
                              card={card}
                              onChanged={onChanged}
                            >
                              <div
                                style={{
                                  background: cfg.bg,
                                  borderRadius: 4,
                                  padding: '4px 6px',
                                  marginBottom: 4,
                                  cursor: 'pointer',
                                  fontSize: 12,
                                  border: '1px solid #f0f0f0',
                                }}
                              >
                                <div style={{ fontWeight: 500 }}>
                                  {card.customer_nickname}
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 2 }}>
                                  <Tag color={cfg.color} style={{ fontSize: 10, margin: 0 }}>
                                    {cfg.text}
                                  </Tag>
                                  <span style={{ color: '#722ed1' }}>¥{card.amount}</span>
                                </div>
                              </div>
                            </BookingActionPopover>
                          );
                        })}
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </Card>
    </Spin>
  );
}
