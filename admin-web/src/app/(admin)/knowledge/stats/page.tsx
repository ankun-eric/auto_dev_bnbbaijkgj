'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Card, Tabs, Statistic, Row, Col, message, Tag, Spin, Button,
} from 'antd';
import {
  ThunderboltOutlined, PercentageOutlined, DatabaseOutlined, FileTextOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { get } from '@/lib/api';
import { useRouter } from 'next/navigation';
import dayjs from 'dayjs';

const { Title } = Typography;

interface Overview {
  total_knowledge_bases: number;
  total_entries: number;
  active_entries: number;
  total_hits: number;
  total_misses: number;
  hit_rate: number;
  avg_search_time_ms: number;
}

interface TopHitEntry {
  entry_id: number;
  question?: string;
  title?: string;
  hit_count: number;
  kb_name?: string;
}

interface MissedQuestion {
  id: number;
  question: string;
  scene: string;
  count: number;
  created_at: string;
}

interface TrendItem {
  date: string;
  hits: number;
  misses: number;
}

interface DistributionItem {
  kb_name: string;
  hit_count: number;
}

export default function KnowledgeStatsPage() {
  const router = useRouter();
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overview, setOverview] = useState<Overview>({ total_knowledge_bases: 0, total_entries: 0, active_entries: 0, total_hits: 0, total_misses: 0, hit_rate: 0, avg_search_time_ms: 0 });
  const [activeTab, setActiveTab] = useState('top-hits');

  const [topHits, setTopHits] = useState<TopHitEntry[]>([]);
  const [topHitsLoading, setTopHitsLoading] = useState(false);

  const [missedQuestions, setMissedQuestions] = useState<MissedQuestion[]>([]);
  const [missedLoading, setMissedLoading] = useState(false);

  const [trend, setTrend] = useState<TrendItem[]>([]);
  const [trendLoading, setTrendLoading] = useState(false);

  const [distribution, setDistribution] = useState<DistributionItem[]>([]);
  const [distLoading, setDistLoading] = useState(false);

  const fetchOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const res = await get<Overview>('/api/admin/knowledge-bases/stats/overview');
      setOverview(res);
    } catch {
      // ignore
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const fetchTopHits = useCallback(async () => {
    setTopHitsLoading(true);
    try {
      const res = await get<{ items: TopHitEntry[] }>('/api/admin/knowledge-bases/stats/top-hits');
      setTopHits(res.items || []);
    } catch {
      message.error('获取命中排行失败');
    } finally {
      setTopHitsLoading(false);
    }
  }, []);

  const fetchMissed = useCallback(async () => {
    setMissedLoading(true);
    try {
      const res = await get<{ items: MissedQuestion[] }>('/api/admin/knowledge-bases/stats/missed-questions');
      setMissedQuestions(res.items || []);
    } catch {
      message.error('获取未命中问题失败');
    } finally {
      setMissedLoading(false);
    }
  }, []);

  const fetchTrend = useCallback(async () => {
    setTrendLoading(true);
    try {
      const res = await get<{ items: TrendItem[] }>('/api/admin/knowledge-bases/stats/trend');
      setTrend(res.items || []);
    } catch {
      message.error('获取命中趋势失败');
    } finally {
      setTrendLoading(false);
    }
  }, []);

  const fetchDistribution = useCallback(async () => {
    setDistLoading(true);
    try {
      const res = await get<{ items: DistributionItem[] }>('/api/admin/knowledge-bases/stats/distribution');
      setDistribution(res.items || []);
    } catch {
      message.error('获取知识库分布失败');
    } finally {
      setDistLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  useEffect(() => {
    if (activeTab === 'top-hits') fetchTopHits();
    else if (activeTab === 'missed') fetchMissed();
    else if (activeTab === 'trend') fetchTrend();
    else if (activeTab === 'distribution') fetchDistribution();
  }, [activeTab, fetchTopHits, fetchMissed, fetchTrend, fetchDistribution]);

  const topHitColumns = [
    {
      title: '条目名称', key: 'title', ellipsis: true,
      render: (_: any, record: TopHitEntry) => record.question || record.title || '-',
    },
    { title: '所属知识库', dataIndex: 'kb_name', key: 'kb_name', width: 160 },
    { title: '命中次数', dataIndex: 'hit_count', key: 'hit_count', width: 120 },
  ];

  const missedColumns = [
    { title: '问题内容', dataIndex: 'question', key: 'question', ellipsis: true },
    { title: '场景', dataIndex: 'scene', key: 'scene', width: 120, render: (v: string) => v || '-' },
    { title: '出现次数', dataIndex: 'count', key: 'count', width: 100 },
    {
      title: '首次记录时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
  ];

  const trendColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '命中次数', dataIndex: 'hits', key: 'hits', width: 120 },
    { title: '未命中次数', dataIndex: 'misses', key: 'misses', width: 120 },
    {
      title: '命中率', key: 'hit_rate', width: 120,
      render: (_: any, record: TrendItem) => {
        const total = record.hits + record.misses;
        return total > 0 ? `${((record.hits / total) * 100).toFixed(1)}%` : '-';
      },
    },
  ];

  const distColumns = [
    { title: '知识库名称', dataIndex: 'kb_name', key: 'kb_name', ellipsis: true },
    { title: '命中次数', dataIndex: 'hit_count', key: 'hit_count', width: 120 },
    {
      title: '占比', key: 'percentage', width: 120,
      render: (_: any, record: DistributionItem) => {
        const totalHits = distribution.reduce((s, d) => s + d.hit_count, 0);
        return totalHits > 0 ? `${((record.hit_count / totalHits) * 100).toFixed(1)}%` : '-';
      },
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/knowledge')}>返回</Button>
        <Title level={4} style={{ margin: 0 }}>知识库数据统计</Title>
      </div>

      <Spin spinning={overviewLoading}>
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic title="总命中次数" value={overview.total_hits} prefix={<ThunderboltOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="命中率"
                value={overview.hit_rate}
                precision={1}
                suffix="%"
                prefix={<PercentageOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="知识库总数" value={overview.total_knowledge_bases} prefix={<DatabaseOutlined />} />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic title="条目总数" value={overview.total_entries} prefix={<FileTextOutlined />} />
            </Card>
          </Col>
        </Row>
      </Spin>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'top-hits',
            label: '命中排行',
            children: (
              <Table
                columns={topHitColumns}
                dataSource={topHits}
                rowKey="entry_id"
                loading={topHitsLoading}
                pagination={{ showTotal: (t) => `共 ${t} 条` }}
                scroll={{ x: 700 }}
              />
            ),
          },
          {
            key: 'missed',
            label: '未命中问题',
            children: (
              <Table
                columns={missedColumns}
                dataSource={missedQuestions}
                rowKey="id"
                loading={missedLoading}
                pagination={{ showTotal: (t) => `共 ${t} 条` }}
                scroll={{ x: 600 }}
              />
            ),
          },
          {
            key: 'trend',
            label: '命中率趋势',
            children: (
              <Table
                columns={trendColumns}
                dataSource={trend}
                rowKey="date"
                loading={trendLoading}
                pagination={{ showTotal: (t) => `共 ${t} 条` }}
                scroll={{ x: 500 }}
              />
            ),
          },
          {
            key: 'distribution',
            label: '各知识库分布',
            children: (
              <Table
                columns={distColumns}
                dataSource={distribution}
                rowKey="kb_name"
                loading={distLoading}
                pagination={{ showTotal: (t) => `共 ${t} 条` }}
                scroll={{ x: 400 }}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
