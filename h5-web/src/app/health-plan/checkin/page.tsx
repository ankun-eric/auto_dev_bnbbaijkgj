'use client';

/**
 * [PRD-439 F-08] 健康打卡入口下线
 *
 * 原 /health-plan/checkin 页面已被 ai-home 中的 🔔 提醒铃铛 + 今日待办抽屉取代。
 * 这里仅做客户端重定向到 /ai-home，并提示"已升级"。
 *
 * 历史打卡数据保留在数据库，本页面不再访问。
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Toast } from 'antd-mobile';

export default function CheckinPage() {
  const router = useRouter();

  useEffect(() => {
    Toast.show({
      content: '健康打卡已升级为提醒，请在首页右下角 🔔 查看',
      duration: 2500,
    });
    const timer = setTimeout(() => {
      router.replace('/ai-home');
    }, 300);
    return () => clearTimeout(timer);
  }, [router]);

  return (
    <div
      data-testid="prd439-checkin-redirect"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#6B7280',
        fontSize: 14,
        background: '#F5F5F7',
      }}
    >
      正在跳转…
    </div>
  );
}
