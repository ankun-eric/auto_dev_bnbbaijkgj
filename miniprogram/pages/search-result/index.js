const { get } = require('../../utils/request');

const plugin = requirePlugin('WechatSI');

const TYPE_LABEL_MAP = {
  all: '全部',
  article: '文章',
  video: '视频',
  service: '服务',
  points_mall: '积分商品'
};

Page({
  data: {
    query: '',
    keyword: '',
    currentTab: 'all',
    tabs: [
      { label: '全部', value: 'all' },
      { label: '文章', value: 'article' },
      { label: '视频', value: 'video' },
      { label: '服务', value: 'service' },
      { label: '积分商品', value: 'points_mall' }
    ],
    results: [],
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: false,
    loadingMore: false,
    showVoiceOverlay: false,
    voiceState: '',
    voiceErrorMsg: '',
    recordingTime: 0
  },

  _recordTimer: null,
  _recognizeManager: null,

  onLoad(options) {
    const q = options.q ? decodeURIComponent(options.q) : '';
    let source = options.source === 'voice' ? 'voice' : 'text';
    this.setData({ query: q, keyword: q, _searchSource: source });
    this._initRecognizeManager();
    if (q) {
      this.doSearch();
    }
  },

  onUnload() {
    if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
    this._recognizeManager = null;
  },

  _removePunctuation(str) {
    return str.replace(/[\u3002\uff1b\uff0c\uff1a\u201c\u201d\u2018\u2019\uff08\uff09\u3001\uff1f\u300a\u300b\uff01\u3010\u3011\u2026\u2014\uff5e\u00b7.,!?;:'"()\[\]{}\-_\/\\@#\$%\^&\*\+=~`<>]/g, '').trim();
  },

  _initRecognizeManager() {
    const manager = plugin.getRecordRecognitionManager();

    manager.onRecognize = (res) => {
      if (res.result) {
        this.setData({ keyword: this._removePunctuation(res.result) });
      }
    };

    manager.onStop = (res) => {
      if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }

      const text = res.result ? this._removePunctuation(res.result) : '';
      if (text) {
        this.setData({
          keyword: text,
          showVoiceOverlay: false,
          voiceState: ''
        });
        this._doVoiceSearch(text);
      } else {
        this.setData({
          voiceState: 'error',
          voiceErrorMsg: '未识别到内容，请重试'
        });
      }
    };

    manager.onError = (res) => {
      if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
      this.setData({
        voiceState: 'error',
        voiceErrorMsg: res.msg || '语音识别出错，请重试'
      });
    };

    manager.onStart = () => {
      let t = 0;
      this._recordTimer = setInterval(() => {
        t++;
        this.setData({ recordingTime: t });
        if (t >= 15) {
          this._stopRecording();
        }
      }, 1000);
    };

    this._recognizeManager = manager;
  },

  _doVoiceSearch(text) {
    this.setData({
      query: text,
      keyword: text,
      _searchSource: 'voice',
      results: [],
      page: 1,
      hasMore: true
    });
    this.doSearch();
  },

  onInput(e) {
    this.setData({ keyword: e.detail.value });
  },

  onClear() {
    this.setData({ keyword: '' });
  },

  onSearchAgain() {
    const q = this.data.keyword.trim();
    if (!q) return;
    this.setData({
      query: q,
      _searchSource: 'text',
      results: [],
      page: 1,
      hasMore: true
    });
    this.doSearch();
  },

  onMicTap() {
    if (this.data.showVoiceOverlay) return;
    this.setData({
      showVoiceOverlay: true,
      voiceState: 'recording',
      recordingTime: 0,
      voiceErrorMsg: ''
    });
    this._startRecording();
  },

  onStopRecording() {
    this._stopRecording();
  },

  _startRecording() {
    if (!this._recognizeManager) {
      this._initRecognizeManager();
    }
    this._recognizeManager.start({ lang: 'zh_CN' });
  },

  _stopRecording() {
    if (this._recordTimer) { clearInterval(this._recordTimer); this._recordTimer = null; }
    this.setData({ voiceState: 'recognizing' });
    if (this._recognizeManager) {
      this._recognizeManager.stop();
    }
  },

  onRetryVoice() {
    this.setData({
      voiceState: 'recording',
      recordingTime: 0,
      voiceErrorMsg: ''
    });
    this._startRecording();
  },

  onCloseVoice() {
    this.setData({
      showVoiceOverlay: false,
      voiceState: '',
      voiceErrorMsg: ''
    });
  },

  preventMove() {},

  onTabTap(e) {
    const value = e.currentTarget.dataset.value;
    if (value === this.data.currentTab) return;
    this.setData({
      currentTab: value,
      results: [],
      page: 1,
      hasMore: true
    });
    this.doSearch();
  },

  async doSearch() {
    const { query, currentTab, page, pageSize } = this.data;
    if (!query) return;

    if (page === 1) {
      this.setData({ loading: true });
    } else {
      this.setData({ loadingMore: true });
    }

    try {
      const res = await get('/api/search', {
        q: query,
        type: currentTab,
        page,
        page_size: pageSize,
        source: this.data._searchSource || 'text'
      }, { showLoading: false, suppressErrorToast: true });

      const items = Array.isArray(res) ? res : (res && res.items ? res.items : []);
      const total = res && res.total != null ? res.total : items.length;

      const enriched = items.map(item => ({
        ...item,
        type_label: TYPE_LABEL_MAP[item.type] || item.type || '内容'
      }));

      const allResults = page === 1 ? enriched : this.data.results.concat(enriched);
      const hasMore = allResults.length < total;

      this.setData({
        results: allResults,
        hasMore,
        loading: false,
        loadingMore: false
      });
    } catch (e) {
      this.setData({ loading: false, loadingMore: false });
      if (page === 1) {
        this.setData({ results: [] });
      }
    }
  },

  loadMore() {
    if (!this.data.hasMore || this.data.loadingMore) return;
    this.setData({ page: this.data.page + 1 });
    this.doSearch();
  },

  onReachBottom() {
    this.loadMore();
  },

  onResultTap(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) return;

    const type = item.type;
    const id = item.id;

    if (type === 'article') {
      wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
    } else if (type === 'video') {
      wx.navigateTo({ url: `/pages/article-detail/index?id=${id}` });
    } else if (type === 'service') {
      wx.navigateTo({ url: `/pages/service-detail/index?id=${id}` });
    } else if (type === 'points_mall') {
      wx.navigateTo({ url: `/pages/points-mall/index` });
    } else if (item.url) {
      wx.navigateTo({
        url: item.url,
        fail() {
          wx.switchTab({ url: item.url });
        }
      });
    }
  }
});
