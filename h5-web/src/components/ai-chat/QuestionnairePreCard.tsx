/**
 * [PRD-TCM-DRAWER-V12 2026-05-20] 通用问卷"对话内说明卡片"组件
 *
 * [PRD-AICHAT-FUNCCARD-V2 2026-05-20] 改造说明：
 *   - 不再单独维护一套视觉样式，统一委托 FunctionCardV2 渲染
 *   - 历史会话回看也直接以新版样式呈现（一刀切刷新，无版本字段判断）
 *
 * 数据契约（来自后端 chat_function_buttons）与旧版完全一致，外部调用方零改动。
 */
'use client';

import React from 'react';
import FunctionCardV2 from './FunctionCardV2';

export interface QuestionnairePreCardData {
  buttonId: number;
  templateId?: number | null;
  templateCode?: string | null;
  title: string;
  subtitle?: string | null;
  coverImage?: string | null;
  description?: string | null;
  buttonText?: string;
  icon?: string | null;
  iconType?: 'url' | 'emoji' | 'default' | string | null;
  /** 按钮副说明文字（v2 新增展示位） */
  buttonSubDesc?: string | null;
}

interface QuestionnairePreCardProps {
  data: QuestionnairePreCardData;
  onStart: (data: QuestionnairePreCardData) => void;
}

export default function QuestionnairePreCard({ data, onStart }: QuestionnairePreCardProps) {
  // 副标题：优先用 subtitle，否则降级使用 description（保持旧版数据兼容）
  const subtitle = (data.subtitle && data.subtitle.trim())
    || (data.description && data.description.trim())
    || null;

  return (
    <div data-testid="questionnaire-pre-card">
      <FunctionCardV2
        testid="questionnaire-pre-card-fcv2"
        data={{
          title: data.title || '健康测评',
          subtitle,
          coverImage: data.coverImage || null,
          icon: data.icon || null,
          iconType: data.iconType || 'default',
          buttonSubDesc: data.buttonSubDesc || null,
          // [PRD-AICHAT-FUNCCARD-V2-DESIGN-D 2026-05-20 v1.2] 决策 12：固定「开始」
          buttonText: '开始',
        }}
        onClick={() => onStart(data)}
      />
    </div>
  );
}
