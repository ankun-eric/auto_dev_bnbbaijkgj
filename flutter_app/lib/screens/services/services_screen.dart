import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';

class _Category {
  final String id;
  final String name;
  final String? icon;
  final int? parentId;
  final bool isVirtual;
  _Category({required this.id, required this.name, this.icon, this.parentId, this.isVirtual = false});
}

class _Product {
  final int id;
  final String name;
  final String? description;
  final double salePrice;
  final double? marketPrice;
  final String? coverImage;
  final List<String> images;
  final double? minPrice;
  final bool hasMultiSpec;
  final int salesCount;
  _Product({
    required this.id,
    required this.name,
    this.description,
    required this.salePrice,
    this.marketPrice,
    this.coverImage,
    this.images = const [],
    this.minPrice,
    this.hasMultiSpec = false,
    this.salesCount = 0,
  });

  factory _Product.fromJson(Map<String, dynamic> json) {
    return _Product(
      id: json['id'] is int ? json['id'] : int.tryParse('${json['id']}') ?? 0,
      name: json['name']?.toString() ?? '',
      description: json['description']?.toString(),
      salePrice: double.tryParse('${json['sale_price'] ?? 0}') ?? 0.0,
      marketPrice: json['market_price'] != null ? double.tryParse('${json['market_price']}') : null,
      minPrice: json['min_price'] != null ? double.tryParse('${json['min_price']}') : null,
      hasMultiSpec: json['has_multi_spec'] == true,
      coverImage: json['cover_image']?.toString(),
      images: (json['images'] is List)
          ? (json['images'] as List).map((e) => e.toString()).toList()
          : <String>[],
      salesCount: json['sales_count'] is int ? json['sales_count'] : (int.tryParse('${json['sales_count'] ?? 0}') ?? 0),
    );
  }
}

class ServicesScreen extends StatefulWidget {
  const ServicesScreen({super.key});

  @override
  State<ServicesScreen> createState() => _ServicesScreenState();
}

class _ServicesScreenState extends State<ServicesScreen> with TickerProviderStateMixin {
  TabController? _tabController;
  List<_Category> _categories = [];
  final Map<String, List<_Product>> _productsByCat = {};
  final Map<String, int> _pageByCat = {};
  final Map<String, bool> _hasMoreByCat = {};
  final Map<String, bool> _loadingByCat = {};
  bool _initialLoading = true;

