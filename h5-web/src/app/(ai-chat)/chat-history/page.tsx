'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { NavBar, Dialog, Toast, Checkbox } from 'antd-mobile';
import { THEME } from '@/lib/theme';
import api from '@/lib/api';

interface ChatHistoryItem {
  id: string;
  title: string;
  time: string;
  pinned?: boolean;
  has_attachments?: boolean;
}

export default function ChatHistoryPage() {
  const router = useRouter();
  const [items, setItems] = useState<ChatHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [managing, setManaging] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [longPressId, setLongPressId] = useState<string | null>(null);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/chat-sessions');
      const data = res.data || res;
      const list = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
      setItems(list.map((s: any) => ({
        id: String(s.id),
        title: s.title || '新对话',
        time: s.updated_at || s.created_at || '',
        pinned: s.is_pinned || false,
        has_attachments: false,
      })));
    } catch {
      setItems([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchList(); }, [fetchList]);

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const s = new Set(prev);
      if (s.has(id)) s.delete(id); else s.add(id);
      return s;
    });
  };

  const handleSelectAll = () => {
    if (selected.size === items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map(i => i.id)));
    }
  };

  const handleDelete = async (ids: string[]) => {
    if (!ids.length) return;
    const hasAttachments = ids.some(id => items.find(i => i.id === id)?.has_attachments);
    const confirmed = await Dialog.confirm({
      content: hasAttachments
        ? '选中的对话包含附件，删除后附件也会一并删除，确定吗？'
        : `确定删除${ids.length}条对话记录吗？`,
    });
    if (!confirmed) return;

    try {
      await api.post('/api/chat-sessions/batch-delete', { session_ids: ids.map(Number) });
      Toast.show({ content: '删除成功', icon: 'success' });
      setSelected(new Set());
      fetchList();
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  const handleClearAll = async () => {
    const confirmed = await Dialog.confirm({ content: '确定清空全部对话记录吗？此操作不可恢复' });
    if (!confirmed) return;
    try {
      await api.delete('/api/chat-sessions/clear-all');
      Toast.show({ content: '已清空', icon: 'success' });
      setItems([]);
    } catch {
      Toast.show({ content: '操作失败', icon: 'fail' });
    }
  };

  const handlePin = async (id: string, pin: boolean) => {
    try {
      await api.put(`/api/chat-sessions/${id}/pin`, { is_pinned: pin });
      fetchList();
    } catch {
      Toast.show({ content: '操作失败', icon: 'fail' });
    }
    setLongPressId(null);
  };

  const groupByTime = (list: ChatHistoryItem[]) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterday = today - 86400000;
    const week = today - 7 * 86400000;
    const groups: { label: string; items: ChatHistoryItem[] }[] = [
      { label: '今天', items: [] },
      { label: '昨天', items: [] },
      { label: '近7天', items: [] },
      { label: '更早', items: [] },
    ];
    list.forEach(item => {
      const t = new Date(item.time).getTime();
      if (t >= today) groups[0].items.push(item);
      else if (t >= yesterday) groups[1].items.push(item);
      else if (t >= week) groups[2].items.push(item);
      else groups[3].items.push(item);
    });
    return groups.filter(g => g.items.length > 0);
  };

  const pinned = items.filter(i => i.pinned);
  const unpinned = items.filter(i => !i.pinned);
  const grouped = groupByTime(unpinned);

  return (
    <div className="min-h-screen" style={{ background: THEME.background }}>
      <NavBar
        onBack={() => router.back()}
        right={
          <div className="flex gap-3">
            {managing ? (
              <button className="text-sm" style={{ color: THEME.primary }} onClick={() => { setManaging(false); setSelected(new Set()); }}>
                完成
              </button>
            ) : (
              <button className="text-sm" style={{ color: THEME.primary }} onClick={() => setManaging(true)}>
                管理
              </button>
            )}
          </div>
        }
        style={{ background: THEME.cardBg, '--border-bottom': `1px solid ${THEME.divider}` } as React.CSSProperties}
      >
        <span style={{ color: THEME.textPrimary, fontWeight: 600 }}>历史对话</span>
      </NavBar>

      <div className="px-4 py-3">
        {loading ? (
          <div className="text-center py-12 text-sm" style={{ color: THEME.textSecondary }}>加载中...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-sm" style={{ color: THEME.textSecondary }}>暂无历史对话</div>
        ) : (
          <>
            {pinned.length > 0 && (
              <div className="mb-4">
                <div className="text-xs mb-2 px-1" style={{ color: THEME.textSecondary }}>📌 置顶</div>
                {pinned.map(item => (
                  <HistoryItem
                    key={item.id}
                    item={item}
                    managing={managing}
                    isSelected={selected.has(item.id)}
                    onToggle={() => toggleSelect(item.id)}
                    onClick={() => !managing && router.push(`/chat/${item.id}`)}
                    onLongPress={() => setLongPressId(item.id)}
                    highlighted
                  />
                ))}
              </div>
            )}

            {grouped.map(group => (
              <div key={group.label} className="mb-4">
                <div className="text-xs mb-2 px-1" style={{ color: THEME.textSecondary }}>{group.label}</div>
                {group.items.map(item => (
                  <HistoryItem
                    key={item.id}
                    item={item}
                    managing={managing}
                    isSelected={selected.has(item.id)}
                    onToggle={() => toggleSelect(item.id)}
                    onClick={() => !managing && router.push(`/chat/${item.id}`)}
                    onLongPress={() => setLongPressId(item.id)}
                  />
                ))}
              </div>
            ))}
          </>
        )}
      </div>

      {/* Manage footer */}
      {managing && (
        <div
          className="fixed bottom-0 left-0 right-0 flex items-center justify-between px-4 py-3"
          style={{ background: THEME.cardBg, borderTop: `1px solid ${THEME.divider}`, maxWidth: 750, margin: '0 auto', paddingBottom: 'calc(12px + env(safe-area-inset-bottom))' }}
        >
          <button className="text-sm" style={{ color: THEME.primary }} onClick={handleSelectAll}>
            {selected.size === items.length ? '取消全选' : '全选'}
          </button>
          <div className="flex gap-3">
            <button className="text-sm" style={{ color: '#FF4D4F' }} onClick={handleClearAll}>清空全部</button>
            <button
              className="px-4 py-1.5 rounded-full text-sm text-white"
              style={{ background: selected.size > 0 ? '#FF4D4F' : '#ccc' }}
              onClick={() => handleDelete(Array.from(selected))}
              disabled={selected.size === 0}
            >
              删除({selected.size})
            </button>
          </div>
        </div>
      )}

      {/* Long press menu */}
      {longPressId && (
        <div className="fixed inset-0 z-50" onClick={() => setLongPressId(null)}>
          <div className="absolute inset-0 bg-black/20" />
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-2xl overflow-hidden shadow-xl"
            style={{ background: THEME.cardBg, minWidth: 180 }}
            onClick={e => e.stopPropagation()}
          >
            {items.find(i => i.id === longPressId)?.pinned ? (
              <button
                className="w-full px-4 py-3 text-sm text-left"
                style={{ color: THEME.textPrimary, borderBottom: `1px solid ${THEME.divider}` }}
                onClick={() => handlePin(longPressId, false)}
              >
                取消置顶
              </button>
            ) : (
              <button
                className="w-full px-4 py-3 text-sm text-left"
                style={{ color: THEME.textPrimary, borderBottom: `1px solid ${THEME.divider}` }}
                onClick={() => handlePin(longPressId, true)}
              >
                📌 置顶
              </button>
            )}
            <button
              className="w-full px-4 py-3 text-sm text-left"
              style={{ color: '#FF4D4F' }}
              onClick={() => handleDelete([longPressId])}
            >
              🗑 删除
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryItem({
  item,
  managing,
  isSelected,
  onToggle,
  onClick,
  onLongPress,
  highlighted,
}: {
  item: ChatHistoryItem;
  managing: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onClick: () => void;
  onLongPress: () => void;
  highlighted?: boolean;
}) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  const startPress = () => {
    timerRef.current = setTimeout(() => onLongPress(), 600);
  };
  const endPress = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };

  return (
    <div
      ref={ref}
      className="flex items-center gap-3 px-3 py-3 rounded-xl mb-1 cursor-pointer"
      style={{ background: highlighted ? THEME.primaryLight : THEME.cardBg }}
      onClick={managing ? onToggle : onClick}
      onTouchStart={startPress}
      onTouchEnd={endPress}
      onMouseDown={startPress}
      onMouseUp={endPress}
      onMouseLeave={endPress}
    >
      {managing && (
        <Checkbox
          checked={isSelected}
          onChange={onToggle}
          style={{ '--icon-size': '18px', '--adm-color-primary': THEME.primary } as React.CSSProperties}
        />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm truncate" style={{ color: THEME.textPrimary }}>{item.title}</div>
        <div className="text-xs mt-0.5" style={{ color: THEME.textSecondary }}>
          {new Date(item.time).toLocaleDateString('zh-CN')}
        </div>
      </div>
    </div>
  );
}

