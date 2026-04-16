import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});

  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<Map<String, String>> _tabs = [
    {'label': '商品', 'tab': 'product'},
    {'label': '知识', 'tab': 'knowledge'},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的收藏'),
        backgroundColor: const Color(0xFF52C41A),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          tabs: _tabs.map((t) => Tab(text: t['label'])).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _tabs.map((t) => _FavoriteTab(tab: t['tab']!)).toList(),
      ),
    );
  }
}

class _FavoriteTab extends StatefulWidget {
  final String tab;
  const _FavoriteTab({required this.tab});

  @override
  State<_FavoriteTab> createState() => _FavoriteTabState();
}

class _FavoriteTabState extends State<_FavoriteTab> with AutomaticKeepAliveClientMixin {
  final ApiService _api = ApiService();
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadFavorites();
  }

  Future<void> _loadFavorites() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getFavorites(tab: widget.tab);
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _items = (data['items'] as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _unfavorite(Map<String, dynamic> item) async {
    try {
      await _api.toggleFavorite(item['content_id'], item['content_type']);
      _loadFavorites();
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_items.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.favorite_border, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('暂无收藏', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadFavorites,
      color: const Color(0xFF52C41A),
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: _items.length,
        itemBuilder: (context, index) => _buildFavoriteCard(_items[index]),
      ),
    );
  }

  Widget _buildFavoriteCard(Map<String, dynamic> item) {
    final detail = item['detail'] as Map<String, dynamic>?;
    if (detail == null) {
      return const SizedBox.shrink();
    }

    final isProduct = item['content_type'] == 'product';

    return Dismissible(
      key: Key('fav_${item['id']}'),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        color: Colors.red,
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => _unfavorite(item),
      child: GestureDetector(
        onTap: () {
          if (isProduct) {
            Navigator.pushNamed(context, '/product-detail', arguments: detail['id']);
          }
        },
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(
                  width: 70,
                  height: 70,
                  child: _buildImage(detail, isProduct),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      isProduct ? (detail['name'] ?? '') : (detail['title'] ?? ''),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w500),
                    ),
                    if (isProduct && detail['sale_price'] != null) ...[
                      const SizedBox(height: 4),
                      Text('¥${detail['sale_price']}',
                          style: const TextStyle(color: Color(0xFFFF4D4F), fontWeight: FontWeight.bold)),
                    ],
                    if (!isProduct && detail['summary'] != null) ...[
                      const SizedBox(height: 4),
                      Text(detail['summary'], maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildImage(Map<String, dynamic> detail, bool isProduct) {
    String? imageUrl;
    if (isProduct) {
      final images = detail['images'];
      if (images is List && images.isNotEmpty) {
        imageUrl = images[0].toString();
      }
    } else {
      imageUrl = detail['cover_image']?.toString();
    }

    if (imageUrl != null && imageUrl.isNotEmpty) {
      return Image.network(imageUrl, fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => _placeholder(isProduct));
    }
    return _placeholder(isProduct);
  }

  Widget _placeholder(bool isProduct) {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: Icon(
        isProduct ? Icons.shopping_bag_outlined : Icons.article_outlined,
        color: const Color(0xFF52C41A),
        size: 28,
      ),
    );
  }
}
