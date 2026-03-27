import 'package:flutter/material.dart';
import '../../models/service_item.dart';
import '../../widgets/service_card.dart';

class ServicesScreen extends StatefulWidget {
  const ServicesScreen({super.key});

  @override
  State<ServicesScreen> createState() => _ServicesScreenState();
}

class _ServicesScreenState extends State<ServicesScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  final List<String> _categories = ['全部', '体检套餐', '专家咨询', '中医理疗', '心理咨询', '营养指导'];

  final List<ServiceItem> _services = [
    ServiceItem(id: '1', name: '全面体检套餐', description: '涵盖血液、影像等多项检查', price: 599, salesCount: 1280, categoryName: '体检套餐'),
    ServiceItem(id: '2', name: '专家在线咨询', description: '三甲医院主任医师一对一', price: 199, salesCount: 860, categoryName: '专家咨询'),
    ServiceItem(id: '3', name: '中医推拿理疗', description: '传统中医手法，缓解疲劳', price: 298, salesCount: 520, categoryName: '中医理疗'),
    ServiceItem(id: '4', name: '心理健康咨询', description: '专业心理咨询师在线服务', price: 159, salesCount: 380, categoryName: '心理咨询'),
    ServiceItem(id: '5', name: '个性化营养方案', description: '根据体质定制专属营养方案', price: 99, salesCount: 720, categoryName: '营养指导'),
    ServiceItem(id: '6', name: '深度体检尊享套餐', description: '全面深度检查，VIP服务', price: 1299, originalPrice: 1599, salesCount: 320, categoryName: '体检套餐'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _categories.length, vsync: this);
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
        title: const Text('健康服务'),
        backgroundColor: const Color(0xFF52C41A),
        centerTitle: true,
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {},
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          labelStyle: const TextStyle(fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.normal),
          tabs: _categories.map((c) => Tab(text: c)).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _categories.map((category) {
          final filtered = category == '全部'
              ? _services
              : _services.where((s) => s.categoryName == category).toList();
          return filtered.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.search_off, size: 60, color: Colors.grey[300]),
                      const SizedBox(height: 12),
                      Text('暂无相关服务', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    return ServiceCard(
                      service: filtered[index],
                      onTap: () => Navigator.pushNamed(
                        context,
                        '/service-detail',
                        arguments: filtered[index].id,
                      ),
                    );
                  },
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
}
