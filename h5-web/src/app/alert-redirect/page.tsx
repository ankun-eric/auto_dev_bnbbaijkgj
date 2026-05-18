'use client';

/**
 * [PRD-FAMILY-GUARDIAN-V1] 公众号推送·中转页（Q14/Q15-补/Q17）
 *
 * 路径：/alert-redirect
 *
 * URL 参数：
 *   logId      - family_alert_log.id（点击回执必传）
 *   memberId   - family_member.id（被守护者档案）
 *   reportId   - checkup_report.id（体检报告）
 *   t          - 时间戳（防缓存 + 参与签名）
 *   sig        - HMAC 签名（防越权）
 *
 * 时序：
 *   T=0~2300ms   尝试唤起 App + 显示「正在为您打开 App...」加载态
 *   T=2300ms+    若 App 仍未唤起 → 进入降级链路（微信内 / 浏览器）
 *
 * 兼容性：
 *   - iOS 14+ Safari 静默拦截 scheme：通过 location.href 触发 + 2s 超时静默降级，不弹"打开 App"提示
 *   - 微信 6.7.2 以下不支持 wx-open-launch-weapp：检测后隐藏小程序按钮，仅展示下载 App + 网页查看
 */

import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';

export const dynamic = 'force-dynamic';

type Stage = 'launching' | 'fallback' | 'invalid';

const APP_DOWNLOAD_URL = 'https://bini-health.com/app-download';
const WEAPP_USERNAME = 'gh_xxxxxxxxxxxx';
const FALLBACK_TIMEOUT_MS = 2000;

interface AlertEventBody {
  event: string;
  logId?: number;
  memberId?: number;
  reportId?: number;
  extra?: Record<string, unknown>;
}

function fireEvent(body: AlertEventBody) {
  try {
    api.post('/api/alert/event', body).catch(() => undefined);
  } catch {
    /* 埋点失败不影响主流程 */
  }
}

function safeInt(v: string | null): number | undefined {
  if (!v) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function isWeChatBrowser(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /MicroMessenger/i.test(navigator.userAgent);
}

function getWeChatVersion(): [number, number, number] | null {
  if (typeof navigator === 'undefined') return null;
  const m = navigator.userAgent.match(/MicroMessenger\/([0-9.]+)/i);
  if (!m) return null;
  const parts = m[1].split('.').map((s) => parseInt(s, 10));
  return [parts[0] || 0, parts[1] || 0, parts[2] || 0];
}

function isWxOpenLaunchSupported(): boolean {
  const v = getWeChatVersion();
  if (!v) return false;
  // wx-open-launch-weapp 自 微信 6.7.2 起支持
  if (v[0] > 6) return true;
  if (v[0] === 6 && v[1] > 7) return true;
  if (v[0] === 6 && v[1] === 7 && v[2] >= 2) return true;
  return false;
}

function FamilyAlertText({ count }: { count?: number }) {
  if (count && count > 0) {
    return (
      <div style={{ fontSize: 15, lineHeight: 1.6, color: '#444', textAlign: 'center', margin: '8px 0 24px' }}>
        您家人的体检报告有 <span style={{ color: '#e64545', fontWeight: 600 }}>{count}</span> 项异常项目，请尽快查看
      </div>
    );
  }
  return (
    <div style={{ fontSize: 15, lineHeight: 1.6, color: '#444', textAlign: 'center', margin: '8px 0 24px' }}>
      您家人的体检报告出现异常项目，请尽快查看并联系家人关注健康
    </div>
  );
}

function Header() {
  return (
    <div style={{ textAlign: 'center', padding: '32px 0 16px' }}>
      <div
        style={{
          width: 64,
          height: 64,
          margin: '0 auto 12px',
          borderRadius: 16,
          background: 'linear-gradient(135deg, #ff6b6b 0%, #ffa94d 100%)',
          color: '#fff',
          fontSize: 32,
          lineHeight: '64px',
          fontWeight: 700,
          boxShadow: '0 6px 20px rgba(255,107,107,0.30)',
        }}
      >
        ⚠️
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, color: '#222' }}>bini-health</div>
    </div>
  );
}

