'use client';

/**
 * 卡管理 v2.0 第 5 期：卡销售看板
 * - 时间范围：今日 / 本周 / 本月 / 自定义
 * - 三大指标：销量 / 销售额 / 核销次数
 * - 趋势曲线（day / week 粒度）
 */
import { useEffect, useState, useCallback } from 'react';
import { Card, Col, DatePicker, Radio, Row, Statistic, Table, Spin } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import api from '@/lib/api';

interface Summary {
  sales_count: number;
  sales_amount: number;
  redemption_count: number;
  start: string;
  end: string;
}

interface TrendPoint {
  period: string;
  sales_count: number;
  sales_amount: number;
  redemption_count: number;
}

const presets: { key: string; label: string }[] = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'custom', label: '自定义' },
];

export default function CardDashboardPage() {
  const [preset, setPreset] = useState<string>('week');
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().startOf('week'), dayjs().endOf('day')]);
  const [granularity, setGranularity] = useState<'day' | 'week'>('day');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(false);

  const handlePreset = (k: string) => {
    setPreset(k);
    if (k === 'today') setRange([dayjs().startOf('day'), dayjs().endOf('day')]);
    else if (k === 'week') setRange([dayjs().startOf('week'), dayjs().endOf('day')]);
    else if (k === 'month') setRange([dayjs().startOf('month'), dayjs().endOf('day')]);
  };

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        start: range[0].toISOString(),
        end: range[1].toISOString(),
      };
      const [s, t] = await Promise.all([
        api.get('/api/admin/cards/dashboard/summary', { params }),
        api.get('/api/admin/cards/dashboard/trend', { params: { ...params, granularity } }),
      ]);
      setSummary(s.data);
      setTrend(t.data?.items || []);
    } finally {
      setLoading(false);
    }
  }, [range, granularity]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-4">卡销售看板</h1>
      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-4">
          <Radio.Group value={preset} onChange={(e) => handlePreset(e.target.value)}>
            {presets.map((p) => (
              <Radio.Button key={p.key} value={p.key}>
                {p.label}
              </Radio.Button>
            ))}
          </Radio.Group>
          <DatePicker.RangePicker
            value={range as any}
            onChange={(v) => v && v[0] && v[1] && (setPreset('custom'), setRange([v[0], v[1]] as any))}
          />
          <Radio.Group value={granularity} onChange={(e) => setGranularity(e.target.value)}>
            <Radio.Button value="day">日</Radio.Button>
            <Radio.Button value="week">周</Radio.Button>
          </Radio.Group>
        </div>
      </Card>

      <Spin spinning={loading}>
        <Row gutter={16} className="mb-4">
          <Col span={8}>
            <Card>
              <Statistic title="销量（张）" value={summary?.sales_count ?? 0} />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="销售额（元）"
                value={summary?.sales_amount ?? 0}
                precision={2}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic title="核销次数" value={summary?.redemption_count ?? 0} />
            </Card>
          </Col>
        </Row>

        <Card title="趋势">
          <Table
            rowKey="period"
            size="small"
            dataSource={trend}
            pagination={false}
            columns={[
              { title: '时间', dataIndex: 'period', width: 140 },
              { title: '销量', dataIndex: 'sales_count', width: 120 },
              { title: '销售额', dataIndex: 'sales_amount', width: 140 },
              { title: '核销次数', dataIndex: 'redemption_count', width: 140 },
            ]}
          />
        </Card>
      </Spin>
    </div>
  );
}
