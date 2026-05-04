'use client';

import React, { useState } from 'react';
import {
  Tabs,
  Button,
  DatePicker,
  Input,
  Space,
  Popover,
  Select,
  Tag,
} from 'antd';
import {
  LeftOutlined,
  RightOutlined,
  FilterOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import type {
  CalendarView,
  CalendarFilters,
  AppointmentStatus,
} from './types';
import { STATUS_FILTER_OPTIONS, SOURCE_OPTIONS } from './types';
import MyViewsManager from './MyViewsManager';

interface ToolbarProps {
  storeId: number | null;
  view: CalendarView;
  onViewChange: (v: CalendarView) => void;
  currentDate: Dayjs;
  onDateChange: (d: Dayjs) => void;
  filters: CalendarFilters;
  onFiltersChange: (f: CalendarFilters) => void;
}

const VIEW_TABS: { key: CalendarView; label: string }[] = [
  { key: 'month', label: '月' },
  { key: 'week', label: '周' },
  { key: 'day', label: '日' },
  { key: 'resource', label: '资源' },
  { key: 'list', label: '列表' },
];

export default function CalendarToolbar({
  storeId,
  view,
  onViewChange,
  currentDate,
  onDateChange,
  filters,
  onFiltersChange,
}: ToolbarProps) {
  const [filterOpen, setFilterOpen] = useState(false);
  const [tempStatuses, setTempStatuses] = useState<AppointmentStatus[]>(
    filters.statuses ?? []
  );
  const [tempSources, setTempSources] = useState<string[]>(filters.sources ?? []);
  const [searchInput, setSearchInput] = useState<string>(filters.q ?? '');

  const stepLabel: Record<CalendarView, 'month' | 'week' | 'day'> = {
    month: 'month',
    week: 'week',
    day: 'day',
    resource: 'week',
    list: 'week',
  };

  const goPrev = () => onDateChange(currentDate.subtract(1, stepLabel[view]));
  const goNext = () => onDateChange(currentDate.add(1, stepLabel[view]));
  const goToday = () => onDateChange(dayjs());

  const applyFilters = () => {
    onFiltersChange({
      ...filters,
      statuses: tempStatuses.length ? tempStatuses : undefined,
      sources: tempSources.length ? tempSources : undefined,
    });
    setFilterOpen(false);
  };

  const clearFilters = () => {
    setTempStatuses([]);
    setTempSources([]);
    setSearchInput('');
    onFiltersChange({});
  };

  const activeFilterCount =
    (filters.statuses?.length ?? 0) +
    (filters.sources?.length ?? 0) +
    (filters.product_ids?.length ?? 0) +
    (filters.staff_ids?.length ?? 0) +
    (filters.q ? 1 : 0);

  const handleSearch = (val: string) => {
    onFiltersChange({ ...filters, q: val ? val.trim() : undefined });
  };

  const filterContent = (
    <div style={{ width: 320 }}>
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 6, color: '#8c8c8c', fontSize: 12 }}>状态</div>
        <Select
          mode="multiple"
          allowClear
          value={tempStatuses}
          onChange={(v) => setTempStatuses(v)}
          options={STATUS_FILTER_OPTIONS}
          placeholder="选择状态"
          style={{ width: '100%' }}
        />
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ marginBottom: 6, color: '#8c8c8c', fontSize: 12 }}>来源</div>
        <Select
          mode="multiple"
          allowClear
          value={tempSources}
          onChange={(v) => setTempSources(v)}
          options={SOURCE_OPTIONS}
          placeholder="选择来源"
          style={{ width: '100%' }}
        />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
        <Button onClick={clearFilters} size="small">
          清空
        </Button>
        <Button type="primary" onClick={applyFilters} size="small">
          应用
        </Button>
      </div>
    </div>
  );

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 16px',
        background: '#fff',
        border: '1px solid #f0f0f0',
        borderRadius: 8,
        marginBottom: 16,
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      <Space size={12} wrap>
        <Tabs
          activeKey={view}
          onChange={(k) => onViewChange(k as CalendarView)}
          items={VIEW_TABS.map((t) => ({ key: t.key, label: t.label }))}
          style={{ marginBottom: -16 }}
        />
        <Space size={4}>
          <Button icon={<LeftOutlined />} onClick={goPrev} size="small" />
          <Button onClick={goToday} size="small">
            今天
          </Button>
          <Button icon={<RightOutlined />} onClick={goNext} size="small" />
          <DatePicker
            value={currentDate}
            onChange={(d) => d && onDateChange(d)}
            allowClear={false}
            size="small"
          />
        </Space>
      </Space>

      <Space size={8} wrap>
        {(view === 'day' || view === 'resource') && (
          <Select
            value="service"
            disabled
            options={[{ label: '按服务项目', value: 'service' }]}
            size="small"
            style={{ width: 120 }}
          />
        )}
        <Input
          allowClear
          size="small"
          prefix={<SearchOutlined />}
          placeholder="顾客手机号/姓名"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onPressEnter={() => handleSearch(searchInput)}
          onBlur={() => handleSearch(searchInput)}
          style={{ width: 200 }}
        />
        <Popover
          content={filterContent}
          trigger="click"
          open={filterOpen}
          onOpenChange={setFilterOpen}
          placement="bottomRight"
        >
          <Button icon={<FilterOutlined />} size="small">
            筛选
            {activeFilterCount > 0 && (
              <Tag color="processing" style={{ marginLeft: 4 }}>
                {activeFilterCount}
              </Tag>
            )}
          </Button>
        </Popover>
        <MyViewsManager
          storeId={storeId}
          currentFilters={filters}
          currentView={view}
          onApplyView={(v) => {
            if (v.view_type) onViewChange(v.view_type);
            onFiltersChange(v.filter_payload || {});
          }}
        />
      </Space>
    </div>
  );
}
