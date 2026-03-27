const { get, post } = require('../../utils/request');
const { generateId } = require('../../utils/util');

Page({
  data: {
    article: {
      id: '1',
      title: '春季养生：如何预防过敏性鼻炎',
      author: '健康编辑部',
      time: '2026-03-27',
      views: 1280,
      likes: 256,
      comments: 3,
      tags: ['养生', '春季', '过敏'],
      content: '春季是过敏性鼻炎的高发季节，随着气温回暖，花粉、柳絮等过敏原增多，许多人都会出现打喷嚏、流鼻涕、鼻塞等症状。\n\n一、什么是过敏性鼻炎？\n\n过敏性鼻炎是一种由过敏原引起的鼻黏膜非感染性炎症。常见症状包括阵发性喷嚏、清水样鼻涕、鼻塞和鼻痒。\n\n二、预防措施\n\n1. 减少外出：花粉浓度高的时段（上午10点到下午4点）尽量避免外出\n2. 佩戴口罩：外出时佩戴防花粉口罩\n3. 清洁鼻腔：每天用生理盐水冲洗鼻腔\n4. 保持室内清洁：定期清洗床上用品，使用空气净化器\n5. 增强免疫力：适当运动，保证充足睡眠，均衡饮食\n\n三、饮食建议\n\n• 多食用富含维生素C的食物，如猕猴桃、橙子\n• 适量食用蜂蜜，可能有助于缓解过敏症状\n• 避免食用可能加重过敏的食物\n\n如果症状严重，建议及时就医，在医生指导下使用抗过敏药物。'
    },
    liked: false,
    commentValue: '',
    commentFocus: false,
    commentList: [
      { id: '1', user: '健康达人', content: '非常实用的文章，学到了很多！', time: '1小时前', color: '#52c41a' },
      { id: '2', user: '春日暖阳', content: '每年春天都被过敏性鼻炎折磨，试试这些方法', time: '3小时前', color: '#13c2c2' },
      { id: '3', user: '养生爱好者', content: '盐水冲鼻确实有效，亲测好用', time: '5小时前', color: '#722ed1' }
    ]
  },

  onLoad(options) {
    if (options.id) {
      this.loadArticle(options.id);
    }
  },

  async loadArticle(id) {
    try {
      // const res = await get(`/api/articles/${id}`);
      // this.setData({ article: res.data });
    } catch (e) {
      console.log('loadArticle error', e);
    }
  },

  toggleLike() {
    const liked = !this.data.liked;
    this.setData({
      liked,
      'article.likes': this.data.article.likes + (liked ? 1 : -1)
    });
  },

  focusComment() {
    this.setData({ commentFocus: true });
  },

  onCommentInput(e) {
    this.setData({ commentValue: e.detail.value });
  },

  submitComment() {
    const content = this.data.commentValue.trim();
    if (!content) return;

    const newComment = {
      id: generateId(),
      user: '我',
      content,
      time: '刚刚',
      color: '#1890ff'
    };

    this.setData({
      commentList: [newComment, ...this.data.commentList],
      commentValue: '',
      'article.comments': this.data.article.comments + 1
    });
    wx.showToast({ title: '评论成功', icon: 'success' });
  },

  shareArticle() {
    wx.showToast({ title: '分享功能开发中', icon: 'none' });
  }
});
