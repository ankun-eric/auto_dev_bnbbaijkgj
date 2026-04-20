'use client';

import { useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { SpinLoading } from 'antd-mobile';

/**
 * 已废弃：旧简版诊断详情页。
 * PRD v1.0（测评记录优化）明确：所有测评记录点击统一跳转 /tcm/result/{id}。
 * 此路由仅作为兜底，用于外部分享链接自动跳转到新版 6 屏结果页。
 */
export default function DeprecatedDiagnosisPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string | undefined;

  useEffect(() => {
    if (id) {
      router.replace(`/tcm/result/${id}`);
    } else {
      router.replace('/tcm');
    }
  }, [id, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SpinLoading style={{ '--size': '32px', '--color': '#52c41a' }} />
    </div>
  );
}
