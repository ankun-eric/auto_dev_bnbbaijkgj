import 'package:flutter/material.dart';
import '../../models/product.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';

class ProductListScreen extends StatefulWidget {
  const ProductListScreen({super.key});

  @override
  State<ProductListScreen> createState() => _ProductListScreenState();
}

class _ProductListScreenState extends State<ProductListScreen> {
  final ApiService _api = ApiService();
  final ScrollController _scrollController = ScrollController();

  List<ProductCategory> _categories = [];
  List<Product> _products = [];
  int? _selectedCategoryId;
  int _page = 1;
  int _total = 0;
  bool _loading = true;
  bool _loadingMore = false;
  String _keyword = '';

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _loadProducts();
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >= _scrollController.position.maxScrollExtent - 200) {
      if (!_loadingMore && _products.length < _total) {
        _loadMore();
      }
    }
  }

  Future<void> _loadCategories() async {
    try {
      final res = await _api.getProductCategories();
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _categories = (data['items'] as List)
              .map((e) => ProductCategory.fromJson(e as Map<String, dynamic>))
              .toList();
        });
      }
    } catch (_) {}
  }

  Future<void> _loadProducts() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getProducts(
        categoryId: _selectedCategoryId,
        keyword: _keyword.isNotEmpty ? _keyword : null,
        page: 1,
      );
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _products = (data['items'] as List)
              .map((e) => Product.fromJson(e as Map<String, dynamic>))
              .toList();
          _total = data['total'] ?? 0;
          _page = 1;
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _loadMore() async {
    setState(() => _loadingMore = true);
    try {
      final res = await _api.getProducts(
        categoryId: _selectedCategoryId,
        keyword: _keyword.isNotEmpty ? _keyword : null,
        page: _page + 1,
      );
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _products.addAll((data['items'] as List)
              .map((e) => Product.fromJson(e as Map<String, dynamic>)));
          _page++;
        });
      }
    } catch (_) {}
    setState(() => _loadingMore = false);
  }

  void _onCategoryTap(int? categoryId) {
    setState(() => _selectedCategoryId = categoryId);
    _loadProducts();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('健康商品'),
        backgroundColor: const Color(0xFF52C41A),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: _showSearchDialog,
          ),
        ],
      ),
      body: Column(
        children: [
          _buildCategoryBar(),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
                : _products.isEmpty
                    ? _buildEmpty()
                    : RefreshIndicator(
                        onRefresh: _loadProducts,
                        color: const Color(0xFF52C41A),
                        child: GridView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.all(12),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            childAspectRatio: 0.68,
                            crossAxisSpacing: 10,
                            mainAxisSpacing: 10,
                          ),
                          itemCount: _products.length + (_loadingMore ? 1 : 0),
                          itemBuilder: (context, index) {
                            if (index == _products.length) {
                              return const Center(
                                child: Padding(
                                  padding: EdgeInsets.all(16),
                                  child: CircularProgressIndicator(color: Color(0xFF52C41A), strokeWidth: 2),
                                ),
                              );
                            }
                            return _buildProductCard(_products[index]);
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryBar() {
    return Container(
      height: 48,
      color: Colors.white,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8),
        children: [
          _buildCategoryChip('全部', null),
          ..._categories.map((c) => _buildCategoryChip(c.name, c.id)),
        ],
      ),
    );
  }

  Widget _buildCategoryChip(String label, int? id) {
    final selected = _selectedCategoryId == id;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        selectedColor: const Color(0xFF52C41A),
        labelStyle: TextStyle(
          color: selected ? Colors.white : Colors.black87,
          fontSize: 13,
        ),
        onSelected: (_) => _onCategoryTap(id),
      ),
    );
  }

  Widget _buildProductCard(Product product) {
    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/product-detail', arguments: product.id),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              child: AspectRatio(
                aspectRatio: 1,
                child: product.firstImage.isNotEmpty
                    ? Image.network(
                        product.firstImage,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _buildPlaceholder(),
                      )
                    : _buildPlaceholder(),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 8, 8, 4),
              child: Text(
                product.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  Text(
                    '¥${formatPrice(product.salePrice)}',
                    style: const TextStyle(
                      color: Color(0xFFFF4D4F),
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  if (product.originalPrice != null && product.originalPrice! > product.salePrice) ...[
                    const SizedBox(width: 4),
                    Text(
                      '¥${formatPrice(product.originalPrice)}',
                      style: TextStyle(
                        color: Colors.grey[400],
                        fontSize: 11,
                        decoration: TextDecoration.lineThrough,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 2, 8, 8),
              child: Text(
                '已售${product.salesCount}',
                style: TextStyle(fontSize: 11, color: Colors.grey[500]),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: const Center(
        child: Icon(Icons.shopping_bag_outlined, size: 40, color: Color(0xFF52C41A)),
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.shopping_bag_outlined, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 12),
          Text('暂无商品', style: TextStyle(color: Colors.grey[500])),
        ],
      ),
    );
  }

  void _showSearchDialog() {
    final controller = TextEditingController(text: _keyword);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('搜索商品'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(hintText: '输入商品名称'),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              setState(() => _keyword = '');
              _loadProducts();
            },
            child: const Text('清除'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              setState(() => _keyword = controller.text.trim());
              _loadProducts();
            },
            child: const Text('搜索'),
          ),
        ],
      ),
    );
  }
}
