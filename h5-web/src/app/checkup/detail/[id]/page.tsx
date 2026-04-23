'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { NavBar, SpinLoading, Toast, Image, ImageViewer, Input, Dialog } from 'antd-mobile';
import { EditSOutline } from 'antd-mobile-icons';
import api from '@/lib/api';

interface ReportDetail {
  id: number;
  title: string;
  ocr_text: string;
  images: string[];
  member_id: number | null;
  member_name: string | null;
  member_relation: string | null;
  created_at: string;
  interpret_session_id: number | null;
}

export default function CheckupDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params?.id);

  const [data, setData] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [ocrExpanded, setOcrExpanded] = useState(false);
  const [previewIdx, setPreviewIdx] = useState(-1);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState('');
  const [savingTitle, setSavingTitle] = useState(false);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const res = await api.get<ReportDetail>(`/api/checkup/reports/${id}`);
        setData(res);
        setTitleInput(res.title || '');
      } catch (e: any) {
        Toast.show({ content: e?.message || '加载失败' });
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const handleSaveTitle = async () => {
    const t = titleInput.trim();
    if (!t) {
      Toast.show({ content: '标题不能为空' });
      return;
    }
    if (t.length > 50) {
      Toast.show({ content: '标题最多 50 字' });
      return;
    }
    setSavingTitle(true);
    try {
      await api.put(`/api/checkup/reports/${id}`, { title: t });
      setData((prev) => (prev ? { ...prev, title: t } : prev));
      setEditingTitle(false);
      Toast.show({ icon: 'success', content: '已保存' });
    } catch (e: any) {
      Toast.show({ content: e?.message || '保存失败' });
    } finally {
      setSavingTitle(false);
    }
  };

  const handleContinueChat = async () => {
    if (!data) return;
    if (data.interpret_session_id) {
      // [2026-04-23 对话页统一化] 跳转改向公共咨询页
      router.push(`/chat/${data.interpret_session_id}?type=report_interpret`);
      return;
    }
    // 没有会话则引导重新发起
    const ok = await Dialog.confirm({ content: '该报告尚未开启 AI 解读，是否立即开始？' });
    if (!ok) return;
    try {
      // [2026-04-23] 使用新接口 ensure-session（幂等，老数据懒加载）
      const resp: any = await api.post(`/api/checkup/reports/${data.id}/ensure-session`, {
        member_id: data.member_id,
      });
      const sid = resp?.session_id;
      if (sid) {
        // [2026-04-23 对话页统一化] 跳转改向公共咨询页
        router.push(`/chat/${sid}?auto_start=1&type=report_interpret`);
      }
    } catch (e: any) {
      Toast.show({ content: e?.message || '创建失败' });
    }
  };

  const handleCompareFromHere = () => {
    if (!data) return;
    if (!data.member_id) {
      Toast.show({ content: '该报告未绑定咨询人，无法对比' });
      return;
    }
    router.push(`/checkup/compare/select?member_id=${data.member_id}&preselect=${data.id}`);
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <SpinLoading color="primary" />
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <NavBar onBack={() => router.back()}>报告详情</NavBar>
        <div style={{ padding: 24, textAlign: 'center', color: '#999' }}>报告不存在或已删除</div>
      </div>
    );
  }

  const memberLabel = data.member_name ? `${data.member_relation || ''} · ${data.member_name}` : '未设置咨询人';

  return (
    <div style={{ minHeight: '100vh', background: '#f6f7f9', paddingBottom: 100 }}>
      <NavBar onBack={() => router.back()}>报告详情</NavBar>

      <div style={{ padding: 12 }}>
        <div style={{ background: '#fff', borderRadius: 12, padding: 16, marginBottom: 12 }}>
          {/* 标题（可编辑） */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            {editingTitle ? (
              <>
                <Input
                  value={titleInput}
                  onChange={setTitleInput}
                  maxLength={50}
                  style={{ flex: 1, fontSize: 16, fontWeight: 600 }}
                />
                <button
                  onClick={handleSaveTitle}
                  disabled={savingTitle}
                  style={{ padding: '4px 10px', background: '#52c41a', color: '#fff', borderRadius: 6, border: 0, fontSize: 13 }}
                >
                  保存
                </button>
                <button
                  onClick={() => { setEditingTitle(false); setTitleInput(data.title); }}
                  style={{ padding: '4px 10px', background: '#eee', color: '#666', borderRadius: 6, border: 0, fontSize: 13 }}
                >
                  取消
                </button>
              </>
            ) : (
              <>
                <div style={{ flex: 1, fontSize: 17, fontWeight: 600, color: '#222' }}>{data.title}</div>
                <button
                  onClick={() => setEditingTitle(true)}
                  style={{ padding: 6, background: 'transparent', border: 0, color: '#1890ff', display: 'flex', alignItems: 'center' }}
                  aria-label="编辑标题"
                >
                  <EditSOutline fontSize={18} />
                </button>
              </>
            )}
          </div>

          <div style={{ fontSize: 13, color: '#666', lineHeight: 1.8 }}>
            <div>咨询人：{memberLabel}</div>
            <div>上传时间：{new Date(data.created_at).toLocaleString('zh-CN')}</div>
          </div>
        </div>

        {/* 报告图片 */}
        {data.images.length > 0 && (
          <div style={{ background: '#fff', borderRadius: 12, padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 8 }}>📄 报告图片</div>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto' }}>
              {data.images.map((url, idx) => (
                <Image
                  key={idx}
                  src={url}
                  width={120}
                  height={120}
                  fit="cover"
                  style={{ borderRadius: 8, flexShrink: 0 }}
                  onClick={() => setPreviewIdx(idx)}
                />
              ))}
            </div>
          </div>
        )}

        {/* OCR 原文（折叠） */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 12 }}>
          <div
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => setOcrExpanded(!ocrExpanded)}
          >
            <span style={{ fontSize: 14, fontWeight: 500 }}>📝 OCR 原文</span>
            <span style={{ fontSize: 12, color: '#1890ff' }}>{ocrExpanded ? '收起' : '展开'}</span>
          </div>
          {ocrExpanded && (
            <pre
              style={{
                marginTop: 10,
                fontSize: 13,
                lineHeight: 1.7,
                color: '#333',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
                maxHeight: 400,
                overflow: 'auto',
                background: '#fafafa',
                borderRadius: 6,
                padding: 10,
              }}
            >
              {data.ocr_text || '(OCR 文本为空)'}
            </pre>
          )}
        </div>
      </div>

      {/* 底部按钮 */}
      <div
        style={{
          position: 'fixed',
          bottom: 0,
          left: 0,
          right: 0,
          background: '#fff',
          padding: '10px 16px',
          borderTop: '1px solid #eee',
          display: 'flex',
          gap: 10,
          zIndex: 10,
        }}
      >
        <button
          onClick={handleCompareFromHere}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 22,
            background: '#fff',
            color: '#1890ff',
            border: '1px solid #1890ff',
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          🔄 找另一份对比
        </button>
        <button
          onClick={handleContinueChat}
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 22,
            background: 'linear-gradient(135deg, #52c41a, #13c2c2)',
            color: '#fff',
            border: 0,
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          💬 继续咨询
        </button>
      </div>

      <ImageViewer.Multi
        images={data.images}
        visible={previewIdx >= 0}
        defaultIndex={Math.max(0, previewIdx)}
        onClose={() => setPreviewIdx(-1)}
      />
    </div>
  );
}