  static const int pageSize = 10;

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  Future<void> _loadCategories() async {
    try {
      final res = await ApiService().getProductCategories();
      final data = res.data is Map ? res.data as Map : {};
      final items = (data['items'] as List? ?? [])
          .map((c) => _Category(
                id: '${c['id']}',
                name: c['name']?.toString() ?? '',
                icon: c['icon']?.toString(),
                parentId: c['parent_id'] is int ? c['parent_id'] : null,
                isVirtual: c['is_virtual'] == true,
              ))
          .toList();
      if (!mounted) return;
      setState(() {
        _categories = items;
        _tabController?.dispose();
        _tabController = TabController(length: items.length, vsync: this);
        _tabController!.addListener(_onTabChanged);
        _initialLoading = false;
      });
      if (items.isNotEmpty) {
        await _loadProducts(items.first.id, reset: true);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _categories = [];
        _initialLoading = false;
      });
    }
  }

  void _onTabChanged() {
    if (_tabController == null || _tabController!.indexIsChanging) return;
    final cat = _categories[_tabController!.index];
    if (!_productsByCat.containsKey(cat.id)) {
      _loadProducts(cat.id, reset: true);
    }
  }

  Future<void> _loadProducts(String categoryId, {bool reset = false}) async {
    if (_loadingByCat[categoryId] == true) return;
    _loadingByCat[categoryId] = true;
    final page = reset ? 1 : (_pageByCat[categoryId] ?? 1);
    try {
      final res = categoryId == 'recommend'
          ? await ApiService().getProductsByStringCategory(categoryId: categoryId, page: page, pageSize: pageSize)
          : await ApiService().getProducts(categoryId: int.tryParse(categoryId), page: page, pageSize: pageSize);
      final data = res.data is Map ? res.data as Map : {};
      final List items = data['items'] as List? ?? [];
      final list = items.map((e) => _Product.fromJson(Map<String, dynamic>.from(e as Map))).toList();
      final total = (data['total'] is int) ? data['total'] as int : int.tryParse('${data['total'] ?? 0}') ?? 0;
      if (!mounted) return;
      setState(() {
        if (reset) {
          _productsByCat[categoryId] = list;
        } else {
          _productsByCat[categoryId] = [...(_productsByCat[categoryId] ?? []), ...list];
        }
        _pageByCat[categoryId] = page + 1;
        _hasMoreByCat[categoryId] = page * pageSize < total;
      });
    } catch (_) {
      if (!mounted) return;
      if (reset) {
        setState(() {
          _productsByCat[categoryId] = [];
          _hasMoreByCat[categoryId] = false;
        });
      }
    } finally {
      _loadingByCat[categoryId] = false;
    }
  }

  @override
  void dispose() {
    _tabController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_initialLoading) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('健康服务'),
          backgroundColor: const Color(0xFF52C41A),
          centerTitle: true,
          automaticallyImplyLeading: false,
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_categories.isEmpty || _tabController == null) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('健康服务'),
          backgroundColor: const Color(0xFF52C41A),
          centerTitle: true,
          automaticallyImplyLeading: false,
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.search_off, size: 60, color: Colors.grey[300]),
              const SizedBox(height: 12),
              Text('暂无分类', style: TextStyle(color: Colors.grey[500])),
            ],
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () => Navigator.pushNamed(context, '/experts'),
          backgroundColor: const Color(0xFF52C41A),
          icon: const Icon(Icons.person_search),
          label: const Text('找专家'),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('健康服务'),
        backgroundColor: const Color(0xFF52C41A),
        centerTitle: true,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () => Navigator.pushNamed(context, '/search'),
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          labelStyle: const TextStyle(fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.normal),
          tabs: _categories.map((c) => Tab(
            text: c.isVirtual ? '${c.icon ?? "🔥"} ${c.name}' : c.name,
          )).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _categories.map((cat) {
          final products = _productsByCat[cat.id] ?? [];
          final hasMore = _hasMoreByCat[cat.id] ?? false;
          if (products.isEmpty && _loadingByCat[cat.id] == true) {
            return const Center(child: CircularProgressIndicator());
          }
          if (products.isEmpty) {
            return RefreshIndicator(
              onRefresh: () => _loadProducts(cat.id, reset: true),
              child: ListView(
                children: [
                  SizedBox(height: MediaQuery.of(context).size.height / 4),
                  Center(
                    child: Column(
                      children: [
                        Icon(Icons.inventory_2_outlined, size: 60, color: Colors.grey[300]),
                        const SizedBox(height: 12),
                        Text('暂无相关服务', style: TextStyle(color: Colors.grey[500])),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: () => _loadProducts(cat.id, reset: true),
            child: NotificationListener<ScrollNotification>(
              onNotification: (n) {
                if (n is ScrollEndNotification &&
                    n.metrics.pixels >= n.metrics.maxScrollExtent - 80 &&
                    hasMore &&
                    _loadingByCat[cat.id] != true) {
                  _loadProducts(cat.id);
                }
                return false;
              },
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(vertical: 12),
                itemCount: products.length + (hasMore ? 1 : 0),
                itemBuilder: (context, index) {
                  if (index >= products.length) {
                    return const Padding(
                      padding: EdgeInsets.all(12),
                      child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
                    );
                  }
                  final p = products[index];
                  return _buildProductCard(p, cat.icon);
                },
              ),
            ),
          );
        }).toList(),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.pushNamed(context, '/experts'),
        backgroundColor: const Color(0xFF52C41A),
        icon: const Icon(Icons.person_search),
        label: const Text('找专家'),
      ),
    );
  }

  Widget _buildProductCard(_Product p, String? catIcon) {
    final cover = p.coverImage ?? (p.images.isNotEmpty ? p.images.first : null);
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/product-detail', arguments: p.id),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.05),
              blurRadius: 10,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                bottomLeft: Radius.circular(12),
              ),
              child: Container(
                width: 120,
                height: 100,
                color: const Color(0xFFE8F5E9),
                child: cover != null
                    ? Image.network(cover, fit: BoxFit.cover, errorBuilder: (_, __, ___) {
                        return Center(child: Text(catIcon ?? '🏥', style: const TextStyle(fontSize: 32)));
                      })
                    : Center(child: Text(catIcon ?? '🏥', style: const TextStyle(fontSize: 32))),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p.name,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 4),
                    if (p.description != null && p.description!.isNotEmpty)
                      Text(
                        p.description!,
                        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.baseline,
                          textBaseline: TextBaseline.alphabetic,
                          children: [
                            Text(
                              '¥${formatPrice(p.minPrice ?? p.salePrice)}',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFFFF6B35),
                              ),
                            ),
                            if (p.hasMultiSpec)
                              const Text(
                                '起',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.normal,
                                  color: Color(0xFFFF6B35),
                                ),
                              ),
                            if (p.marketPrice != null && p.marketPrice! > p.salePrice)
                              Padding(
                                padding: const EdgeInsets.only(left: 4),
                                child: Text(
                                  '¥${formatPrice(p.marketPrice)}',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Colors.grey[400],
                                    decoration: TextDecoration.lineThrough,
                                  ),
                                ),
                              ),
                          ],
                        ),
                        Text(
                          '已售${p.salesCount}',
                          style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
