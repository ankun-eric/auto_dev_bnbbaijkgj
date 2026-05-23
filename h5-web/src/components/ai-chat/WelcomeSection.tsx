'use client';
import React, { useState, useEffect } from 'react';

const HEALTH_TIPS = [
  '每天饮水 2000ml，有助于维持身体正常代谢',
  '成年人每天建议步行 6000-10000 步',
  '保持规律作息，每晚 7-8 小时睡眠最为理想',
  '久坐1小时后起身活动5分钟，保护腰椎健康',
  '每天摄入 300-500g 蔬菜，保证膳食纤维充足',
  '餐后30分钟散步有助于消化和控制血糖',
  '定期测量血压，了解自己的健康基线',
  '保持心情愉快，情绪健康也是身体健康的重要组成部分',
];

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 6) return '夜深了';
  if (h < 12) return '早上好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

interface WelcomeSectionProps {
  userName?: string;
}

export default function WelcomeSection({ userName }: WelcomeSectionProps) {
  const [tipVisible, setTipVisible] = useState(true);
  const [tip] = useState(() => HEALTH_TIPS[Math.floor(Math.random() * HEALTH_TIPS.length)]);

  useEffect(() => {
    const today = new Date().toDateString();
    const key = 'bh_tip_dismissed';
    if (localStorage.getItem(key) === today) {
      setTipVisible(false);
    }
  }, []);

  const dismissTip = () => {
    setTipVisible(false);
    localStorage.setItem('bh_tip_dismissed', new Date().toDateString());
  };

  return (
    <div style={{ padding: '16px 16px 8px' }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: '#0C4A6E', marginBottom: 12 }}>
        {getGreeting()}{userName ? `，${userName}` : ''}
      </div>
      {tipVisible && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          background: '#F0F9FF', borderRadius: 12, padding: '12px 16px',
        }}>
          <span style={{ fontSize: 20, flexShrink: 0 }}>💡</span>
          <span style={{ flex: 1, fontSize: 13, color: '#374151', lineHeight: 1.5 }}>{tip}</span>
          <button
            onClick={dismissTip}
            style={{
              background: 'none', border: 'none', padding: 4, cursor: 'pointer',
              fontSize: 16, color: '#9CA3AF', flexShrink: 0,
            }}
          >✕</button>
        </div>
      )}
    </div>
  );
}
