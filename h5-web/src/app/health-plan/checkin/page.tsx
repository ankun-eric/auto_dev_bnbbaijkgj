'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Card, Button, Dialog, Toast, SpinLoading, ProgressBar, SwipeAction } from 'antd-mobile';
import { AddOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface CheckinItem {
  id: number;
  name: string;
  target_value: number | null;
  target_unit: string;
  actual_value: number | null;
  is_checked: boolean;
  remind_time: string | null;
  repeat_frequency: string;
  today_completed?: boolean;
}

export default function CheckinPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<CheckinItem[]>([]);
  const [inputVisible, setInputVisible] = useState<number | null>(null);
  const [inputValue, setInputValue] = useState('');

  const fetchData = useCallback(async () => {
    try {
      const res: any = await api.get('/api/health-plan/checkin-items');
      const data = res.data || res;
      const rawItems = data.items || data || [];
      setItems(rawItems.map((item: any) => ({
        ...item,
        is_checked: item.today_completed || false,
        remind_time: Array.isArray(item.remind_times) ? item.remind_times[0] : item.remind_time || null,
      })));
    } catch {
      Toast.show({ content: '加载失败', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSimpleCheck = async (item: CheckinItem) => {
    try {
      await api.post(`/api/health-plan/checkin-items/${item.id}/checkin`, { actual_value: null });
      Toast.show({ content: '打卡成功', icon: 'success' });
      fetchData();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  const handleValueCheck = async (item: CheckinItem) => {
    const val = parseFloat(inputValue);
    if (isNaN(val) || val < 0) {
      Toast.show({ content: '请输入有效数值', icon: 'fail' });
      return;
    }
    try {
      await api.post(`/api/health-plan/checkin-items/${item.id}/checkin`, { actual_value: val });
      Toast.show({ content: '打卡成功', icon: 'success' });
      setInputVisible(null);
      setInputValue('');
      fetchData();
    } catch {
      Toast.show({ content: '打卡失败', icon: 'fail' });
    }
  };

  const handleDelete = async (item: CheckinItem) => {
    const confirmed = await Dialog.confirm({ content: `确定删除「${item.name}」吗？` });
    if (confirmed) {
      try {
        await api.delete(`/api/health-plan/checkin-items/${item.id}`);
        Toast.show({ content: '删除成功', icon: 'success' });
        fetchData();
      } catch {
        Toast.show({ content: '删除失败', icon: 'fail' });
      }
    }
  };

  const getProgress = (item: CheckinItem): number => {
    if (!item.target_value || item.target_value <= 0) return item.is_checked ? 100 : 0;
    return Math.min(100, Math.round(((item.actual_value || 0) / item.target_value) * 100));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>健康打卡</NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>健康打卡</NavBar>

      <div className="px-4 py-4" style={{ background: 'linear-gradient(135deg, #52c41a, #73d13d)' }}>
        <div className="text-white text-center">
          <div className="text-lg font-bold">✅ 健康打卡</div>
          <div className="text-xs opacity-80 mt-1">养成健康好习惯</div>
        </div>
      </div>

      <div className="px-4 -mt-3">
        {items.length === 0 ? (
          <Card style={{ borderRadius: 12, textAlign: 'center', padding: '40px 20px' }}>
            <div className="text-4xl mb-3">✅</div>
            <div className="text-gray-400 text-sm mb-4">暂无打卡项</div>
            <Button
              color="primary"
              size="small"
              style={{ borderRadius: 20, background: 'linear-gradient(135deg, #52c41a, #73d13d)', border: 'none' }}
              onClick={() => router.push('/health-plan/checkin/add')}
            >
              添加打卡项
            </Button>
          </Card>
        ) : (
          items.map((item) => {
            const progress = getProgress(item);
            const hasTarget = item.target_value && item.target_value > 0;
            return (
              <SwipeAction
                key={item.id}
                rightActions={[
                  {
                    key: 'edit',
                    text: '编辑',
                    color: 'primary',
                    onClick: () => router.push(`/health-plan/checkin/add?id=${item.id}`),
                  },
                  {
                    key: 'delete',
                    text: '删除',
                    color: 'danger',
                    onClick: () => handleDelete(item),
                  },
                ]}
              >
                <Card style={{ borderRadius: 12, marginBottom: 12 }}>
                  <div className="flex items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">{item.name}</span>
                        {hasTarget && (
                          <span className="text-xs text-gray-400">
                            目标: {item.target_value}{item.target_unit}
                          </span>
                        )}
                      </div>

                      {hasTarget ? (
                        <>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-gray-500">
                              已完成: {item.actual_value || 0}{item.target_unit}
                            </span>
                            <span className="text-xs" style={{ color: '#52c41a' }}>{progress}%</span>
                          </div>
                          <ProgressBar
                            percent={progress}
                            style={{ '--track-width': '6px', '--fill-color': '#52c41a' }}
                          />
                          {inputVisible === item.id ? (
                            <div className="flex items-center mt-2 gap-2">
                              <input
                                type="number"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                placeholder={`输入${item.target_unit || '数值'}`}
                                className="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200"
                                autoFocus
                              />
                              <Button
                                size="mini"
                                color="primary"
                                style={{ borderRadius: 8, background: '#52c41a', border: 'none' }}
                                onClick={() => handleValueCheck(item)}
                              >
                                确认
                              </Button>
                              <Button
                                size="mini"
                                style={{ borderRadius: 8 }}
                                onClick={() => { setInputVisible(null); setInputValue(''); }}
                              >
                                取消
                              </Button>
                            </div>
                          ) : (
                            <Button
                              size="mini"
                              style={{ marginTop: 8, borderRadius: 8, color: '#52c41a', borderColor: '#52c41a' }}
                              onClick={() => { setInputVisible(item.id); setInputValue(''); }}
                            >
                              记录数值
                            </Button>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center justify-between mt-2">
                          <span className={`text-xs ${item.is_checked ? 'text-green-500' : 'text-gray-400'}`}>
                            {item.is_checked ? '✅ 已完成' : '⬜ 未完成'}
                          </span>
                          {!item.is_checked && (
                            <Button
                              size="mini"
                              color="primary"
                              style={{ borderRadius: 8, background: '#52c41a', border: 'none' }}
                              onClick={() => handleSimpleCheck(item)}
                            >
                              打卡
                            </Button>
                          )}
                        </div>
                      )}

                      {item.remind_time && (
                        <div className="text-xs text-gray-400 mt-2">⏰ 提醒: {item.remind_time}</div>
                      )}
                    </div>
                  </div>
                </Card>
              </SwipeAction>
            );
          })
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #52c41a, #73d13d)', border: 'none', height: 48 }}
          onClick={() => router.push('/health-plan/checkin/add')}
        >
          <AddOutline /> 添加打卡项
        </Button>
      </div>
    </div>
  );
}
