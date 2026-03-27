'use client';

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { NavBar, Button, TextArea, List, Avatar, Tag, Toast, Divider } from 'antd-mobile';
import { HeartOutline, HeartFill, StarOutline, StarFill } from 'antd-mobile-icons';

const mockArticle = {
  id: 1,
  title: '春季养生：这5个习惯让你元气满满',
  tag: '养生',
  author: '宾尼健康编辑部',
  time: '2024-03-15',
  views: 1230,
  likes: 89,
  collected: false,
  content: `
春季是万物复苏的季节，也是养生保健的好时机。以下5个习惯，帮你在春季保持元气满满。

**1. 早睡早起，顺应春气**

春季阳气升发，应顺应自然规律，做到早睡早起。建议晚上11点前入睡，早上6-7点起床。充足的睡眠有助于肝气疏泄，让身体更好地适应春季气候变化。

**2. 饮食清淡，多吃时令蔬菜**

春季饮食应以清淡为主，多食用时令蔬菜如菠菜、荠菜、春笋等。这些蔬菜富含维生素和矿物质，有助于清热解毒、补充营养。

**3. 适当运动，舒展筋骨**

春天适合进行户外运动，如散步、慢跑、太极拳等。适当运动可以促进血液循环，增强体质，还能帮助改善情绪。

**4. 保持心情舒畅**

中医认为，春季与肝相应，肝主疏泄，喜条达而恶抑郁。因此，春季要特别注意调节情志，保持心情愉悦，避免过度焦虑。

**5. 多喝水，防春燥**

春季气候干燥，容易上火。建议每天饮水2000ml以上，也可以适当饮用菊花茶、枸杞茶等养生茶饮。
  `,
  comments: [
    { id: 1, user: '健康达人', content: '写得很好，已经开始按照这些建议执行了', time: '2024-03-15', avatar: '' },
    { id: 2, user: '养生爱好者', content: '春季养生确实很重要，感谢分享', time: '2024-03-14', avatar: '' },
  ],
};

export default function ArticleDetailPage() {
  const router = useRouter();
  const params = useParams();
  const [liked, setLiked] = useState(false);
  const [collected, setCollected] = useState(false);
  const [likeCount, setLikeCount] = useState(mockArticle.likes);
  const [comment, setComment] = useState('');
  const [comments, setComments] = useState(mockArticle.comments);

  const toggleLike = () => {
    setLiked(!liked);
    setLikeCount(liked ? likeCount - 1 : likeCount + 1);
  };

  const toggleCollect = () => {
    setCollected(!collected);
    Toast.show({ content: collected ? '已取消收藏' : '收藏成功' });
  };

  const submitComment = () => {
    if (!comment.trim()) return;
    setComments([
      { id: Date.now(), user: '我', content: comment, time: '刚刚', avatar: '' },
      ...comments,
    ]);
    setComment('');
    Toast.show({ content: '评论成功' });
  };

  const renderContent = (text: string) => {
    const lines = text.trim().split('\n');
    return lines.map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <br key={i} />;
      const formatted = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      return (
        <p
          key={i}
          className="mb-2 text-sm text-gray-700 leading-relaxed"
          dangerouslySetInnerHTML={{ __html: formatted }}
        />
      );
    });
  };

  return (
    <div className="min-h-screen bg-white pb-20">
      <NavBar
        onBack={() => router.back()}
        right={
          <div className="flex items-center gap-4">
            <span onClick={toggleCollect}>
              {collected ? <StarFill style={{ color: '#fa8c16', fontSize: 20 }} /> : <StarOutline style={{ fontSize: 20, color: '#999' }} />}
            </span>
            <span className="text-sm text-gray-400">分享</span>
          </div>
        }
        style={{ background: '#fff' }}
      >
        文章详情
      </NavBar>

      <div className="px-4 pt-4">
        <h1 className="text-xl font-bold leading-tight">{mockArticle.title}</h1>
        <div className="flex items-center mt-3 mb-4">
          <Tag
            style={{
              '--background-color': '#52c41a15',
              '--text-color': '#52c41a',
              '--border-color': 'transparent',
              fontSize: 10,
            }}
          >
            {mockArticle.tag}
          </Tag>
          <span className="text-xs text-gray-400 ml-2">{mockArticle.author}</span>
          <span className="text-xs text-gray-300 ml-2">{mockArticle.time}</span>
          <span className="text-xs text-gray-300 ml-2">{mockArticle.views}阅读</span>
        </div>

        <div className="mb-6">{renderContent(mockArticle.content)}</div>

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
