import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/chat_provider.dart';
import '../models/chat_session.dart';

class ChatHistoryDrawer extends StatefulWidget {
  final VoidCallback? onNewChat;
  final void Function(ChatSession session)? onSessionTap;

  const ChatHistoryDrawer({
    super.key,
    this.onNewChat,
    this.onSessionTap,
  });

  @override
  State<ChatHistoryDrawer> createState() => _ChatHistoryDrawerState();
}

class _ChatHistoryDrawerState extends State<ChatHistoryDrawer> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<ChatProvider>(context, listen: false).loadSessionsFromHistory();
    });
  }

  String _getTypeLabel(String type) {
    switch (type) {
      case 'health_qa':
      case 'general':
        return '问答';
      case 'symptom_check':
      case 'pediatric':
        return '自查';
      case 'tcm':
      case 'gynecology':
        return '养生';
      case 'drug_query':
      case 'drug':
      case 'drug_identify':
        return '用药参考';
      default:
        return 'AI';
    }
  }

  Color _getTypeColor(String type) {
    switch (type) {
      case 'health_qa':
      case 'general':
        return const Color(0xFF52C41A);
      case 'symptom_check':
      case 'pediatric':
        return const Color(0xFF1890FF);
      case 'tcm':
      case 'gynecology':
        return const Color(0xFFEB2F96);
      case 'drug_query':
      case 'drug':
      case 'drug_identify':
        return const Color(0xFF722ED1);
      case 'constitution':
        return const Color(0xFFEB2F96);
      default:
        return const Color(0xFF52C41A);
    }
  }

  String _formatTime(String? dateStr) {
    if (dateStr == null) return '';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final diff = now.difference(date);
      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
      if (diff.inDays < 1) return '${diff.inHours}小时前';
      if (diff.inDays == 1) return '昨天';
      if (diff.inDays < 7) return '${diff.inDays}天前';
      return '${date.month}/${date.day}';
    } catch (_) {
      return '';
    }
  }

  String _getGroupLabel(String? dateStr) {
    if (dateStr == null) return '更早';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final sessionDay = DateTime(date.year, date.month, date.day);
      final diff = today.difference(sessionDay).inDays;
      if (diff == 0) return '今天';
      if (diff == 1) return '昨天';
      if (diff <= 7) return '近7天';
      if (diff <= 30) return '近30天';
      return '更早';
    } catch (_) {
      return '更早';
    }
  }

  Map<String, List<ChatSession>> _groupSessions(List<ChatSession> sessions) {
    final pinned = sessions.where((s) => s.isPinned).toList();
    final unpinned = sessions.where((s) => !s.isPinned).toList();

    final groups = <String, List<ChatSession>>{};

    if (pinned.isNotEmpty) {
      groups['置顶'] = pinned;
    }

    final orderedKeys = ['今天', '昨天', '近7天', '近30天', '更早'];
    for (final session in unpinned) {
      final key = _getGroupLabel(session.updatedAt ?? session.createdAt);
      groups.putIfAbsent(key, () => []);
      groups[key]!.add(session);
    }

    final result = <String, List<ChatSession>>{};
    if (groups.containsKey('置顶')) result['置顶'] = groups['置顶']!;
    for (final key in orderedKeys) {
      if (groups.containsKey(key)) result[key] = groups[key]!;
    }
    return result;
  }

  void _showActionSheet(ChatSession session) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 36,
                height: 4,
                margin: const EdgeInsets.only(bottom: 12),
                decoration: BoxDecoration(
                  color: Colors.grey[300],
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: Text(
                  session.title ?? session.typeLabel,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.edit_outlined, color: Color(0xFF333333)),
                title: const Text('重命名'),
                onTap: () {
                  Navigator.pop(ctx);
                  _showRenameDialog(session);
                },
              ),
              ListTile(
                leading: Icon(
                  session.isPinned ? Icons.push_pin : Icons.push_pin_outlined,
                  color: const Color(0xFF333333),
                ),
                title: Text(session.isPinned ? '取消置顶' : '置顶'),
                onTap: () {
                  Navigator.pop(ctx);
                  _togglePin(session);
                },
              ),
              ListTile(
                leading: const Icon(Icons.share_outlined, color: Color(0xFF333333)),
                title: const Text('分享'),
                onTap: () {
                  Navigator.pop(ctx);
                  _shareSession(session);
                },
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.delete_outline, color: Colors.red),
                title: const Text('删除', style: TextStyle(color: Colors.red)),
                onTap: () {
                  Navigator.pop(ctx);
                  _showDeleteConfirm(session);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showRenameDialog(ChatSession session) {
    final controller = TextEditingController(text: session.title ?? '');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('重命名对话'),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: InputDecoration(
            hintText: '输入新的对话名称',
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消', style: TextStyle(color: Color(0xFF999999))),
          ),
          TextButton(
            onPressed: () async {
              final title = controller.text.trim();
              if (title.isEmpty) return;
              Navigator.pop(ctx);
              final provider = Provider.of<ChatProvider>(context, listen: false);
              final success = await provider.renameSession(session.id, title);
              if (mounted && success) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('重命名成功'), duration: Duration(seconds: 1)),
                );
              }
            },
            child: const Text('确定', style: TextStyle(color: Color(0xFF52C41A))),
          ),
        ],
      ),
    );
  }

  void _showDeleteConfirm(ChatSession session) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除对话'),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        content: const Text('确定要删除这条对话记录吗？删除后不可恢复。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('取消', style: TextStyle(color: Color(0xFF999999))),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final provider = Provider.of<ChatProvider>(context, listen: false);
              final success = await provider.deleteSession(session.id);
              if (mounted && success) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('已删除'), duration: Duration(seconds: 1)),
                );
              }
            },
            child: const Text('删除', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  void _togglePin(ChatSession session) async {
    final provider = Provider.of<ChatProvider>(context, listen: false);
    final success = await provider.pinSession(session.id, !session.isPinned);
    if (mounted && success) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(session.isPinned ? '已取消置顶' : '已置顶'),
          duration: const Duration(seconds: 1),
        ),
      );
    }
  }

  void _shareSession(ChatSession session) async {
    final provider = Provider.of<ChatProvider>(context, listen: false);
    final result = await provider.shareSession(session.id);
    if (!mounted) return;

    if (result != null && result['share_url'] != null) {
      final shareUrl = result['share_url'] as String;
      showModalBottomSheet(
        context: context,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
        ),
        builder: (ctx) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 36,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const Text('分享对话', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF5F7FA),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          shareUrl,
                          style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      GestureDetector(
                        onTap: () {
                          Clipboard.setData(ClipboardData(text: shareUrl));
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('链接已复制到剪贴板'), duration: Duration(seconds: 1)),
                          );
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: const Color(0xFF52C41A),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Text('复制', style: TextStyle(color: Colors.white, fontSize: 13)),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('获取分享链接失败'), duration: Duration(seconds: 2)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: Colors.white,
      child: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            const Divider(height: 1),
            Expanded(
              child: Consumer<ChatProvider>(
                builder: (context, provider, _) {
                  if (provider.isLoading) {
                    return const Center(
                      child: CircularProgressIndicator(color: Color(0xFF52C41A)),
                    );
                  }

                  if (provider.sessions.isEmpty) {
                    return Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.chat_bubble_outline, size: 48, color: Colors.grey[300]),
                          const SizedBox(height: 12),
                          Text('暂无对话记录', style: TextStyle(color: Colors.grey[500])),
                        ],
                      ),
                    );
                  }

                  final grouped = _groupSessions(provider.sessions);
                  return ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: grouped.entries.length,
                    itemBuilder: (context, index) {
                      final entry = grouped.entries.elementAt(index);
                      return _buildGroup(entry.key, entry.value, provider);
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text(
            '对话历史',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          GestureDetector(
            onTap: () {
              Navigator.pop(context);
              widget.onNewChat?.call();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFF52C41A),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.add, color: Colors.white, size: 16),
                  SizedBox(width: 4),
                  Text('新对话', style: TextStyle(color: Colors.white, fontSize: 13)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGroup(String label, List<ChatSession> sessions, ChatProvider provider) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          child: Row(
            children: [
              if (label == '置顶')
                const Icon(Icons.push_pin, size: 14, color: Color(0xFFFA8C16)),
              if (label == '置顶') const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: label == '置顶' ? const Color(0xFFFA8C16) : Colors.grey[500],
                ),
              ),
            ],
          ),
        ),
        ...sessions.map((session) => _buildSessionTile(session, provider)),
      ],
    );
  }

  Widget _buildSessionTile(ChatSession session, ChatProvider provider) {
    final isActive = provider.currentSession?.id == session.id;

    return GestureDetector(
      onTap: () {
        provider.setCurrentSession(session);
        provider.loadMessages(session.id);
        Navigator.pop(context);
        widget.onSessionTap?.call(session);
      },
      onLongPress: () => _showActionSheet(session),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFFF0F9EB) : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: _getTypeColor(session.type).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          _getTypeLabel(session.type),
                          style: TextStyle(fontSize: 10, color: _getTypeColor(session.type), fontWeight: FontWeight.w500),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          session.title ?? session.typeLabel,
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                            color: const Color(0xFF333333),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _formatTime(session.updatedAt ?? session.createdAt),
                    style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                  ),
                ],
              ),
            ),
            if (session.isPinned)
              Padding(
                padding: const EdgeInsets.only(left: 4),
                child: Icon(Icons.push_pin, size: 14, color: Colors.grey[400]),
              ),
          ],
        ),
      ),
    );
  }
}
