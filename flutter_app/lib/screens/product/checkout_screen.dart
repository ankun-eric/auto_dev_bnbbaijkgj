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
  // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系手机号
  final TextEditingController _contactPhoneController = TextEditingController();
  String? _contactPhoneError;

  DateTime? _selectedDate = DateTime.now();
  String? _selectedTimeSlot;
  String _appointmentNote = '';
  List<Map<String, dynamic>> _slotAvailability = [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    _product = args['product'] as Product;
    _quantity = args['quantity'] as int;
    _loadAddresses();
    _loadCoupons();
    _loadSlotAvailability();
  }

  @override
  void dispose() {
    _notesController.dispose();
    _contactPhoneController.dispose();
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

  // [先下单后预约 Bug 修复 v1.0]
  // 是否在下单页展示预约时间控件 = 商品需预约 且 商品配置为「下单即预约」
  bool get _isBookWithOrder {
    final mode = _product.purchaseAppointmentMode;
    return mode == null ||
        mode.isEmpty ||
        mode == 'purchase_with_appointment' ||
        mode == 'must_appoint';
  }
  bool get _needAppointment =>
      _product.appointmentMode != 'none' && _isBookWithOrder;

  Future<void> _loadSlotAvailability() async {
    if (!_needAppointment) return;
    if (_product.timeSlots == null || _product.timeSlots!.isEmpty) return;
    if (_selectedDate == null) return;
    try {
      final dateStr = _formatDate(_selectedDate!);
      final res = await _api.get('/api/products/${_product.id}/time-slots/availability?date=$dateStr');
      if (res.data is Map && res.data['data'] is Map) {
        final slots = res.data['data']['slots'];
        if (slots is List) {
          setState(() {
            _slotAvailability = slots.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          });
        }
      }
    } catch (_) {
      setState(() => _slotAvailability = []);
    }
  }

  bool _isSlotExpired(String slotEnd) {
    if (_selectedDate == null) return false;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final selDay = DateTime(_selectedDate!.year, _selectedDate!.month, _selectedDate!.day);
    if (selDay != today) return false;
    final parts = slotEnd.split(':');
    if (parts.length < 2) return false;
    final endHour = int.tryParse(parts[0]) ?? 0;
    final endMin = int.tryParse(parts[1]) ?? 0;
    final nowMinutes = now.hour * 60 + now.minute;
    final endMinutes = endHour * 60 + endMin;
    return endMinutes <= nowMinutes;
  }

  bool _isSlotFullyBooked(String label) {
    final avail = _slotAvailability.where((s) =>
      '${s['start_time']}-${s['end_time']}' == label
    ).toList();
    if (avail.isEmpty) return false;
    return (avail.first['available'] ?? 1) <= 0;
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

  String _formatDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _submitOrder() async {
    if (_needAddress && _selectedAddress == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择收货地址')));
      return;
    }

    if (_needAppointment && _selectedDate == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择预约日期')));
      return;
    }

    setState(() => _submitting = true);
    try {
      final itemData = <String, dynamic>{
        'product_id': _product.id,
        'quantity': _quantity,
      };

      if (_needAppointment && _selectedDate != null) {
        final dateStr = _formatDate(_selectedDate!);
        // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系手机号必填校验
        final phone = _contactPhoneController.text.trim();
        final phoneRe = RegExp(r'^1[3-9]\d{9}$');
        if (phone.isEmpty || !phoneRe.hasMatch(phone)) {
          setState(() {
            _submitting = false;
            _contactPhoneError = '请输入正确的手机号';
          });
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('请输入正确的联系手机号')),
            );
          }
          return;
        }
        itemData['appointment_time'] = _selectedTimeSlot != null
            ? '${dateStr}T$_selectedTimeSlot:00'
            : '${dateStr}T00:00:00';
        itemData['appointment_data'] = {
          'date': dateStr,
          'time_slot': _selectedTimeSlot,
          'note': _appointmentNote,
          'contact_phone': phone,
        };
      }

      final data = <String, dynamic>{
        'items': [itemData],
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
            if (_needAppointment) ...[
              const SizedBox(height: 8),
              _buildAppointmentSection(),
            ],
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

  Widget _buildAppointmentSection() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final hasAdvanceDays = _product.advanceDays != null && _product.advanceDays! > 0;
    // BUG-PRODUCT-APPT-002：可预约日期范围统一公式
    // include_today=true  → [today, today + N - 1]
    // include_today=false → [today + 1, today + N]
    final firstDate = (_product.includeToday)
        ? today
        : today.add(const Duration(days: 1));
    final lastDate = hasAdvanceDays
        ? firstDate.add(Duration(days: _product.advanceDays! - 1))
        : today.add(const Duration(days: 365));

    final defaultTimeSlots = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'];

    final hasTimeSlots = _product.timeSlots != null && _product.timeSlots!.isNotEmpty;

    return Container(
      color: Colors.white,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('预约信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          if (hasAdvanceDays) ...[
            const SizedBox(height: 8),
            Text(
              '可预约：${firstDate.month}月${firstDate.day}日 ~ ${lastDate.month}月${lastDate.day}日'
              '${_product.includeToday ? '' : '（不含今天）'}',
              style: TextStyle(fontSize: 13, color: Colors.grey[500]),
            ),
          ],
          const SizedBox(height: 12),
          InkWell(
            onTap: () async {
              final picked = await showDatePicker(
                context: context,
                firstDate: firstDate,
                lastDate: lastDate,
                initialDate: _selectedDate ?? firstDate,
                locale: const Locale('zh'),
              );
              if (picked != null) {
                setState(() => _selectedDate = picked);
                _loadSlotAvailability();
              }
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey[300]!),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.calendar_today, size: 18, color: Color(0xFF52C41A)),
                  const SizedBox(width: 8),
                  Text(
                    _selectedDate != null
                        ? '${_selectedDate!.year}-${_selectedDate!.month.toString().padLeft(2, '0')}-${_selectedDate!.day.toString().padLeft(2, '0')}'
                        : '请选择预约日期',
                    style: TextStyle(
                      fontSize: 14,
                      color: _selectedDate != null ? Colors.black87 : Colors.grey[400],
                    ),
                  ),
                  const Spacer(),
                  Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text('选择时段', style: TextStyle(fontSize: 14, color: Colors.grey[700])),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: hasTimeSlots
                ? _product.timeSlots!.map((slot) {
                    final label = '${slot['start'] ?? ''}-${slot['end'] ?? ''}';
                    final endTime = slot['end'] ?? '';
                    final expired = _isSlotExpired(endTime);
                    final fullyBooked = _isSlotFullyBooked(label);
                    final disabled = expired || fullyBooked;
                    final chipLabel = fullyBooked && !expired ? '$label 已约满' : label;
                    return ChoiceChip(
                      label: Text(
                        chipLabel,
                        style: TextStyle(
                          color: disabled ? const Color(0xFF999999) : null,
                        ),
                      ),
                      selected: _selectedTimeSlot == label,
                      selectedColor: const Color(0xFFD9F7BE),
                      disabledColor: const Color(0xFFF5F5F5),
                      onSelected: disabled
                          ? null
                          : (selected) {
                              setState(() => _selectedTimeSlot = selected ? label : null);
                            },
                    );
                  }).toList()
                : defaultTimeSlots.map((slot) {
                    return ChoiceChip(
                      label: Text(slot),
                      selected: _selectedTimeSlot == slot,
                      selectedColor: const Color(0xFFD9F7BE),
                      onSelected: (selected) {
                        setState(() => _selectedTimeSlot = selected ? slot : null);
                      },
                    );
                  }).toList(),
          ),
          const SizedBox(height: 12),
          // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系手机号
          TextField(
            controller: _contactPhoneController,
            keyboardType: TextInputType.phone,
            maxLength: 11,
            decoration: InputDecoration(
              labelText: '联系手机号',
              hintText: '请输入联系手机号',
              errorText: _contactPhoneError,
              border: const OutlineInputBorder(),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              counterText: '',
            ),
            style: const TextStyle(fontSize: 14),
            onChanged: (_) => setState(() => _contactPhoneError = null),
          ),
          const SizedBox(height: 12),
          TextField(
            decoration: const InputDecoration(
              hintText: '预约备注（选填，最多 50 字）',
              border: OutlineInputBorder(),
              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              hintStyle: TextStyle(fontSize: 14),
            ),
            maxLines: 2,
            maxLength: 50,
            style: const TextStyle(fontSize: 14),
            onChanged: (v) => _appointmentNote = v,
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
