import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class TemplateCategoriesScreen extends StatefulWidget {
  const TemplateCategoriesScreen({super.key});

  @override
  State<TemplateCategoriesScreen> createState() => _TemplateCategoriesScreenState();
}

class _TemplateCategoriesScreenState extends State<TemplateCategoriesScreen> {
  final ApiService _apiService = ApiService();
  bool _loading = true;
  List<Map<String, dynamic>> _categories = [];

  static const _categoryColors = [
    Color(0xFF52C41A),
    Color(0xFF1890FF),
    Color(0xFFFA8C16),
    Color(0xFF722ED1),
    Color(0xFFEB2F96),
    Color(0xFF13C2C2),
  ];

  static const _categoryIcons = [
    Icons.fitness_center,
    Icons.restaurant,
    Icons.bedtime,
    Icons.self_improvement,
    Icons.monitor_heart,
    Icons.spa,
  ];

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  Future<void> _loadCategories() async {
    try {
      final response = await _apiService.getTemplateCategories();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        List items = [];
        if (data is Map && data['items'] is List) {
          items = data['items'] as List;
        } else if (data is List) {
          items = data;
        }
        setState(() {
          _categories = items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          _loading = false;
        });
        return;
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('自定义计划'),
        backgroundColor: const Color(0xFF1890FF),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1890FF)))
          : _categories.isEmpty
              ? _buildEmpty()
              : RefreshIndicator(
                  color: const Color(0xFF1890FF),
                  onRefresh: _loadCategories,
                  child: GridView.builder(
                    padding: const EdgeInsets.all(16),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      childAspectRatio: 1.3,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                    ),
                    itemCount: _categories.length,
                    itemBuilder: (context, index) => _buildCategoryCard(_categories[index], index),
                  ),
                ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.category_outlined, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          Text('暂无计划分类', style: TextStyle(fontSize: 16, color: Colors.grey[400])),
        ],
      ),
    );
  }

  Widget _buildCategoryCard(Map<String, dynamic> cat, int index) {
    final color = _categoryColors[index % _categoryColors.length];
    final icon = _categoryIcons[index % _categoryIcons.length];

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/hp-category-detail', arguments: cat),
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [color, color.withOpacity(0.7)],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(color: color.withOpacity(0.3), blurRadius: 8, offset: const Offset(0, 4)),
          ],
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: Colors.white, size: 22),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  cat['name']?.toString() ?? '',
                  style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w600),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                if (cat['description'] != null)
                  Text(
                    cat['description'].toString(),
                    style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 12),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
