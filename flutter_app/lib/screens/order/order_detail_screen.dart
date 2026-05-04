import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';
import '../../widgets/custom_app_bar.dart';

class OrderDetailScreen extends StatelessWidget {
  const OrderDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '订单详情'),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF52C41A), Color(0xFF13C2C2)],
                ),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Column(
                children: [
                  Icon(Icons.check_circle, color: Colors.white, size: 48),
                  SizedBox(height: 8),
                  Text('已支付', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('等待服务确认', style: TextStyle(color: Colors.white70, fontSize: 14)),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('服务信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 14),
                  _buildInfoRow('服务名称', '全面体检套餐'),
                  _buildInfoRow('订单编号', '2024032700001'),
                  _buildInfoRow('下单时间', '2024-03-25 10:30'),
                  _buildInfoRow('支付金额', '¥599.00'),
                  // [2026-05-04 H5 优惠券抵扣 0 元下单 Bug 修复 v1.0 · D6]
                  // 本屏幕仍为旧 demo 入口（mock 数据，未对接后端订单）。
                  // 不会出现 coupon_deduction 0 元单数据，仅去掉硬编码"微信支付"避免误导，
                  // 真实订单数据请使用 UnifiedOrderDetailScreen。
                  _buildInfoRow('支付方式', '-'),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                children: [
                  const Text('核销码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 16),
                  QrImageView(
                    data: 'BINI-2024032700001',
                    version: QrVersions.auto,
                    size: 180,
                    gapless: true,
                    embeddedImage: null,
                  ),
                  const SizedBox(height: 12),
                  Text('BINI-2024032700001', style: TextStyle(fontSize: 14, color: Colors.grey[600], letterSpacing: 1)),
                  const SizedBox(height: 8),
                  Text('到店出示此二维码即可核销', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                ],
              ),
            ),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('物流信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 14),
                  _buildLogisticsItem('2024-03-25 10:30', '订单已创建', true),
                  _buildLogisticsItem('2024-03-25 10:31', '支付成功', true),
                  _buildLogisticsItem('待确认', '等待服务方确认', false),
                  _buildLogisticsItem('待完成', '服务完成', false),
                ],
              ),
            ),
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.pushNamed(context, '/customer-service'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: const BorderSide(color: Color(0xFF52C41A)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                    ),
                    child: const Text('联系客服', style: TextStyle(color: Color(0xFF52C41A))),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () {},
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    child: const Text('申请退款'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(fontSize: 14, color: Colors.grey[600])),
          Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildLogisticsItem(String time, String desc, bool isDone) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Column(
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isDone ? const Color(0xFF52C41A) : Colors.grey[300],
              ),
            ),
            Container(width: 2, height: 30, color: Colors.grey[200]),
          ],
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(desc, style: TextStyle(fontSize: 14, color: isDone ? const Color(0xFF333333) : Colors.grey[400])),
              Text(time, style: TextStyle(fontSize: 12, color: Colors.grey[400])),
              const SizedBox(height: 14),
            ],
          ),
        ),
      ],
    );
  }
}
