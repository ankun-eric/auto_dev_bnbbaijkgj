import 'package:flutter/material.dart';
import '../../models/unified_order.dart';
import '../../services/api_service.dart';

class RefundListScreen extends StatefulWidget {
  const RefundListScreen({super.key});

  @override
  State<RefundListScreen> createState() => _RefundListScreenState();
}

class _RefundListScreenState extends State<RefundListScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  final List<Map<String, String>> _tabs = [
    {'label': '全部', 'filter': 'all_refund'},
    {'label': '申请中', 'filter': 'applied'},
    {'label': '处理中', 'filter': 'reviewing,returning'},
    {'label': '已退款', 'filter': 'refund_success,approved'},
    {'label': '已拒绝', 'filter': 'rejected'},
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
        title: const Text('退款/售后'),
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
        children: _tabs.map((t) => _RefundTab(filter: t['filter']!)).toList(),
      ),
    );
  }
}

class _RefundTab extends StatefulWidget {
  final String filter;
  const _RefundTab({required this.filter});

  @override
  State<_RefundTab> createState() => _RefundTabState();
}

class _RefundTabState extends State<_RefundTab>
    with AutomaticKeepAliveClientMixin {
  final ApiService _api = ApiService();
  final ScrollController _scrollController = ScrollController();
  List<UnifiedOrder> _orders = [];
  bool _loading = true;
  bool _loadingMore = false;
  int _page = 1;
  int _total = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _loadOrders(reset: true);
  }

  @override
  void dispose() {
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
            _scrollController.position.maxScrollExtent - 100 &&
        !_loadingMore &&
        _orders.length < _total) {
      _loadMore();
    }
  }

  Future<void> _loadOrders({bool reset = false}) async {
    if (reset) {
      setState(() {
        _loading = true;
        _page = 1;
      });
    }
    try {
      final res = await _api.getUnifiedOrders(
        refundStatus: widget.filter,
        page: 1,
        pageSize: 20,
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
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadMore() async {
    if (_loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final nextPage = _page + 1;
      final res = await _api.getUnifiedOrders(
        refundStatus: widget.filter,
        page: nextPage,
        pageSize: 20,
      );
      final data = res.data;
      if (data is Map && data['items'] is List) {
        final more = (data['items'] as List)
            .map((e) => UnifiedOrder.fromJson(e as Map<String, dynamic>))
            .toList();
        setState(() {
          _orders.addAll(more);
          _total = data['total'] ?? _total;
          _page = nextPage;
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _loadingMore = false);
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_loading) {
      return const Center(
          child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_orders.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.replay_outlined, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('暂无退款订单', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: () => _loadOrders(reset: true),
      color: const Color(0xFF52C41A),
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.all(12),
        itemCount: _orders.length + (_orders.length < _total ? 1 : 0),
        itemBuilder: (context, index) {
          if (index >= _orders.length) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Color(0xFF52C41A),
                  ),
                ),
              ),
            );
          }
          return _buildOrderCard(_orders[index]);
        },
      ),
    );
  }

  Widget _buildOrderCard(UnifiedOrder order) {
    return GestureDetector(
      onTap: () async {
        await Navigator.pushNamed(
          context,
          '/unified-order-detail',
          arguments: order.id,
        );
        _loadOrders(reset: true);
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8)
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      order.orderNo,
                      style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(
                      color: _refundStatusColor(order.refundStatus)
                          .withOpacity(0.1),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      _refundStatusLabel(order.refundStatus),
                      style: TextStyle(
                        color: _refundStatusColor(order.refundStatus),
                        fontSize: 12,
                      ),
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
                          child: item.productImage != null &&
                                  item.productImage!.isNotEmpty
                              ? Image.network(
                                  item.productImage!,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, __, ___) => _placeholder(),
                                )
                              : _placeholder(),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              item.productName,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 14, fontWeight: FontWeight.w500),
                            ),
                            const SizedBox(height: 4),
                            Row(
                              mainAxisAlignment:
                                  MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  '¥${item.productPrice.toStringAsFixed(2)}',
                                  style: const TextStyle(
                                      color: Color(0xFFFF4D4F), fontSize: 14),
                                ),
                                Text(
                                  'x${item.quantity}',
                                  style: TextStyle(
                                      color: Colors.grey[500], fontSize: 13),
                                ),
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
                        style: const TextStyle(
                          color: Color(0xFFFF4D4F),
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                    ],
                  ),
                ],
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
      child: const Icon(Icons.shopping_bag_outlined,
          color: Color(0xFF52C41A), size: 24),
    );
  }

  String _refundStatusLabel(String s) {
    switch (s) {
      case 'applied':
        return '申请中';
      case 'reviewing':
        return '审核中';
      case 'approved':
        return '已同意';
      case 'returning':
        return '退货中';
      case 'refund_success':
        return '已退款';
      case 'rejected':
        return '已拒绝';
      case 'none':
        return '无退款';
      default:
        return '退款';
    }
  }

  Color _refundStatusColor(String s) {
    switch (s) {
      case 'applied':
      case 'reviewing':
        return const Color(0xFFFAAD14);
      case 'approved':
      case 'returning':
        return const Color(0xFF1890FF);
      case 'refund_success':
        return const Color(0xFF52C41A);
      case 'rejected':
        return const Color(0xFFFF4D4F);
      default:
        return Colors.grey;
    }
  }
}
