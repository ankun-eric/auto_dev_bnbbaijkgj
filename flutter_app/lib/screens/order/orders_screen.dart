import 'package:flutter/material.dart';
import '../../models/order.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/empty_widget.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  final List<String> _tabs = ['全部', '待付款', '待收货', '待使用', '已完成', '待评价', '已取消'];
  final List<String> _statusFilters = ['all', 'pending_payment', 'pending_receipt', 'pending_use', 'completed', 'pending_review', 'cancelled'];

  final List<Order> _orders = [
    Order(id: '1', orderNo: '2024032700001', serviceName: '全面体检套餐', amount: 599, status: 'paid', createdAt: '2024-03-25 10:30'),
    Order(id: '2', orderNo: '2024032700002', serviceName: '专家在线咨询', amount: 199, status: 'pending', expertName: '张明华', createdAt: '2024-03-26 14:20'),
    Order(id: '3', orderNo: '2024032700003', serviceName: '中医推拿理疗', amount: 298, status: 'completed', createdAt: '2024-03-20 09:15'),
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
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
        title: const Text('我的订单'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          isScrollable: true,
          tabs: _tabs.map((t) => Tab(text: t)).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _statusFilters.map((status) {
          final filtered = status == 'all'
              ? _orders
              : _orders.where((o) => o.status == status).toList();
          return filtered.isEmpty
              ? const EmptyWidget(message: '暂无订单', icon: Icons.receipt_long_outlined)
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: filtered.length,
                  itemBuilder: (context, index) => _buildOrderCard(filtered[index]),
                );
        }).toList(),
      ),
    );
  }

  Widget _buildOrderCard(Order order) {
    Color statusColor;
    switch (order.status) {
      case 'pending':
        statusColor = const Color(0xFFFA8C16);
        break;
      case 'paid':
        statusColor = const Color(0xFF1890FF);
        break;
      case 'completed':
        statusColor = const Color(0xFF52C41A);
        break;
      default:
        statusColor = Colors.grey;
    }

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/order-detail', arguments: order.id),
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
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
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('订单号: ${order.orderNo}', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    order.statusLabel,
                    style: TextStyle(fontSize: 12, color: statusColor, fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
            const Divider(height: 20),
            Row(
              children: [
                Container(
                  width: 60,
                  height: 60,
                  decoration: BoxDecoration(
                    color: const Color(0xFFE8F5E9),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.medical_services, color: Color(0xFF52C41A), size: 28),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        order.serviceName ?? '',
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                      ),
                      if (order.expertName != null)
                        Text('专家: ${order.expertName}', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                    ],
                  ),
                ),
                Text(
                  '¥${order.amount.toStringAsFixed(0)}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFFFF6B35)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(order.createdAt ?? '', style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                if (order.status == 'pending')
                  Row(
                    children: [
                      OutlinedButton(
                        onPressed: () {},
                        style: OutlinedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                          side: BorderSide(color: Colors.grey[300]!),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        ),
                        child: Text('取消', style: TextStyle(fontSize: 13, color: Colors.grey[600])),
                      ),
                      const SizedBox(width: 8),
                      ElevatedButton(
                        onPressed: () {},
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        ),
                        child: const Text('去支付', style: TextStyle(fontSize: 13)),
                      ),
                    ],
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
