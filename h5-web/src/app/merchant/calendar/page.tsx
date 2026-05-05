'use client';

// [PRD「商家 PC 后台预约日历优化」v1.0] 驾驶舱总入口
// 保留旧的 DailyOrdersModal + Drawer 作为月视图点击日期的兼容入口
//
// [PRD-03 客户端改期能力收口 v1.0]：本页所有「改约」按钮已下线。
// 改期权 100% 归客户端，商家在本页只能查看、联系顾客、查看详情、核销，
// 不能直接改时间；如需改时间，由顾客自行在小程序/APP/H5 客户端发起。

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, ConfigProvider } from 'antd';
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
import type { CalendarFilters, CalendarView } from './types';

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
      const d = dayjs(date);
      setCurrentDate(d);
      if (cell && cell.booking_count > 0) {
        setPopupDate(date);
        setPopupOpen(true);
      } else {
        setView('day');
      }
    },
    []
  );

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

        {/* [PRD-03 客户端改期能力收口 v1.0]
            商家端无任何「改时间」入口，改期由顾客在客户端自助操作 */}
        <div
          style={{
            background: '#fffbe6',
            border: '1px solid #ffe58f',
            color: '#ad6800',
            padding: '8px 12px',
            borderRadius: 6,
            marginBottom: 12,
            fontSize: 13,
          }}
        >
          📌 改期权已收归客户端，商家无法直接改时间。如顾客需要改期，请提示其在小程序 / APP / H5 自助操作。
        </div>

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
              onChanged={triggerReload}
            />
          )}
          {view === 'resource' && (
            <ResourceView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onChanged={triggerReload}
            />
          )}
          {view === 'list' && (
            <ListView
              storeId={storeId}
              currentDate={currentDate}
              filters={filters}
              onChanged={triggerReload}
            />
          )}
        </div>

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
