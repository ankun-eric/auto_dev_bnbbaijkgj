'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  NavBar,
  Card,
  Rate,
  TextArea,
  ImageUploader,
  Button,
  Toast,
} from 'antd-mobile';
import type { ImageUploadItem } from 'antd-mobile/es/components/image-uploader';
import api from '@/lib/api';

export default function ReviewPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = params.orderId as string;
  const [rating, setRating] = useState(5);
  const [content, setContent] = useState('');
  const [images, setImages] = useState<ImageUploadItem[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const handleUpload = async (file: File): Promise<ImageUploadItem> => {
    const url = URL.createObjectURL(file);
    return { url };
  };

  const handleSubmit = async () => {
    if (rating < 1) {
      Toast.show({ content: '请选择评分' });
      return;
    }
    setSubmitting(true);
    try {
      const reviewData: any = {
        rating,
        content: content || undefined,
        images: images.length > 0 ? images.map((img) => img.url) : undefined,
      };
      await api.post(`/api/orders/unified/${orderId}/review`, reviewData);
      Toast.show({ content: '评价成功', icon: 'success' });
      router.back();
    } catch (err: any) {
      Toast.show({ content: err?.response?.data?.detail || '评价失败' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        评价订单
      </NavBar>

      <div className="px-4 pt-4">
        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-3">请为本次服务评分</div>
            <Rate
              value={rating}
              onChange={setRating}
              style={{
                '--star-size': '32px',
                '--active-color': '#faad14',
              }}
            />
            <div className="text-xs text-gray-400 mt-2">
              {rating === 5 ? '非常满意' : rating === 4 ? '满意' : rating === 3 ? '一般' : rating === 2 ? '不满意' : '非常不满意'}
            </div>
          </div>
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="text-sm text-gray-500 mb-2">文字评价</div>
          <TextArea
            placeholder="分享您的使用体验，帮助其他用户做出更好的选择"
            value={content}
            onChange={setContent}
            maxLength={500}
            showCount
            rows={4}
          />
        </Card>

        <Card style={{ borderRadius: 12, marginBottom: 12 }}>
          <div className="text-sm text-gray-500 mb-2">上传图片（选填）</div>
          <ImageUploader
            value={images}
            onChange={setImages}
            upload={handleUpload}
            maxCount={6}
            style={{ '--cell-size': '80px' }}
          />
        </Card>
      </div>

      <div
        className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full bg-white border-t border-gray-100 px-4 py-3"
        style={{ maxWidth: 750, paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
      >
        <Button
          block
          loading={submitting}
          onClick={handleSubmit}
          style={{
            borderRadius: 24,
            height: 44,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 'none',
          }}
        >
          提交评价
        </Button>
      </div>
    </div>
  );
}
