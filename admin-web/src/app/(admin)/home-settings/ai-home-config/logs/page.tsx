'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  Typography,
  Table,
  Button,
  Space,
  DatePicker,
  Select,
  message,
  Drawer,
  Tag,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { get } from '@/lib/api';
import { useRouter } from 'next/navigation';
import dayjs, { Dayjs } from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface LogItem {
  id: number;
  operator_id?: number;
  operator_name?: string;
  module: string;
  summary?: string;
  operator_ip?: string;
  created_at?: string;
}

const MODULE_LABEL: Record<string, string> = {
  welcome: '欢迎区',
  topbar: '顶栏与品牌',
  input: '输入栏',
  session: '会话策略',
  floating_button: '浮动按钮',
  banner: 'Banner 显隐',
  func_grid: '功能宫格',
  quick_tags: '快捷标签条',
  recommended_questions: '推荐问列表',
  all: '整体保存',
};

export default function AIHomeConfigLogsPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [moduleFilter, setModuleFilter] = useState<string | undefined>();
  const [range, setRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);

  const [detail, setDetail] = useState<any>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (moduleFilter) params.module = moduleFilter;
      if (range && range[0]) params.start_date = range[0].format('YYYY-MM-DD');
      if (range && range[1]) params.end_date = range[1].format('YYYY-MM-DD');
      const res = await get<{ items: LogItem[]; total: number }>(
        '/api/admin/ai-home-config/logs',
        params
      );
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch {
      message.error('加载日志失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, moduleFilter, range]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openDetail = async (id: number) => {
    try {
      const data = await get(`/api/admin/ai-home-config/logs/${id}`);
      setDetail(data);
      setDetailOpen(true);
    } catch {
      message.error('加载详情失败');
    }
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => router.back()}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          AI 对话首页配置 - 操作日志（保留 90 天）
        </Title>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <RangePicker
            value={range as any}
            onChange={(v) => setRange(v as any)}
            placeholder={['开始日期', '结束日期']}
          />
          <Select
            allowClear
            placeholder="选择模块"
            style={{ width: 200 }}
            value={moduleFilter}
            onChange={(v) => setModuleFilter(v)}
            options={Object.entries(MODULE_LABEL).map(([k, v]) => ({
              value: k,
              label: v,
            }))}
          />
          <Button
            type="primary"
            onClick={() => {
              setPage(1);
              fetchData();
            }}
          >
            查询
          </Button>
          <Button
            onClick={() => {
              setRange(null);
              setModuleFilter(undefined);
              setPage(1);
            }}
          >
            重置
          </Button>
        </Space>
      </Card>

      <Card>
        <Table<LogItem>
          rowKey="id"
          loading={loading}
          dataSource={logs}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          columns={[
            { title: '序号', dataIndex: 'id', width: 80 },
            {
              title: '操作人',
              dataIndex: 'operator_name',
              render: (v, r) => v || `用户 #${r.operator_id ?? '-'}`,
            },
            {
              title: '操作时间',
              dataIndex: 'created_at',
              render: (v) =>
                v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
              width: 180,
            },
            {
              title: '变更模块',
              dataIndex: 'module',
              render: (v) => <Tag color="blue">{MODULE_LABEL[v] || v}</Tag>,
              width: 140,
            },
            { title: '变更摘要', dataIndex: 'summary' },
            { title: '操作 IP', dataIndex: 'operator_ip', width: 140 },
            {
              title: '操作',
              width: 120,
              render: (_, r) => (
                <Button size="small" onClick={() => openDetail(r.id)}>
                  查看 diff
                </Button>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title={detail ? `日志详情 #${detail.id}` : '日志详情'}
        width={920}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
      >
        {detail && (
          <div>
            <p>
              <strong>操作人：</strong>
              {detail.operator_name || `用户 #${detail.operator_id}`}{' '}
              <strong>IP：</strong>
              {detail.operator_ip}
            </p>
            <p>
              <strong>时间：</strong>
              {detail.created_at
                ? dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')
                : '-'}{' '}
              <strong>模块：</strong>
              <Tag color="blue">{MODULE_LABEL[detail.module] || detail.module}</Tag>
            </p>
            <p>
              <strong>摘要：</strong>
              {detail.summary}
            </p>
            <div style={{ display: 'flex', gap: 16 }}>
              <div style={{ flex: 1 }}>
                <h4>变更前</h4>
                <pre
                  style={{
                    background: '#fafafa',
                    padding: 8,
                    maxHeight: 480,
                    overflow: 'auto',
                  }}
                >
                  {JSON.stringify(detail.before_json, null, 2)}
                </pre>
              </div>
              <div style={{ flex: 1 }}>
                <h4>变更后</h4>
                <pre
                  style={{
                    background: '#f6ffed',
                    padding: 8,
                    maxHeight: 480,
                    overflow: 'auto',
                  }}
                >
                  {JSON.stringify(detail.after_json, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
