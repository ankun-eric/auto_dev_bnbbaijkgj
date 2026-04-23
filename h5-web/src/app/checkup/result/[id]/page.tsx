'use client';

/**
 * [2026-04-23] 旧的结构化解读页下线，保留路由作为 Loading 中转页：
 * - 查询报告 detail -> 如有 interpret_session_id 则跳 /chat/{sid}（对话页统一化后）
 * - 否则调 /api/report/interpret/start 创建会话再跳
 */
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { SpinLoading, Toast } from 'antd-mobile';
import api from '@/lib/api';

export default function CheckupResultLoadingPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const detail: any = await api.get(`/api/checkup/reports/${id}`);
        if (detail?.interpret_session_id) {
          // [2026-04-23 对话页统一化] 跳转改向公共咨询页
          router.replace(`/chat/${detail.interpret_session_id}?type=report_interpret`);
          return;
        }
        // [2026-04-23] 老数据懒加载：使用 /api/checkup/reports/{id}/ensure-session
        const resp: any = await api.post(`/api/checkup/reports/${id}/ensure-session`, {
          member_id: detail?.member_id,
        });
        const sid = resp?.session_id;
        if (sid) {
          // [2026-04-23 对话页统一化] 跳转改向公共咨询页
          router.replace(`/chat/${sid}?auto_start=1&type=report_interpret`);
        } else {
          router.replace(`/checkup/detail/${id}`);
        }
      } catch (e: any) {
        Toast.show({ content: e?.message || '加载失败' });
        router.replace(`/checkup/detail/${id}`);
      }
    })();
  }, [id, router]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
      <SpinLoading color="primary" style={{ '--size': '40px' } as any} />
      <div style={{ fontSize: 14, color: '#666' }}>正在为您准备 AI 解读...</div>
    </div>
  );
}
