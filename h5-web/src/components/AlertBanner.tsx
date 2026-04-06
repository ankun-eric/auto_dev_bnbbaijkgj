'use client';

import { useState, useEffect } from 'react';
import { NoticeBar, Tag } from 'antd-mobile';
import { CloseOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface AlertItem {
  id: number;
  indicator_name: string;
  message: string;
  level: string;
  created_at: string;
}

export default function AlertBanner() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    try {
      const res: any = await api.get('/api/report/alerts');
      const items = res.data || res.items || res || [];
      if (Array.isArray(items)) {
        setAlerts(items);
      }
    } catch {
      // ignore
    }
  };

  const markRead = async (id: number) => {
    try {
      await api.put(`/api/report/alerts/${id}/read`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch {
      // ignore
    }
  };

  if (alerts.length === 0) return null;

  const levelColor = (level: string) => {
    if (level === 'high' || level === '高') return '#f5222d';
    if (level === 'medium' || level === '中') return '#fa8c16';
    return '#faad14';
  };

  return (
    <div className="mx-4 mt-3">
      <div
        className="rounded-xl overflow-hidden"
        style={{ background: '#fff5f5', border: '1px solid #ffccc7' }}
      >
        <div
          className="flex items-center justify-between px-3 py-2 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <span className="text-base">⚠️</span>
            <span className="text-sm font-medium text-red-600 truncate">
              您有 {alerts.length} 条健康预警未读
            </span>
          </div>
          <span className="text-xs text-gray-400">{expanded ? '收起' : '展开'}</span>
        </div>

        {expanded && (
          <div className="px-3 pb-3 space-y-2">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-start justify-between bg-white rounded-lg p-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Tag
                      style={{
                        '--background-color': `${levelColor(alert.level)}15`,
                        '--text-color': levelColor(alert.level),
                        '--border-color': 'transparent',
                        fontSize: 10,
                      }}
                    >
                      {alert.indicator_name}
                    </Tag>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{alert.message}</p>
                </div>
                <button
                  className="ml-2 mt-1 flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-gray-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    markRead(alert.id);
                  }}
                >
                  <CloseOutline fontSize={10} color="#999" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
