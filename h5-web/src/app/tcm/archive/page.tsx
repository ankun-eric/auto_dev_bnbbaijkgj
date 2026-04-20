'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Empty, SpinLoading } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface ArchiveItem {
  diagnosis_id: number;
  created_at: string;
  member_label: string;
  constitution_type: string;
  persona_emoji: string;
  persona_color: string;
  one_line_desc: string;
}

/**
 * 我的体质档案（Phase 1 最简版）
 * 列表展示历史测评记录，点击跳转到对应的 6 屏结果页。
 */
export default function TcmArchivePage() {
  const router = useRouter();
  const [items, setItems] = useState<ArchiveItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/constitution/archive');
        const data = res.data || res;
        setItems(data.items || []);
      } catch (err) {
        setItems([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <GreenNavBar back={() => router.push('/tcm')}>我的体质档案</GreenNavBar>

      {loading && (
        <div className="flex flex-col items-center py-20">
          <SpinLoading style={{ '--size': '36px', '--color': '#52c41a' }} />
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="py-20">
          <Empty description="暂无测评记录，快去完成一次体质测评吧" />
          <div className="text-center mt-4">
            <button
              onClick={() => router.push('/tcm')}
              className="px-6 py-2 rounded-full text-sm text-white"
              style={{ background: 'linear-gradient(135deg, #52c41a, #13c2c2)' }}
            >
              开始测评
            </button>
          </div>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div className="p-4 space-y-3">
          <div className="text-[11px] text-gray-400 px-1">
            共 {items.length} 次测评记录
          </div>
          {items.map((it) => (
            <div
              key={it.diagnosis_id}
              onClick={() => router.push(`/tcm/result/${it.diagnosis_id}`)}
              className="bg-white rounded-xl p-4 shadow-sm active:bg-gray-50 cursor-pointer"
              style={{ borderLeft: `4px solid ${it.persona_color}` }}
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center text-2xl flex-shrink-0"
                  style={{ background: `${it.persona_color}15` }}
                >
                  {it.persona_emoji || '🌿'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2">
                    <span
                      className="font-bold text-base"
                      style={{ color: it.persona_color }}
                    >
                      {it.constitution_type}
                    </span>
                    <span className="text-[11px] text-gray-400">
                      {it.member_label}
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-500 mt-0.5 truncate">
                    {it.one_line_desc}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1">
                    {new Date(it.created_at).toLocaleString()}
                  </div>
                </div>
                <span className="text-gray-300">›</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
