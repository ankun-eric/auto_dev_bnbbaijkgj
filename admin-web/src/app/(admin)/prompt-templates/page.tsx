'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography,
  Input,
  Button,
  Spin,
  message,
  Modal,
  Tag,
  Collapse,
  List,
  Space,
  Divider,
  Alert,
} from 'antd';
import {
  SaveOutlined,
  EyeOutlined,
  HistoryOutlined,
  RollbackOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface TemplateVersion {
  id: number;
  name: string;
  prompt_type: string;
  content: string;
  version: number;
  is_active: boolean;
  parent_id?: number | null;
  preview_input?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface PromptTemplateHistoryResponse {
  prompt_type: string;
  display_name: string;
  active?: TemplateVersion | null;
  history: TemplateVersion[];
}

const TEMPLATE_TYPES = [
  { key: 'checkup_report_interpret', label: '体检报告解读（对话式）' },
  { key: 'checkup_report_compare', label: '报告对比（对话式）' },
  { key: 'drug_general', label: '药物识别通用建议' },
  { key: 'drug_personal', label: '药物识别个性化建议' },
  { key: 'drug_interaction', label: '药物相互作用分析' },
  { key: 'drug_query', label: '用药咨询对话' },
  { key: 'drug_chat_opening_single', label: '用药对话首条消息（单药 · 4段式）' },
  { key: 'drug_chat_opening_multi', label: '用药对话首条消息（多药对比 · 最多2个）' },
  { key: 'checkup_report', label: '体检报告解读（旧·已下线）' },
  { key: 'trend_analysis', label: '趋势解读（已下线）' },
];

const DEFAULT_PREVIEW_INPUTS: Record<string, string> = {
  checkup_report:
    '血红蛋白 105g/L（参考120-160），血糖 7.2mmol/L（参考3.9-6.1），总胆固醇 5.8mmol/L（参考<5.2）',
  checkup_report_interpret:
    '姓名：张三\n关系：父亲\n年龄：58 岁\n血红蛋白 105g/L（参考120-160），血糖 7.2mmol/L（参考3.9-6.1）',
  checkup_report_compare:
    '咨询对象：爸爸 张三 58岁\n报告A（2025-01-15）：血糖 6.8mmol/L\n报告B（2026-04-20）：血糖 7.5mmol/L',
  drug_general: '阿莫西林胶囊 0.25g×24粒 用于呼吸道感染',
  drug_personal: '阿莫西林胶囊 0.25g×24粒 用于呼吸道感染',
  drug_interaction: '阿莫西林、布洛芬、阿司匹林',
  drug_query:
    '咨询对象：妈妈 李四 62岁，高血压\n药品列表：1. 氨氯地平片 5mg×28片；2. 阿司匹林肠溶片 100mg×30片',
  drug_chat_opening_single:
    '咨询对象：妈妈 李四 62岁，高血压\n药品：氨氯地平片 5mg×28片',
  drug_chat_opening_multi:
    '咨询对象：妈妈 李四 62岁，高血压\n药品A：氨氯地平片 5mg×28片\n药品B：硝苯地平缓释片 20mg×30片',
  trend_analysis:
    '血糖指标近3次：2024-01: 6.8mmol/L，2024-07: 7.1mmol/L，2025-01: 7.5mmol/L，参考范围3.9-6.1',
};

const PROMPT_VARIABLES: Record<string, { name: string; desc: string }[]> = {
  checkup_report_interpret: [
    { name: '{member_info}', desc: '咨询人档案（姓名、关系、年龄、性别、身高体重、慢病史、过敏史）' },
    { name: '{report_ocr_text}', desc: '报告 OCR 全文' },
    { name: '{report_date}', desc: '报告日期（YYYY-MM-DD）' },
    { name: '{report_title}', desc: '报告标题' },
  ],
  checkup_report_compare: [
    { name: '{member_info}', desc: '咨询人档案' },
    { name: '{report_a_date}', desc: '报告 A 日期（较早）' },
    { name: '{report_a_title}', desc: '报告 A 标题' },
    { name: '{report_a_ocr}', desc: '报告 A OCR 文本' },
    { name: '{report_b_date}', desc: '报告 B 日期（较晚）' },
    { name: '{report_b_title}', desc: '报告 B 标题' },
    { name: '{report_b_ocr}', desc: '报告 B OCR 文本' },
  ],
  drug_query: [
    { name: '{member_info}', desc: '咨询人健康档案（姓名、关系、年龄、慢病史、过敏史等）' },
    { name: '{drug_list}', desc: '药品列表（名称、规格、用法等）' },
  ],
  drug_chat_opening_single: [
    { name: '{member_info}', desc: '咨询人健康档案' },
    { name: '{drug_list}', desc: '药品信息（单药）' },
  ],
  drug_chat_opening_multi: [
    { name: '{member_info}', desc: '咨询人健康档案' },
    { name: '{drug_list}', desc: '药品信息（最多 2 个，用于对比）' },
  ],
};

const TYPE_HINTS: Record<string, string> = {
  drug_query:
    '支持占位符 {member_info}（健康档案）+ {drug_list}（药品列表），系统会在调用 AI 时自动替换。',
  drug_chat_opening_single:
    '用药对话首条消息（单药 · 4段式）。支持占位符 {member_info} + {drug_list}，系统会在调用 AI 时自动替换。',
  drug_chat_opening_multi:
    '用药对话首条消息（多药对比 · 最多 2 个）。支持占位符 {member_info} + {drug_list}，系统会在调用 AI 时自动替换。',
};

export default function PromptTemplatesPage() {
  const [activeType, setActiveType] = useState('checkup_report');
  const [templates, setTemplates] = useState<Record<string, PromptTemplateHistoryResponse>>({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewInput, setPreviewInput] = useState('');
  const [previewResult, setPreviewResult] = useState('');
  const [previewing, setPreviewing] = useState(false);
  const [rollingBack, setRollingBack] = useState<number | null>(null);

  const fetchTemplate = useCallback(async (type: string) => {
    setLoading(true);
    try {
      const res = await get<PromptTemplateHistoryResponse>(`/api/admin/prompt-templates/${type}`);
      setTemplates((prev) => ({ ...prev, [type]: res }));
    } catch {
      message.error('获取模板失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTemplate(activeType);
  }, [activeType, fetchTemplate]);

  const handleContentChange = (value: string) => {
    setTemplates((prev) => {
      const current = prev[activeType];
      if (!current) return prev;
      return {
        ...prev,
        [activeType]: {
          ...current,
          active: current.active
            ? { ...current.active, content: value }
            : {
                id: 0,
                name: activeType,
                prompt_type: activeType,
                content: value,
                version: 1,
                is_active: true,
              },
        },
      };
    });
  };

  const handleSave = async () => {
    const tpl = templates[activeType];
    if (!tpl?.active?.content?.trim()) {
      message.warning('请输入模板内容');
      return;
    }
    setSaving(true);
    try {
      await put(`/api/admin/prompt-templates/${activeType}`, { content: tpl.active.content });
      message.success('保存成功，已自动创建新版本');
      fetchTemplate(activeType);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleOpenPreview = () => {
    setPreviewInput(DEFAULT_PREVIEW_INPUTS[activeType] || '');
    setPreviewResult('');
    setPreviewOpen(true);
  };

  const handlePreview = async () => {
    if (!previewInput.trim()) {
      message.warning('请输入示例内容');
      return;
    }
    setPreviewing(true);
    try {
      const res = await post<{ prompt_type: string; input_text: string; ai_result: any }>(
        `/api/admin/prompt-templates/${activeType}/preview`,
        { input_text: previewInput }
      );
      const aiResult = res.ai_result;
      setPreviewResult(
        typeof aiResult === 'string' ? aiResult : JSON.stringify(aiResult, null, 2)
      );
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '预览失败';
      message.error(typeof detail === 'string' ? detail : '预览失败');
    } finally {
      setPreviewing(false);
    }
  };

  const handleRollback = async (version: number) => {
    setRollingBack(version);
    try {
      await post(`/api/admin/prompt-templates/${activeType}/rollback/${version}`);
      message.success(`已回滚到版本 v${version}`);
      fetchTemplate(activeType);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '回滚失败';
      message.error(typeof detail === 'string' ? detail : '回滚失败');
    } finally {
      setRollingBack(null);
    }
  };

  const currentTplGroup = templates[activeType];
  const currentTpl = currentTplGroup?.active;
  const currentTypeLabel = TEMPLATE_TYPES.find((t) => t.key === activeType)?.label || '';

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        Prompt 模板配置
      </Title>
      <div style={{ display: 'flex', gap: 0, minHeight: 600 }}>
        {/* Left nav */}
        <div
          style={{
            width: 200,
            flexShrink: 0,
            borderRight: '1px solid #f0f0f0',
            paddingRight: 0,
          }}
        >
          {TEMPLATE_TYPES.map((type) => (
            <div
              key={type.key}
              onClick={() => setActiveType(type.key)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderRadius: '8px 0 0 8px',
                marginBottom: 4,
                background: activeType === type.key ? '#f0f5ff' : 'transparent',
                borderRight:
                  activeType === type.key ? '3px solid #4096ff' : '3px solid transparent',
                color: activeType === type.key ? '#4096ff' : '#333',
                fontWeight: activeType === type.key ? 600 : 400,
                transition: 'all 0.2s',
                fontSize: 14,
              }}
            >
              {type.label}
            </div>
          ))}
        </div>

        {/* Right content */}
        <div style={{ flex: 1, paddingLeft: 24 }}>
          <Spin spinning={loading}>
            {/* Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                marginBottom: 16,
                flexWrap: 'wrap',
              }}
            >
              <Title level={5} style={{ margin: 0 }}>
                {currentTypeLabel}
              </Title>
              {currentTpl?.version != null && (
                <Tag color="blue">版本 v{currentTpl.version}</Tag>
              )}
              {currentTpl?.updated_at && (
                <Text type="secondary" style={{ fontSize: 13 }}>
                  最后修改时间：{dayjs(currentTpl.updated_at).format('YYYY-MM-DD HH:mm:ss')}
                </Text>
              )}
            </div>

            {/* 类型使用提示 */}
            {TYPE_HINTS[activeType] && (
              <Alert
                type="info"
                showIcon
                message={TYPE_HINTS[activeType]}
                style={{ marginBottom: 12 }}
              />
            )}

            {/* 变量占位符说明 */}
            {PROMPT_VARIABLES[activeType] && (
              <div style={{ marginBottom: 12, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6, padding: '10px 12px' }}>
                <Text strong style={{ fontSize: 13, color: '#389e0d' }}>支持的变量占位符（后端自动渲染）：</Text>
                <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {PROMPT_VARIABLES[activeType].map((v) => (
                    <Tag key={v.name} color="green" style={{ margin: 0 }}>
                      <code>{v.name}</code> - {v.desc}
                    </Tag>
                  ))}
                </div>
              </div>
            )}

            {/* TextArea */}
            <TextArea
              rows={16}
              value={currentTpl?.content || ''}
              onChange={(e) => handleContentChange(e.target.value)}
              placeholder={`请输入 ${currentTypeLabel} 的 Prompt 模板内容...`}
              style={{ marginBottom: 16, fontSize: 14, lineHeight: 1.7 }}
            />

            {/* Action buttons */}
            <Space style={{ marginBottom: 24 }}>
              <Button icon={<EyeOutlined />} onClick={handleOpenPreview}>
                预览效果
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
              >
                保存
              </Button>
            </Space>

            {/* History versions */}
            {currentTplGroup?.history && currentTplGroup.history.length > 0 && (
              <Collapse
                ghost
                items={[
                  {
                    key: 'history',
                    label: (
                      <Space>
                        <HistoryOutlined />
                        <span>历史版本（{currentTplGroup.history.length} 条）</span>
                      </Space>
                    ),
                    children: (
                      <List
                        size="small"
                        dataSource={currentTplGroup.history}
                        renderItem={(ver) => (
                          <List.Item
                            actions={[
                              <Button
                                key="rollback"
                                size="small"
                                icon={<RollbackOutlined />}
                                loading={rollingBack === ver.version}
                                onClick={() => handleRollback(ver.version)}
                                disabled={ver.version === currentTpl?.version}
                              >
                                {ver.version === currentTpl?.version ? '当前版本' : '回滚'}
                              </Button>,
                            ]}
                          >
                            <Space>
                              <Tag>v{ver.version}</Tag>
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {dayjs(ver.created_at).format('YYYY-MM-DD HH:mm:ss')}
                              </Text>
                            </Space>
                          </List.Item>
                        )}
                      />
                    ),
                  },
                ]}
              />
            )}
          </Spin>
        </div>
      </div>

      {/* Preview Modal */}
      <Modal
        title={`预览效果 - ${currentTypeLabel}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={720}
        destroyOnClose
      >
        <div style={{ marginBottom: 8 }}>
          <Text strong>示例输入：</Text>
        </div>
        <TextArea
          rows={4}
          value={previewInput}
          onChange={(e) => setPreviewInput(e.target.value)}
          placeholder="请输入示例输入内容..."
          style={{ marginBottom: 12 }}
        />
        <Button
          type="primary"
          onClick={handlePreview}
          loading={previewing}
          style={{ marginBottom: 16 }}
        >
          发送预览
        </Button>

        {previewResult && (
          <>
            <Divider style={{ margin: '12px 0' }} />
            <div style={{ marginBottom: 8 }}>
              <Text strong>AI 返回结果：</Text>
            </div>
            <div
              style={{
                background: '#f8f9fa',
                borderRadius: 8,
                padding: 16,
                whiteSpace: 'pre-wrap',
                fontSize: 14,
                lineHeight: 1.8,
                maxHeight: 400,
                overflowY: 'auto',
                border: '1px solid #e8e8e8',
              }}
            >
              {previewResult}
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
