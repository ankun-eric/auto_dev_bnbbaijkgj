// PRD F2：文章详情页标题栏主题绿 + 评论区使用真实头像/昵称（后端 JOIN users）
import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

class ArticleDetailScreen extends StatefulWidget {
  const ArticleDetailScreen({super.key});

  @override
  State<ArticleDetailScreen> createState() => _ArticleDetailScreenState();
}

class _ArticleDetailScreenState extends State<ArticleDetailScreen> {
  final ApiService _api = ApiService();
  final TextEditingController _commentController = TextEditingController();
  bool _isCollected = false;
  int? _articleId;
  Map<String, dynamic>? _article;
  List<Map<String, dynamic>> _comments = [];
  bool _loading = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_articleId == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      int? id;
      if (args is int) id = args;
      if (args is String) id = int.tryParse(args);
      if (args is Map && args['id'] != null) id = int.tryParse('${args['id']}');
      _articleId = id;
      if (id != null) {
        _loadArticle();
        _loadComments();
      } else {
        setState(() => _loading = false);
      }
    }
  }

  @override
  void dispose() {
    _commentController.dispose();
    super.dispose();
  }

  Future<void> _loadArticle() async {
    try {
      final res = await _api.get('/api/content/articles/$_articleId');
      final data = res.data is Map ? Map<String, dynamic>.from(res.data as Map) : <String, dynamic>{};
      setState(() {
        _article = data;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _loadComments() async {
    try {
      final res = await _api.get(
        '/api/content/comments',
        query: {'content_type': 'article', 'content_id': _articleId},
      );
      final data = res.data is Map ? res.data as Map : {};
      final items = (data['items'] ?? []) as List;
      setState(() {
        _comments = items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
      });
    } catch (_) {
      setState(() => _comments = []);
    }
  }

  Future<void> _submitComment() async {
    final text = _commentController.text.trim();
    if (text.isEmpty || _articleId == null) return;
    try {
      await _api.post('/api/content/comments', data: {
        'content_type': 'article',
        'content_id': _articleId,
        'content': text,
      });
      _commentController.clear();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('评论成功'), backgroundColor: Color(0xFF4CAF50)),
        );
      }
      _loadComments();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('评论失败')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '文章详情',
        actions: [
          IconButton(
            icon: Icon(
              _isCollected ? Icons.bookmark : Icons.bookmark_border,
              color: Colors.white,
            ),
            onPressed: () => setState(() => _isCollected = !_isCollected),
          ),
          IconButton(
            icon: const Icon(Icons.share, color: Colors.white),
            onPressed: () {},
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50)))
          : (_article == null
              ? const Center(child: Text('文章不存在或已下架', style: TextStyle(color: Colors.grey)))
              : _buildBody()),
    );
  }

  Widget _buildBody() {
    final a = _article!;
    final title = a['title']?.toString() ?? '';
    final author = a['author_name']?.toString() ?? '';
    final time = (a['published_at'] ?? a['created_at'] ?? '').toString();
    final content = (a['content_html']?.toString().isNotEmpty == true
        ? _stripHtml(a['content_html'].toString())
        : (a['content']?.toString() ?? ''));
    final views = a['view_count'] ?? 0;
    return Column(
      children: [
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, height: 1.3)),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      decoration: BoxDecoration(
                        color: const Color(0xFF4CAF50).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: const Icon(Icons.person, color: Color(0xFF4CAF50), size: 18),
                    ),
                    const SizedBox(width: 8),
                    Text(author, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                    const SizedBox(width: 12),
                    Text(time.length >= 10 ? time.substring(0, 10) : time,
                        style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                    const Spacer(),
                    Icon(Icons.visibility, size: 16, color: Colors.grey[400]),
                    const SizedBox(width: 4),
                    Text('$views', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
                  ],
                ),
                const Divider(height: 32),
                Text(content, style: const TextStyle(fontSize: 16, height: 1.8, color: Color(0xFF333333))),
                const SizedBox(height: 24),
                Text('评论 (${_comments.length})',
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                if (_comments.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Text('暂无评论', style: TextStyle(color: Colors.grey)),
                  )
                else
                  ..._comments.map(_buildComment),
                const SizedBox(height: 20),
              ],
            ),
          ),
        ),
        Container(
          padding: EdgeInsets.only(
            left: 12, right: 12, top: 8,
            bottom: MediaQuery.of(context).padding.bottom + 8,
          ),
          decoration: BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 8, offset: const Offset(0, -2)),
            ],
          ),
          child: Row(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFFF5F7FA),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: TextField(
                    controller: _commentController,
                    decoration: const InputDecoration(
                      hintText: '说点什么...',
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    ),
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.send, color: Color(0xFF4CAF50)),
                onPressed: _submitComment,
              ),
            ],
          ),
        ),
      ],
    );
  }

  // PRD F2.2：优先使用 author_avatar / author_nick；空头像用默认灰色剪影占位
  Widget _buildComment(Map<String, dynamic> c) {
    final user = (c['author_nick'] ?? c['user_name'] ?? '用户').toString();
    final avatar = (c['author_avatar'] ?? c['user_avatar'] ?? '').toString();
    final content = c['content']?.toString() ?? '';
    final time = (c['created_at'] ?? '').toString().replaceAll('T', ' ');
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          avatar.isNotEmpty
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(18),
                  child: Image.network(
                    avatar, width: 36, height: 36, fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => _fallbackAvatar(user),
                  ),
                )
              : _fallbackAvatar(user),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(user, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    const Spacer(),
                    Text(time.length >= 10 ? time.substring(0, 10) : time,
                        style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                  ],
                ),
                const SizedBox(height: 4),
                Text(content, style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.4)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _fallbackAvatar(String name) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: const Color(0xFFE0E0E0),
        borderRadius: BorderRadius.circular(18),
      ),
      child: const Center(
        child: Icon(Icons.person, color: Colors.white, size: 20),
      ),
    );
  }

  String _stripHtml(String html) {
    var s = html;
    s = s.replaceAll(RegExp(r'</(p|div|h[1-6]|li|br)>', caseSensitive: false), '\n');
    s = s.replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), '\n');
    s = s.replaceAll(RegExp(r'<[^>]+>'), '');
    s = s.replaceAll('&nbsp;', ' ')
        .replaceAll('&amp;', '&')
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>');
    return s.trim();
  }
}
