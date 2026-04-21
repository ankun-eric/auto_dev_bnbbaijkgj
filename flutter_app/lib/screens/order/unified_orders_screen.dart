import 'package:flutter/material.dart';
import '../../models/unified_order.dart';
import '../../services/api_service.dart';

class UnifiedOrdersScreen extends StatefulWidget {
  const UnifiedOrdersScreen({super.key});

  @override
  State<UnifiedOrdersScreen> createState() => _UnifiedOrdersScreenState();
}

class _UnifiedOrdersScreenState extends State<UnifiedOrdersScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiService _api = ApiService();

  final List<Map<String, String>> _tabs = [
    {'label': '全部', 'status': 'all'},
    {'label': '待付款', 'status': 'pending_payment'},
    {'label': '待收货', 'status': 'pending_receipt'},
    {'label': '待使用', 'status': 'pending_use'},
    {'label': '已完成', 'status': 'completed'},
    {'label': '待评价', 'status': 'pending_review'},
    {'label': '已取消', 'status': 'cancelled'},
  ];

  @override
  void initState() {
    super.initState();
    final initialIndex = ModalRoute.of(context) != null ? 0 : 0;
    _tabController = TabController(length: _tabs.length, vsync: this, initialIndex: initialIndex);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final tabIndex = ModalRoute.of(context)?.settings.arguments as int?;
    if (tabIndex != null && tabIndex < _tabs.length) {
      _tabController.index = tabIndex;
    }
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
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          labelStyle: const TextStyle(fontWeight: FontWeight.w600),
          unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.normal),
          tabs: _tabs.map((t) => Tab(text: t['label'])).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _tabs.map((t) => _OrderTab(status: t['status']!)).toList(),
      ),
    );
  }
}

class _OrderTab extends StatefulWidget {
  final String status;
  const _OrderTab({required this.status});

  @override
  State<_OrderTab> createState() => _OrderTabState();
}

class _OrderTabState extends State<_OrderTab> with AutomaticKeepAliveClientMixin {
  final ApiService _api = ApiService();
  List<UnifiedOrder> _orders = [];
  bool _loading = true;
  int _page = 1;
  int _total = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadOrders();
  }

  Future<void> _loadOrders() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getUnifiedOrders(
        status: widget.status != 'all' ? widget.status : null,
        page: 1,
      );
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _orders = (data['items'] as List)
              .map((e) => UnifiedOrder.fromJson(e as Map<String, dynamic>))
              .toList();
          _total = data['total'] ?? 0;
          _page = 1;
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_orders.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.receipt_long_outlined, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('暂无订单', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadOrders,
      color: const Color(0xFF52C41A),
      child: ListView.builder(
        padding: const EdgeInsets.all(12),
        itemCount: _orders.length,
        itemBuilder: (context, index) => _buildOrderCard(_orders[index]),
      ),
    );
  }

  Widget _buildOrderCard(UnifiedOrder order) {
    return GestureDetector(
      onTap: () async {
        await Navigator.pushNamed(context, '/unified-order-detail', arguments: order.id);
        _loadOrders();
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8)],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(order.orderNo, style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: _statusColor(order.status).withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      order.statusLabel,
                      style: TextStyle(color: _statusColor(order.status), fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            ...order.items.map((item) => Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
              child: Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: SizedBox(
                      width: 60,
                      height: 60,
                      child: item.productImage != null && item.productImage!.isNotEmpty
                          ? Image.network(item.productImage!, fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => _placeholder())
                          : _placeholder(),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.productName, maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500)),
                        const SizedBox(height: 4),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('¥${item.productPrice.toStringAsFixed(2)}',
                                style: const TextStyle(color: Color(0xFFFF4D4F), fontSize: 14)),
                            Text('x${item.quantity}', style: TextStyle(color: Colors.grey[500], fontSize: 13)),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            )),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    '共${order.items.fold<int>(0, (sum, i) => sum + i.quantity)}件商品',
                    style: TextStyle(color: Colors.grey[500], fontSize: 13),
                  ),
                  Row(
                    children: [
                      const Text('实付 ', style: TextStyle(fontSize: 13)),
                      Text(
                        '¥${order.paidAmount.toStringAsFixed(2)}',
                        style: const TextStyle(color: Color(0xFFFF4D4F), fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (_hasActions(order.status))
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: _buildActions(order),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _placeholder() {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF52C41A), size: 24),
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'pending_payment':
        return const Color(0xFFFF4D4F);
      case 'pending_shipment':
      case 'pending_receipt':
      case 'pending_use':
        return const Color(0xFF1890FF);
      case 'pending_review':
        return const Color(0xFFFAAD14);
      case 'completed':
        return const Color(0xFF52C41A);
      case 'cancelled':
        return Colors.grey;
      default:
        return Colors.grey;
    }
  }

  bool _hasActions(String status) {
    return ['pending_payment', 'pending_review', 'pending_receipt'].contains(status);
  }

  List<Widget> _buildActions(UnifiedOrder order) {
    final actions = <Widget>[];
    switch (order.status) {
      case 'pending_payment':
        actions.add(_actionButton('取消订单', Colors.grey, () => _cancelOrder(order)));
        actions.add(const SizedBox(width: 8));
        actions.add(_actionButton('去支付', const Color(0xFF52C41A), () => _payOrder(order), filled: true));
        break;
      case 'pending_receipt':
        actions.add(_actionButton('确认收货', const Color(0xFF52C41A), () => _confirmReceipt(order), filled: true));
        break;
      case 'pending_review':
        actions.add(_actionButton('去评价', const Color(0xFFFAAD14), () {
          Navigator.pushNamed(context, '/review', arguments: order.id);
        }, filled: true));
        break;
    }
    return actions;
  }

  Widget _actionButton(String text, Color color, VoidCallback onTap, {bool filled = false}) {
    return SizedBox(
      height: 32,
      child: filled
          ? ElevatedButton(
              onPressed: onTap,
              style: ElevatedButton.styleFrom(
                backgroundColor: color,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                textStyle: const TextStyle(fontSize: 13),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: Text(text),
            )
          : OutlinedButton(
              onPressed: onTap,
              style: OutlinedButton.styleFrom(
                foregroundColor: color,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                textStyle: const TextStyle(fontSize: 13),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                side: BorderSide(color: color),
              ),
              child: Text(text),
            ),
    );
  }

  Future<void> _cancelOrder(UnifiedOrder order) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('取消订单'),
        content: const Text('确定要取消该订单吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('再想想')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确定取消')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.cancelUnifiedOrder(order.id);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('订单已取消')));
      _loadOrders();
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('取消失败')));
    }
  }

  Future<void> _payOrder(UnifiedOrder order) async {
    try {
      await _api.payUnifiedOrder(order.id);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付成功')));
      _loadOrders();
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付失败')));
    }
  }

  Future<void> _confirmReceipt(UnifiedOrder order) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('确认收货'),
        content: const Text('确定已收到货物吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确认')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      await _api.confirmReceipt(order.id);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('确认收货成功')));
      _loadOrders();
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('操作失败')));
    }
  }
}
