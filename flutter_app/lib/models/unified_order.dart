class OrderItem {
  final int id;
  final int orderId;
  final int productId;
  final String productName;
  final String? productImage;
  final double productPrice;
  final int quantity;
  final double subtotal;
  final String fulfillmentType;
  final String? verificationCode;
  final String? verificationQrcodeToken;
  final int totalRedeemCount;
  final int usedRedeemCount;
  final dynamic appointmentData;
  final String? appointmentTime;
  final String? createdAt;

  OrderItem({
    required this.id,
    required this.orderId,
    required this.productId,
    required this.productName,
    this.productImage,
    required this.productPrice,
    required this.quantity,
    required this.subtotal,
    required this.fulfillmentType,
    this.verificationCode,
    this.verificationQrcodeToken,
    this.totalRedeemCount = 0,
    this.usedRedeemCount = 0,
    this.appointmentData,
    this.appointmentTime,
    this.createdAt,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) {
    return OrderItem(
      id: json['id'] ?? 0,
      orderId: json['order_id'] ?? 0,
      productId: json['product_id'] ?? 0,
      productName: json['product_name'] ?? '',
      productImage: json['product_image'],
      productPrice: (json['product_price'] ?? 0).toDouble(),
      quantity: json['quantity'] ?? 1,
      subtotal: (json['subtotal'] ?? 0).toDouble(),
      fulfillmentType: json['fulfillment_type'] ?? 'in_store',
      verificationCode: json['verification_code'],
      verificationQrcodeToken: json['verification_qrcode_token'],
      totalRedeemCount: json['total_redeem_count'] ?? 0,
      usedRedeemCount: json['used_redeem_count'] ?? 0,
      appointmentData: json['appointment_data'],
      appointmentTime: json['appointment_time']?.toString(),
      createdAt: json['created_at']?.toString(),
    );
  }
}

class UnifiedOrder {
  final int id;
  final String orderNo;
  final int userId;
  final double totalAmount;
  final double paidAmount;
  final int pointsDeduction;
  final String? paymentMethod;
  final int? couponId;
  final double couponDiscount;
  final String status;
  final String refundStatus;
  final int? shippingAddressId;
  final dynamic shippingInfo;
  final int? serviceAddressId;
  final dynamic serviceAddressSnapshot;
  final String? trackingNumber;
  final String? trackingCompany;
  final String? notes;
  final int paymentTimeoutMinutes;
  final String? paidAt;
  final String? shippedAt;
  final String? receivedAt;
  final String? completedAt;
  final String? cancelledAt;
  final String? cancelReason;
  final int autoConfirmDays;
  final List<OrderItem> items;
  final String? createdAt;
  final String? updatedAt;
  final String? displayStatus;
  final String? displayStatusColor;
  final List<String> actionButtons;

  UnifiedOrder({
    required this.id,
    required this.orderNo,
    required this.userId,
    required this.totalAmount,
    required this.paidAmount,
    this.pointsDeduction = 0,
    this.paymentMethod,
    this.couponId,
    this.couponDiscount = 0,
    required this.status,
    this.refundStatus = 'none',
    this.shippingAddressId,
    this.shippingInfo,
    this.serviceAddressId,
    this.serviceAddressSnapshot,
    this.trackingNumber,
    this.trackingCompany,
    this.notes,
    this.paymentTimeoutMinutes = 15,
    this.paidAt,
    this.shippedAt,
    this.receivedAt,
    this.completedAt,
    this.cancelledAt,
    this.cancelReason,
    this.autoConfirmDays = 7,
    this.items = const [],
    this.createdAt,
    this.updatedAt,
    this.displayStatus,
    this.displayStatusColor,
    this.actionButtons = const [],
  });

  String get statusLabel {
    switch (status) {
      case 'pending_payment':
        return '待支付';
      case 'pending_shipment':
        return '待发货';
      case 'pending_receipt':
        return '待收货';
      case 'pending_appointment':
        return '待预约';
      case 'appointed':
        return '待核销';
      case 'pending_use':
        return '待核销';
      case 'partial_used':
        return '部分核销';
      case 'pending_review':
        return '待评价';
      case 'completed':
        return '已完成';
      case 'expired':
        return '已过期';
      case 'refunding':
        return '退款中';
      case 'refunded':
        return '已退款';
      case 'cancelled':
        return '已取消';
      default:
        return status;
    }
  }

  String get displayStatusLabel {
    if (displayStatus != null && displayStatus!.isNotEmpty) {
      return displayStatus!;
    }
    return statusLabel;
  }

  factory UnifiedOrder.fromJson(Map<String, dynamic> json) {
    return UnifiedOrder(
      id: json['id'] ?? 0,
      orderNo: json['order_no'] ?? '',
      userId: json['user_id'] ?? 0,
      totalAmount: (json['total_amount'] ?? 0).toDouble(),
      paidAmount: (json['paid_amount'] ?? 0).toDouble(),
      pointsDeduction: json['points_deduction'] ?? 0,
      paymentMethod: json['payment_method'],
      couponId: json['coupon_id'],
      couponDiscount: (json['coupon_discount'] ?? 0).toDouble(),
      status: json['status'] ?? 'pending_payment',
      refundStatus: json['refund_status'] ?? 'none',
      shippingAddressId: json['shipping_address_id'],
      shippingInfo: json['shipping_info'],
      serviceAddressId: json['service_address_id'],
      serviceAddressSnapshot: json['service_address_snapshot'],
      trackingNumber: json['tracking_number'],
      trackingCompany: json['tracking_company'],
      notes: json['notes'],
      paymentTimeoutMinutes: json['payment_timeout_minutes'] ?? 15,
      paidAt: json['paid_at']?.toString(),
      shippedAt: json['shipped_at']?.toString(),
      receivedAt: json['received_at']?.toString(),
      completedAt: json['completed_at']?.toString(),
      cancelledAt: json['cancelled_at']?.toString(),
      cancelReason: json['cancel_reason'],
      autoConfirmDays: json['auto_confirm_days'] ?? 7,
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => OrderItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      createdAt: json['created_at']?.toString(),
      updatedAt: json['updated_at']?.toString(),
      displayStatus: json['display_status']?.toString(),
      displayStatusColor: json['display_status_color']?.toString(),
      actionButtons: (json['action_buttons'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
    );
  }
}
