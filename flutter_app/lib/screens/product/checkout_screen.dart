import 'package:flutter/material.dart';
import '../../models/product.dart';
import '../../models/address.dart';
import '../../models/coupon.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final ApiService _api = ApiService();

  late Product _product;
  late int _quantity;
  List<UserAddress> _addresses = [];
  UserAddress? _selectedAddress;
  List<UserCoupon> _coupons = [];
  UserCoupon? _selectedCoupon;
  int _pointsDeduction = 0;
  bool _submitting = false;
  final TextEditingController _notesController = TextEditingController();

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    _product = args['product'] as Product;
    _quantity = args['quantity'] as int;
    _loadAddresses();
    _loadCoupons();
  }

  @override
  void dispose() {
    _notesController.dispose();
    super.dispose();
  }

  Future<void> _loadAddresses() async {
    try {
      final res = await _api.getAddresses();
      if (res.data is Map && res.data['items'] is List) {
        setState(() {
          _addresses = (res.data['items'] as List)
              .map((e) => UserAddress.fromJson(e as Map<String, dynamic>))
              .toList();
          _selectedAddress = _addresses.where((a) => a.isDefault).firstOrNull ?? _addresses.firstOrNull;
        });
      }
    } catch (_) {}
  }

  Future<void> _loadCoupons() async {
    try {
      final res = await _api.getMyCoupons(tab: 'unused');
      if (res.data is Map && res.data['items'] is List) {
        setState(() {
          _coupons = (res.data['items'] as List)
              .map((e) => UserCoupon.fromJson(e as Map<String, dynamic>))
              .toList();
        });
      }
    } catch (_) {}
  }

  double get _subtotal => _product.salePrice * _quantity;

  double get _couponDiscount {
    if (_selectedCoupon?.coupon == null) return 0;
    final c = _selectedCoupon!.coupon!;
    if (_subtotal < c.conditionAmount) return 0;
    switch (c.type) {
      case 'full_reduction':
        return c.discountValue;
      case 'discount':
        return _subtotal * (1 - c.discountRate);
      case 'voucher':
        return c.discountValue;
      default:
        return 0;
    }
  }

  double get _pointsValue => _pointsDeduction / 100.0;

  double get _totalAmount {
    final amount = _subtotal - _couponDiscount - _pointsValue;
    return amount > 0 ? amount : 0;
  }

  bool get _needAddress => _product.fulfillmentType == 'delivery';

  Future<void> _submitOrder() async {
    if (_needAddress && _selectedAddress == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择收货地址')));
      return;
    }

    setState(() => _submitting = true);
    try {
      final data = <String, dynamic>{
        'items': [
          {
            'product_id': _product.id,
            'quantity': _quantity,
          }
        ],
        'points_deduction': _pointsDeduction,
        'notes': _notesController.text.isNotEmpty ? _notesController.text : null,
      };

      if (_selectedCoupon != null) {
        data['coupon_id'] = _selectedCoupon!.couponId;
      }
      if (_selectedAddress != null) {
        data['shipping_address_id'] = _selectedAddress!.id;
      }

      final res = await _api.createUnifiedOrder(data);
      if (mounted) {
        if (res.data is Map && res.data['id'] != null) {
          Navigator.pushReplacementNamed(
            context,
            '/unified-order-detail',
            arguments: res.data['id'],
          );
        }
      }
    } catch (e) {
      if (mounted) {
        final msg = e.toString().contains('detail')
            ? RegExp(r'"detail"\s*:\s*"([^"]*)"').firstMatch(e.toString())?.group(1) ?? '下单失败'
            : '下单失败';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    }
    setState(() => _submitting = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('确认订单'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: SingleChildScrollView(
        child: Column(
          children: [
            if (_needAddress) _buildAddressSection(),
            const SizedBox(height: 8),
            _buildProductSection(),
            const SizedBox(height: 8),
            _buildCouponSection(),
            const SizedBox(height: 8),
            _buildNotesSection(),
            const SizedBox(height: 8),
            _buildPriceSection(),
            const SizedBox(height: 80),
          ],
        ),
      ),
      bottomNavigationBar: Container(
        padding: EdgeInsets.fromLTRB(16, 8, 16, MediaQuery.of(context).padding.bottom + 8),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 8, offset: const Offset(0, -2))],
        ),
        child: Row(
          children: [
            Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('合计', style: TextStyle(fontSize: 13, color: Colors.grey)),
                Text(
                  '¥${formatPrice(_totalAmount)}',
                  style: const TextStyle(color: Color(0xFFFF4D4F), fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const Spacer(),
            ElevatedButton(
              onPressed: _submitting ? null : _submitOrder,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF52C41A),
                padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 14),
              ),
              child: _submitting
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
                  : const Text('提交订单', style: TextStyle(fontSize: 16)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildAddressSection() {
    return GestureDetector(
      onTap: () async {
        final result = await Navigator.pushNamed(context, '/address-list', arguments: true);
        if (result is UserAddress) {
          setState(() => _selectedAddress = result);
        }
      },
      child: Container(
        padding: const EdgeInsets.all(16),
        color: Colors.white,
        child: _selectedAddress != null
            ? Row(
                children: [
                  const Icon(Icons.location_on, color: Color(0xFF52C41A)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(_selectedAddress!.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(width: 12),
                            Text(_selectedAddress!.phone, style: TextStyle(color: Colors.grey[600])),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _selectedAddress!.fullAddress,
                          style: TextStyle(fontSize: 13, color: Colors.grey[600]),
                        ),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: Colors.grey[400]),
                ],
              )
            : Row(
                children: [
                  const Icon(Icons.add_location, color: Color(0xFF52C41A)),
                  const SizedBox(width: 12),
                  const Text('选择收货地址'),
                  const Spacer(),
                  Icon(Icons.chevron_right, color: Colors.grey[400]),
                ],
              ),
      ),
    );
  }

  Widget _buildProductSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: SizedBox(
              width: 80,
              height: 80,
              child: _product.firstImage.isNotEmpty
                  ? Image.network(_product.firstImage, fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: const Color(0xFFF0F9EB),
                        child: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF52C41A)),
                      ),
                    )
                  : Container(
                      color: const Color(0xFFF0F9EB),
                      child: const Icon(Icons.shopping_bag_outlined, color: Color(0xFF52C41A)),
                    ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(_product.name, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w500)),
                const SizedBox(height: 4),
                Text(_product.fulfillmentLabel, style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                const SizedBox(height: 6),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('¥${formatPrice(_product.salePrice)}',
                        style: const TextStyle(color: Color(0xFFFF4D4F), fontWeight: FontWeight.bold)),
                    Text('x$_quantity', style: TextStyle(color: Colors.grey[500])),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCouponSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Column(
        children: [
          GestureDetector(
            onTap: _showCouponPicker,
            child: Row(
              children: [
                const Icon(Icons.local_offer_outlined, color: Color(0xFF52C41A), size: 20),
                const SizedBox(width: 8),
                const Text('优惠券'),
                const Spacer(),
                Text(
                  _selectedCoupon != null
                      ? '-¥${formatPrice(_couponDiscount)}'
                      : _coupons.isEmpty
                          ? '暂无可用'
                          : '${_coupons.length}张可用',
                  style: TextStyle(
                    color: _selectedCoupon != null ? const Color(0xFFFF4D4F) : Colors.grey[500],
                    fontSize: 14,
                  ),
                ),
                Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNotesSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: TextField(
        controller: _notesController,
        decoration: const InputDecoration(
          hintText: '订单备注（选填）',
          border: InputBorder.none,
          hintStyle: TextStyle(fontSize: 14),
        ),
        maxLines: 2,
        style: const TextStyle(fontSize: 14),
      ),
    );
  }

  Widget _buildPriceSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Column(
        children: [
          _buildPriceRow('商品金额', '¥${formatPrice(_subtotal)}'),
          if (_couponDiscount > 0)
            _buildPriceRow('优惠券', '-¥${formatPrice(_couponDiscount)}', valueColor: const Color(0xFFFF4D4F)),
          if (_pointsValue > 0)
            _buildPriceRow('积分抵扣', '-¥${formatPrice(_pointsValue)}', valueColor: const Color(0xFFFF4D4F)),
          const Divider(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('实付金额', style: TextStyle(fontWeight: FontWeight.bold)),
              Text(
                '¥${formatPrice(_totalAmount)}',
                style: const TextStyle(color: Color(0xFFFF4D4F), fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPriceRow(String label, String value, {Color? valueColor}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: TextStyle(color: Colors.grey[600], fontSize: 14)),
          Text(value, style: TextStyle(color: valueColor ?? Colors.black87, fontSize: 14)),
        ],
      ),
    );
  }

  void _showCouponPicker() {
    if (_coupons.isEmpty) return;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) {
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('选择优惠券', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),
            ListTile(
              title: const Text('不使用优惠券'),
              trailing: _selectedCoupon == null ? const Icon(Icons.check, color: Color(0xFF52C41A)) : null,
              onTap: () {
                setState(() => _selectedCoupon = null);
                Navigator.pop(ctx);
              },
            ),
            ...(_coupons.map((uc) {
              final c = uc.coupon;
              if (c == null) return const SizedBox.shrink();
              return ListTile(
                title: Text(c.name),
                subtitle: Text(c.discountText),
                trailing: _selectedCoupon?.id == uc.id ? const Icon(Icons.check, color: Color(0xFF52C41A)) : null,
                onTap: () {
                  setState(() => _selectedCoupon = uc);
                  Navigator.pop(ctx);
                },
              );
            })),
            SizedBox(height: MediaQuery.of(ctx).padding.bottom + 16),
          ],
        );
      },
    );
  }
}
