'use client';

// [2026-04-24] 移动端 - P2 页面兜底提示：请用 PC 访问

import React from 'react';
import { NavBar, Button, Toast } from 'antd-mobile';
import { useRouter } from 'next/navigation';

export default function PcOnlyPage({
  title,
  pcPath,
  description,
}: {
  title: string;
  pcPath: string;
  description?: string;
}) {
  const router = useRouter();

  const copyLink = () => {
    const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
    const url = `${window.location.origin}${basePath}${pcPath}?desktop=1`;
    navigator.clipboard?.writeText(url).then(
      () => Toast.show({ icon: 'success', content: 'PC 端链接已复制' }),
      () => Toast.show({ content: url })
    );
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa' }}>
      <NavBar onBack={() => router.back()}>{title}</NavBar>
      <div
        style={{
          padding: '48px 24px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 56, marginBottom: 12 }}>💻</div>
        <div style={{ fontSize: 16, fontWeight: 600, color: '#333', marginBottom: 8 }}>
          请使用电脑访问 PC 商家端
        </div>
        <div style={{ fontSize: 13, color: '#999', marginBottom: 24, lineHeight: 1.6 }}>
          {description || `「${title}」功能内容较多，移动端暂未适配，请使用电脑浏览器访问 PC 商家端进行操作。`}
        </div>
        <Button color="primary" onClick={copyLink}>
          复制 PC 端链接
        </Button>
      </div>
    </div>
  );
}