function FamilyAlertContent() {
  const params = useSearchParams();

  const logId = safeInt(params.get('logId'));
  const memberId = safeInt(params.get('memberId'));
  const reportId = safeInt(params.get('reportId'));
  const t = safeInt(params.get('t'));
  const sig = params.get('sig') || undefined;

  const [stage, setStage] = useState<Stage>('launching');
  const [invalidReason, setInvalidReason] = useState<string>('');
  const wxSupported = useMemo(() => (typeof window === 'undefined' ? true : isWxOpenLaunchSupported()), []);
  const wxBrowser = useMemo(() => (typeof window === 'undefined' ? false : isWeChatBrowser()), []);
  const fired = useRef(false);

  useEffect(() => {
    // 必填参数校验
    if (!logId) {
      setStage('invalid');
      setInvalidReason('链接参数不完整');
      return;
    }

    if (fired.current) return;
    fired.current = true;

    // 1) 上报点击回执（异步，不阻塞）
    api
      .post('/api/alert/click-tracking', {
        logId,
        memberId,
        reportId,
        t,
        sig,
      })
      .catch((err) => {
        // 403 → 链接失效；其他错误（如 404）也提示链接失效，但不阻塞唤起 App
        const status = err?.response?.status;
        if (status === 403) {
          setStage('invalid');
          setInvalidReason('链接已失效');
        } else if (status === 404) {
          setStage('invalid');
          setInvalidReason('该消息已失效');
        }
      });

    fireEvent({ event: 'alert_redirect_view', logId, memberId, reportId });

    // 2) 尝试唤起 App
    const scheme = `binihealth://family/alert?memberId=${memberId || ''}&reportId=${reportId || ''}&logId=${logId}`;
    try {
      // 直接 location.href 触发 scheme，避免触发系统"是否打开"提示框
      window.location.href = scheme;
    } catch {
      /* 静默失败 */
    }

    // 3) 启动超时计时；监听 visibilitychange 用于检测 App 唤起成功
    let timer: ReturnType<typeof setTimeout> | null = null;
    let done = false;

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden' && !done) {
        done = true;
        if (timer) clearTimeout(timer);
        fireEvent({ event: 'alert_redirect_app_launched', logId, memberId, reportId });
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    timer = setTimeout(() => {
      if (done) return;
      done = true;
      // 进入降级链路
      setStage((prev) => (prev === 'launching' ? 'fallback' : prev));
      if (wxBrowser) {
        fireEvent({
          event: 'alert_redirect_fallback_wechat',
          logId,
          memberId,
          reportId,
          extra: { wxOpenLaunchSupported: wxSupported },
        });
      } else {
        fireEvent({ event: 'alert_redirect_fallback_browser', logId, memberId, reportId });
      }
    }, FALLBACK_TIMEOUT_MS);

    return () => {
      if (timer) clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logId, memberId, reportId, t, sig]);

  if (stage === 'invalid') {
    return (
      <div style={pageStyle}>
        <Header />
        <div style={cardStyle}>
          <div style={{ textAlign: 'center', padding: '24px 12px' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🔒</div>
            <div style={{ fontSize: 18, color: '#333', fontWeight: 600, marginBottom: 8 }}>
              {invalidReason || '链接已失效'}
            </div>
            <div style={{ fontSize: 14, color: '#999', lineHeight: 1.6 }}>
              请前往「贝尼健康」公众号底部菜单进入小程序查看最新提醒。
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (stage === 'launching') {
    return (
      <div style={pageStyle}>
        <Header />
        <div style={{ textAlign: 'center', padding: '8px 16px' }}>
          <div style={{ fontSize: 16, color: '#333', marginBottom: 14 }}>正在为您打开 App...</div>
          <Spinner />
          <FamilyAlertText />
        </div>
      </div>
    );
  }

  // fallback
  return (
    <div style={pageStyle}>
      <Header />
      <div style={cardStyle}>
        <FamilyAlertText />

        {wxBrowser && wxSupported && (
          <div
            style={{ width: '100%', marginBottom: 12 }}
            data-testid="weapp-btn"
            onClickCapture={() =>
              fireEvent({ event: 'alert_redirect_click_weapp', logId, memberId, reportId })
            }
            dangerouslySetInnerHTML={{
              __html: `
                <wx-open-launch-weapp
                  username="${WEAPP_USERNAME}"
                  path="pages/family-alert-detail/index?reportId=${reportId || ''}&memberId=${memberId || ''}"
                  style="display:block;width:100%;">
                  <script type="text/wxtag-template">
                    <button style="width:100%;height:50px;background:#1296db;color:#fff;border:none;border-radius:10px;font-size:16px;">📱 在小程序中查看详情</button>
                  </script>
                </wx-open-launch-weapp>
              `,
            }}
          />
        )}

        <a
          href={APP_DOWNLOAD_URL}
          onClick={() => fireEvent({ event: 'alert_redirect_click_download', logId, memberId, reportId })}
          style={primaryBtnStyle}
          data-testid="download-btn"
        >
          ⬇️ 下载 App 接收实时提醒
        </a>

        <a
          href={`/family/alert/${reportId || ''}?memberId=${memberId || ''}&logId=${logId || ''}`}
          onClick={() => fireEvent({ event: 'alert_redirect_click_h5', logId, memberId, reportId })}
          style={secondaryBtnStyle}
          data-testid="h5-btn"
        >
          🌐 在网页查看（功能受限）
        </a>

        {wxBrowser && !wxSupported && (
          <div style={tipStyle}>
            💡 当前微信版本较低，无法直接跳转小程序。请升级微信或在「贝尼健康」公众号底部菜单进入小程序查看。
          </div>
        )}
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <>
      <div
        style={{
          width: 32,
          height: 32,
          margin: '0 auto 16px',
          border: '3px solid #ffe3e3',
          borderTopColor: '#ff6b6b',
          borderRadius: '50%',
          animation: 'alert-spin 0.9s linear infinite',
        }}
      />
      <style>{`@keyframes alert-spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

const pageStyle: React.CSSProperties = {
  minHeight: '100vh',
  background: '#f5f7fa',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  padding: '0 16px 32px',
};

const cardStyle: React.CSSProperties = {
  background: '#fff',
  width: '100%',
  maxWidth: 480,
  padding: '20px 16px 24px',
  borderRadius: 12,
  boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
};

const primaryBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  height: 50,
  background: '#52c41a',
  color: '#fff',
  borderRadius: 10,
  fontSize: 16,
  marginBottom: 12,
  textDecoration: 'none',
};

const secondaryBtnStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  height: 48,
  background: '#fafafa',
  color: '#333',
  border: '1px solid #e8e8e8',
  borderRadius: 10,
  fontSize: 15,
  textDecoration: 'none',
};

const tipStyle: React.CSSProperties = {
  marginTop: 16,
  padding: 12,
  background: '#f9f9f9',
  borderRadius: 8,
  fontSize: 13,
  color: '#666',
  lineHeight: 1.6,
};

export default function AlertRedirectPage() {
  return (
    <Suspense
      fallback={
        <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>加载中…</div>
      }
    >
      <FamilyAlertContent />
    </Suspense>
  );
}
