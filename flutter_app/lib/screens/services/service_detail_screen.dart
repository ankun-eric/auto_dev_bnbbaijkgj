import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class ServiceDetailScreen extends StatefulWidget {
  const ServiceDetailScreen({super.key});

  @override
  State<ServiceDetailScreen> createState() => _ServiceDetailScreenState();
}

class _ServiceDetailScreenState extends State<ServiceDetailScreen> {
  final PageController _imageController = PageController();
  int _currentImage = 0;

  @override
  void dispose() {
    _imageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 250,
            pinned: true,
            backgroundColor: const Color(0xFF52C41A),
            leading: IconButton(
              icon: Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: Colors.black26,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Icon(Icons.arrow_back_ios_new, size: 16, color: Colors.white),
              ),
              onPressed: () => Navigator.pop(context),
            ),
            flexibleSpace: FlexibleSpaceBar(
              background: Stack(
                children: [
                  PageView.builder(
                    controller: _imageController,
                    onPageChanged: (i) => setState(() => _currentImage = i),
                    itemCount: 3,
                    itemBuilder: (context, index) {
                      return Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [
                              const Color(0xFF52C41A).withOpacity(0.3),
                              const Color(0xFF13C2C2).withOpacity(0.3),
                            ],
                          ),
                        ),
                        child: const Icon(Icons.medical_services, size: 80, color: Colors.white54),
                      );
                    },
                  ),
                  Positioned(
                    bottom: 12,
                    right: 16,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.black38,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${_currentImage + 1}/3',
                        style: const TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '全面体检套餐',
                        style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Text(
                            '¥599',
                            style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFFFF6B35)),
                          ),
                          const SizedBox(width: 12),
                          Text(
                            '¥899',
                            style: TextStyle(
                              fontSize: 16,
                              color: Colors.grey[400],
                              decoration: TextDecoration.lineThrough,
                            ),
                          ),
                          const Spacer(),
                          Text('已售1280', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        children: ['免费报告解读', '专家一对一', 'VIP通道'].map((tag) {
                          return Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: const Color(0xFF52C41A).withOpacity(0.1),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              tag,
                              style: const TextStyle(fontSize: 12, color: Color(0xFF52C41A)),
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('服务详情', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      _buildDetailItem('服务时长', '约2小时'),
                      _buildDetailItem('服务地点', '宾尼健康中心'),
                      _buildDetailItem('适用人群', '18-70岁成年人'),
                      _buildDetailItem('注意事项', '体检前8小时禁食'),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('套餐内容', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                      SizedBox(height: 12),
                      Text(
                        '• 血常规、尿常规、肝功能、肾功能\n'
                        '• 血脂四项、血糖、甲状腺功能\n'
                        '• 心电图、胸部X光\n'
                        '• 腹部B超（肝胆脾胰肾）\n'
                        '• 眼科检查、耳鼻喉检查\n'
                        '• 中医体质辨识\n'
                        '• AI健康报告解读',
                        style: TextStyle(fontSize: 14, height: 1.8, color: Color(0xFF666666)),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 80),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: Container(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 10,
          bottom: MediaQuery.of(context).padding.bottom + 10,
        ),
        decoration: const BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Colors.black12, blurRadius: 6, offset: Offset(0, -2))],
        ),
        child: Row(
          children: [
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.headset_mic, color: Color(0xFF52C41A)),
                  onPressed: () => Navigator.pushNamed(context, '/customer-service'),
                ),
                const Text('客服', style: TextStyle(fontSize: 11, color: Color(0xFF999999))),
              ],
            ),
            const SizedBox(width: 12),
            Expanded(
              child: SizedBox(
                height: 48,
                child: ElevatedButton(
                  onPressed: () {},
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFF6B35),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                  ),
                  child: const Text('立即预约', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailItem(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Text(label, style: TextStyle(fontSize: 14, color: Colors.grey[600])),
          const SizedBox(width: 20),
          Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }
}
