'use client';

// [PRD「商家 PC 后台预约日历优化」v1.0] 驾驶舱总入口
// 保留旧的 DailyOrdersModal + Drawer 作为月视图点击日期的兼容入口

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, ConfigProvider, message } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { CalendarOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import 'dayjs/locale/zh-cn';
import { getCurrentStoreId } from '../lib';
import DailyOrdersModal from './DailyOrdersModal';
import KpiBar from './KpiBar';
import CalendarToolbar from './CalendarToolbar';
import MonthView from './MonthView';
import WeekView from './WeekView';
import DayView from './DayView';
import ResourceView from './ResourceView';
import ListView from './ListView';
import RescheduleModal from './RescheduleModal';
import type {
  CalendarFilters,
  CalendarView,
  ItemCard,
  ListItem,
} from './types';

dayjs.locale('zh-cn');

const { Title } = Typography;

export default function CalendarPCPage() {
  const [storeId, setStoreId] = useState<number | null>(null);
  const [view, setView] = useState<CalendarView>('month');
  const [currentDate, setCurrentDate] = useState<Dayjs>(dayjs());
  const [filters, setFilters] = useState<CalendarFilters>({});
  const [reloadKey, setReloadKey] = useState(0);

  // 月视图点击日期：保留旧 DailyOrdersModal 作为兼容入口
  const [popupOpen, setPopupOpen] = useState(false);
  const [popupDate, setPopupDate] = useState<string | null>(null);

  // 改约 Modal
  const [reschedOpen, setReschedOpen] = useState(false);
  const [reschedTarget, setReschedTarget] = useState<{
    orderItemId: number | null;
    currentTime?: string | null;
    currentProductId?: number | null;
  }>({ orderItemId: null });

  useEffect(() => {
    const sid = getCurrentStoreId();
    setStoreId(sid);
  }, []);

  const handleKpiClick = (type: 'today' | 'week' | 'month') => {
    const now = dayjs();
    setCurrentDate(now);
    if (type === 'today') {
      setView('day');
    } else if (type === 'week') {
      setView('week');
    } else {
      setView('month');
    }
  };

  const handleMonthCellClick = useCallback(
    (date: string, cell: any) => {
      // 保留旧逻辑：有数据时打开 DailyOrdersModal；同时切到日视图
      const d = dayjs(date);
      setCurrentDate(d);
      if (cell && cell.booking_count > 0) {
        setPopupDate(date);
        setPopupOpen(true);
      } else {
        // 无单也允许切到日视图
        setView('day');
      }
    },
    []
  );

  const openReschedule = useCallback((card: ItemCard | ListItem) => {
    setReschedTarget({
      orderItemId: card.order_item_id,
      currentTime:
        'appointment_time' in card
          ? (card as ItemCard).appointment_time
          : (card as ListItem).appointment_date && (card as ListItem).appointment_time
          ? `${(card as ListItem).appointment_date} ${(card as ListItem).appointment_time}`
          : null,
      currentProductId: (card as ItemCard).product_id ?? null,
    });
    setReschedOpen(true);
  }, []);

  const triggerReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  if (!storeId) {
    return (
      <ConfigProvider locale={zhCN}>
        <div>
          <Title level={4}>
            <CalendarOutlined style={{ marginRight: 8 }} />
            预约日历
          </Title>
          <div style={{ color: '#8c8c8c', padding: 24 }}>
            尚未选择门店，请先在右上角切换门店。
          </div>
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider locale={zhCN}>
      <div>
        <Title level={4}>
          <CalendarOutlined style={{ marginRight: 8 }} />
          预约日历
        </Title>

        <KpiBar storeId={storeId} onClickKpi={handleKpiClick} />

        <CalendarToolbar
          storeId={storeId}
          view={view}
          onViewChange={setView}
          currentDate={currentDate}
          onDateChange={setCurrentDate}
          filters={filters}
          onFiltersChange={setFilters}
        />

        {/* 关键性能：通过条件渲染避免 KPI 重新拉取，但每个视图自身按 store/date/filters 决定是否请求 */}
        <div key={reloadKey}>
          {view === 'month' && (
            <MonthView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onPanelChange={(d) => setCurrentDate(d)}
              onCellClick={handleMonthCellClick}
            />
          )}
          {view === 'week' && (
            <WeekView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onCellClick={(date) => {
                setCurrentDate(dayjs(date));
                setView('day');
              }}
            />
          )}
          {view === 'day' && (
            <DayView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onReschedule={openReschedule}
              onChanged={triggerReload}
            />
          )}
          {view === 'resource' && (
            <ResourceView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onReschedule={openReschedule}
              onChanged={triggerReload}
            />
          )}
          {view === 'list' && (
            <ListView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onReschedule={openReschedule}
              onChanged={triggerReload}
            />
          )}
        </div>

        {/* 改约 Modal */}
        <RescheduleModal
          open={reschedOpen}
          storeId={storeId}
          orderItemId={reschedTarget.orderItemId}
          currentTime={reschedTarget.currentTime}
          currentProductId={reschedTarget.currentProductId}
          onClose={() => setReschedOpen(false)}
          onSuccess={() => {
            triggerReload();
            message.success('已刷新');
          }}
        />

        {/* 兼容旧版：月视图点击日期触发的当日订单弹窗 */}
        <DailyOrdersModal
          open={popupOpen}
          date={popupDate}
          storeId={storeId}
          onClose={() => setPopupOpen(false)}
        />
      </div>
    </ConfigProvider>
  );
}
