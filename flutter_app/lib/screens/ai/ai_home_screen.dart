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

class _AiHomeScreenState extends State<AiHomeScreen> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final ApiService _apiService = ApiService();

  // [PRD-425] AI 助手昵称（取 ai_chat.signature；为空时兜底"小康"），超 8 字截断
  String _aiSignature = '小康';
  // [PRD-425] 通知中心未读总数；-1=未加载/接口异常（不显示徽标）
  int _unreadCount = -1;

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
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<ChatProvider>(context, listen: false).loadSessions();
      _loadAiSignature();
      _loadUnreadCount();
    });
  }

  // [PRD-425] 加载 AI 助手昵称（ai_chat.signature）
  Future<void> _loadAiSignature() async {
    try {
      final resp = await _apiService.dio.get('/api/ai-home-config');
      final data = resp.data is Map ? resp.data['config'] ?? resp.data['data']?['config'] ?? resp.data : null;
      final sig = (data is Map ? data['ai_chat']?['signature'] : null)?.toString().trim() ?? '';
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
  Future<void> _loadUnreadCount() async {
    try {
      final resp = await _apiService.dio.get('/api/v1/notifications/unread-count');
      final cnt = resp.data is Map ? resp.data['data']?['unreadCount'] : null;
      if (!mounted) return;
      if (cnt is int && cnt >= 0) {
        setState(() => _unreadCount = cnt);
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
          IconButton(
            icon: const Icon(Icons.more_horiz),
            onPressed: () => _scaffoldKey.currentState?.openDrawer(),
          ),
        ],
      ),
      body: Consumer<ChatProvider>(
        builder: (context, chatProvider, child) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          color: Colors.white.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: const Icon(Icons.smart_toy, color: Colors.white, size: 32),
                      ),
                      const SizedBox(width: 16),
                      const Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '小康AI健康顾问',
                              style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                            ),
                            SizedBox(height: 4),
                            Text(
                              '24小时在线，智能分析您的健康问题',
                              style: TextStyle(color: Colors.white70, fontSize: 13),
                            ),
                          ],
                        ),
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
