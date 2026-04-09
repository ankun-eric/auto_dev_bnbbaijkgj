import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class SearchResultScreen extends StatefulWidget {
  const SearchResultScreen({super.key});

  @override
  State<SearchResultScreen> createState() => _SearchResultScreenState();
}

class _SearchResultScreenState extends State<SearchResultScreen> with SingleTickerProviderStateMixin {
  static const List<Map<String, String>> _tabs = [
    {'key': 'all', 'label': '全部'},
    {'key': 'article', 'label': '文章'},
    {'key': 'video', 'label': '视频'},
    {'key': 'service', 'label': '服务'},
    {'key': 'points_mall', 'label': '积分商品'},
  ];

  final TextEditingController _controller = TextEditingController();
  final ApiService _apiService = ApiService();
  late TabController _tabController;

  String _query = '';
  String _currentType = 'all';
  String _searchSource = 'text';
  int _page = 1;
  bool _loading = false;
  bool _hasMore = true;
  List<dynamic> _results = [];
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(_onTabChanged);
    _scrollController.addListener(_onScroll);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map) {
        _query = args['query']?.toString() ?? '';
        final raw = args['source']?.toString();
        _searchSource = raw == 'voice' ? 'voice' : 'text';
      } else if (args is String && args.isNotEmpty) {
        _query = args;
      }
      if (_query.isNotEmpty) {
        _controller.text = _query;
        _doSearch();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _tabController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (!_tabController.indexIsChanging) return;
    _currentType = _tabs[_tabController.index]['key']!;
    _page = 1;
    _hasMore = true;
    _results = [];
    _doSearch();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      _loadMore();
    }
  }

  Future<void> _doSearch() async {
    final q = _query.trim();
    if (q.isEmpty) return;
    setState(() {
      _loading = true;
      _page = 1;
      _hasMore = true;
    });

    try {
      final data = await _apiService.search(q: q, type: _currentType, page: 1, source: _searchSource);
      if (!mounted) return;
      final items = data['items'] ?? data['results'] ?? [];
      final total = data['total'] ?? 0;
      setState(() {
        _results = items is List ? items : [];
        _hasMore = _results.length < (total is int ? total : 0);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _results = [];
        _loading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (_loading || !_hasMore) return;
    setState(() => _loading = true);
    final nextPage = _page + 1;
    try {
      final data = await _apiService.search(q: _query, type: _currentType, page: nextPage, source: _searchSource);
      if (!mounted) return;
      final items = data['items'] ?? data['results'] ?? [];
      final total = data['total'] ?? 0;
      setState(() {
        if (items is List) _results.addAll(items);
        _page = nextPage;
        _hasMore = _results.length < (total is int ? total : 0);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _loading = false);
    }
  }

  void _onSubmit(String value) {
    _query = value.trim();
    if (_query.isEmpty) return;
    _doSearch();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF52C41A),
        titleSpacing: 0,
        title: _buildSearchBar(),
        actions: [
          TextButton(
            onPressed: () => _onSubmit(_controller.text),
            child: const Text('搜索', style: TextStyle(color: Colors.white, fontSize: 15)),
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontSize: 14),
          tabs: _tabs.map((t) => Tab(text: t['label'])).toList(),
        ),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildSearchBar() {
    return Container(
      height: 38,
      margin: const EdgeInsets.only(left: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(19),
      ),
      child: Row(
        children: [
          const SizedBox(width: 12),
          const Icon(Icons.search, color: Color(0xFF999999), size: 20),
          const SizedBox(width: 6),
          Expanded(
            child: TextField(
              controller: _controller,
              textInputAction: TextInputAction.search,
              onSubmitted: _onSubmit,
              decoration: const InputDecoration(
                hintText: '搜索症状、疾病、药品',
                hintStyle: TextStyle(color: Color(0xFF999999), fontSize: 14),
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.symmetric(vertical: 8),
              ),
              style: const TextStyle(fontSize: 14),
            ),
          ),
          if (_controller.text.isNotEmpty)
            GestureDetector(
              onTap: () => _controller.clear(),
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 8),
                child: Icon(Icons.close, size: 18, color: Color(0xFF999999)),
              ),
            ),
          const SizedBox(width: 4),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading && _results.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_results.isEmpty) {
      return _buildEmpty();
    }
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: _results.length + (_hasMore ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _results.length) {
          return const Padding(
            padding: EdgeInsets.all(16),
            child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A))),
          );
        }
        return _buildResultItem(_results[index]);
      },
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.search_off, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text(
            _query.isEmpty ? '请输入搜索关键词' : '未找到相关结果',
            style: TextStyle(fontSize: 15, color: Colors.grey[500]),
          ),
          if (_query.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('换个关键词试试吧', style: TextStyle(fontSize: 13, color: Colors.grey[400])),
          ],
        ],
      ),
    );
  }

  Widget _buildResultItem(dynamic item) {
    if (item is! Map) return const SizedBox.shrink();
    final title = item['title']?.toString() ?? '';
    final summary = item['summary']?.toString() ?? item['description']?.toString() ?? '';
    final type = item['type']?.toString() ?? '';
    final imageUrl = item['cover_image']?.toString() ?? item['image_url']?.toString() ?? '';

    return InkWell(
      onTap: () => _onResultTap(item),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: Color(0xFFF0F0F0))),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (type.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          margin: const EdgeInsets.only(right: 6),
                          decoration: BoxDecoration(
                            color: _typeColor(type).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            _typeLabel(type),
                            style: TextStyle(fontSize: 11, color: _typeColor(type)),
                          ),
                        ),
                      Expanded(
                        child: Text(
                          title,
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: Color(0xFF333333)),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  if (summary.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      summary,
                      style: const TextStyle(fontSize: 13, color: Color(0xFF999999), height: 1.4),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ],
              ),
            ),
            if (imageUrl.isNotEmpty) ...[
              const SizedBox(width: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  imageUrl,
                  width: 80,
                  height: 60,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    width: 80,
                    height: 60,
                    color: const Color(0xFFF5F5F5),
                    child: const Icon(Icons.image, color: Color(0xFFCCCCCC)),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _onResultTap(Map item) {
    final type = item['type']?.toString() ?? '';
    final id = item['id']?.toString() ?? '';
    switch (type) {
      case 'article':
        Navigator.pushNamed(context, '/article-detail', arguments: id);
        break;
      case 'service':
        Navigator.pushNamed(context, '/service-detail', arguments: id);
        break;
      case 'points_mall':
        Navigator.pushNamed(context, '/points-mall');
        break;
      default:
        if (id.isNotEmpty) {
          Navigator.pushNamed(context, '/article-detail', arguments: id);
        }
    }
  }

  Color _typeColor(String type) {
    switch (type) {
      case 'article':
        return const Color(0xFF1890FF);
      case 'video':
        return const Color(0xFFFA541C);
      case 'service':
        return const Color(0xFF52C41A);
      case 'points_mall':
        return const Color(0xFFFA8C16);
      default:
        return const Color(0xFF999999);
    }
  }

  String _typeLabel(String type) {
    switch (type) {
      case 'article':
        return '文章';
      case 'video':
        return '视频';
      case 'service':
        return '服务';
      case 'points_mall':
        return '积分商品';
      default:
        return type;
    }
  }
}
