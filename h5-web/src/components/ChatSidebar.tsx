'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  ActionSheet,
  Dialog,
  Toast,
  SpinLoading,
  Button,
} from 'antd-mobile';
import { AddOutline, CloseOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface SessionItem {
  id: number;
  title: string;
  session_type: string;
  message_count: number;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

interface TimeGroup {
  label: string;
  items: SessionItem[];
}

interface ChatSidebarProps {
  visible: boolean;
  onClose: () => void;
  currentSessionId?: string;
  onSessionCreated?: (sessionId: number) => void;
}

const typeLabel: Record<string, { text: string; color: string }> = {
  health_qa: { text: '问答', color: '#52c41a' },
  health: { text: '问答', color: '#52c41a' },
  symptom_check: { text: '健康自查', color: '#1890ff' },
  symptom: { text: '健康自查', color: '#1890ff' },
  tcm: { text: '养生', color: '#eb2f96' },
  drug_query: { text: '参考', color: '#fa8c16' },
  drug: { text: '参考', color: '#fa8c16' },
};

function groupByTime(items: SessionItem[]): TimeGroup[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayStart = new Date(todayStart.getTime() - 86400000);
  const weekStart = new Date(todayStart.getTime() - 7 * 86400000);
  const monthStart = new Date(todayStart.getTime() - 30 * 86400000);

  const groups: Record<string, SessionItem[]> = {
    pinned: [],
    today: [],
    yesterday: [],
    week: [],
    month: [],
    older: [],
  };

  items.forEach((item) => {
    if (item.is_pinned) {
      groups.pinned.push(item);
      return;
    }
    const d = new Date(item.updated_at);
    if (d >= todayStart) groups.today.push(item);
    else if (d >= yesterdayStart) groups.yesterday.push(item);
    else if (d >= weekStart) groups.week.push(item);
    else if (d >= monthStart) groups.month.push(item);
    else groups.older.push(item);
  });

  const result: TimeGroup[] = [];
  if (groups.pinned.length) result.push({ label: '已置顶', items: groups.pinned });
  if (groups.today.length) result.push({ label: '今天', items: groups.today });
  if (groups.yesterday.length) result.push({ label: '昨天', items: groups.yesterday });
  if (groups.week.length) result.push({ label: '近7天', items: groups.week });
  if (groups.month.length) result.push({ label: '近30天', items: groups.month });
  if (groups.older.length) result.push({ label: '更早', items: groups.older });
  return result;
}

export default function ChatSidebar({
  visible,
  onClose,
  currentSessionId,
  onSessionCreated,
}: ChatSidebarProps) {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [actionTarget, setActionTarget] = useState<SessionItem | null>(null);
  const [actionVisible, setActionVisible] = useState(false);
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/chat-sessions', {
        params: { page: 1, page_size: 100 },
      });
      const data = res.data || res;
      setSessions(data.items || data || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (visible) fetchSessions();
  }, [visible, fetchSessions]);

  const handleNewChat = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const res: any = await api.post('/api/chat/sessions', {
        session_type: 'health_qa',
        title: '新对话',
      });
      const data = res.data || res;
      if (onSessionCreated) {
        onSessionCreated(data.id);
      } else {
        router.push(`/chat/${data.id}`);
      }
      onClose();
    } catch {
      Toast.show({ content: '创建失败', icon: 'fail' });
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (item: SessionItem) => {
    const confirmed = await Dialog.confirm({
      content: `确定删除「${item.title}」？`,
      confirmText: '删除',
      cancelText: '取消',
    });
    if (!confirmed) return;
    try {
      await api.delete(`/api/chat-sessions/${item.id}`);
      Toast.show({ content: '已删除', icon: 'success' });
      fetchSessions();
    } catch {
      Toast.show({ content: '删除失败', icon: 'fail' });
    }
  };

  const handleRename = async (item: SessionItem) => {
    let newTitle = item.title;
    const confirmed = await Dialog.confirm({
      title: '重命名对话',
      content: (
        <input
          defaultValue={item.title}
          onChange={(e) => { newTitle = e.target.value; }}
          style={{
            width: '100%',
            padding: '8px 12px',
            border: '1px solid #ddd',
            borderRadius: 8,
            fontSize: 14,
            outline: 'none',
            marginTop: 8,
          }}
          autoFocus
        />
      ),
      confirmText: '确定',
      cancelText: '取消',
    });
    if (!confirmed || !newTitle.trim()) return;
    try {
      await api.put(`/api/chat-sessions/${item.id}`, { title: newTitle.trim() });
      Toast.show({ content: '已重命名', icon: 'success' });
      fetchSessions();
    } catch {
      Toast.show({ content: '重命名失败', icon: 'fail' });
    }
  };

  const handlePin = async (item: SessionItem) => {
    try {
      await api.put(`/api/chat-sessions/${item.id}/pin`, {
        is_pinned: !item.is_pinned,
      });
      Toast.show({
        content: item.is_pinned ? '已取消置顶' : '已置顶',
        icon: 'success',
      });
      fetchSessions();
    } catch {
      Toast.show({ content: '操作失败', icon: 'fail' });
    }
  };

  const handleShare = async (item: SessionItem) => {
    try {
      const res: any = await api.post(`/api/chat-sessions/${item.id}/share`);
      const data = res.data || res;
      const shareUrl = data.share_url || `${window.location.origin}/shared/chat/${data.share_token}`;
      if (navigator.clipboard) {
        await navigator.clipboard.writeText(shareUrl);
        Toast.show({ content: '分享链接已复制', icon: 'success' });
      } else {
        Dialog.alert({ content: `分享链接：${shareUrl}`, confirmText: '确定' });
      }
    } catch {
      Toast.show({ content: '生成分享链接失败', icon: 'fail' });
    }
  };

  const handleTouchStart = (item: SessionItem) => {
    longPressTimer.current = setTimeout(() => {
      setActionTarget(item);
      setActionVisible(true);
    }, 500);
  };

  const handleTouchEnd = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const handleItemClick = (item: SessionItem) => {
    router.push(`/chat/${item.id}`);
    onClose();
  };

  const actionActions = actionTarget
    ? [
        { text: '重命名', key: 'rename', onClick: () => handleRename(actionTarget) },
        {
          text: actionTarget.is_pinned ? '取消置顶' : '置顶',
          key: 'pin',
          onClick: () => handlePin(actionTarget),
        },
        { text: '分享', key: 'share', onClick: () => handleShare(actionTarget) },
        {
          text: '删除',
          key: 'delete',
          danger: true,
          onClick: () => handleDelete(actionTarget),
        },
      ]
    : [];

  const grouped = groupByTime(sessions);

  return (
    <>
      {/* Backdrop */}
      <div
        className={`fixed inset-0 bg-black/40 z-[1000] transition-opacity duration-300 ${
          visible ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
        onClick={onClose}
      />

      {/* Sidebar panel */}
      <div
        className={`fixed top-0 left-0 h-full z-[1001] bg-white flex flex-col transition-transform duration-300 ease-in-out ${
          visible ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ width: 280, maxWidth: '80vw' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
          }}
        >
          <span className="text-white font-bold text-base">对话记录</span>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full"
            style={{ background: 'rgba(255,255,255,0.2)' }}
          >
            <CloseOutline color="#fff" fontSize={16} />
          </button>
        </div>

        {/* New chat button */}
        <div className="px-3 py-3 flex-shrink-0 border-b border-gray-100">
          <Button
            block
            onClick={handleNewChat}
            loading={creating}
            style={{
              background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
              color: '#fff',
              border: 'none',
              borderRadius: 10,
              height: 40,
              fontWeight: 500,
              fontSize: 14,
            }}
          >
            <AddOutline style={{ marginRight: 6, fontSize: 14 }} />
            新建对话
          </Button>
        </div>

        {/* Session list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <SpinLoading style={{ '--size': '24px', '--color': '#52c41a' }} />
            </div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-10 text-gray-400 text-sm">暂无对话记录</div>
          ) : (
            grouped.map((group) => (
              <div key={group.label}>
                <div className="px-4 py-2 text-xs text-gray-400 font-medium sticky top-0 bg-white/95 backdrop-blur-sm">
                  {group.label}
                </div>
                {group.items.map((item) => {
                  const label = typeLabel[item.session_type] || {
                    text: '对话',
                    color: '#999',
                  };
                  const isActive = currentSessionId === String(item.id);
                  return (
                    <div
                      key={item.id}
                      className="px-3 py-2 mx-2 mb-1 rounded-lg cursor-pointer transition-colors"
                      style={{
                        background: isActive ? '#f0faf0' : 'transparent',
                      }}
                      onClick={() => handleItemClick(item)}
                      onTouchStart={() => handleTouchStart(item)}
                      onTouchEnd={handleTouchEnd}
                      onTouchMove={handleTouchEnd}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setActionTarget(item);
                        setActionVisible(true);
                      }}
                    >
                      <div className="flex items-center gap-2">
                        {item.is_pinned && (
                          <span className="text-xs" style={{ color: '#fa8c16' }}>📌</span>
                        )}
                        <span
                          className="text-sm truncate flex-1"
                          style={{
                            color: isActive ? '#52c41a' : '#333',
                            fontWeight: isActive ? 600 : 400,
                          }}
                        >
                          {item.title}
                        </span>
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded flex-shrink-0"
                          style={{
                            background: `${label.color}15`,
                            color: label.color,
                          }}
                        >
                          {label.text}
                        </span>
                      </div>
                      <div className="text-[11px] text-gray-300 mt-1 pl-0">
                        {item.message_count || 0}条消息 ·{' '}
                        {new Date(item.updated_at).toLocaleDateString('zh-CN', {
                          month: 'numeric',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Action Sheet */}
      <ActionSheet
        visible={actionVisible}
        actions={actionActions}
        onClose={() => setActionVisible(false)}
        cancelText="取消"
        getContainer={() => document.body}
        popupClassName="action-sheet-above-sidebar"
      />
    </>
  );
}
