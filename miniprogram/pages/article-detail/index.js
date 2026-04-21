const { get, post } = require('../../utils/request');

Page({
  data: {
    article: null,
    liked: false,
    collected: false,
    commentValue: '',
    commentFocus: false,
    commentList: [],
    articleId: null,
  },

  onLoad(options) {
    const id = options.id;
    if (id) {
      this.setData({ articleId: id });
      this.loadArticle(id);
      this.loadComments(id);
    }
  },

  async loadArticle(id) {
    try {
      const res = await get(`/api/content/articles/${id}`);
      const data = res?.data || res || {};
      this.setData({
        article: {
          id: data.id,
          title: data.title || '',
          author: data.author_name || '',
          time: (data.published_at || data.created_at || '').slice(0, 10),
          views: data.view_count || 0,
          likes: data.like_count || 0,
          comments: data.comment_count || 0,
          tags: data.tags || [],
          content: data.content_html || data.content || '',
        },
      });
    } catch (e) {
      wx.showToast({ title: '加载失败', icon: 'none' });
    }
  },

  // PRD F2：评论走真实接口，用后端 JOIN users 返回的 author_avatar / author_nick
  async loadComments(id) {
    try {
      const res = await get(`/api/content/comments?content_type=article&content_id=${id}`);
      const items = res?.items || res?.data?.items || [];
      const list = items.map((c) => ({
        id: c.id,
        user: c.author_nick || c.user_name || '用户',
        avatar: c.author_avatar || c.user_avatar || '',
        content: c.content || '',
        time: c.created_at ? (c.created_at || '').replace('T', ' ').slice(0, 19) : '',
      }));
      this.setData({ commentList: list });
    } catch (e) {
      this.setData({ commentList: [] });
    }
  },

  toggleLike() {
    const liked = !this.data.liked;
    const article = this.data.article || {};
    this.setData({
      liked,
      article: { ...article, likes: (article.likes || 0) + (liked ? 1 : -1) },
    });
    if (this.data.articleId) {
      post(`/api/content/favorites?content_type=article&content_id=${this.data.articleId}`, {}).catch(() => {});
    }
  },

  focusComment() {
    this.setData({ commentFocus: true });
  },

  onCommentInput(e) {
    this.setData({ commentValue: e.detail.value });
  },

  async submitComment() {
    const content = this.data.commentValue.trim();
    if (!content || !this.data.articleId) return;
    try {
      await post('/api/content/comments', {
        content_type: 'article',
        content_id: Number(this.data.articleId),
        content,
      });
      this.setData({ commentValue: '' });
      wx.showToast({ title: '评论成功', icon: 'success' });
      this.loadComments(this.data.articleId);
    } catch (e) {
      wx.showToast({
        title: (e && (e.data?.detail || e.message)) || '评论失败',
        icon: 'none',
      });
    }
  },

  shareArticle() {
    wx.showToast({ title: '分享功能开发中', icon: 'none' });
  },
});
