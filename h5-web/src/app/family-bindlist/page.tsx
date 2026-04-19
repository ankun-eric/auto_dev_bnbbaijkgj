'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Dialog, Button } from 'antd-mobile';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

interface ManagedByItem {
  id: number;
  manager_user_id: number;
  manager_nickname?: string;
  status: string;
  created_at: string;
}

export default function FamilyBindListPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [list, setList] = useState<ManagedByItem[]>([]);

  const fetchList = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/family/managed-by');
      const data = res.data || res;
      setList(Array.isArray(data.items) ? data.items : []);
    } catch {
      setList([]);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleRevoke = async (item: ManagedByItem) => {
    const result = await Dialog.confirm({
      title: '取消授权',
      content: `确定取消 ${item.manager_nickname || '该用户'} 对您健康档案的管理权限吗？取消后对方将无法查看您的档案。`,
    });
    if (!result) return;
    try {
      await api.delete(`/api/family/management/${item.id}`);
      Toast.show({ content: '已取消授权', icon: 'success' });
      await fetchList();
    } catch {
      Toast.show({ content: '操作失败，请重试', icon: 'fail' });
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    } catch {
      return '';
    }
  };

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(160deg, #f0faf0 0%, #e8f4ff 100%)' }}>
      <GreenNavBar>
        家庭关联
      </GreenNavBar>

      <div className="px-4 pt-2 pb-8">
        {/* Header description */}
        <div
          className="rounded-xl px-4 py-3 mb-4"
          style={{ background: '#e6f7ff', border: '1px solid #91d5ff' }}
        >
          <div className="flex items-center gap-2">
            <span style={{ fontSize: 16 }}>👥</span>
            <span className="text-xs text-gray-600">
              以下用户正在管理您的健康档案，您可以随时取消授权
            </span>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16 text-gray-400 text-sm">加载中...</div>
        ) : list.length === 0 ? (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">🔒</div>
            <div className="text-sm text-gray-400">暂无管理您档案的用户</div>
          </div>
        ) : (
          <div className="space-y-3">
            {list.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl bg-white p-4"
                style={{ boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
              >
                <div className="flex items-center">
                  {/* Avatar placeholder */}
                  <div
                    className="flex items-center justify-center rounded-full flex-shrink-0"
                    style={{
                      width: 44,
                      height: 44,
                      background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
                    }}
                  >
                    <span className="text-white text-lg">
                      {(item.manager_nickname || '?')[0]}
                    </span>
                  </div>

                  <div className="ml-3 flex-1 min-w-0">
                    <div className="text-sm font-semibold text-gray-800 truncate">
                      {item.manager_nickname || '未知用户'}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      关联时间：{formatDate(item.created_at)}
                    </div>
                  </div>

                  <Button
                    size="mini"
                    style={{
                      '--border-color': '#ff4d4f',
                      '--text-color': '#ff4d4f',
                      borderRadius: 16,
                      fontSize: 12,
                    }}
                    onClick={() => handleRevoke(item)}
                  >
                    取消授权
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
