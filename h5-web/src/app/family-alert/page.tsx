'use client';

/**
 * [PRD-FAMILY-GUARDIAN-V1] 公众号推送中转页
 *
 * 公众号模板消息点击后落在此页：
 *   1) 检测是否安装 App（通过 URL Scheme / Universal Link 唤起）
 *   2) 500ms 内未唤起成功 → 提供小程序入口（show wx-open-launch-weapp）
 *   3) 同时提供"复制链接到微信打开小程序"等兜底
 */

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

export const dynamic = 'force-dynamic';

function FamilyAlertBridge() {
  const params = useSearchParams();
  const reportId = params.get('report_id');
  const memberId = params.get('member_id');

  const [openAppTried, setOpenAppTried] = useState(false);
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    // 1) 尝试唤起 App
    const tryOpenApp = () => {
      const scheme = `binihealth://family-alert?report_id=${reportId || ''}&member_id=${memberId || ''}`;
      const start = Date.now();
      try {
        // 在 iframe 中尝试唤起，避免页面跳错
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = scheme;
        document.body.appendChild(iframe);
        setTimeout(() => {
          try { document.body.removeChild(iframe); } catch {}
        }, 1500);
      } catch {}

      // 500ms 后如果还在本页，认为唤起失败 → 显示兜底
      setTimeout(() => {
        if (Date.now() - start >= 400 && !document.hidden) {
          setShowFallback(true);
        }
      }, 1000);
    };

    setOpenAppTried(true);
    tryOpenApp();
  }, [reportId, memberId]);

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f5f7fa',
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #ff6b6b 0%, #ffa94d 100%)',
        color: '#fff',
        padding: '24px 20px',
        borderRadius: '16px',
        width: '100%',
        maxWidth: '480px',
        marginBottom: '24px',
        boxShadow: '0 8px 24px rgba(255,107,107,0.25)',
      }}>
        <div style={{ fontSize: '28px', marginBottom: '12px' }}>⚠️ 体检异常提醒</div>
        <div style={{ fontSize: '15px', lineHeight: 1.6, opacity: 0.95 }}>
          您家人的体检报告出现异常项目，请尽快查看并联系家人关注健康。
        </div>
      </div>

      <div style={{
        background: '#fff',
        padding: '20px',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '480px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
      }}>
        <div style={{ fontWeight: 600, color: '#333', marginBottom: '12px' }}>请选择查看方式</div>

        <button
          onClick={() => {
            const scheme = `binihealth://family-alert?report_id=${reportId || ''}&member_id=${memberId || ''}`;
            window.location.href = scheme;
            setTimeout(() => setShowFallback(true), 1500);
          }}
          style={{
            display: 'block',
            width: '100%',
            background: '#52c41a',
            color: '#fff',
            padding: '14px 0',
            border: 'none',
            borderRadius: '10px',
            fontSize: '16px',
            marginBottom: '12px',
            cursor: 'pointer',
          }}
        >
          📱 打开 App 查看
        </button>

        {(showFallback || openAppTried) && (
          <>
            <div style={{
              color: '#999',
              fontSize: '13px',
              textAlign: 'center',
              margin: '12px 0',
            }}>
              ── 未安装 App？使用小程序查看 ──
            </div>

            {/* 小程序链接（在微信中点击会自动跳转）- 使用 dangerouslySetInnerHTML 渲染 wx-open-launch-weapp 标签 */}
            <div
              style={{ width: '100%' }}
              dangerouslySetInnerHTML={{
                __html: `
                  <wx-open-launch-weapp
                    username="gh_xxx_binihealth"
                    path="/pages/checkup-detail/index?report_id=${reportId || ''}&member_id=${memberId || ''}"
                    style="display:block;width:100%;height:50px;">
                    <script type="text/wxtag-template">
                      <button style="width:100%;height:50px;background:#1296db;color:#fff;border:none;border-radius:10px;font-size:16px;">🟢 打开微信小程序查看</button>
                    </script>
                  </wx-open-launch-weapp>
                `,
              }}
            />

            <div style={{ marginTop: '16px', padding: '12px', background: '#f9f9f9', borderRadius: '8px', fontSize: '13px', color: '#666', lineHeight: 1.6 }}>
              💡 <strong>提示</strong>：如打不开，请确认本页是在微信浏览器中打开，或在「贝尼健康」公众号底部菜单进入小程序查看。
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function FamilyAlertBridgePage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中…</div>}>
      <FamilyAlertBridge />
    </Suspense>
  );
}
