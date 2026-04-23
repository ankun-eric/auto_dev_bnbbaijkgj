'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Input, Modal, Button, Space, Select, ColorPicker, message, Tooltip } from 'antd';
import {
  BoldOutlined, ItalicOutlined, UnderlineOutlined, StrikethroughOutlined,
  OrderedListOutlined, UnorderedListOutlined,
  AlignLeftOutlined, AlignCenterOutlined, AlignRightOutlined,
  LinkOutlined, PictureOutlined, VideoCameraOutlined, TableOutlined,
  UndoOutlined, RedoOutlined, ClearOutlined, FullscreenOutlined, FullscreenExitOutlined,
  FontColorsOutlined, BgColorsOutlined, FontSizeOutlined,
} from '@ant-design/icons';
import { upload } from '@/lib/api';

interface Props {
  value?: string;
  onChange?: (html: string) => void;
  placeholder?: string;
  height?: number | string;
}

const FONT_SIZES = ['12', '14', '16', '18', '20', '24', '28', '32'];

function exec(cmd: string, val?: string) {
  try {
    document.execCommand(cmd, false, val);
  } catch {}
}

export default function SimpleRichEditor({ value = '', onChange, placeholder, height = 280 }: Props) {
  const editorRef = useRef<HTMLDivElement | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [videoModalOpen, setVideoModalOpen] = useState(false);
  const [videoUrl, setVideoUrl] = useState('');
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkText, setLinkText] = useState('');
  const [linkUrl, setLinkUrl] = useState('');

  useEffect(() => {
    if (editorRef.current && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value || '';
    }
  }, [value]);

  const emit = useCallback(() => {
    if (editorRef.current && onChange) {
      onChange(editorRef.current.innerHTML);
    }
  }, [onChange]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoFileInputRef = useRef<HTMLInputElement | null>(null);

  const onImageClick = () => fileInputRef.current?.click();

  const onImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      message.error('图片大小不能超过 5M');
      return;
    }
    try {
      const res = await upload('/api/upload/image', file);
      const url = (res as any)?.url || (res as any)?.data?.url;
      if (url) {
        editorRef.current?.focus();
        exec('insertHTML', `<img src="${url}" alt="image" style="max-width:100%;" />`);
        emit();
      } else {
        message.error('图片上传失败');
      }
    } catch {
      message.error('图片上传失败');
    }
  };

  const onVideoFileClick = () => videoFileInputRef.current?.click();

  const onVideoFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > 100 * 1024 * 1024) {
      message.error('视频大小不能超过 100M');
      return;
    }
    try {
      const res = await upload('/api/upload/image', file); // 复用通用上传（后端支持文件流）
      const url = (res as any)?.url || (res as any)?.data?.url;
      if (url) {
        editorRef.current?.focus();
        exec(
          'insertHTML',
          `<video src="${url}" controls style="max-width:100%;"></video>`
        );
        emit();
      } else {
        message.error('视频上传失败');
      }
    } catch {
      message.error('视频上传失败');
    }
  };

  const insertVideoLink = () => {
    const url = (videoUrl || '').trim();
    if (!url) return;
    editorRef.current?.focus();
    // 识别 B 站/腾讯/优酷/YouTube 嵌入
    let iframeSrc = url;
    if (/bilibili\.com\/video\/(\w+)/i.test(url)) {
      const m = url.match(/bilibili\.com\/video\/(\w+)/i);
      if (m) iframeSrc = `https://player.bilibili.com/player.html?bvid=${m[1]}`;
    } else if (/youtube\.com\/watch\?v=([\w-]+)/i.test(url)) {
      const m = url.match(/youtube\.com\/watch\?v=([\w-]+)/i);
      if (m) iframeSrc = `https://www.youtube.com/embed/${m[1]}`;
    }
    const html = `<iframe src="${iframeSrc}" width="560" height="315" frameborder="0" allowfullscreen style="max-width:100%;"></iframe>`;
    exec('insertHTML', html);
    setVideoModalOpen(false);
    setVideoUrl('');
    emit();
  };

  const insertLink = () => {
    const url = (linkUrl || '').trim();
    if (!url) return;
    editorRef.current?.focus();
    const text = linkText || url;
    exec('insertHTML', `<a href="${url}" target="_blank">${text}</a>`);
    setLinkModalOpen(false);
    setLinkText('');
    setLinkUrl('');
    emit();
  };

  const insertTable = () => {
    const rows = 3;
    const cols = 3;
    let html = '<table style="border-collapse:collapse;width:100%;" border="1">';
    for (let i = 0; i < rows; i++) {
      html += '<tr>';
      for (let j = 0; j < cols; j++) {
        html += `<td style="border:1px solid #ccc;padding:6px;min-width:60px;">&nbsp;</td>`;
      }
      html += '</tr>';
    }
    html += '</table><p><br/></p>';
    editorRef.current?.focus();
    exec('insertHTML', html);
    emit();
  };

  const setFontSize = (sz: string) => {
    // execCommand fontSize 只支持 1-7，需要手动插入 span
    editorRef.current?.focus();
    exec('insertHTML', '<span id="__fs_anchor"></span>');
    exec('fontSize', '7');
    const anchor = document.getElementById('__fs_anchor');
    if (anchor && anchor.parentElement) {
      // 找到最近的 font 节点并替换为 span 自定义 size
      const fonts = editorRef.current?.querySelectorAll('font');
      fonts?.forEach(f => {
        const span = document.createElement('span');
        span.style.fontSize = `${sz}px`;
        span.innerHTML = f.innerHTML;
        f.replaceWith(span);
      });
      anchor.remove();
    }
    emit();
  };

  const setColor = (val: any, cmd: 'foreColor' | 'hiliteColor') => {
    const color = typeof val === 'string' ? val : val?.toHexString?.() ?? '#000';
    editorRef.current?.focus();
    exec(cmd, color);
    emit();
  };

  const containerStyle: React.CSSProperties = fullscreen
    ? { position: 'fixed', left: 0, top: 0, right: 0, bottom: 0, zIndex: 1200, background: '#fff', padding: 12 }
    : {};

  return (
    <div style={{ border: '1px solid #d9d9d9', borderRadius: 6, ...containerStyle }}>
      <div style={{ borderBottom: '1px solid #f0f0f0', padding: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        <Space size={2} wrap>
          <Tooltip title="粗体"><Button size="small" icon={<BoldOutlined />} onClick={() => { exec('bold'); emit(); }} /></Tooltip>
          <Tooltip title="斜体"><Button size="small" icon={<ItalicOutlined />} onClick={() => { exec('italic'); emit(); }} /></Tooltip>
          <Tooltip title="下划线"><Button size="small" icon={<UnderlineOutlined />} onClick={() => { exec('underline'); emit(); }} /></Tooltip>
          <Tooltip title="删除线"><Button size="small" icon={<StrikethroughOutlined />} onClick={() => { exec('strikeThrough'); emit(); }} /></Tooltip>
          <Select
            size="small"
            placeholder="标题"
            style={{ width: 78 }}
            onChange={(v) => { exec('formatBlock', v); emit(); }}
            options={[
              { value: 'H1', label: 'H1' },
              { value: 'H2', label: 'H2' },
              { value: 'H3', label: 'H3' },
              { value: 'P', label: '正文' },
              { value: 'BLOCKQUOTE', label: '引用' },
            ]}
          />
          <Select
            size="small"
            placeholder="字号"
            style={{ width: 76 }}
            suffixIcon={<FontSizeOutlined />}
            onChange={setFontSize}
            options={FONT_SIZES.map(s => ({ value: s, label: `${s}px` }))}
          />
          <Tooltip title="文字颜色">
            <ColorPicker size="small" onChange={(v) => setColor(v, 'foreColor')}>
              <Button size="small" icon={<FontColorsOutlined />} />
            </ColorPicker>
          </Tooltip>
          <Tooltip title="背景高亮">
            <ColorPicker size="small" onChange={(v) => setColor(v, 'hiliteColor')}>
              <Button size="small" icon={<BgColorsOutlined />} />
            </ColorPicker>
          </Tooltip>
          <Tooltip title="有序列表"><Button size="small" icon={<OrderedListOutlined />} onClick={() => { exec('insertOrderedList'); emit(); }} /></Tooltip>
          <Tooltip title="无序列表"><Button size="small" icon={<UnorderedListOutlined />} onClick={() => { exec('insertUnorderedList'); emit(); }} /></Tooltip>
          <Tooltip title="左对齐"><Button size="small" icon={<AlignLeftOutlined />} onClick={() => { exec('justifyLeft'); emit(); }} /></Tooltip>
          <Tooltip title="居中"><Button size="small" icon={<AlignCenterOutlined />} onClick={() => { exec('justifyCenter'); emit(); }} /></Tooltip>
          <Tooltip title="右对齐"><Button size="small" icon={<AlignRightOutlined />} onClick={() => { exec('justifyRight'); emit(); }} /></Tooltip>
          <Tooltip title="超链接"><Button size="small" icon={<LinkOutlined />} onClick={() => setLinkModalOpen(true)} /></Tooltip>
          <Tooltip title="插入图片"><Button size="small" icon={<PictureOutlined />} onClick={onImageClick} /></Tooltip>
          <Tooltip title="插入视频"><Button size="small" icon={<VideoCameraOutlined />} onClick={() => setVideoModalOpen(true)} /></Tooltip>
          <Tooltip title="插入表格"><Button size="small" icon={<TableOutlined />} onClick={insertTable} /></Tooltip>
          <Tooltip title="撤销"><Button size="small" icon={<UndoOutlined />} onClick={() => { exec('undo'); emit(); }} /></Tooltip>
          <Tooltip title="重做"><Button size="small" icon={<RedoOutlined />} onClick={() => { exec('redo'); emit(); }} /></Tooltip>
          <Tooltip title="清除格式"><Button size="small" icon={<ClearOutlined />} onClick={() => { exec('removeFormat'); emit(); }} /></Tooltip>
          <Tooltip title={fullscreen ? '退出全屏' : '全屏编辑'}>
            <Button size="small" icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />} onClick={() => setFullscreen(f => !f)} />
          </Tooltip>
        </Space>
      </div>
      <div
        ref={editorRef}
        contentEditable
        suppressContentEditableWarning
        onInput={emit}
        onBlur={emit}
        data-placeholder={placeholder || '请输入商品描述'}
        style={{
          minHeight: fullscreen ? 'calc(100vh - 120px)' : height,
          maxHeight: fullscreen ? 'calc(100vh - 120px)' : 480,
          overflowY: 'auto',
          padding: 12,
          outline: 'none',
          fontSize: 14,
          lineHeight: 1.6,
        }}
      />
      <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onImageChange} />
      <input ref={videoFileInputRef} type="file" accept="video/mp4,video/quicktime" style={{ display: 'none' }} onChange={onVideoFileChange} />

      <Modal
        open={videoModalOpen}
        title="插入视频"
        onCancel={() => setVideoModalOpen(false)}
        onOk={insertVideoLink}
        okText="插入外链"
        cancelText="取消"
        footer={[
          <Button key="local" onClick={() => { setVideoModalOpen(false); onVideoFileClick(); }}>本地上传视频</Button>,
          <Button key="cancel" onClick={() => setVideoModalOpen(false)}>取消</Button>,
          <Button key="ok" type="primary" onClick={insertVideoLink}>插入外链</Button>,
        ]}
      >
        <Input
          placeholder="粘贴视频外链（B 站、腾讯视频、YouTube 等）"
          value={videoUrl}
          onChange={e => setVideoUrl(e.target.value)}
        />
      </Modal>

      <Modal
        open={linkModalOpen}
        title="插入链接"
        onCancel={() => setLinkModalOpen(false)}
        onOk={insertLink}
      >
        <Input placeholder="链接文字（可选）" value={linkText} onChange={e => setLinkText(e.target.value)} style={{ marginBottom: 8 }} />
        <Input placeholder="URL" value={linkUrl} onChange={e => setLinkUrl(e.target.value)} />
      </Modal>
    </div>
  );
}
