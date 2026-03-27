import 'package:flutter/material.dart';
import '../../models/article.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/article_card.dart';

class ArticlesScreen extends StatefulWidget {
  const ArticlesScreen({super.key});

  @override
  State<ArticlesScreen> createState() => _ArticlesScreenState();
}

class _ArticlesScreenState extends State<ArticlesScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<String> _categories = ['推荐', '养生', '饮食', '运动', '心理', '中医'];

  final List<Article> _articles = [
    Article(id: '1', title: '春季养生：如何预防过敏性鼻炎', summary: '春季是过敏性鼻炎的高发季节，了解预防措施很重要', author: '健康专家', viewCount: 2345, category: '养生'),
    Article(id: '2', title: '每天走一万步真的健康吗？', summary: '运动量因人而异，科学运动更重要', author: '运动医学', viewCount: 1892, category: '运动'),
    Article(id: '3', title: '中医教你看舌象辨健康', summary: '舌诊是中医四诊之一，通过舌象可以了解身体状态', author: '中医养生', viewCount: 3210, category: '中医'),
    Article(id: '4', title: '地中海饮食：最健康的饮食方式', summary: '研究表明，地中海饮食有助于降低心血管疾病风险', author: '营养师', viewCount: 1560, category: '饮食'),
    Article(id: '5', title: '压力管理：职场人的心理健康指南', summary: '学会管理压力，保持心理健康', author: '心理咨询师', viewCount: 2100, category: '心理'),
    Article(id: '6', title: '秋冬进补：中医推荐的养生方', summary: '秋冬季节适当进补，增强体质', author: '中医养生', viewCount: 1780, category: '中医'),
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
        title: const Text('健康知识'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          tabs: _categories.map((c) => Tab(text: c)).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _categories.map((category) {
          final filtered = category == '推荐'
              ? _articles
              : _articles.where((a) => a.category == category).toList();
          return ListView.builder(
            padding: const EdgeInsets.symmetric(vertical: 12),
            itemCount: filtered.length,
            itemBuilder: (context, index) {
              return ArticleCard(
                article: filtered[index],
                onTap: () => Navigator.pushNamed(context, '/article-detail', arguments: filtered[index].id),
              );
            },
          );
        }).toList(),
      ),
    );
  }
}
