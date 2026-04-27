'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Toast, ImageUploader, type ImageUploadItem, Input, TextArea } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';

const FEEDBACK_TYPES = [
  { value: 'feature', label: '功能建议' },
  { value: 'bug', label: '故障反馈' },
  { value: 'content', label: '内容问题' },
  { value: 'service', label: '服务体验' },
  { value: 'other', label: '其他' },
];

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function FeedbackPage() {
  const router = useRouter();
  const [feedbackType, setFeedbackType] = useState('');
  const [content, setContent] = useState('');
  const [images, setImages] = useState<ImageUploadItem[]>([]);
  const [contact, setContact] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!feedbackType) { Toast.show({ content: '请选择反馈类型' }); return; }
    if (!content.trim()) { Toast.show({ content: '请填写反馈内容' }); return; }
    if (content.length > 500) { Toast.show({ content: '内容不超过500字' }); return; }

    setSubmitting(true);
    try {
      const imageUrls = images.map(img => img.url).filter(Boolean);
      await api.post('/api/feedback', {
        feedback_type: feedbackType,
        description: content.trim(),
        images: imageUrls,
        contact: contact.trim() || undefined,
      });
      Toast.show({ content: '提交成功，感谢反馈！', icon: 'success' });
      router.back();
    } catch {
      Toast.show({ content: '提交失败', icon: 'fail' });
    }
    setSubmitting(false);
  };

  const uploadImage = async (file: File): Promise<ImageUploadItem> => {
    const formData = new FormData();
    formData.append('file', file);
    const res: any = await api.post('/api/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    const data = res.data || res;
    return { url: data.url || data.file_url || '' };
  };

  return (
    <div className="min-h-screen" style={{ background: THEME.background }}>
      <NavBar
        onBack={() => router.back()}
        style={{ background: THEME.cardBg, '--border-bottom': `1px solid ${THEME.divider}` } as React.CSSProperties}
      >
        <span style={{ color: THEME.textPrimary, fontWeight: 600 }}>意见反馈</span>
      </NavBar>

      <div className="px-4 py-4 space-y-4">
        {/* Feedback Type */}
        <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
          <div className="text-sm font-semibold mb-3" style={{ color: THEME.textPrimary }}>反馈类型</div>
          <div className="flex flex-wrap gap-2">
            {FEEDBACK_TYPES.map(type => (
              <button
                key={type.value}
                className="px-4 py-2 rounded-full text-sm"
                style={{
                  background: feedbackType === type.value ? THEME.primary : THEME.primaryLight,
                  color: feedbackType === type.value ? '#fff' : THEME.primary,
                  fontWeight: feedbackType === type.value ? 600 : 400,
                }}
                onClick={() => setFeedbackType(type.value)}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold" style={{ color: THEME.textPrimary }}>问题描述</span>
            <span className="text-xs" style={{ color: content.length > 500 ? '#FF4D4F' : THEME.textSecondary }}>
              {content.length}/500
            </span>
          </div>
          <TextArea
            placeholder="请详细描述您遇到的问题或建议..."
            value={content}
            onChange={setContent}
            rows={5}
            maxLength={500}
            style={{ '--font-size': '14px' }}
          />
        </div>

        {/* Images */}
        <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
          <div className="text-sm font-semibold mb-3" style={{ color: THEME.textPrimary }}>
            上传图片 <span className="font-normal text-xs" style={{ color: THEME.textSecondary }}>（最多4张）</span>
          </div>
          <ImageUploader
            value={images}
            onChange={setImages}
            upload={uploadImage}
            maxCount={4}
            style={{ '--cell-size': '80px' }}
          />
        </div>

        {/* Contact */}
        <div className="rounded-2xl p-4" style={{ background: THEME.cardBg }}>
          <div className="text-sm font-semibold mb-2" style={{ color: THEME.textPrimary }}>
            联系方式 <span className="font-normal text-xs" style={{ color: THEME.textSecondary }}>（选填）</span>
          </div>
          <Input
            placeholder="手机号或邮箱，方便我们联系您"
            value={contact}
            onChange={setContact}
            style={{ '--font-size': '14px' }}
          />
        </div>

        {/* Submit */}
        <button
          className="w-full py-3 rounded-xl text-white font-medium text-base"
          style={{ background: submitting ? '#ccc' : THEME.primary }}
          disabled={submitting}
          onClick={handleSubmit}
        >
          {submitting ? '提交中...' : '提交反馈'}
        </button>
      </div>
    </div>
  );
}
