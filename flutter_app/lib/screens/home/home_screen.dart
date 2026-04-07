import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../models/article.dart';
import '../../services/api_service.dart';
import '../../widgets/article_card.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final PageController _bannerController = PageController();
  int _currentBanner = 0;
  final List<Map<String, dynamic>> _banners = [
    {'title': 'AI健康咨询', 'subtitle': '足不出户，在线咨询', 'color': const Color(0xFF52C41A)},
    {'title': '中医体质辨识', 'subtitle': '了解体质，养生有方', 'color': const Color(0xFF13C2C2)},
    {'title': '家庭健康管理', 'subtitle': '全家健康，一手掌握', 'color': const Color(0xFF1890FF)},
  ];

  final List<Map<String, dynamic>> _features = [
    {'icon': Icons.smart_toy, 'label': 'AI咨询', 'route': '/ai', 'color': const Color(0xFF52C41A)},
    {'icon': Icons.assignment, 'label': '体检报告', 'route': '/checkup', 'color': const Color(0xFF1890FF)},
    {'icon': Icons.search, 'label': '症状自查', 'route': '/symptom', 'color': const Color(0xFFFA8C16)},
    {'icon': Icons.spa, 'label': '中医辨证', 'route': '/tcm', 'color': const Color(0xFF722ED1)},
    {'icon': Icons.medication, 'label': '用药参考', 'route': '/drug', 'color': const Color(0xFFEB2F96)},
    {'icon': Icons.calendar_today, 'label': '健康计划', 'route': '/health-plan', 'color': const Color(0xFF13C2C2)},
  ];

  final List<Article> _articles = [
    Article(id: '1', title: '春季养生：如何预防过敏性鼻炎', summary: '春季是过敏性鼻炎的高发季节，了解预防措施...', author: '健康专家', viewCount: 2345),
    Article(id: '2', title: '每天走一万步真的健康吗？', summary: '运动量因人而异，科学运动更重要...', author: '运动医学', viewCount: 1892),
    Article(id: '3', title: '中医教你看舌象辨健康', summary: '舌诊是中医四诊之一，通过舌象可以了解...', author: '中医养生', viewCount: 3210),
  ];

  @override
  void dispose() {
    _bannerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 0,
            floating: true,
            pinned: true,
            backgroundColor: const Color(0xFF52C41A),
            title: GestureDetector(
              onTap: () {},
              child: Container(
                height: 38,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(19),
                ),
                child: Row(
                  children: [
                    const SizedBox(width: 14),
                    Icon(Icons.search, color: Colors.white.withOpacity(0.8), size: 20),
                    const SizedBox(width: 8),
                    Text(
                      '搜索症状、疾病、药品',
                      style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                    ),
                  ],
                ),
              ),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.notifications_outlined, color: Colors.white),
                onPressed: () => Navigator.pushNamed(context, '/notifications'),
              ),
            ],
          ),
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildBanner(),
                const SizedBox(height: 20),
                _buildFeatureGrid(),
                const SizedBox(height: 20),
                _buildHealthTip(),
                const SizedBox(height: 20),
                _buildSectionHeader('健康知识', onMore: () => Navigator.pushNamed(context, '/articles')),
                const SizedBox(height: 8),
              ],
            ),
          ),
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) => ArticleCard(
                article: _articles[index],
                onTap: () => Navigator.pushNamed(context, '/article-detail', arguments: _articles[index].id),
              ),
              childCount: _articles.length,
            ),
          ),
          const SliverPadding(padding: EdgeInsets.only(bottom: 20)),
        ],
      ),
    );
  }

  Widget _buildBanner() {
    return Container(
      height: 160,
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          children: [
            PageView.builder(
              controller: _bannerController,
              itemCount: _banners.length,
              onPageChanged: (index) => setState(() => _currentBanner = index),
              itemBuilder: (context, index) {
                final banner = _banners[index];
                return Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        (banner['color'] as Color),
                        (banner['color'] as Color).withOpacity(0.7),
                      ],
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          banner['title'],
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 22,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          banner['subtitle'],
                          style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 14),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
            Positioned(
              bottom: 12,
              right: 16,
              child: Row(
                children: List.generate(
                  _banners.length,
                  (index) => Container(
                    width: _currentBanner == index ? 18 : 6,
                    height: 6,
                    margin: const EdgeInsets.only(left: 4),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      color: _currentBanner == index
                          ? Colors.white
                          : Colors.white.withOpacity(0.5),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureGrid() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 3,
          childAspectRatio: 1.1,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
        ),
        itemCount: _features.length,
        itemBuilder: (context, index) {
          final feature = _features[index];
          return GestureDetector(
            onTap: () => Navigator.pushNamed(context, feature['route']),
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.04),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: (feature['color'] as Color).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      feature['icon'],
                      color: feature['color'],
                      size: 24,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    feature['label'],
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildHealthTip() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF52C41A).withOpacity(0.08),
            const Color(0xFF13C2C2).withOpacity(0.08),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.lightbulb_outline, color: Color(0xFF52C41A), size: 22),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '今日健康提示',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                ),
                SizedBox(height: 4),
                Text(
                  '春季多饮水、早睡早起，适当进行户外运动有助于增强免疫力。',
                  style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, {VoidCallback? onMore}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          if (onMore != null)
            GestureDetector(
              onTap: onMore,
              child: Row(
                children: [
                  Text('查看更多', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                  Icon(Icons.chevron_right, size: 18, color: Colors.grey[500]),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
