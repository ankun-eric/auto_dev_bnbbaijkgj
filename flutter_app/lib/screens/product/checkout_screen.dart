import 'package:flutter/material.dart';
import '../../models/product.dart';
import '../../models/address.dart';
import '../../models/coupon.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';

class CheckoutScreen extends StatefulWidget {
  /// OPT-1：构造参数 initialCouponId — 带券下单时由上游透传
  final int? initialCouponId;
  const CheckoutScreen({super.key, this.initialCouponId});

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
  // OPT-1：带券下单 — 优先级：路由 args > 构造参数
  int? _initialCouponId;
  int _pointsDeduction = 0;
  bool _submitting = false;
  final TextEditingController _notesController = TextEditingController();
  // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系手机号
  final TextEditingController _contactPhoneController = TextEditingController();
  String? _contactPhoneError;

  DateTime? _selectedDate = DateTime.now();
  String? _selectedTimeSlot;
  String _appointmentNote = '';
  // [PRD v1.0 2026-05-04 用户端下单页时段网格化展示与满额置灰]
  // 后端 /api/h5/checkout/info 返回的两组满额信息：
  //   _slotAvailability：time_slot 模式时段 [{start_time,end_time,is_available,unavailable_reason}]
  //   _availableDates：date 模式日期 [{date,is_available,unavailable_reason}]
  List<Map<String, dynamic>> _slotAvailability = [];
  List<Map<String, dynamic>> _availableDates = [];

  // [H5 支付链路修复 v1.0] 支付方式
  List<Map<String, dynamic>> _paymentMethods = [];
  String? _selectedChannelCode;

