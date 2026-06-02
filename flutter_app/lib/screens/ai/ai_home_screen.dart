import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/chat_provider.dart';
import '../../models/chat_session.dart';
import '../../widgets/chat_history_drawer.dart';
import '../../services/api_service.dart';

class AiHomeScreen extends StatefulWidget {
  const AiHomeScreen({super.key});

  @override
  State<AiHomeScreen> createState() => _AiHomeScreenState();
}

class _AiHomeScreenState extends State<AiHomeScreen> with WidgetsBindingObserver {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final ApiService _apiService = ApiService();

  // [PRD-425] AI 助手昵称（取 ai_chat.signature；为空时兜底"小康"），超 8 字截断
  String _aiSignature = '小康';

  // [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 时段问候（与关怀模式同口径）
  String _greeting() {
    final h = DateTime.now().hour;
    if (h >= 5 && h < 11) return '早上好 ☀️';
    if (h >= 11 && h < 18) return '中午好 🌤️';
    return '晚上好 🌙';
  }
  // [PRD-425] 通知中心未读总数；-1=未加载/接口异常（不显示徽标）
  int _unreadCount = -1;

  // [PRD-AI-HOME-OPTIM-V4 2026-05-21] 60 分钟刷新阈值（来自 /api/ai-home/refresh-config）
  Duration _v4RefreshThreshold = const Duration(minutes: 60);
  // 悬浮球展开面板可见
  bool _v4FloatingPanelOpen = false;
  // 首次引导气泡可见
  bool _v4FloatingFirstGuideVisible = false;

