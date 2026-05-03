import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';

class _Category {
  final String id;
  final String name;
  final String? icon;
  final int? parentId;
  final bool isVirtual;
  final List<_Category> children;
  _Category({
    required this.id,
    required this.name,
    this.icon,
    this.parentId,
    this.isVirtual = false,
    this.children = const [],
  });
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
  final String? fulfillmentType;
  final String? sellingPoint;
  final String? categoryName;
  final int? categoryId;
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
    this.fulfillmentType,
    this.sellingPoint,
    this.categoryName,
    this.categoryId,
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
      salesCount: json['sales_count'] is int
          ? json['sales_count']
          : (int.tryParse('${json['sales_count'] ?? 0}') ?? 0),
      fulfillmentType: json['fulfillment_type']?.toString(),
      sellingPoint: json['selling_point']?.toString(),
      categoryName: json['category_name']?.toString(),
      categoryId: json['category_id'] is int
          ? json['category_id']
          : int.tryParse('${json['category_id'] ?? ''}'),
    );
  }
}

class ServicesScreen extends StatefulWidget {
  const ServicesScreen({super.key});

  @override
  State<ServicesScreen> createState() => _ServicesScreenState();
}

class _ServicesScreenState extends State<ServicesScreen> with TickerProviderStateMixin {
  List<_Category> _categories = [];
  int _selectedCategoryIndex = 0;
  bool _initialLoading = true;

  List<_Product> _currentProducts = [];
  bool _productsLoading = false;

  TabController? _subTabController;
  List<_Category> _currentChildren = [];

  final ScrollController _productScrollController = ScrollController();
  final Map<int, GlobalKey> _sectionKeys = {};
  bool _isProgrammaticScroll = false;

  static const Color _themeColor = Color(0xFF52C41A);
  static const Color _priceColor = Color(0xFFFF6B35);

  @override
  void initState() {
    super.initState();
    _productScrollController.addListener(_onProductScroll);
    _loadCategories();
  }

  @override
  void dispose() {
    _productScrollController.removeListener(_onProductScroll);
    _productScrollController.dispose();
    _subTabController?.dispose();
    super.dispose();
  }

