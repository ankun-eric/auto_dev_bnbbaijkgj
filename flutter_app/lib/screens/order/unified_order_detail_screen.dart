import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../models/unified_order.dart';
import '../../services/api_service.dart';

class UnifiedOrderDetailScreen extends StatefulWidget {
  const UnifiedOrderDetailScreen({super.key});

  @override
  State<UnifiedOrderDetailScreen> createState() => _UnifiedOrderDetailScreenState();
}

class _UnifiedOrderDetailScreenState extends State<UnifiedOrderDetailScreen> {
  final ApiService _api = ApiService();
  UnifiedOrder? _order;
  bool _loading = true;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_order == null) {
      final orderId = ModalRoute.of(context)!.settings.arguments as int;
      _loadOrder(orderId);
    }
  }

  Future<void> _loadOrder(int id) async {
    try {
      final res = await _api.getUnifiedOrderDetail(id);
      if (res.data is Map) {
        setState(() {
          _order = UnifiedOrder.fromJson(res.data as Map<String, dynamic>);
          _loading = false;
        });
      }
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
      );
    }
    if (_order == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: Text('订单不存在')),
      );
    }

    final o = _order!;
    return Scaffold(
      appBar: AppBar(title: const Text('订单详情'), backgroundColor: const Color(0xFF52C41A)),
      body: SingleChildScrollView(
        child: Column(
          children: [
            _buildStatusHeader(o),
            const SizedBox(height: 8),
            _buildItemsSection(o),
            const SizedBox(height: 8),
            _buildPriceSection(o),
            const SizedBox(height: 8),
            _buildInfoSection(o),
            if (o.items.any((i) => i.verificationCode != null && i.verificationCode!.isNotEmpty)) ...[
              const SizedBox(height: 8),
              _buildVerificationSection(o),
            ],
            if (o.trackingNumber != null && o.trackingNumber!.isNotEmpty) ...[
              const SizedBox(height: 8),
              _buildTrackingSection(o),
            ],
            const SizedBox(height: 80),
          ],
        ),
      ),
      bottomNavigationBar: _buildBottomActions(o),
    );
  }

  Widget _buildStatusHeader(UnifiedOrder o) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_statusColor(o.status), _statusColor(o.status).withOpacity(0.7)],
        ),
      ),
      child: Column(
        children: [
          Icon(_statusIcon(o.status), color: Colors.white, size: 40),
          const SizedBox(height: 8),
          Text(o.statusLabel, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
          if (o.refundStatus != 'none') ...[
            const SizedBox(height: 4),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text('退款状态: ${_refundLabel(o.refundStatus)}',
                  style: const TextStyle(color: Colors.white, fontSize: 12)),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildItemsSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('商品信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ...o.items.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SizedBox(
                    width: 70,
                    height: 70,
                    child: item.productImage != null
                        ? Image.network(item.productImage!, fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => _placeholder())
                        : _placeholder(),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(item.productName, style: const TextStyle(fontWeight: FontWeight.w500)),
                      const SizedBox(height: 4),
                      Text(_fulfillmentLabel(item.fulfillmentType),
                          style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                      const SizedBox(height: 4),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text('¥${item.productPrice.toStringAsFixed(2)}',
                              style: const TextStyle(color: Color(0xFFFF4D4F))),
                          Text('x${item.quantity}', style: TextStyle(color: Colors.grey[500])),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildPriceSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _infoRow('商品总额', '¥${o.totalAmount.toStringAsFixed(2)}'),
          if (o.couponDiscount > 0) _infoRow('优惠券', '-¥${o.couponDiscount.toStringAsFixed(2)}'),
          if (o.pointsDeduction > 0) _infoRow('积分抵扣', '-¥${(o.pointsDeduction / 100).toStringAsFixed(2)}'),
          const Divider(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('实付金额', style: TextStyle(fontWeight: FontWeight.bold)),
              Text('¥${o.paidAmount.toStringAsFixed(2)}',
                  style: const TextStyle(color: Color(0xFFFF4D4F), fontSize: 18, fontWeight: FontWeight.bold)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInfoSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('订单信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _infoRow('订单编号', o.orderNo, copyable: true),
          _infoRow('下单时间', _formatTime(o.createdAt)),
          if (o.paymentMethod != null) _infoRow('支付方式', o.paymentMethod!),
          if (o.paidAt != null) _infoRow('支付时间', _formatTime(o.paidAt)),
          if (o.notes != null && o.notes!.isNotEmpty) _infoRow('备注', o.notes!),
        ],
      ),
    );
  }

  Widget _buildVerificationSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('核销码', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ...o.items.where((i) => i.verificationCode != null).map((item) => Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF0F9EB),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              children: [
                const Icon(Icons.qr_code, color: Color(0xFF52C41A), size: 32),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(item.productName, style: const TextStyle(fontSize: 13)),
                    Text(item.verificationCode!, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: 2)),
                    Text('已使用${item.usedRedeemCount}/${item.totalRedeemCount}次', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                  ],
                ),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildTrackingSection(UnifiedOrder o) {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('物流信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          _infoRow('物流公司', o.trackingCompany ?? ''),
          _infoRow('运单号', o.trackingNumber!, copyable: true),
        ],
      ),
    );
  }

  Widget? _buildBottomActions(UnifiedOrder o) {
    final actions = <Widget>[];

    switch (o.status) {
      case 'pending_payment':
        actions.add(_actionBtn('取消订单', Colors.grey, () => _cancelOrder(o)));
        actions.add(const SizedBox(width: 12));
        actions.add(_actionBtn('去支付', const Color(0xFF52C41A), () => _payOrder(o), filled: true));
        break;
      case 'pending_receipt':
        actions.add(_actionBtn('确认收货', const Color(0xFF52C41A), () => _confirmReceipt(o), filled: true));
        break;
      case 'pending_review':
        actions.add(_actionBtn('申请退款', Colors.grey, () {
          Navigator.pushNamed(context, '/refund', arguments: o.id);
        }));
        actions.add(const SizedBox(width: 12));
        actions.add(_actionBtn('去评价', const Color(0xFFFAAD14), () {
          Navigator.pushNamed(context, '/review', arguments: o.id);
        }, filled: true));
        break;
      case 'pending_use':
      case 'pending_shipment':
        actions.add(_actionBtn('申请退款', Colors.grey, () {
          Navigator.pushNamed(context, '/refund', arguments: o.id);
        }));
        break;
    }

    if (actions.isEmpty) return null;

    return Container(
      padding: EdgeInsets.fromLTRB(16, 8, 16, MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 8, offset: const Offset(0, -2))],
      ),
      child: Row(mainAxisAlignment: MainAxisAlignment.end, children: actions),
    );
  }

  Widget _actionBtn(String text, Color color, VoidCallback onTap, {bool filled = false}) {
    return filled
        ? ElevatedButton(
            onPressed: onTap,
            style: ElevatedButton.styleFrom(
              backgroundColor: color,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
            ),
            child: Text(text),
          )
        : OutlinedButton(
            onPressed: onTap,
            style: OutlinedButton.styleFrom(
              foregroundColor: color,
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              side: BorderSide(color: color),
            ),
            child: Text(text),
          );
  }

  Widget _placeholder() {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF52C41A), size: 24),
    );
  }

  Widget _infoRow(String label, String value, {bool copyable = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 80, child: Text(label, style: TextStyle(color: Colors.grey[500], fontSize: 14))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14))),
          if (copyable)
            GestureDetector(
              onTap: () {
                Clipboard.setData(ClipboardData(text: value));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('已复制'), duration: Duration(seconds: 1)),
                );
              },
              child: Icon(Icons.copy, size: 16, color: Colors.grey[400]),
            ),
        ],
      ),
    );
  }

  String _formatTime(String? time) {
    if (time == null) return '';
    return time.replaceFirst('T', ' ').split('.').first;
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
      default:
        return Colors.grey;
    }
  }

  IconData _statusIcon(String status) {
    switch (status) {
      case 'pending_payment':
        return Icons.payment;
      case 'pending_shipment':
        return Icons.local_shipping;
      case 'pending_receipt':
        return Icons.inventory;
      case 'pending_use':
        return Icons.qr_code;
      case 'pending_review':
        return Icons.rate_review;
      case 'completed':
        return Icons.check_circle;
      case 'cancelled':
        return Icons.cancel;
      default:
        return Icons.receipt_long;
    }
  }

  String _refundLabel(String status) {
    switch (status) {
      case 'applied':
        return '申请中';
      case 'approved':
        return '已同意';
      case 'rejected':
        return '已拒绝';
      case 'refunded':
        return '已退款';
      default:
        return status;
    }
  }

  String _fulfillmentLabel(String type) {
    switch (type) {
      case 'delivery':
        return '快递配送';
      case 'in_store':
        return '到店消费';
      case 'virtual':
        return '虚拟商品';
      default:
        return type;
    }
  }

  Future<void> _cancelOrder(UnifiedOrder o) async {
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
      await _api.cancelUnifiedOrder(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('订单已取消')));
        _loadOrder(o.id);
      }
    } catch (_) {}
  }

  Future<void> _payOrder(UnifiedOrder o) async {
    try {
      await _api.payUnifiedOrder(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付成功')));
        _loadOrder(o.id);
      }
    } catch (_) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('支付失败')));
    }
  }

  Future<void> _confirmReceipt(UnifiedOrder o) async {
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
      await _api.confirmReceipt(o.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('确认收货成功')));
        _loadOrder(o.id);
      }
    } catch (_) {}
  }
}
