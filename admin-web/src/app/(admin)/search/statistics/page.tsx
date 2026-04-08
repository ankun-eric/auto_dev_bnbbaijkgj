'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Typography, Table, Card, DatePicker, Space, Spin, message, Row, Col,
} from 'antd';
import { BarChartOutlined, SearchOutlined, WarningOutlined, PieChartOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import dayjs, { Dayjs } from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

let Line: any = null;
let Pie: any = null;
let chartsAvailable = false;

try {
  const charts = require('@ant-design/charts');
  Line = charts.Line;
  Pie = charts.Pie;
  chartsAvailable = true;
} catch {
  chartsAvailable = false;
}

interface TopKeyword {
  keyword: string;
  count: number;
}

interface TrendItem {
  date: string;
  count: number;
}

interface NoResultKeyword {
  keyword: string;
  count: number;
}

interface StatisticsData {
  top_keywords: TopKeyword[];
  trend: TrendItem[];
  no_result_keywords: NoResultKeyword[];
  type_distribution: Record<string, number>;
}

export default function SearchStatisticsPage() {
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>([
    dayjs().subtract(7, 'day'),
    dayjs(),
  ]);
  const [stats, setStats] = useState<StatisticsData>({
    top_keywords: [],
    trend: [],
    no_result_keywords: [],
    type_distribution: {},
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<StatisticsData>('/api/admin/search/statistics', {
        start_date: dateRange[0].format('YYYY-MM-DD'),
        end_date: dateRange[1].format('YYYY-MM-DD'),
      });
      const typeDistMap = res.type_distribution || {};
      setStats({
        top_keywords: res.top_keywords || [],
        trend: res.trend || [],
        no_result_keywords: res.no_result_keywords || [],
        type_distribution: typeDistMap,
      });
    } catch {
      message.error('获取搜索统计数据失败');
    } finally {
      setLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDateChange = (dates: any) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange([dates[0], dates[1]]);
    }
  };

  const hotWordColumns = [
    {
      title: '排名',
      dataIndex: 'rank',
      key: 'rank',
      width: 80,
      render: (_: any, __: any, index: number) => index + 1,
    },
    { title: '搜索词', dataIndex: 'keyword', key: 'keyword' },
    {
      title: '搜索次数',
      dataIndex: 'count',
      key: 'count',
      width: 120,
      sorter: (a: TopKeyword, b: TopKeyword) => b.count - a.count,
    },
  ];

  const noResultColumns = [
    { title: '搜索词', dataIndex: 'keyword', key: 'keyword' },
    {
      title: '搜索次数',
      dataIndex: 'count',
      key: 'count',
      width: 120,
      sorter: (a: NoResultKeyword, b: NoResultKeyword) => b.count - a.count,
    },
  ];

  const trendTableColumns = [
    { title: '日期', dataIndex: 'date', key: 'date' },
    { title: '搜索次数', dataIndex: 'count', key: 'count', width: 120 },
  ];

  const categoryTableColumns = [
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '点击次数', dataIndex: 'count', key: 'count', width: 120 },
  ];

  const lineConfig = useMemo(() => ({
    data: stats.trend,
    xField: 'date',
    yField: 'count',
    smooth: true,
    point: { size: 3 },
    height: 300,
    meta: {
      date: { alias: '日期' },
      count: { alias: '搜索次数' },
    },
  }), [stats.trend]);

  const typeDistArray = useMemo(() =>
    Object.entries(stats.type_distribution).map(([category, count]) => ({ category, count })),
    [stats.type_distribution]
  );

  const pieConfig = useMemo(() => ({
    data: typeDistArray,
    angleField: 'count',
    colorField: 'category',
    radius: 0.8,
    innerRadius: 0.5,
    height: 300,
    label: {
      text: (d: { category: string; count: number }) => `${d.category}: ${d.count}`,
      position: 'outside',
    },
    legend: { position: 'bottom' as const },
  }), [typeDistArray]);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>搜索数据统计</Title>
      <Space style={{ marginBottom: 24 }}>
        <Text>日期范围：</Text>
        <RangePicker
          value={dateRange}
          onChange={handleDateChange}
          allowClear={false}
        />
      </Space>

      <Spin spinning={loading}>
        <Row gutter={[24, 24]}>
          <Col xs={24} lg={12}>
            <Card
              title={
                <Space><BarChartOutlined />热门搜索词排行</Space>
              }
              style={{ borderRadius: 12 }}
            >
              <Table
                columns={hotWordColumns}
                dataSource={stats.top_keywords}
                rowKey="keyword"
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
                size="small"
              />
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card
              title={
                <Space><SearchOutlined />搜索次数趋势</Space>
              }
              style={{ borderRadius: 12 }}
            >
              {chartsAvailable && Line ? (
                <Line {...lineConfig} />
              ) : (
                <Table
                  columns={trendTableColumns}
                  dataSource={stats.trend}
                  rowKey="date"
                  pagination={false}
                  size="small"
                />
              )}
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card
              title={
                <Space><WarningOutlined />无结果搜索词 Top N</Space>
              }
              style={{ borderRadius: 12 }}
            >
              <Table
                columns={noResultColumns}
                dataSource={stats.no_result_keywords}
                rowKey="keyword"
                pagination={{ pageSize: 10, showTotal: (total) => `共 ${total} 条` }}
                size="small"
              />
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card
              title={
                <Space><PieChartOutlined />各类别点击分布</Space>
              }
              style={{ borderRadius: 12 }}
            >
              {chartsAvailable && Pie ? (
                <Pie {...pieConfig} />
              ) : (
                <Table
                  columns={categoryTableColumns}
                  dataSource={typeDistArray}
                  rowKey="category"
                  pagination={false}
                  size="small"
                />
              )}
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  );
}
