'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Card, Spin, Tag, Empty, Typography, Tooltip } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';
import type { CalendarFilters, ItemCard } from './types';
import { STATUS_CONFIG } from './types';
import BookingActionPopover from './BookingActionPopover';

const { Text } = Typography;

// [PRD-03 客户端改期能力收口 v1.0] 商家端「改约」入口已移除
interface ResourceViewProps {
  storeId: number | null;
  currentDate: Dayjs;
  filters: CalendarFilters;
  onChanged?: () => void;
}

const HOUR_START = 9;
const HOUR_END = 20; // 9:00 ~ 20:00（共 11 个小时）
const HOURS = Array.from({ length: HOUR_END - HOUR_START }, (_, i) => HOUR_START + i);
const HOUR_WIDTH = 80; // 每小时 80px
const ROW_HEIGHT = 60;

export default function ResourceView({
  storeId,
  currentDate,
  filters,
  onChanged,
}: ResourceViewProps) {
  const [items, setItems] = useState<ItemCard[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      // 默认按周加载
      const start = currentDate.startOf('week').add(currentDate.day() === 0 ? -6 : 1 - currentDate.day(), 'day');
      const end = start.add(6, 'day');
      const params: any = {
        store_id: storeId,
        start_date: start.format('YYYY-MM-DD'),
        end_date: end.format('YYYY-MM-DD'),
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

  // 当日的项目（资源）
  const dayStr = currentDate.format('YYYY-MM-DD');
  const dayItems = useMemo(
    () =>
      items.filter((it) => {
        if (!it.appointment_time) return false;
        return dayjs(it.appointment_time).format('YYYY-MM-DD') === dayStr;
      }),
    [items, dayStr]
  );

  const products = useMemo(() => {
    const map = new Map<string, { id?: number; name: string }>();
    dayItems.forEach((it) => {
      const key = String(it.product_id ?? it.product_name ?? '其它');
      if (!map.has(key)) {
        map.set(key, { id: it.product_id ?? undefined, name: it.product_name || '未命名服务' });
      }
    });
    return Array.from(map.values());
  }, [dayItems]);

  return (
    <Spin spinning={loading}>
      <Card title={`资源视图 — ${currentDate.format('YYYY 年 M 月 D 日')}（${dayItems.length} 条）`}>
        {products.length === 0 ? (
          <Empty description="当天暂无预约" />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <div style={{ minWidth: 200 + HOURS.length * HOUR_WIDTH }}>
              {/* 时间轴表头 */}
              <div style={{ display: 'flex', borderBottom: '1px solid #f0f0f0' }}>
                <div style={{ width: 200, padding: 8, background: '#fafafa', borderRight: '1px solid #f0f0f0' }}>
                  <Text strong>服务项目</Text>
                </div>
                {HOURS.map((h) => (
                  <div
                    key={h}
                    style={{
                      width: HOUR_WIDTH,
                      padding: '8px 4px',
                      textAlign: 'center',
                      background: '#fafafa',
                      borderRight: '1px solid #f0f0f0',
                      fontSize: 12,
                    }}
                  >
                    {h}:00
                  </div>
                ))}
              </div>
              {products.map((p) => {
                const rowItems = dayItems.filter(
                  (it) => String(it.product_id ?? it.product_name ?? '其它') === String(p.id ?? p.name)
                );
                return (
                  <div
                    key={String(p.id ?? p.name)}
                    style={{
                      display: 'flex',
                      borderBottom: '1px solid #f5f5f5',
                      position: 'relative',
                      minHeight: ROW_HEIGHT,
                    }}
                  >
                    <div
                      style={{
                        width: 200,
                        padding: 8,
                        borderRight: '1px solid #f0f0f0',
                        background: '#fafafa',
                      }}
                    >
                      <Text strong>{p.name}</Text>
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>{rowItems.length} 个预约</div>
                    </div>
                    <div style={{ flex: 1, position: 'relative' }}>
                      {/* 背景小时格 */}
                      {HOURS.map((h, idx) => (
                        <div
                          key={h}
                          style={{
                            position: 'absolute',
                            left: idx * HOUR_WIDTH,
                            top: 0,
                            bottom: 0,
                            width: HOUR_WIDTH,
                            borderRight: '1px solid #f5f5f5',
                          }}
                        />
                      ))}
                      {/* 预约时间条 */}
                      {rowItems.map((it) => {
                        if (!it.appointment_time) return null;
                        const t = dayjs(it.appointment_time);
                        const startH = t.hour() + t.minute() / 60;
                        const offsetX = (startH - HOUR_START) * HOUR_WIDTH;
                        const widthPx = HOUR_WIDTH; // 默认 60 分钟
                        const cfg = STATUS_CONFIG[it.status];
                        if (offsetX < 0 || offsetX > HOURS.length * HOUR_WIDTH) return null;
                        return (
                          <BookingActionPopover
                            key={it.order_item_id}
                            storeId={storeId}
                            card={it}
                            onChanged={onChanged}
                          >
                            <Tooltip
                              title={`${it.customer_nickname} · ${cfg.text} · ¥${it.amount}`}
                            >
                              <div
                                style={{
                                  position: 'absolute',
                                  left: offsetX,
                                  top: 6,
                                  height: ROW_HEIGHT - 12,
                                  width: widthPx - 4,
                                  background: cfg.bg,
                                  border: `1px solid #d9d9d9`,
                                  borderRadius: 4,
                                  padding: '4px 6px',
                                  cursor: 'pointer',
                                  overflow: 'hidden',
                                  fontSize: 12,
                                }}
                              >
                                <div style={{ fontWeight: 500 }}>
                                  {it.customer_nickname}
                                </div>
                                <Tag color={cfg.color} style={{ fontSize: 10, margin: 0 }}>
                                  {cfg.text}
                                </Tag>
                              </div>
                            </Tooltip>
                          </BookingActionPopover>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>
    </Spin>
  );
}
