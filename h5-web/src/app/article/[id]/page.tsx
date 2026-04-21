'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Button, TextArea, Avatar, Tag, Toast, Divider, SpinLoading } from 'antd-mobile';
import { HeartOutline, HeartFill, StarOutline, StarFill } from 'antd-mobile-icons';
import api from '@/lib/api';

interface ArticleDetail {
  id: number;
  title: string;
  category?: string;
  author_name?: string;
  created_at?: string;
  published_at?: string;
  view_count?: number;
  like_count?: number;
  comment_count?: number;
  content?: string;
  content_html?: string;
  tags?: string[];
}

interface CommentItem {
  id: number;
  user: string;
  content: string;
  time: string;
  avatar: string;
}

export default function ArticleDetailPage() {
  const router = useRouter();
  const params = useParams();
  const articleId = params?.id as string;

  const [loading, setLoading] = useState(true);
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [liked, setLiked] = useState(false);
  const [collected, setCollected] = useState(false);
  const [likeCount, setLikeCount] = useState(0);
  const [comment, setComment] = useState('');
  const [comments, setComments] = useState<CommentItem[]>([]);

  const loadArticle = useCallback(async () => {
    try {
      setLoading(true);
      const res: any = await api.get(`/api/content/articles/${articleId}`);
      const data: ArticleDetail = res?.data ?? res;
      setArticle(data);
      setLikeCount(data.like_count ?? 0);
    } catch {
      Toast.show({ content: '加载失败' });
    } finally {
      setLoading(false);
    }
  }, [articleId]);

  const loadComments = useCallback(async () => {
    try {
      const res: any = await api.get(`/api/content/comments?content_type=article&content_id=${articleId}`);
      const items: any[] = res?.items ?? res?.data?.items ?? [];
      setComments(items.map((c) => ({
        id: c.id,
        // PRD F2：优先使用后端 JOIN users 返回的实时字段
        user: c.author_nick || c.user_name || c.user?.name || '用户',
        content: c.content ?? '',
        time: c.created_at ? new Date(c.created_at).toLocaleDateString('zh-CN') : '',
        avatar: c.author_avatar || c.user_avatar || c.user?.avatar || '',
      })));
    } catch {
      setComments([]);
    }
  }, [articleId]);

  useEffect(() => {
    if (articleId) {
      loadArticle();
      loadComments();
    }
  }, [articleId, loadArticle, loadComments]);

  const toggleLike = async () => {
    try {
      const res: any = await api.post(`/api/content/favorites?content_type=article&content_id=${articleId}`, {});
      const favorited = res?.favorited ?? !liked;
      setLiked(favorited);
      setCollected(favorited);
      setLikeCount(favorited ? likeCount + 1 : Math.max(0, likeCount - 1));
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const toggleCollect = async () => {
    try {
      const res: any = await api.post(`/api/content/favorites?content_type=article&content_id=${articleId}`, {});
      const favorited = res?.favorited ?? !collected;
      setCollected(favorited);
      setLiked(favorited);
      Toast.show({ content: favorited ? '收藏成功' : '已取消收藏' });
    } catch {
      Toast.show({ content: '操作失败' });
    }
  };

  const submitComment = async () => {
    if (!comment.trim()) return;
    try {
      await api.post('/api/content/comments', {
        content_type: 'article',
        content_id: Number(articleId),
        content: comment.trim(),
      });
      setComment('');
      Toast.show({ content: '评论成功' });
      loadComments();
    } catch {
      Toast.show({ content: '评论失败' });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <SpinLoading color="primary" />
      </div>
    );
  }

  if (!article) {
    return (
      <div className="min-h-screen bg-white">
        <NavBar onBack={() => router.back()}>文章详情</NavBar>
        <div className="text-center text-gray-400 py-20">文章不存在或已下架</div>
      </div>
    );
  }

  const contentHtml = article.content_html && article.content_html.trim()
    ? article.content_html
    : (article.content || '').split('\n').map((line) => line.trim() ? `<p>${line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}</p>` : '').join('');

  const timeText = article.published_at || article.created_at || '';

  return (
    <div className="min-h-screen bg-white pb-20">
      {/* PRD F2.1：文章详情页标题栏统一主题绿 + 白字 */}
      <NavBar
        onBack={() => router.back()}
        right={
          <div className="flex items-center gap-4">
            <span onClick={toggleCollect}>
              {collected ? (
                <StarFill style={{ color: '#fff', fontSize: 20 }} />
              ) : (
                <StarOutline style={{ fontSize: 20, color: '#fff' }} />
              )}
            </span>
          </div>
        }
        style={{
          background: '#4CAF50',
          '--height': '44px',
          color: '#fff',
          ['--border-bottom' as any]: 'none',
        } as any}
        backArrow={
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
        }
      >
        <span style={{ color: '#fff' }}>文章详情</span>
      </NavBar>

      <div className="px-4 pt-4">
        <h1 className="text-xl font-bold leading-tight">{article.title}</h1>
        <div className="flex items-center flex-wrap mt-3 mb-4 gap-2">
          {article.category && (
            <Tag
              style={{
                '--background-color': '#52c41a15',
                '--text-color': '#52c41a',
                '--border-color': 'transparent',
                fontSize: 10,
              }}
            >
              {article.category}
            </Tag>
          )}
          {article.author_name && <span className="text-xs text-gray-400">{article.author_name}</span>}
          {timeText && <span className="text-xs text-gray-300">{new Date(timeText).toLocaleDateString('zh-CN')}</span>}
          <span className="text-xs text-gray-300">{article.view_count ?? 0}阅读</span>
        </div>

        <div className="mb-6 rich-text text-sm text-gray-700 leading-relaxed" dangerouslySetInnerHTML={{ __html: contentHtml }} />

        <div className="flex items-center justify-center gap-8 py-4 border-y border-gray-100">
          <div className="flex items-center gap-1 cursor-pointer" onClick={toggleLike}>
            {liked ? (
              <HeartFill style={{ color: '#f5222d', fontSize: 20 }} />
            ) : (
              <HeartOutline style={{ color: '#999', fontSize: 20 }} />
            )}
            <span className={`text-sm ${liked ? 'text-red-500' : 'text-gray-400'}`}>{likeCount}</span>
          </div>
          <div className="flex items-center gap-1 cursor-pointer" onClick={toggleCollect}>
            {collected ? (
              <StarFill style={{ color: '#fa8c16', fontSize: 20 }} />
            ) : (
              <StarOutline style={{ color: '#999', fontSize: 20 }} />
            )}
            <span className={`text-sm ${collected ? 'text-orange-400' : 'text-gray-400'}`}>
              {collected ? '已收藏' : '收藏'}
            </span>
          </div>
        </div>

        <Divider>评论 ({comments.length})</Divider>

        <div className="flex gap-2 mb-4">
          <TextArea
            placeholder="写下你的评论..."
            value={comment}
            onChange={setComment}
            rows={2}
            style={{ '--font-size': '14px', flex: 1 }}
          />
          <Button
            size="small"
            onClick={submitComment}
            style={{
              alignSelf: 'flex-end',
              borderRadius: 16,
              background: '#52c41a',
              color: '#fff',
              border: 'none',
            }}
          >
            发送
          </Button>
        </div>

        {comments.map((c) => (
          <div key={c.id} className="flex py-3 border-b border-gray-50">
            <Avatar
              src={c.avatar}
              style={{
                '--size': '32px',
                '--border-radius': '50%',
                background: '#52c41a30',
                flexShrink: 0,
              }}
            />
            <div className="ml-3 flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{c.user}</span>
                <span className="text-xs text-gray-300">{c.time}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1">{c.content}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
