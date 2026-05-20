'use client';

/**
 * [PRD-QUESTIONNAIRE-IMAGE-CAPTURE-V1 2026-05-19]
 * 通用问卷模板管理页面 — 最小可用版。
 *
 * 功能：
 * - 列表：搜索 / 分页 / 新建 / 编辑 / 删除 / 启停
 * - 编辑抽屉：基础信息 + 题目列表（增删改）+ 分型规则（增删改）+ 推荐配置（按分型查看）
 * - 题目支持 single_choice / multi_choice / text 三种类型
 *
 * 注：本页是「最小版」，复杂的可视化分型预览/AI Prompt 试运行等高级能力放后续迭代。
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useRouter } from 'next/navigation';
import { del, get, post, put } from '@/lib/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface QuestionnaireTemplate {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  cover_image?: string | null;
  intro_text?: string | null;
  estimated_minutes?: number;
  allow_back?: boolean;
  shuffle_questions?: boolean;
  ai_prompt_template?: string | null;
  ai_opening?: string | null;
  report_layout?: string;
  status?: number;
  // [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19]
  result_summary_template?: string | null;
  source?: string | null;
  // [PRD-TAG-RECOMMEND-V1 2026-05-20]
  result_display_mode?: 'simple' | 'triple' | null;
  ai_followup_enabled?: boolean | null;
  recommend_click_mode?: 'drawer' | 'external' | null;
  recommend_display_count?: number | null;
  // [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] AI 追问关键字段 code 列表
  key_field_codes?: string[] | null;
  created_at?: string;
}

interface QuestionnaireQuestion {
  id: number;
  template_id: number;
  sort_order: number;
  question_type: 'single_choice' | 'multi_choice' | 'text';
  title: string;
  subtitle?: string | null;
  required?: boolean;
  options?: Array<{ label: string; value: string; score?: number; tags?: string[] }> | null;
  dimension?: string | null;
}

interface ClassificationRule {
  id: number;
  template_id: number;
  code: string;
  name: string;
  description?: string | null;
  rule_type: 'score_range' | 'dimension_max' | 'tag_match';
  rule_config: Record<string, any>;
  sort_order?: number;
}

const QUESTION_TYPE_OPTIONS = [
  { value: 'single_choice', label: '单选' },
  { value: 'multi_choice', label: '多选' },
  { value: 'text', label: '文本填空' },
];

const RULE_TYPE_OPTIONS = [
  { value: 'score_range', label: '分数区间（rule_config: {min, max}）' },
  { value: 'dimension_max', label: '维度最高（rule_config: {dimension}）' },
  { value: 'tag_match', label: '标签命中（rule_config: {tags, min_hits}）' },
];

const REPORT_LAYOUT_OPTIONS = [
  { value: 'standard', label: '标准（分型描述 + 推荐位）' },
  { value: 'radar', label: '雷达图（多维度可视化）' },
  { value: 'score_bar', label: '分数条' },
];

export default function QuestionnaireTemplatesPage() {
  const [items, setItems] = useState<QuestionnaireTemplate[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState('');
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editing, setEditing] = useState<QuestionnaireTemplate | null>(null);
  const [form] = Form.useForm();

  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTpl, setDrawerTpl] = useState<QuestionnaireTemplate | null>(null);
  const [questions, setQuestions] = useState<QuestionnaireQuestion[]>([]);
  const [classifications, setClassifications] = useState<ClassificationRule[]>([]);

  // [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐配置
  const [recommendConfigs, setRecommendConfigs] = useState<Record<string, any>>({});
  const [allTags, setAllTags] = useState<any[]>([]);
  const [allCategories, setAllCategories] = useState<any[]>([]);
  const [allProducts, setAllProducts] = useState<any[]>([]);
  const [recActiveKey, setRecActiveKey] = useState<string>('');
  const [previewItems, setPreviewItems] = useState<any[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);

  const loadRecommendMeta = useCallback(async () => {
    try {
      const [tagsRes, catsRes, prodsRes] = await Promise.all([
        get<any>('/api/admin/tags', { page: 1, page_size: 500 }),
        get<any>('/api/admin/product/categories').catch(() => ({ items: [] })),
        get<any>('/api/admin/products', { page: 1, page_size: 200 }).catch(() => ({ items: [] })),
      ]);
      setAllTags(tagsRes.items || []);
      setAllCategories(catsRes?.items || catsRes || []);
      setAllProducts(prodsRes?.items || prodsRes || []);
    } catch {
      // 静默
    }
  }, []);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/questionnaire/templates', {
        page,
        page_size: pageSize,
        ...(keyword ? { keyword } : {}),
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch {
      message.error('获取问卷模板列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, keyword]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const openEdit = (record?: QuestionnaireTemplate) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        ...record,
        status: record.status === 1,
        allow_back: record.allow_back !== false,
        shuffle_questions: !!record.shuffle_questions,
        result_display_mode: record.result_display_mode || 'simple',
        ai_followup_enabled: record.ai_followup_enabled !== false,
        recommend_click_mode: record.recommend_click_mode || 'drawer',
        recommend_display_count: record.recommend_display_count || 6,
        key_field_codes: Array.isArray(record.key_field_codes) ? record.key_field_codes : [],
      });
    } else {
      form.setFieldsValue({
        estimated_minutes: 3,
        allow_back: true,
        shuffle_questions: false,
        report_layout: 'standard',
        status: true,
        result_display_mode: 'simple',
        ai_followup_enabled: true,
        recommend_click_mode: 'drawer',
        recommend_display_count: 6,
        key_field_codes: [],
      });
    }
    setEditModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      // 推荐卡点击行为：若选 external 需二次确认
      if (values.recommend_click_mode === 'external') {
        const ok = await new Promise<boolean>((resolve) => {
          Modal.confirm({
            title: '确认选择"跳商城"？',
            content: '⚠️ 选择"跳商城"会让用户离开 AI 对话页，仅建议在【商品需大量展示评价/参数】等极少数场景使用。是否继续？',
            okText: '确认',
            cancelText: '改回抽屉',
            onOk: () => resolve(true),
            onCancel: () => resolve(false),
          });
        });
        if (!ok) {
          form.setFieldsValue({ recommend_click_mode: 'drawer' });
          return;
        }
      }
      const payload = {
        ...values,
        status: values.status ? 1 : 0,
        ai_followup_enabled: !!values.ai_followup_enabled,
      };
      if (editing) {
        await put(`/api/admin/questionnaire/templates/${editing.id}`, payload);
        message.success('更新成功');
      } else {
        await post('/api/admin/questionnaire/templates', payload);
        message.success('创建成功');
      }
      setEditModalOpen(false);
      fetchList();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const openDrawer = async (record: QuestionnaireTemplate) => {
    setDrawerTpl(record);
    setDrawerOpen(true);
    setRecommendConfigs({});
    try {
      const detail = await get<any>(`/api/questionnaire/templates/${record.id}`);
      setQuestions(detail.questions || []);
      setClassifications(detail.classifications || []);
      if ((detail.classifications || []).length) {
        setRecActiveKey(detail.classifications[0].code);
      }
      // 加载推荐配置 + 元数据
      const [recRes] = await Promise.all([
        get<any>(`/api/admin/questionnaire/templates/${record.id}/recommend`).catch(() => ({ configs: [] })),
      ]);
      const cfgMap: Record<string, any> = {};
      (recRes.configs || []).forEach((c: any) => {
        cfgMap[c.result_key] = c;
      });
      setRecommendConfigs(cfgMap);
      await loadRecommendMeta();
    } catch {
      setQuestions([]);
      setClassifications([]);
    }
  };

  const reloadDrawer = async () => {
    if (!drawerTpl) return;
    const detail = await get<any>(`/api/questionnaire/templates/${drawerTpl.id}`);
    setQuestions(detail.questions || []);
    setClassifications(detail.classifications || []);
  };

  // ─── Question CRUD ───
  const addQuestion = async () => {
    if (!drawerTpl) return;
    await post('/api/admin/questionnaire/questions', {
      template_id: drawerTpl.id,
      sort_order: (questions.length + 1) * 10,
      question_type: 'single_choice',
      title: '新题目',
      options: [
        { label: '选项 A', value: 'a', score: 0 },
        { label: '选项 B', value: 'b', score: 1 },
      ],
    });
    await reloadDrawer();
  };

  const editQuestion = async (q: QuestionnaireQuestion) => {
    Modal.confirm({
      title: `编辑题目 #${q.id}`,
      width: 640,
      content: (
        <div>
          <Text type="secondary">
            提示：本最小版直接编辑 JSON。后续会做可视化题目编辑器。
          </Text>
          <TextArea
            id={`q-edit-${q.id}`}
            rows={12}
            defaultValue={JSON.stringify(q, null, 2)}
          />
        </div>
      ),
      onOk: async () => {
        const ta = document.getElementById(`q-edit-${q.id}`) as HTMLTextAreaElement | null;
        if (!ta) return;
        try {
          const parsed = JSON.parse(ta.value);
          await put(`/api/admin/questionnaire/questions/${q.id}`, {
            sort_order: parsed.sort_order,
            question_type: parsed.question_type,
            title: parsed.title,
            subtitle: parsed.subtitle,
            required: parsed.required,
            options: parsed.options,
            dimension: parsed.dimension,
          });
          await reloadDrawer();
          message.success('保存成功');
        } catch (e: any) {
          message.error(e?.message || '保存失败');
        }
      },
    });
  };

  const deleteQuestion = async (q: QuestionnaireQuestion) => {
    await del(`/api/admin/questionnaire/questions/${q.id}`);
    await reloadDrawer();
  };

  // ─── Classification CRUD ───
  const addClassification = async () => {
    if (!drawerTpl) return;
    await post('/api/admin/questionnaire/classifications', {
      template_id: drawerTpl.id,
      code: `cls_${Date.now()}`,
      name: '新分型',
      rule_type: 'score_range',
      rule_config: { min: 0, max: 999 },
      sort_order: classifications.length * 10,
    });
    await reloadDrawer();
  };

  const editClassification = async (c: ClassificationRule) => {
    Modal.confirm({
      title: `编辑分型 #${c.id}`,
      width: 640,
      content: (
        <TextArea
          id={`c-edit-${c.id}`}
          rows={12}
          defaultValue={JSON.stringify(c, null, 2)}
        />
      ),
      onOk: async () => {
        const ta = document.getElementById(`c-edit-${c.id}`) as HTMLTextAreaElement | null;
        if (!ta) return;
        try {
          const parsed = JSON.parse(ta.value);
          await put(`/api/admin/questionnaire/classifications/${c.id}`, {
            code: parsed.code,
            name: parsed.name,
            description: parsed.description,
            rule_type: parsed.rule_type,
            rule_config: parsed.rule_config,
            sort_order: parsed.sort_order,
          });
          await reloadDrawer();
          message.success('保存成功');
        } catch (e: any) {
          message.error(e?.message || '保存失败');
        }
      },
    });
  };

  const deleteClassification = async (c: ClassificationRule) => {
    await del(`/api/admin/questionnaire/classifications/${c.id}`);
    await reloadDrawer();
  };

  // ─── [PRD-TAG-RECOMMEND-V1 2026-05-20] 推荐配置保存 / 预览 ───
  const updateRecConfig = (resultKey: string, patch: any) => {
    setRecommendConfigs((prev) => ({
      ...prev,
      [resultKey]: { ...(prev[resultKey] || { result_key: resultKey, mode: 1 }), ...patch },
    }));
  };

  const saveRecommendConfigs = async () => {
    if (!drawerTpl) return;
    const items = Object.values(recommendConfigs).filter((c: any) => c && c.result_key && c.mode);
    try {
      await put(`/api/admin/questionnaire/templates/${drawerTpl.id}/recommend`, { items });
      message.success('推荐配置已保存');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const previewRecommend = async (resultKey: string) => {
    if (!drawerTpl) return;
    const cfg = recommendConfigs[resultKey];
    if (!cfg) {
      message.warning('请先配置该分型的推荐');
      return;
    }
    try {
      const res = await post<any>(
        `/api/admin/questionnaire/templates/${drawerTpl.id}/recommend/preview`,
        {
          result_key: resultKey,
          mode: cfg.mode,
          filter_json: cfg.filter_json || null,
          manual_goods_ids: cfg.manual_goods_ids || null,
          limit: drawerTpl.recommend_display_count || 6,
        },
      );
      setPreviewItems(res.items || []);
      setPreviewOpen(true);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '预览失败');
    }
  };

  const handleDelete = (record: QuestionnaireTemplate) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除问卷模板「${record.name}」吗？该操作不可恢复。`,
      okType: 'danger',
      onOk: async () => {
        await del(`/api/admin/questionnaire/templates/${record.id}`);
        message.success('删除成功');
        fetchList();
      },
    });
  };

  return (
    <div data-testid="questionnaire-templates-page">
      <Title level={3}>通用问卷模板管理</Title>
      <Text type="secondary">
        所有问卷类业务（健康自查 / 体质测评 / 睡眠测评 / 焦虑量表 等）共用本模板表。
        新增问卷类业务时，运营在此新建模板 + 题目 + 分型，再到「功能按钮管理」绑定，
        无需开发改代码。
      </Text>

      <Space style={{ margin: '16px 0', width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Input.Search
            placeholder="按编码或名称搜索"
            allowClear
            style={{ width: 260 }}
            onSearch={(v) => {
              setKeyword(v);
              setPage(1);
            }}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEdit()}>
          新建问卷模板
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: (p, s) => {
            setPage(p);
            setPageSize(s);
          },
        }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 80 },
          { title: '编码', dataIndex: 'code', width: 200, render: (v) => <Tag color="blue">{v}</Tag> },
          { title: '名称', dataIndex: 'name' },
          {
            title: '来源',
            dataIndex: 'source',
            width: 100,
            render: (v) =>
              v === 'system_migrated'
                ? <Tag color="orange">系统迁移</Tag>
                : <Tag color="green">运营新建</Tag>,
          },
          { title: '预计分钟', dataIndex: 'estimated_minutes', width: 100 },
          {
            title: '状态',
            dataIndex: 'status',
            width: 100,
            render: (v) => (v === 1 ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>),
          },
          {
            title: '操作',
            width: 320,
            render: (_, record) => {
              // [PRD-AI-PAGE-OPTIM-V1 2026-05-21 块D] 健康自查双入口合并：
              // - 列表保留可见，但编辑按钮变为"前往专属配置页"跳转链接
              // - 内容字段不允许在此处直接编辑（避免双写打架）
              // - 删除按钮保留（统一在此处删除）
              const isHsc = record.code === 'health_self_check';
              if (isHsc) {
                return (
                  <Space>
                    <Tooltip title="健康自查模板有专属深度配置页（部位、症状持续档位、Prompt 模板等），请前往该页面进行编辑">
                      <Button
                        type="primary"
                        size="small"
                        icon={<ArrowRightOutlined />}
                        data-testid="goto-health-check-templates"
                        onClick={() => router.push('/health-check-templates')}
                      >
                        前往健康自查专属配置页
                      </Button>
                    </Tooltip>
                    <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record)}>
                      <Button size="small" danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                );
              }
              return (
                <Space>
                  <Button size="small" onClick={() => openDrawer(record)}>
                    题目/分型
                  </Button>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>
                    编辑
                  </Button>
                  <Popconfirm title="确认删除？" onConfirm={() => handleDelete(record)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              );
            },
          },
        ]}
      />

      {/* 编辑/新建模板 Modal */}
      <Modal
        title={editing ? '编辑问卷模板' : '新建问卷模板'}
        open={editModalOpen}
        onOk={handleSave}
        onCancel={() => setEditModalOpen(false)}
        destroyOnClose
        width={680}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="编码 code" name="code" rules={[{ required: true, message: '请输入模板编码' }]}>
            <Input placeholder="如 health_self_check / tcm_constitution / sleep_test_v1" disabled={!!editing} />
          </Form.Item>
          <Form.Item label="名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input maxLength={64} />
          </Form.Item>
          <Form.Item label="模板说明" name="description">
            <TextArea rows={2} placeholder="一句话介绍" />
          </Form.Item>
          <Form.Item label="开篇引导文" name="intro_text">
            <TextArea rows={3} placeholder="用户进入问卷时显示的引导文" />
          </Form.Item>
          <Space wrap>
            <Form.Item label="预计分钟" name="estimated_minutes">
              <InputNumber min={1} max={60} />
            </Form.Item>
            <Form.Item label="允许返回" name="allow_back" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="打乱题目顺序" name="shuffle_questions" valuePropName="checked">
              <Switch />
            </Form.Item>
            <Form.Item label="报告布局" name="report_layout">
              <Select options={REPORT_LAYOUT_OPTIONS} style={{ width: 180 }} />
            </Form.Item>
            <Form.Item label="启用" name="status" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item label="AI 解读 Prompt 模板" name="ai_prompt_template">
            <TextArea rows={4} placeholder="支持 {占位符}：分型名称 / 维度 / 得分 / 答题摘要 等" />
          </Form.Item>
          <Form.Item label="答完 AI 开场白" name="ai_opening">
            <Input placeholder="例如：根据您的答题，初步分析如下…" />
          </Form.Item>
          {/* [PRD-QUESTIONNAIRE-DRAWER-V1 2026-05-19] 结果摘要模板 */}
          <Form.Item
            label="结果摘要模板"
            name="result_summary_template"
            extra={
              <span>
                用于"问卷结果卡片"渲染，支持 <code>{'{题目名/维度}'}</code> 占位符。
                <br />
                示例：<code>部位：{'{部位}'} | 症状：{'{症状}'} | 持续：{'{持续时间}'}</code>
              </span>
            }
          >
            <TextArea
              rows={2}
              placeholder="部位：{部位} | 症状：{症状} | 持续：{持续时间}"
              maxLength={500}
              showCount
            />
          </Form.Item>

          {/* [PRD-TAG-RECOMMEND-V1 2026-05-20] 问卷完成后体验 4 配置项 */}
          <div
            style={{
              border: '1px solid #E0F2FE',
              borderRadius: 8,
              padding: '12px 14px',
              marginBottom: 16,
              background: '#F0F9FF',
            }}
            data-testid="qn-tpl-result-config-block"
          >
            <div style={{ fontWeight: 600, marginBottom: 10, color: '#0F172A' }}>
              问卷完成后体验配置
            </div>
            <Space wrap size="large">
              <Form.Item
                label="结果呈现形态"
                name="result_display_mode"
                extra="体质测评推荐选「三段式」"
              >
                <Select
                  style={{ width: 220 }}
                  data-testid="qn-result-display-mode"
                  options={[
                    { value: 'simple', label: '简单结果卡' },
                    { value: 'triple', label: '三段式（汇总+详情+推荐）' },
                  ]}
                />
              </Form.Item>
              <Form.Item
                label="AI 追问开关"
                name="ai_followup_enabled"
                valuePropName="checked"
                extra="完成问卷后 AI 主动接续"
              >
                <Switch checkedChildren="开" unCheckedChildren="关" data-testid="qn-ai-followup-switch" />
              </Form.Item>
              <Form.Item
                label="推荐卡点击行为"
                name="recommend_click_mode"
                extra="默认抽屉打开（强烈建议）"
              >
                <Select
                  style={{ width: 220 }}
                  data-testid="qn-click-mode-select"
                  options={[
                    { value: 'drawer', label: '抽屉打开（推荐）' },
                    {
                      value: 'external',
                      label: '⚠️ 跳商城（会离开 AI 对话页）',
                    },
                  ]}
                />
              </Form.Item>
              <Form.Item
                label="推荐展示数量"
                name="recommend_display_count"
                extra="横滑商品卡上限"
              >
                <Select
                  style={{ width: 120 }}
                  data-testid="qn-display-count-select"
                  options={[
                    { value: 4, label: '4 个' },
                    { value: 5, label: '5 个' },
                    { value: 6, label: '6 个（默认）' },
                  ]}
                />
              </Form.Item>
              {/* [BUG-HEALTH-SELF-CHECK-FIX-V1 2026-05-21] AI 追问关键字段 */}
              <Form.Item
                label="AI 追问关键字段"
                name="key_field_codes"
                extra="供 AI 追问 prompt 使用的关键字段名（按题目维度名填写，如 部位/症状/严重程度/持续时间）。空表示用全部摘要。"
                style={{ minWidth: 360 }}
              >
                <Select
                  mode="tags"
                  style={{ width: 360 }}
                  data-testid="qn-key-field-codes-select"
                  placeholder="按回车输入字段名，如「部位」「症状」「严重程度」「持续时间」"
                  tokenSeparators={[',', ' ']}
                  options={[
                    { value: '部位', label: '部位' },
                    { value: '症状', label: '症状' },
                    { value: '严重程度', label: '严重程度' },
                    { value: '持续时间', label: '持续时间' },
                    { value: '症状性质', label: '症状性质' },
                    { value: '症状备注', label: '症状备注' },
                  ]}
                />
              </Form.Item>
            </Space>
          </div>
        </Form>
      </Modal>

      {/* 题目 / 分型 抽屉 */}
      <Drawer
        title={drawerTpl ? `「${drawerTpl.name}」题目与分型` : ''}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={920}
      >
        <Tabs
          items={[
            {
              key: 'questions',
              label: `题目（${questions.length}）`,
              children: (
                <>
                  <Space style={{ marginBottom: 12 }}>
                    <Button icon={<PlusOutlined />} type="primary" onClick={addQuestion}>
                      新增题目
                    </Button>
                  </Space>
                  <Table
                    rowKey="id"
                    dataSource={questions}
                    pagination={false}
                    columns={[
                      { title: '#', dataIndex: 'sort_order', width: 60 },
                      { title: '类型', dataIndex: 'question_type', width: 100 },
                      { title: '题干', dataIndex: 'title', ellipsis: true },
                      { title: '维度', dataIndex: 'dimension', width: 120 },
                      {
                        title: '操作',
                        width: 160,
                        render: (_, q) => (
                          <Space>
                            <Button size="small" onClick={() => editQuestion(q)}>
                              编辑
                            </Button>
                            <Popconfirm
                              title="确认删除？"
                              onConfirm={() => deleteQuestion(q)}
                            >
                              <Button size="small" danger>
                                删除
                              </Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </>
              ),
            },
            {
              key: 'classifications',
              label: `分型规则（${classifications.length}）`,
              children: (
                <>
                  <Space style={{ marginBottom: 12 }}>
                    <Button icon={<PlusOutlined />} type="primary" onClick={addClassification}>
                      新增分型
                    </Button>
                  </Space>
                  <Table
                    rowKey="id"
                    dataSource={classifications}
                    pagination={false}
                    columns={[
                      { title: '编码', dataIndex: 'code' },
                      { title: '名称', dataIndex: 'name' },
                      { title: '规则类型', dataIndex: 'rule_type', width: 140 },
                      {
                        title: '规则配置',
                        dataIndex: 'rule_config',
                        render: (v) => <code style={{ fontSize: 12 }}>{JSON.stringify(v)}</code>,
                      },
                      {
                        title: '操作',
                        width: 160,
                        render: (_, c) => (
                          <Space>
                            <Button size="small" onClick={() => editClassification(c)}>
                              编辑
                            </Button>
                            <Popconfirm title="确认删除？" onConfirm={() => deleteClassification(c)}>
                              <Button size="small" danger>
                                删除
                              </Button>
                            </Popconfirm>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </>
              ),
            },
            {
              key: 'recommend',
              label: `关联推荐（${classifications.length} 分型）`,
              children: (
                <div data-testid="recommend-config-block">
                  <div style={{ color: '#666', marginBottom: 8, fontSize: 13 }}>
                    为每个分型独立配置推荐商品。三种模式：
                    <b>①标签智能匹配</b>（按类目+履约+标签筛选）/{' '}
                    <b>②按标签固定推荐</b>（仅按标签）/ <b>③手动挑商品</b>。
                    每个分型可选择其一。
                  </div>
                  {classifications.length === 0 ? (
                    <div style={{ padding: 24, color: '#999', textAlign: 'center' }}>
                      请先到「分型规则」Tab 创建分型
                    </div>
                  ) : (
                    <>
                      <Space style={{ marginBottom: 12 }}>
                        <Button type="primary" onClick={saveRecommendConfigs} data-testid="rec-save-btn">
                          保存全部分型推荐配置
                        </Button>
                      </Space>
                      <Tabs
                        activeKey={recActiveKey}
                        onChange={setRecActiveKey}
                        items={classifications.map((c) => {
                          const cfg = recommendConfigs[c.code] || { mode: 1, filter_json: {}, manual_goods_ids: [] };
                          const mode = cfg.mode || 1;
                          const fj = cfg.filter_json || {};
                          return {
                            key: c.code,
                            label: c.name,
                            children: (
                              <div style={{ padding: '8px 0' }}>
                                <Form layout="vertical">
                                  <Form.Item label="推荐模式">
                                    <Select
                                      style={{ width: 320 }}
                                      value={mode}
                                      onChange={(v) => updateRecConfig(c.code, { mode: v })}
                                      data-testid={`rec-mode-${c.code}`}
                                      options={[
                                        { value: 1, label: '① 标签智能匹配（类目+履约+标签）' },
                                        { value: 2, label: '② 按标签固定推荐（仅标签）' },
                                        { value: 3, label: '③ 手动挑商品' },
                                      ]}
                                    />
                                  </Form.Item>

                                  {(mode === 1 || mode === 2) && (
                                    <>
                                      {mode === 1 && (
                                        <>
                                          <Form.Item label="商品类目（可多选）">
                                            <Select
                                              mode="multiple"
                                              allowClear
                                              style={{ width: '100%' }}
                                              value={fj.category_ids || []}
                                              onChange={(v) => updateRecConfig(c.code, { filter_json: { ...fj, category_ids: v } })}
                                              options={(allCategories || []).map((ct: any) => ({
                                                value: ct.id,
                                                label: ct.name,
                                              }))}
                                              placeholder="不选则不限"
                                            />
                                          </Form.Item>
                                          <Form.Item label="履约方式（可多选）">
                                            <Select
                                              mode="multiple"
                                              allowClear
                                              style={{ width: '100%' }}
                                              value={fj.fulfillment_types || []}
                                              onChange={(v) => updateRecConfig(c.code, { filter_json: { ...fj, fulfillment_types: v } })}
                                              options={[
                                                { value: 'delivery', label: '实物配送' },
                                                { value: 'in_store', label: '到店服务' },
                                                { value: 'on_site', label: '上门服务' },
                                                { value: 'virtual', label: '权益服务' },
                                              ]}
                                              placeholder="不选则不限"
                                            />
                                          </Form.Item>
                                        </>
                                      )}
                                      <Form.Item label="属性标签（可多选）">
                                        <Select
                                          mode="multiple"
                                          allowClear
                                          showSearch
                                          optionFilterProp="label"
                                          style={{ width: '100%' }}
                                          value={fj.tag_ids || []}
                                          onChange={(v) => updateRecConfig(c.code, { filter_json: { ...fj, tag_ids: v } })}
                                          options={(allTags || []).map((t: any) => ({
                                            value: t.id,
                                            label: `${t.name}（${t.category}）`,
                                          }))}
                                          placeholder="按标签精准匹配"
                                        />
                                      </Form.Item>
                                    </>
                                  )}

                                  {mode === 3 && (
                                    <Form.Item label="手动挑商品（1~10 个）">
                                      <Select
                                        mode="multiple"
                                        allowClear
                                        showSearch
                                        optionFilterProp="label"
                                        style={{ width: '100%' }}
                                        value={cfg.manual_goods_ids || []}
                                        onChange={(v) => updateRecConfig(c.code, { manual_goods_ids: v })}
                                        options={(allProducts || []).map((p: any) => ({
                                          value: p.id,
                                          label: `${p.name}（¥${p.sale_price}）`,
                                        }))}
                                      />
                                    </Form.Item>
                                  )}

                                  <Space>
                                    <Button onClick={() => previewRecommend(c.code)} data-testid={`rec-preview-${c.code}`}>
                                      预览推荐
                                    </Button>
                                  </Space>
                                </Form>
                              </div>
                            ),
                          };
                        })}
                      />
                    </>
                  )}
                </div>
              ),
            },
          ]}
        />
      </Drawer>

      {/* 预览弹窗 */}
      <Modal
        title="推荐预览"
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={720}
      >
        {previewItems.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>
            根据当前配置，无匹配商品
          </div>
        ) : (
          <Table
            rowKey="id"
            dataSource={previewItems}
            pagination={false}
            columns={[
              { title: 'ID', dataIndex: 'id', width: 80 },
              { title: '商品名', dataIndex: 'name' },
              { title: '价格', dataIndex: 'sale_price', width: 100, render: (v) => `¥${v}` },
              { title: '履约', dataIndex: 'fulfillment_label', width: 100 },
              { title: '销量', dataIndex: 'sales_count', width: 80 },
              { title: '命中标签', dataIndex: 'hit_tags', width: 90 },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
