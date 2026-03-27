import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/chat_provider.dart';
import '../../models/chat_session.dart';

class AiHomeScreen extends StatefulWidget {
  const AiHomeScreen({super.key});

  @override
  State<AiHomeScreen> createState() => _AiHomeScreenState();
}

class _AiHomeScreenState extends State<AiHomeScreen> {
  final List<Map<String, dynamic>> _consultTypes = [
    {
      'type': 'general',
      'title': '综合问诊',
      'desc': '常见疾病症状咨询',
      'icon': Icons.medical_information,
      'color': const Color(0xFF52C41A),
    },
    {
      'type': 'pediatric',
      'title': '儿科问诊',
      'desc': '儿童健康问题咨询',
      'icon': Icons.child_care,
      'color': const Color(0xFF1890FF),
    },
    {
      'type': 'gynecology',
      'title': '妇科问诊',
      'desc': '女性健康问题咨询',
      'icon': Icons.female,
      'color': const Color(0xFFEB2F96),
    },
    {
      'type': 'tcm',
      'title': '中医问诊',
      'desc': '中医辨证施治咨询',
      'icon': Icons.spa,
      'color': const Color(0xFF722ED1),
    },
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<ChatProvider>(context, listen: false).loadSessions();
    });
  }

  void _createNewSession(String type) async {
    final chatProvider = Provider.of<ChatProvider>(context, listen: false);
    final session = await chatProvider.createSession(type);
    if (session != null && mounted) {
      Navigator.pushNamed(context, '/chat');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI问诊'),
        backgroundColor: const Color(0xFF52C41A),
        centerTitle: true,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            onPressed: () {},
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
                              '小康AI医生',
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
                  '选择问诊类型',
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
                        onPressed: () {},
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
                          Text('选择上方问诊类型开始对话', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
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