  bool _depsParsed = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_depsParsed) return;
    _depsParsed = true;
    final args = ModalRoute.of(context)!.settings.arguments as Map<String, dynamic>;
    _product = args['product'] as Product;
    _quantity = args['quantity'] as int;
    // OPT-1：路由 args 中的 initialCouponId 优先于构造参数
    final routeCid = args['initialCouponId'];
    if (routeCid is int) {
      _initialCouponId = routeCid;
    } else if (routeCid != null) {
      _initialCouponId = int.tryParse('$routeCid');
    }
    _initialCouponId ??= widget.initialCouponId;
    _loadAddresses();
    _loadCoupons();
    _loadSlotAvailability();
    _loadPaymentMethods();
  }

  Future<void> _loadPaymentMethods() async {
    try {
      final res = await _api.getAvailablePayMethods(platform: 'app');
      final raw = res.data;
      List list = [];
      if (raw is List) {
        list = raw;
      } else if (raw is Map && raw['data'] is List) {
        list = raw['data'] as List;
      }
      setState(() {
        _paymentMethods = list
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        if (_paymentMethods.isNotEmpty) {
          _selectedChannelCode =
              _paymentMethods.first['channel_code'] as String?;
        }
      });
    } catch (_) {
      setState(() => _paymentMethods = []);
    }
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
    // [优惠券下单页 Bug 修复 v2 · B3] 切换为下单页专用接口（仅返回本单可用的券）
    try {
      final res = await _api.getUsableCouponsForOrder(
        productId: _product.id,
        subtotal: _subtotal,
      );
      if (res.data is Map && res.data['items'] is List) {
        setState(() {
          _coupons = (res.data['items'] as List)
              .map((e) => UserCoupon.fromJson(e as Map<String, dynamic>))
              .toList();
          // OPT-1：若上游带券进入下单页，则默认选中该券（命中 user_coupon_id）
          if (_selectedCoupon == null && _initialCouponId != null) {
            for (final uc in _coupons) {
              if (uc.id == _initialCouponId) {
                _selectedCoupon = uc;
                break;
              }
            }
          }
          // 已选的券若不再可用则清空
          if (_selectedCoupon != null &&
              !_coupons.any((uc) => uc.id == _selectedCoupon!.id)) {
            _selectedCoupon = null;
          }
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
  // [预约日期模式 Bug 修复 v1.0]
  // 把 _needAppointment 进一步按预约模式拆分：
  //   - _needDate     : date / time_slot 两种模式都要选日期
  //   - _needTimeSlot : 仅 time_slot 模式要选时段；date 模式按设计只按天限流，绝不再渲染时段
  bool get _needDate =>
      _needAppointment && (_product.appointmentMode == 'date' || _product.appointmentMode == 'time_slot');
  bool get _needTimeSlot =>
      _needAppointment && _product.appointmentMode == 'time_slot';

  // [PRD v1.0 2026-05-04 §6.1] 改为调用 /api/h5/checkout/info 拉取满额数据。
  // 进入页面 + 切换日期时调用，无轮询。
  Future<void> _loadSlotAvailability() async {
    if (!_needAppointment) return;
    if (_selectedDate == null) return;
    try {
      final dateStr = _formatDate(_selectedDate!);
      final res = await _api.get('/api/h5/checkout/info?productId=${_product.id}&date=$dateStr');
      if (res.data is Map && res.data['data'] is Map) {
        final data = res.data['data'] as Map;
        final slots = data['available_slots'];
        final dates = data['available_dates'];
        setState(() {
          _slotAvailability = slots is List
              ? slots.map((e) => Map<String, dynamic>.from(e as Map)).toList()
              : [];
          _availableDates = dates is List
              ? dates.map((e) => Map<String, dynamic>.from(e as Map)).toList()
              : [];
        });
      }
    } catch (_) {
      setState(() {
        _slotAvailability = [];
        _availableDates = [];
      });
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

  // [PRD v1.0 2026-05-04 §4.2] 满额判定：基于后端 is_available + unavailable_reason
  bool _isSlotFullyBooked(String label) {
    final avail = _slotAvailability.where((s) =>
      '${s['start_time']}-${s['end_time']}' == label
    ).toList();
    if (avail.isEmpty) return false;
    final first = avail.first;
    if (first.containsKey('is_available')) {
      return first['is_available'] == false && first['unavailable_reason'] == 'occupied';
    }
    // 兼容旧返回结构
    return (first['available'] ?? 1) <= 0;
  }

  // 当前选中日期是否已约满（date 模式专用）
  bool get _isSelectedDateFull {
    if (_selectedDate == null) return false;
    final dateStr = _formatDate(_selectedDate!);
    final found = _availableDates.where((d) => d['date'] == dateStr).toList();
    if (found.isEmpty) return false;
    return found.first['is_available'] == false &&
        found.first['unavailable_reason'] == 'occupied';
  }

  // 指定日期是否已约满（用于 selectableDayPredicate 置灰日历）
  bool _isDateFull(DateTime d) {
    final dateStr = _formatDate(d);
    final found = _availableDates.where((it) => it['date'] == dateStr).toList();
    if (found.isEmpty) return false;
    return found.first['is_available'] == false &&
        found.first['unavailable_reason'] == 'occupied';
  }

  double get _subtotal => _product.salePrice * _quantity;

  double get _couponDiscount {
    if (_selectedCoupon?.coupon == null) return 0;
    final c = _selectedCoupon!.coupon!;
    // [优惠券下单页 Bug 修复 v2 · B1] free_trial：整单 0 元抵扣，不受 condition_amount 限制
    if (c.type == 'free_trial') {
      return _subtotal;
    }
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

  bool get _needAddress => _product.fulfillmentType == 'delivery' || _product.fulfillmentType == 'on_site';

  String _formatDate(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _submitOrder() async {
    if (_needAddress && _selectedAddress == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择收货地址')));
      return;
    }

    if (_needDate && _selectedDate == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择预约日期')));
      return;
    }
    // [PRD v1.0 2026-05-04 §4.1.2] date 模式下选中已约满日期 → 禁止提交（前端兜底，后端会再次校验）
    if (_needDate && _product.appointmentMode == 'date' && _isSelectedDateFull) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('所选日期已约满，请重新选择')),
      );
      return;
    }
    // [预约日期模式 Bug 修复 v1.0] time_slot 模式才校验时段
    if (_needTimeSlot && (_selectedTimeSlot == null || _selectedTimeSlot!.isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请选择预约时段')));
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
        // [预约日期模式 Bug 修复 v1.0]
        // time_slot 模式：appointment_time = date+slot.start；appointment_data 携带 time_slot
        // date     模式：appointment_time = date+00:00:00；appointment_data 不携带 time_slot
        if (_needTimeSlot && _selectedTimeSlot != null) {
          itemData['appointment_time'] = '${dateStr}T${_selectedTimeSlot!.split('-').first}:00';
        } else {
          itemData['appointment_time'] = '${dateStr}T00:00:00';
        }
        final apptData = <String, dynamic>{
          'date': dateStr,
          'note': _appointmentNote,
          'contact_phone': phone,
        };
        if (_needTimeSlot && _selectedTimeSlot != null) {
          apptData['time_slot'] = _selectedTimeSlot;
        }
        itemData['appointment_data'] = apptData;
      }

      // [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0]
      // 创建订单的 payment_method 必须为 provider 级别（wechat / alipay），
      // _selectedChannelCode 是通道级别（如 alipay_app / wechat_app），
      // 从 _paymentMethods 列表中按 channel_code 查找对应 provider，
      // 找不到则按 _ 前缀降级提取，确保后端入库的 payment_method 仅为 wechat / alipay。
      String? _providerForOrder;
      if (_selectedChannelCode != null && _selectedChannelCode!.isNotEmpty) {
        final matched = _paymentMethods.firstWhere(
          (m) => (m['channel_code'] as String?) == _selectedChannelCode,
          orElse: () => <String, dynamic>{},
        );
        final p = matched['provider'] as String?;
        if (p != null && p.isNotEmpty) {
          _providerForOrder = p;
        } else {
          _providerForOrder = _selectedChannelCode!.split('_').first;
        }
      }

      final data = <String, dynamic>{
        'items': [itemData],
        // [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0] 仅传 provider 级别值
        if (_providerForOrder != null) 'payment_method': _providerForOrder,
        'points_deduction': _pointsDeduction,
        'notes': _notesController.text.isNotEmpty ? _notesController.text : null,
      };

      if (_selectedCoupon != null) {
        data['coupon_id'] = _selectedCoupon!.couponId;
      }
      if (_selectedAddress != null) {
        if (_product.fulfillmentType == 'on_site') {
          data['service_address_id'] = _selectedAddress!.id;
        } else {
          data['shipping_address_id'] = _selectedAddress!.id;
        }
      }

      final res = await _api.createUnifiedOrder(data);
      if (!mounted) return;
      final orderMap =
          res.data is Map ? Map<String, dynamic>.from(res.data as Map) : null;
      if (orderMap == null || orderMap['id'] == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('创建订单失败')),
        );
        return;
      }
      final orderId = orderMap['id'] as int;
      final paidAmount = (orderMap['paid_amount'] is num)
          ? (orderMap['paid_amount'] as num).toDouble()
          : 0.0;

      if (paidAmount == 0) {
        try {
          await _api.confirmFreeUnifiedOrder(
            orderId,
            channelCode: _selectedChannelCode,
          );
        } catch (_) {
          // 即便失败也继续跳详情，由详情页继续处理
        }
        if (!mounted) return;
        Navigator.pushReplacementNamed(
          context,
          '/unified-order-detail',
          arguments: orderId,
        );
        return;
      }

      if (_selectedChannelCode == null || _selectedChannelCode!.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('请选择支付方式')),
        );
        return;
      }

      try {
        final payRes = await _api.payUnifiedOrder(
          orderId,
          channelCode: _selectedChannelCode,
        );
        final payData = payRes.data is Map ? payRes.data as Map : null;
        final payUrl = payData?['pay_url'] as String?;
        if (!mounted) return;
        if (payUrl != null && payUrl.isNotEmpty) {
          // 本期简化：先用 SnackBar 引导，后续接入 url_launcher.launchUrl(Uri.parse(payUrl))
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('请在浏览器中完成支付：$payUrl')),
          );
        }
        Navigator.pushReplacementNamed(
          context,
          '/unified-order-detail',
          arguments: orderId,
        );
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('支付失败：$e')),
        );
        Navigator.pushReplacementNamed(
          context,
          '/unified-order-detail',
          arguments: orderId,
        );
      }
    } catch (e) {
      if (mounted) {
        final msg = e.toString().contains('detail')
            ? RegExp(r'"detail"\s*:\s*"([^"]*)"').firstMatch(e.toString())?.group(1) ?? '下单失败'
            : '下单失败';
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
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
            _buildPaymentMethodSection(),
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
                // [PRD v1.0 2026-05-04 §4.1.2] 日历组件：已约满日期置灰且不可选
                selectableDayPredicate: (d) => !_isDateFull(d),
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
                  if (_isSelectedDateFull) ...[
                    const SizedBox(width: 8),
                    const Text(
                      '已约满',
                      style: TextStyle(color: Color(0xFFFF4D4F), fontSize: 12),
                    ),
                  ],
                  const Spacer(),
                  Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
                ],
              ),
            ),
          ),
          // [预约日期模式 Bug 修复 v1.0] 仅 time_slot 模式才渲染整块时段；date 模式按设计只按天限流，不展示时段
          // [PRD v1.0 2026-05-04 §4.1.1] 时段每行 3 个固定网格（GridView.count(crossAxisCount: 3)），
          // 与「订单详情→修改时间」一致；满额时段灰底灰字 + 红色"已约满"角标，完全不可点击。
          if (_needTimeSlot) ...[
          const SizedBox(height: 12),
          Text('选择时段', style: TextStyle(fontSize: 14, color: Colors.grey[700])),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 2.6,
            children: (hasTimeSlots
                    ? _product.timeSlots!.map<Map<String, dynamic>>((slot) => {
                          'label': '${slot['start'] ?? ''}-${slot['end'] ?? ''}',
                          'end': (slot['end'] ?? '') as String,
                        }).toList()
                    : defaultTimeSlots
                        .map<Map<String, dynamic>>((s) => {'label': s, 'end': s})
                        .toList())
                .map((m) {
              final label = m['label'] as String;
              final endTime = m['end'] as String;
              final expired = _isSlotExpired(endTime);
              final fullyBooked = _isSlotFullyBooked(label);
              final disabled = expired || fullyBooked;
              final active = _selectedTimeSlot == label;
              return GestureDetector(
                onTap: disabled
                    ? null
                    : () => setState(() => _selectedTimeSlot = active ? null : label),
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        color: fullyBooked
                            ? const Color(0xFFF5F5F5)
                            : (active ? const Color(0xFF52C41A) : Colors.white),
                        border: Border.all(
                          color: fullyBooked
                              ? const Color(0xFFE5E5E5)
                              : (active
                                  ? const Color(0xFF52C41A)
                                  : Colors.grey.shade300),
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        label + (expired && !fullyBooked ? ' 已结束' : ''),
                        style: TextStyle(
                          color: fullyBooked
                              ? const Color(0xFF999999)
                              : (active
                                  ? Colors.white
                                  : (expired ? Colors.grey : Colors.black87)),
                          fontSize: 13,
                        ),
                      ),
                    ),
                    if (fullyBooked)
                      Positioned(
                        top: -6,
                        right: -2,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFF4D4F),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            '已约满',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 10,
                              height: 1.3,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              );
            }).toList(),
          ),
          ], // end if (_needTimeSlot)
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

  // [H5 支付链路修复 v1.0] 支付方式选择区块
  Widget _buildPaymentMethodSection() {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '支付方式',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          if (_paymentMethods.isEmpty)
            const Text(
              '暂未开通支付方式，请联系管理员',
              style: TextStyle(color: Color(0xFF999999), fontSize: 13),
            )
          else
            ..._paymentMethods.map((m) {
              final code = m['channel_code'] as String?;
              final name = m['display_name'] as String? ?? '';
              return RadioListTile<String>(
                value: code ?? '',
                groupValue: _selectedChannelCode ?? '',
                onChanged: (v) =>
                    setState(() => _selectedChannelCode = v),
                title: Text(name),
                contentPadding: EdgeInsets.zero,
                dense: true,
              );
            }),
        ],
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
            // [优惠券下单页 Bug 修复 v2 · B4] 用 Radio 圆点 + Row(crossAxisAlignment.center)
            // 让圆点与文字（标题/副标题两行）整体垂直居中，三端视觉统一
            ListTile(
              leading: Radio<int?>(
                value: -1,
                groupValue: _selectedCoupon == null ? -1 : _selectedCoupon!.id,
                onChanged: (_) {
                  setState(() => _selectedCoupon = null);
                  Navigator.pop(ctx);
                },
                activeColor: const Color(0xFF52C41A),
              ),
              title: const Text('不使用优惠券'),
              onTap: () {
                setState(() => _selectedCoupon = null);
                Navigator.pop(ctx);
              },
            ),
            ...(_coupons.map((uc) {
              final c = uc.coupon;
              if (c == null) return const SizedBox.shrink();
              return ListTile(
                leading: Radio<int>(
                  value: uc.id,
                  groupValue: _selectedCoupon?.id ?? -1,
                  onChanged: (_) {
                    setState(() => _selectedCoupon = uc);
                    Navigator.pop(ctx);
                  },
                  activeColor: const Color(0xFF52C41A),
                ),
                title: Text(c.name),
                subtitle: Text(c.discountText),
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
