import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class PointsMallScreen extends StatelessWidget {
  const PointsMallScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final items = [
      {'name': '健康手环', 'points': 5000, 'image': Icons.watch, 'stock': 50},
      {'name': '体检优惠券 ¥50', 'points': 2000, 'image': Icons.card_giftcard, 'stock': 100},
      {'name': '维生素C礼盒', 'points': 1500, 'image': Icons.medication, 'stock': 80},
      {'name': '中医养生茶', 'points': 800, 'image': Icons.local_cafe, 'stock': 200},
      {'name': '按摩枕', 'points': 3000, 'image': Icons.airline_seat_recline_extra, 'stock': 30},
      {'name': '血压计', 'points': 4000, 'image': Icons.monitor_heart, 'stock': 20},
    ];

    return Scaffold(
      appBar: const CustomAppBar(title: '积分商城'),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            color: const Color(0xFFF0F9EB),
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.monetization_on, color: Color(0xFF52C41A)),
                SizedBox(width: 8),
                Text('可用积分: ', style: TextStyle(fontSize: 15)),
                Text('2,580', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Color(0xFF52C41A))),
              ],
            ),
          ),
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 0.75,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              itemCount: items.length,
              itemBuilder: (context, index) {
                final item = items[index];
                return Container(
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
                    children: [
                      Expanded(
                        flex: 3,
                        child: Container(
                          width: double.infinity,
                          decoration: BoxDecoration(
                            color: const Color(0xFFF0F9EB),
                            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                          ),
                          child: Icon(item['image'] as IconData, size: 50, color: const Color(0xFF52C41A)),
                        ),
                      ),
                      Expanded(
                        flex: 2,
                        child: Padding(
                          padding: const EdgeInsets.all(10),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                item['name'] as String,
                                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              const SizedBox(height: 4),
                              Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(
                                    '${item['points']}积分',
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.bold,
                                      color: Color(0xFFFF6B35),
                                    ),
                                  ),
                                  Text(
                                    '库存${item['stock']}',
                                    style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              SizedBox(
                                width: double.infinity,
                                height: 28,
                                child: ElevatedButton(
                                  onPressed: () {},
                                  style: ElevatedButton.styleFrom(
                                    padding: EdgeInsets.zero,
                                    textStyle: const TextStyle(fontSize: 12),
                                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                                  ),
                                  child: const Text('立即兑换'),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