  final List<Map<String, dynamic>> _consultTypes = [
    {
      'type': 'health_qa',
      'title': '健康问答',
      'desc': 'AI健康顾问在线解答',
      'icon': Icons.chat_bubble_outline,
      'color': const Color(0xFF52C41A),
    },
    {
      'type': 'symptom_check',
      'title': '健康自查',
      'desc': '智能健康自查参考',
      'icon': Icons.search,
      'color': const Color(0xFF1890FF),
    },
    {
      'type': 'tcm',
      'title': '中医养生',
      'desc': '中医养生体质调理',
      'icon': Icons.spa,
      'color': const Color(0xFFEB2F96),
    },
    {
      'type': 'drug_query',
      'title': '用药参考',
      'desc': '用药参考与注意事项',
      'icon': Icons.medication,
      'color': const Color(0xFF722ED1),
    },
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<ChatProvider>(context, listen: false).loadSessions();
      _loadAiSignature();
      _loadUnreadCount();
      // [PRD-AI-HOME-OPTIM-V4 M1] 拉取 60 分钟刷新阈值并执行一次刷新检测
      _loadV4RefreshConfig().then((_) => _runV4RefreshCheck('mounted'));
      // [PRD-AI-HOME-OPTIM-V4 M3] 800ms 后展示一次首次引导气泡（仅一次）
      Future.delayed(const Duration(milliseconds: 800), _maybeShowV4FirstGuide);
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // [PRD-AI-HOME-OPTIM-V4 F-刷新-04] 前后台切换时再次执行刷新检测
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.resumed) {
      _runV4RefreshCheck('resumed');
    }
  }

  // [PRD-AI-HOME-OPTIM-V4 F-刷新-05] 拉取后端阈值配置
  Future<void> _loadV4RefreshConfig() async {
    try {
      final resp = await _apiService.dio.get('/api/ai-home/refresh-config');
      final data = resp.data;
      int? minutes;
      if (data is Map) {
        final v = data['session_refresh_minutes'];
        if (v is int) minutes = v;
        if (v is num) minutes = v.toInt();
      }
      if (!mounted) return;
      if (minutes != null && minutes > 0) {
        setState(() => _v4RefreshThreshold = Duration(minutes: minutes!));
      }
    } catch (_) {
      // 静默：用默认 60min
    }
  }

  // [PRD-AI-HOME-OPTIM-V4 M1] 60 分钟刷新检测：取最近一条会话 updated_at 判断
  Future<void> _runV4RefreshCheck(String triggerSource) async {
    try {
      final cp = Provider.of<ChatProvider>(context, listen: false);
      // 确保 sessions 已加载
      if (cp.sessions.isEmpty) {
        await cp.loadSessions();
      }
      final list = cp.sessions;
      if (list.isEmpty) return;
      // 取第一条（updated_at 最新）作为基准
      final latest = list.first;
      final tsStr = latest.updatedAt ?? latest.lastMessageTime ?? latest.createdAt;
      DateTime? ts;
      try {
        if (tsStr != null && tsStr.isNotEmpty) {
          ts = DateTime.tryParse(tsStr);
        }
      } catch (_) {}
      if (ts == null) return;
      final idle = DateTime.now().difference(ts);
      if (idle >= _v4RefreshThreshold) {
        // 触发刷新埋点
        _reportV4Track('refresh_triggered', {
          'trigger_source': triggerSource,
          'idle_minutes': idle.inMinutes,
        });
      } else {
        _reportV4Track('refresh_skipped', {
          'last_active_minutes': idle.inMinutes,
        });
      }
    } catch (_) {
      // 静默
    }
  }

  void _reportV4Track(String event, Map<String, dynamic> payload) {
    try {
      _apiService.dio.post('/api/ai-home/track', data: {
        'event': event,
        'platform': 'flutter',
        'payload': payload,
      }).catchError((_) => null);
    } catch (_) {
      // 静默
    }
  }

  // [PRD-AI-HOME-OPTIM-V4 M3] 首次引导气泡（仅一次，使用 SharedPreferences 风格的本地存储兜底）
  // 注意：这里使用 in-memory + 简单 ApiService 兜底，按 PRD 不强依赖持久化即可
  static bool _v4FirstGuideShownThisProcess = false;
  void _maybeShowV4FirstGuide() {
    if (_v4FirstGuideShownThisProcess) return;
    if (!mounted) return;
    setState(() => _v4FloatingFirstGuideVisible = true);
    _reportV4Track('first_guide_shown', {});
    _v4FirstGuideShownThisProcess = true;
    Future.delayed(const Duration(seconds: 3), () {
      if (!mounted) return;
      setState(() => _v4FloatingFirstGuideVisible = false);
    });
  }

  // [PRD-425] 加载 AI 助手昵称（ai_chat.signature）
  // [PRD-429] 修复：用显式 if/Map cast 替代 null-aware index `?[]`，兼容 Flutter 3.32.0
  Future<void> _loadAiSignature() async {
    try {
      final resp = await _apiService.dio.get('/api/ai-home-config');
      dynamic data;
      if (resp.data is Map) {
        final m = resp.data as Map;
        if (m['config'] != null) {
          data = m['config'];
        } else if (m['data'] is Map && (m['data'] as Map)['config'] != null) {
          data = (m['data'] as Map)['config'];
        } else {
          data = resp.data;
        }
      }
      String sig = '';
      if (data is Map && data['ai_chat'] is Map) {
        final v = (data['ai_chat'] as Map)['signature'];
        sig = v?.toString().trim() ?? '';
      }
      if (!mounted) return;
      setState(() {
        _aiSignature = sig.isEmpty ? '小康' : (sig.length > 8 ? '${sig.substring(0, 8)}…' : sig);
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _aiSignature = '小康');
    }
  }

  // [PRD-425] 加载通知中心未读总数（进入页面拉一次；接口异常 → 不显示徽标）
  // [PRD-429] 修复：用显式 if/Map cast 替代 null-aware index `?[]`，兼容 Flutter 3.32.0
  Future<void> _loadUnreadCount() async {
    try {
      final resp = await _apiService.dio.get('/api/v1/notifications/unread-count');
      int? cnt;
      if (resp.data is Map) {
        final m = resp.data as Map;
        if (m['data'] is Map) {
          final v = (m['data'] as Map)['unreadCount'];
          if (v is int) cnt = v;
        }
      }
      if (!mounted) return;
      if (cnt != null && cnt >= 0) {
        setState(() => _unreadCount = cnt!);
      }
    } catch (_) {
      // 静默失败：保持 _unreadCount = -1（不显示徽标）
    }
  }

  // [PRD-425] 顶栏标题 + 右上角未读徽标
  Widget _buildTopBarTitle() {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Text(
          _aiSignature,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 17,
            fontWeight: FontWeight.w600,
          ),
        ),
        if (_unreadCount >= 0)
          Positioned(
            top: -6,
            right: -16,
            child: GestureDetector(
              onTap: () async {
                // 点击徽标 → 跳转通知中心；路由不存在时静默
                try {
                  await Navigator.pushNamed(context, '/messages');
                } catch (_) {}
              },
              child: _unreadCount == 0
                  ? Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: Color(0xFFFF3B30),
                        shape: BoxShape.circle,
                      ),
                    )
                  : Container(
                      constraints: const BoxConstraints(minWidth: 16),
                      height: 16,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFF3B30),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.white, width: 1),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        _unreadCount >= 100 ? '99+' : '$_unreadCount',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          height: 1.0,
                        ),
                      ),
                    ),
            ),
          ),
      ],
    );
  }

  void _createNewSession(String type) async {
    if (type == 'drug_query') {
      Navigator.pushNamed(context, '/drug');
      return;
    }
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final session = await chatProvider.createSession(type);
    if (session != null && mounted) {
      Navigator.pushNamed(context, '/chat');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      drawer: ChatHistoryDrawer(
        onNewChat: () {
          // User picks from the consult type grid on the main screen
        },
        onSessionTap: (session) {
          Navigator.pushNamed(context, '/chat');
        },
      ),
      appBar: AppBar(
        // [PRD-425] 标题取 ai_chat.signature（默认"小康"），右上角带未读徽标
        title: _buildTopBarTitle(),
        backgroundColor: const Color(0xFF52C41A),
        centerTitle: true,
        automaticallyImplyLeading: false,
        leading: IconButton(
          icon: const Icon(Icons.menu, color: Colors.white),
          onPressed: () => _scaffoldKey.currentState?.openDrawer(),
        ),
        actions: [
          // [Bug 修复 v1.0 §3.1.4 2026-05-26] 右上角「更多」菜单，首项「👑 会员中心」
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_horiz, color: Colors.white),
            tooltip: '更多',
            offset: const Offset(0, 48),
            onSelected: (value) {
              switch (value) {
                case 'member-center':
                  Navigator.pushNamed(context, '/member-center');
                  break;
                case 'scan':
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('扫一扫开发中')),
                  );
                  break;
                case 'font-size':
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('字体大小设置请在「我的-设置」中调整')),
                  );
                  break;
                case 'share':
                  // [PRD-AIHOME-OPTIM-SHARE-V1 2026-06-02 §需求1] 分享好友：分享当前 AI 首页
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('分享好友开发中')),
                  );
                  break;
              }
            },
            itemBuilder: (context) {
              final now = DateTime.now();
              final showNew = now.isBefore(DateTime.utc(2026, 6, 25));
              return [
                PopupMenuItem<String>(
                  value: 'member-center',
                  child: Row(
                    children: [
                      const Text('👑 ', style: TextStyle(fontSize: 18)),
                      const Text(
                        '会员中心',
                        style: TextStyle(
                          color: Color(0xFFE5A23B),
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (showNew) ...[
                        const SizedBox(width: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFFE5A23B), Color(0xFFF4D793)],
                            ),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Text(
                            '新',
                            style: TextStyle(
                              color: Color(0xFF5C3B00),
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const PopupMenuItem<String>(
                  value: 'scan',
                  child: Row(
                    children: [
                      Text('📷 ', style: TextStyle(fontSize: 18)),
                      Text('扫一扫'),
                    ],
                  ),
                ),
                const PopupMenuItem<String>(
                  value: 'font-size',
                  child: Row(
                    children: [
                      Text('🔤 ', style: TextStyle(fontSize: 18)),
                      Text('字体大小'),
                    ],
                  ),
                ),
                // [PRD-AIHOME-OPTIM-SHARE-V1 2026-06-02 §需求1] 「🎁 分享好友」统一入口
                //   合并原「立即分享」，与 H5 / 小程序 / 关怀模式行为一致（分享当前 AI 首页）。
                const PopupMenuItem<String>(
                  value: 'share',
                  child: Row(
                    children: [
                      Text('🎁 ', style: TextStyle(fontSize: 18)),
                      Text('分享好友'),
                    ],
                  ),
                ),
              ];
            },
          ),
        ],
      ),
      // [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-01] 右下角小康头像悬浮球（F 款）
      floatingActionButton: _buildV4FloatingBall(),
      body: Consumer<ChatProvider>(
        builder: (context, chatProvider, child) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 标准模式欢迎区统一为关怀模式风格
                // （大问候 + 欢迎语 + 机器人头像），背景照搬现关怀模式蓝绿渐变；做瘦身，不含用药提醒卡。
                Container(
                  padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [Color(0xFF1976D2), Color(0xFF43A047)],
                    ),
                    borderRadius: BorderRadius.all(Radius.circular(24)),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _greeting(),
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold),
                            ),
                            const SizedBox(height: 8),
                            // [BUGFIX-AIHOME-STD-GREETING-ALIGN-V1 2026-06-02] 标准模式副标题统一为
                            // 「我是宾尼小康，聊聊健康问题吧~」（与四端标准模式一字不差）。
                            const Text(
                              '我是宾尼小康，聊聊健康问题吧~',
                              style: TextStyle(color: Colors.white, fontSize: 16),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Container(
                        width: 72,
                        height: 72,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white.withOpacity(0.9), width: 2),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.12),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: const Icon(Icons.smart_toy, color: Color(0xFF1976D2), size: 40),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                const Text(
                  '选择咨询类型',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
                ),
                const SizedBox(height: 12),
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 1.5,
                    crossAxisSpacing: 12,
                    mainAxisSpacing: 12,
                  ),
                  itemCount: _consultTypes.length,
                  itemBuilder: (context, index) {
                    final item = _consultTypes[index];
                    return GestureDetector(
                      onTap: () => _createNewSession(item['type']),
                      child: Container(
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.04),
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                          ],
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(item['icon'], color: item['color'], size: 28),
                              const SizedBox(height: 8),
                              Text(
                                item['title'],
                                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                item['desc'],
                                style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                              ),
                            ],
                          ),
                        ),
                      ),
                    );
                  },
                ),
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      '最近对话',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
                    ),
                    if (chatProvider.sessions.isNotEmpty)
                      TextButton(
                        onPressed: () => _scaffoldKey.currentState?.openDrawer(),
                        child: const Text('查看全部', style: TextStyle(color: Color(0xFF52C41A))),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                if (chatProvider.isLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: CircularProgressIndicator(color: Color(0xFF52C41A)),
                    ),
                  )
                else if (chatProvider.sessions.isEmpty)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.all(40),
                      child: Column(
                        children: [
                          Icon(Icons.chat_bubble_outline, size: 60, color: Colors.grey[300]),
                          const SizedBox(height: 12),
                          Text('暂无对话记录', style: TextStyle(color: Colors.grey[500])),
                          const SizedBox(height: 8),
                          Text('选择上方咨询类型开始对话', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
                        ],
                      ),
                    ),
                  )
                else
                  ...chatProvider.sessions.take(5).map((session) => _buildSessionCard(session)),
              ],
            ),
          );
        },
      ),
    );
  }

  // [PRD-AI-HOME-OPTIM-V4 M3 · F-悬浮-01] F 款·小康头像悬浮球
  Widget _buildV4FloatingBall() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        if (_v4FloatingFirstGuideVisible)
          Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFFE5F4FF)),
              boxShadow: [
                BoxShadow(color: Colors.black.withOpacity(0.12), blurRadius: 8, offset: const Offset(0, 2)),
              ],
            ),
            child: const Text('健康服务入口在这里，随时点开',
                style: TextStyle(fontSize: 12, color: Color(0xFF2E2E2E))),
          ),
        GestureDetector(
          onTap: _onV4FloatingBallTap,
          child: Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: const Color(0xFF0EA5E9), width: 2),
              gradient: const LinearGradient(
                colors: [Color(0xFF38BDF8), Color(0xFF0284C7)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(color: Colors.black.withOpacity(0.16), blurRadius: 12, offset: const Offset(0, 4)),
              ],
            ),
            alignment: Alignment.center,
            child: const Text(
              '康',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 22),
            ),
          ),
        ),
      ],
    );
  }

  void _onV4FloatingBallTap() {
    setState(() {
      _v4FloatingFirstGuideVisible = false;
      _v4FloatingPanelOpen = true;
    });
    _reportV4Track('floating_ball_clicked', {});
    // 用 modalBottomSheet 展示面板
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _buildV4FloatingPanel(ctx),
    ).whenComplete(() {
      if (mounted) setState(() => _v4FloatingPanelOpen = false);
    });
  }

  Widget _buildV4FloatingPanel(BuildContext ctx) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('欢迎您！我是 AI 健康顾问小康',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1F2937))),
              IconButton(
                icon: const Icon(Icons.close, color: Color(0xFF9CA3AF)),
                onPressed: () => Navigator.of(ctx).pop(),
              ),
            ],
          ),
          const Padding(
            padding: EdgeInsets.only(bottom: 16),
            child: Text('健康服务入口，随时为您和家人提供专业的健康咨询',
                style: TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
          ),
          // 4 个咨询入口（直接复用 _consultTypes）
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 4,
              childAspectRatio: 0.85,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
            ),
            itemCount: _consultTypes.length,
            itemBuilder: (context, index) {
              final item = _consultTypes[index];
              return GestureDetector(
                onTap: () {
                  Navigator.of(ctx).pop();
                  _reportV4Track('floating_ball_panel_action', {
                    'entry_name': item['title'],
                  });
                  _createNewSession(item['type']);
                },
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFFF0F9FF),
                    border: Border.all(color: const Color(0xFFE0F2FE)),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  padding: const EdgeInsets.all(8),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(item['icon'], color: item['color'], size: 26),
                      const SizedBox(height: 4),
                      Text(
                        item['title'],
                        style: const TextStyle(fontSize: 12, color: Color(0xFF0F172A)),
                        textAlign: TextAlign.center,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSessionCard(ChatSession session) {
    return GestureDetector(
      onTap: () {
        final chatProvider = Provider.of<ChatProvider>(context, listen: false);
        chatProvider.setCurrentSession(session);
        chatProvider.loadMessages(session.id);
        Navigator.pushNamed(context, '/chat');
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: const Color(0xFF52C41A).withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(Icons.chat, color: Color(0xFF52C41A), size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        session.title ?? session.typeLabel,
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                      ),
                      Text(
                        session.lastMessageTime ?? '',
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    session.lastMessage ?? '暂无消息',
                    style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
          ],
        ),
      ),
    );
  }
}