  Future<void> _loadCategories() async {
    try {
      final res = await ApiService().getProductCategories();
      final data = res.data is Map ? res.data as Map : {};
      final items = (data['items'] as List? ?? []).map((c) {
        final childrenRaw = c['children'] as List? ?? [];
        final children = childrenRaw
            .map((ch) => _Category(
                  id: '${ch['id']}',
                  name: ch['name']?.toString() ?? '',
                  icon: ch['icon']?.toString(),
                  parentId: ch['parent_id'] is int ? ch['parent_id'] : null,
                ))
            .toList();
        return _Category(
          id: '${c['id']}',
          name: c['name']?.toString() ?? '',
          icon: c['icon']?.toString(),
          parentId: c['parent_id'] is int ? c['parent_id'] : null,
          isVirtual: c['is_virtual'] == true,
          children: children,
        );
      }).toList();
      if (!mounted) return;
      setState(() {
        _categories = items;
        _initialLoading = false;
      });
      if (items.isNotEmpty) {
        _selectCategory(0);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _categories = [];
        _initialLoading = false;
      });
    }
  }

  void _selectCategory(int index) {
    if (index < 0 || index >= _categories.length) return;
    final cat = _categories[index];
    setState(() {
      _selectedCategoryIndex = index;
      _currentProducts = [];
      _productsLoading = true;
      _sectionKeys.clear();
    });
    _setupSubTabs(cat.children);
    _loadProductsForCategory(cat);
  }

  void _setupSubTabs(List<_Category> children) {
    _subTabController?.dispose();
    final allTab = _Category(id: 'all', name: '全部');
    _currentChildren = [allTab, ...children];
    _subTabController = TabController(length: _currentChildren.length, vsync: this);
    _subTabController!.addListener(_onSubTabChanged);
  }

  void _onSubTabChanged() {
    if (_subTabController == null || _subTabController!.indexIsChanging) return;
    _scrollToSection(_subTabController!.index);
  }

  Future<void> _loadProductsForCategory(_Category cat) async {
    try {
      late final dynamic res;
      if (cat.id == 'recommend' || cat.isVirtual) {
        res = await ApiService().getProductsByStringCategory(
          categoryId: cat.id,
          page: 1,
          pageSize: 100,
        );
      } else {
        final intId = int.tryParse(cat.id);
        if (intId != null) {
          res = await ApiService().getProductsByParentCategory(
            parentCategoryId: intId,
            page: 1,
            pageSize: 100,
          );
        } else {
          res = await ApiService().getProductsByStringCategory(
            categoryId: cat.id,
            page: 1,
            pageSize: 100,
          );
        }
      }
      final data = res.data is Map ? res.data as Map : {};
      final List items = data['items'] as List? ?? [];
      final list = items
          .map((e) => _Product.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList();
      if (!mounted) return;
      setState(() {
        _currentProducts = list;
        _productsLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _currentProducts = [];
        _productsLoading = false;
      });
    }
  }

  Map<String, List<_Product>> get _groupedProducts {
    final map = <String, List<_Product>>{};
    for (final p in _currentProducts) {
      final key = p.categoryId?.toString() ?? 'unknown';
      map.putIfAbsent(key, () => []).add(p);
    }
    return map;
  }

  List<_SectionData> get _sections {
    final grouped = _groupedProducts;
    final cat = _categories[_selectedCategoryIndex];
    final sections = <_SectionData>[];

    if (cat.children.isEmpty) {
      sections.add(_SectionData(
        categoryId: 'all',
        categoryName: '全部',
        products: _currentProducts,
      ));
    } else {
      final ungrouped = <_Product>[];
      for (final child in cat.children) {
        final products = grouped[child.id] ?? [];
        if (products.isNotEmpty) {
          sections.add(_SectionData(
            categoryId: child.id,
            categoryName: child.name,
            products: products,
          ));
        }
      }
      for (final entry in grouped.entries) {
        final isChild = cat.children.any((c) => c.id == entry.key);
        if (!isChild) {
          ungrouped.addAll(entry.value);
        }
      }
      if (ungrouped.isNotEmpty) {
        sections.insert(
          0,
          _SectionData(
            categoryId: 'other',
            categoryName: '其他',
            products: ungrouped,
          ),
        );
      }
    }
    return sections;
  }

  void _scrollToSection(int tabIndex) {
    if (tabIndex == 0) {
      _isProgrammaticScroll = true;
      _productScrollController
          .animateTo(0, duration: const Duration(milliseconds: 400), curve: Curves.easeInOut)
          .then((_) => _isProgrammaticScroll = false);
      return;
    }

    final sectionIndex = tabIndex - 1;
    final key = _sectionKeys[sectionIndex];
    if (key?.currentContext != null) {
      _isProgrammaticScroll = true;
      Scrollable.ensureVisible(
        key!.currentContext!,
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
        alignment: 0.0,
      ).then((_) => _isProgrammaticScroll = false);
    }
  }

  void _onProductScroll() {
    if (_isProgrammaticScroll || _subTabController == null) return;
    final sections = _sections;
    if (sections.isEmpty) return;

    final scrollOffset = _productScrollController.offset;
    int bestTabIndex = 0;

    for (int i = 0; i < sections.length; i++) {
      final key = _sectionKeys[i];
      if (key?.currentContext != null) {
        final box = key!.currentContext!.findRenderObject() as RenderBox?;
        if (box != null) {
          final position = box.localToGlobal(Offset.zero);
          if (position.dy <= 160) {
            final childIdx = _currentChildren.indexWhere((c) => c.id == sections[i].categoryId);
            if (childIdx >= 0) {
              bestTabIndex = childIdx;
            } else {
              bestTabIndex = i + 1;
            }
          }
        }
      }
    }

    if (scrollOffset <= 0) bestTabIndex = 0;

    if (_subTabController!.index != bestTabIndex &&
        bestTabIndex < _subTabController!.length) {
      _subTabController!.removeListener(_onSubTabChanged);
      _subTabController!.animateTo(bestTabIndex);
      _subTabController!.addListener(_onSubTabChanged);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_initialLoading) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('健康服务'),
          backgroundColor: _themeColor,
          centerTitle: true,
          automaticallyImplyLeading: false,
        ),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_categories.isEmpty) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('健康服务'),
          backgroundColor: _themeColor,
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
        floatingActionButton: _buildFab(),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('健康服务'),
        backgroundColor: _themeColor,
        centerTitle: true,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () => Navigator.pushNamed(context, '/search'),
          ),
        ],
      ),
      body: Row(
        children: [
          _buildLeftCategoryBar(),
          Expanded(child: _buildRightContent()),
        ],
      ),
      floatingActionButton: _buildFab(),
    );
  }

  Widget _buildFab() {
    return FloatingActionButton.extended(
      onPressed: () => Navigator.pushNamed(context, '/experts'),
      backgroundColor: _themeColor,
      icon: const Icon(Icons.person_search),
      label: const Text('找专家'),
    );
  }

  Widget _buildLeftCategoryBar() {
    return Container(
      width: 88,
      color: const Color(0xFFF5F5F5),
      child: ListView.builder(
        padding: EdgeInsets.zero,
        itemCount: _categories.length,
        itemBuilder: (context, index) {
          final cat = _categories[index];
          final selected = index == _selectedCategoryIndex;
          return GestureDetector(
            onTap: () => _selectCategory(index),
            child: Container(
              decoration: BoxDecoration(
                color: selected ? Colors.white : const Color(0xFFF5F5F5),
                border: Border(
                  left: BorderSide(
                    color: selected ? _themeColor : Colors.transparent,
                    width: 3,
                  ),
                ),
              ),
              padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 8),
              child: Text(
                cat.isVirtual ? '${cat.icon ?? "🔥"} ${cat.name}' : cat.name,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                  color: selected ? _themeColor : const Color(0xFF666666),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildRightContent() {
    return Column(
      children: [
        _buildSubCategoryTabs(),
        Expanded(child: _buildProductList()),
      ],
    );
  }

  Widget _buildSubCategoryTabs() {
    if (_subTabController == null || _currentChildren.isEmpty) {
      return const SizedBox.shrink();
    }
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.06),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: TabBar(
        controller: _subTabController,
        isScrollable: true,
        labelColor: _themeColor,
        unselectedLabelColor: const Color(0xFF999999),
        labelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
        unselectedLabelStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.normal),
        indicatorColor: _themeColor,
        indicatorWeight: 2.5,
        indicatorSize: TabBarIndicatorSize.label,
        tabAlignment: TabAlignment.start,
        tabs: _currentChildren.map((c) => Tab(text: c.name)).toList(),
      ),
    );
  }

  Widget _buildProductList() {
    if (_productsLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_currentProducts.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.inventory_2_outlined, size: 60, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('暂无相关服务', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }

    final sections = _sections;
    _sectionKeys.clear();
    for (int i = 0; i < sections.length; i++) {
      _sectionKeys[i] = GlobalKey();
    }

    return RefreshIndicator(
      onRefresh: () async {
        final cat = _categories[_selectedCategoryIndex];
        setState(() => _productsLoading = true);
        await _loadProductsForCategory(cat);
      },
      child: ListView.builder(
        controller: _productScrollController,
        padding: const EdgeInsets.only(bottom: 80),
        itemCount: _countListItems(sections),
        itemBuilder: (context, index) => _buildListItem(sections, index),
      ),
    );
  }

  int _countListItems(List<_SectionData> sections) {
    int count = 0;
    for (final s in sections) {
      count += 1; // section header
      count += s.products.length;
    }
    return count;
  }

  Widget _buildListItem(List<_SectionData> sections, int index) {
    int offset = 0;
    for (int si = 0; si < sections.length; si++) {
      if (index == offset) {
        return _buildSectionHeader(sections[si], si);
      }
      offset++;
      final productIndex = index - offset;
      if (productIndex < sections[si].products.length) {
        return _buildProductCard(sections[si].products[productIndex]);
      }
      offset += sections[si].products.length;
    }
    return const SizedBox.shrink();
  }

  Widget _buildSectionHeader(_SectionData section, int sectionIndex) {
    return Container(
      key: _sectionKeys[sectionIndex],
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 16,
            decoration: BoxDecoration(
              color: _themeColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            section.categoryName,
            style: const TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w600,
              color: Color(0xFF333333),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProductCard(_Product p) {
    final cover = p.coverImage ?? (p.images.isNotEmpty ? p.images.first : null);
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/product-detail', arguments: p.id),
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
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
                width: 110,
                height: 100,
                color: const Color(0xFFE8F5E9),
                child: cover != null
                    ? Image.network(cover, fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) =>
                            const Center(child: Text('🏥', style: TextStyle(fontSize: 32))))
                    : const Center(child: Text('🏥', style: TextStyle(fontSize: 32))),
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      p.name,
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                    ),
                    if (p.sellingPoint != null && p.sellingPoint!.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        p.sellingPoint!,
                        style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ] else if (p.description != null && p.description!.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        p.description!,
                        style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.baseline,
                            textBaseline: TextBaseline.alphabetic,
                            children: [
                              Text(
                                '¥${formatPrice(p.minPrice ?? p.salePrice)}',
                                style: const TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.bold,
                                  color: _priceColor,
                                ),
                              ),
                              if (p.hasMultiSpec)
                                const Text(
                                  '起',
                                  style: TextStyle(fontSize: 11, color: _priceColor),
                                ),
                              if (p.marketPrice != null && p.marketPrice! > p.salePrice)
                                Padding(
                                  padding: const EdgeInsets.only(left: 4),
                                  child: Text(
                                    '¥${formatPrice(p.marketPrice)}',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.grey[400],
                                      decoration: TextDecoration.lineThrough,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        if (p.fulfillmentType != null && p.fulfillmentType!.isNotEmpty)
                          _buildFulfillmentBadge(p.fulfillmentType!),
                        if (p.fulfillmentType == null || p.fulfillmentType!.isEmpty)
                          Text(
                            '已售${p.salesCount}',
                            style: TextStyle(fontSize: 11, color: Colors.grey[400]),
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

  Widget _buildFulfillmentBadge(String type) {
    String label;
    Color bgColor;
    switch (type) {
      case 'in_store':
        label = '到店';
        bgColor = const Color(0xFFFF8A3D);
        break;
      case 'delivery':
        label = '快递';
        bgColor = const Color(0xFF3B82F6);
        break;
      case 'virtual':
        label = '虚拟';
        bgColor = const Color(0xFF8B5CF6);
        break;
      case 'on_site':
        label = '上门';
        bgColor = const Color(0xFF10B981);
        break;
      case 'to_store':
        label = '到店';
        bgColor = const Color(0xFF06B6D4);
        break;
      default:
        // 不再回显英文枚举原文，使用公共字典统一处理
        label = '其他';
        bgColor = Colors.grey;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.w500),
      ),
    );
  }
}

class _SectionData {
  final String categoryId;
  final String categoryName;
  final List<_Product> products;
  _SectionData({
    required this.categoryId,
    required this.categoryName,
    required this.products,
  });
}
