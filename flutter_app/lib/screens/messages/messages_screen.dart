import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class MessagesScreen extends StatefulWidget {
  const MessagesScreen({super.key});

  @override
  State<MessagesScreen> createState() => _MessagesScreenState();
}

class _MessagesScreenState extends State<MessagesScreen> {
  final ApiService _apiService = ApiService();
  final ScrollController _scrollController = ScrollController();

  List<Map<String, dynamic>> _messages = [];
  bool _loading = true;
  bool _loadingMore = false;
  int _page = 1;
  int _total = 0;
  static const int _pageSize = 20;

  @override
  void initState() {
    super.initState();
    _loadMessages();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 200) {
      _loadMore();
    }
  }

  Future<void> _loadMessages() async {
    setState(() {
      _loading = true;
      _page = 1;
    });
    try {
      final response = await _apiService.getMessages(page: 1, pageSize: _pageSize);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic>
            ? response.data as Map<String, dynamic>
            : <String, dynamic>{};
        final items = data['items'] as List? ?? [];
        setState(() {
          _messages = items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          _total = data['total'] ?? 0;
          _loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadMore() async {
    if (_loadingMore || _messages.length >= _total) return;
    setState(() => _loadingMore = true);
    try {
      final nextPage = _page + 1;
      final response = await _apiService.getMessages(page: nextPage, pageSize: _pageSize);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic>
            ? response.data as Map<String, dynamic>
            : <String, dynamic>{};
        final items = data['items'] as List? ?? [];
        setState(() {
          _messages.addAll(items.map((e) => Map<String, dynamic>.from(e as Map)));
          _total = data['total'] ?? _total;
          _page = nextPage;
          _loadingMore = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  Future<void> _markRead(Map<String, dynamic> msg) async {
    final id = msg['id'] as int?;
    if (id == null) return;
    if (msg['is_read'] == true) return;
    try {
      await _apiService.markMessageRead(id);
      if (mounted) {
        setState(() {
          msg['is_read'] = true;
          msg['read_at'] = DateTime.now().toIso8601String();
        });
      }
    } catch (_) {}
  }

  Future<void> _markAllRead() async {
    try {
      await _apiService.markAllMessagesRead();
      if (mounted) {
        setState(() {
          for (final msg in _messages) {
            msg['is_read'] = true;
          }
        });
      }
    } catch (_) {}
  }

  void _handleMessageTap(Map<String, dynamic> msg) {
    _markRead(msg);

    final clickAction = msg['click_action']?.toString() ?? '';
    final messageType = msg['message_type']?.toString() ?? '';
    final clickParams = msg['click_action_params'];

    if (clickAction == '/family-bindlist' ||
        messageType == 'family_invite_accepted' ||
        messageType == 'family_auth_granted') {
      Navigator.pushNamed(context, '/family-bindlist');
      return;
    }

    if (messageType == 'family_invite_rejected' ||
        messageType == 'family_auth_rejected') {
      _showRejectedDetail(msg);
      return;
    }

    if (clickAction.isNotEmpty) {
      if (clickParams is Map) {
        Navigator.pushNamed(context, clickAction, arguments: clickParams);
      } else {
        Navigator.pushNamed(context, clickAction);
      }
      return;
    }

    _showMessageDetail(msg);
  }

  void _showRejectedDetail(Map<String, dynamic> msg) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.info_outline, color: Color(0xFFFA8C16), size: 24),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    msg['title']?.toString() ?? '消息详情',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(ctx),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              msg['content']?.toString() ?? '',
              style: TextStyle(fontSize: 15, color: Colors.grey[700]),
            ),
            const SizedBox(height: 8),
            if (msg['sender_nickname'] != null)
              Text(
                '来自：${msg['sender_nickname']}',
                style: TextStyle(fontSize: 13, color: Colors.grey[500]),
              ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  Navigator.pushNamed(context, '/family');
                },
                child: const Text('重新邀请'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  void _showMessageDetail(Map<String, dynamic> msg) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    msg['title']?.toString() ?? '消息详情',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(ctx),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              msg['content']?.toString() ?? '',
              style: TextStyle(fontSize: 15, color: Colors.grey[700]),
            ),
            const SizedBox(height: 8),
            Text(
              _formatTime(msg['created_at']?.toString()),
              style: TextStyle(fontSize: 12, color: Colors.grey[400]),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  IconData _getMessageIcon(String type) {
    switch (type) {
      case 'family_invite':
      case 'family_invite_accepted':
      case 'family_invite_rejected':
      case 'family_auth_granted':
      case 'family_auth_rejected':
        return Icons.people;
      case 'health_alert':
        return Icons.warning_amber;
      case 'medication_remind':
        return Icons.medication;
      case 'system':
        return Icons.campaign;
      default:
        return Icons.notifications;
    }
  }

  Color _getMessageColor(String type) {
    switch (type) {
      case 'family_invite':
      case 'family_invite_accepted':
      case 'family_auth_granted':
        return const Color(0xFF52C41A);
      case 'family_invite_rejected':
      case 'family_auth_rejected':
        return const Color(0xFFFA8C16);
      case 'health_alert':
        return const Color(0xFFFF4D4F);
      case 'medication_remind':
        return const Color(0xFF1890FF);
      default:
        return const Color(0xFF999999);
    }
  }

  String _formatTime(String? isoTime) {
    if (isoTime == null || isoTime.isEmpty) return '';
    try {
      final dt = DateTime.parse(isoTime);
      final now = DateTime.now();
      final diff = now.difference(dt);
      if (diff.inMinutes < 1) return '刚刚';
      if (diff.inHours < 1) return '${diff.inMinutes}分钟前';
      if (diff.inDays < 1) return '${diff.inHours}小时前';
      if (diff.inDays < 7) return '${diff.inDays}天前';
      return '${dt.month}/${dt.day}';
    } catch (_) {
      return '';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('消息'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        actions: [
          TextButton(
            onPressed: _markAllRead,
            child: const Text('全部已读', style: TextStyle(color: Colors.white, fontSize: 14)),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _messages.isEmpty
              ? _buildEmpty()
              : RefreshIndicator(
                  onRefresh: _loadMessages,
                  color: const Color(0xFF52C41A),
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: _messages.length + (_loadingMore ? 1 : 0),
                    itemBuilder: (context, index) {
                      if (index == _messages.length) {
                        return const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(
                            child: SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A)),
                            ),
                          ),
                        );
                      }
                      return _buildMessageItem(_messages[index]);
                    },
                  ),
                ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.notifications_none, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text('暂无消息', style: TextStyle(fontSize: 16, color: Colors.grey[400])),
        ],
      ),
    );
  }

  Widget _buildMessageItem(Map<String, dynamic> msg) {
    final isRead = msg['is_read'] == true;
    final type = msg['message_type']?.toString() ?? '';
    final icon = _getMessageIcon(type);
    final color = _getMessageColor(type);

    return InkWell(
      onTap: () => _handleMessageTap(msg),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isRead ? Colors.white : const Color(0xFFF6FFED),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isRead ? Colors.grey.withOpacity(0.1) : const Color(0xFF52C41A).withOpacity(0.2),
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 20),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          msg['title']?.toString() ?? '',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: isRead ? FontWeight.normal : FontWeight.w600,
                            color: const Color(0xFF333333),
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (!isRead)
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(
                            color: Color(0xFFFF4D4F),
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    msg['content']?.toString() ?? '',
                    style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _formatTime(msg['created_at']?.toString()),
                    style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
