class Coupon {
  final int id;
  final String name;
  final String type;
  final double conditionAmount;
  final double discountValue;
  final double discountRate;
  final String scope;
  final dynamic scopeIds;
  final int totalCount;
  final int claimedCount;
  final int usedCount;
  final String? validStart;
  final String? validEnd;
  final String status;
  final String? createdAt;
  // V2.1：领券中心置灰新增字段
  final bool claimed;
  final bool soldOut;
  final String buttonText;
  final bool buttonDisabled;
  final bool isOffline;

  Coupon({
    required this.id,
    required this.name,
    required this.type,
    this.conditionAmount = 0,
    this.discountValue = 0,
    this.discountRate = 1.0,
    this.scope = 'all',
    this.scopeIds,
    this.totalCount = 0,
    this.claimedCount = 0,
    this.usedCount = 0,
    this.validStart,
    this.validEnd,
    this.status = 'active',
    this.createdAt,
    this.claimed = false,
    this.soldOut = false,
    this.buttonText = '领取',
    this.buttonDisabled = false,
    this.isOffline = false,
  });

  String get typeLabel {
    switch (type) {
      case 'full_reduction':
        return '满减券';
      case 'discount':
        return '折扣券';
      case 'voucher':
        return '代金券';
      case 'free_trial':
        return '免费试用';
      default:
        return type;
    }
  }

  String get discountText {
    switch (type) {
      case 'full_reduction':
        return '满${conditionAmount.toInt()}减${discountValue.toInt()}';
      case 'discount':
        return '${(discountRate * 10).toStringAsFixed(1)}折';
      case 'voucher':
        return '¥${discountValue.toInt()}';
      // [优惠券下单页 Bug 修复 v2 · B1] free_trial：整单 0 元抵扣
      case 'free_trial':
        return '凭券免费试用';
      default:
        return '';
    }
  }

  int get remaining => totalCount > 0 ? totalCount - claimedCount : -1;

  factory Coupon.fromJson(Map<String, dynamic> json) {
    return Coupon(
      id: json['id'] ?? 0,
      name: json['name'] ?? '',
      type: json['type'] ?? 'voucher',
      conditionAmount: (json['condition_amount'] ?? 0).toDouble(),
      discountValue: (json['discount_value'] ?? 0).toDouble(),
      discountRate: (json['discount_rate'] ?? 1.0).toDouble(),
      scope: json['scope'] ?? 'all',
      scopeIds: json['scope_ids'],
      totalCount: json['total_count'] ?? 0,
      claimedCount: json['claimed_count'] ?? 0,
      usedCount: json['used_count'] ?? 0,
      validStart: json['valid_start']?.toString(),
      validEnd: json['valid_end']?.toString(),
      status: json['status'] ?? 'active',
      createdAt: json['created_at']?.toString(),
      claimed: json['claimed'] == true,
      soldOut: json['sold_out'] == true,
      buttonText: (json['button_text'] as String?) ?? '领取',
      buttonDisabled: json['button_disabled'] == true,
      isOffline: json['is_offline'] == true,
    );
  }
}

class UserCoupon {
  final int id;
  final int userId;
  final int couponId;
  final String status;
  final String? usedAt;
  final int? orderId;
  final String? createdAt;
  final Coupon? coupon;

  UserCoupon({
    required this.id,
    required this.userId,
    required this.couponId,
    required this.status,
    this.usedAt,
    this.orderId,
    this.createdAt,
    this.coupon,
  });

  String get statusLabel {
    switch (status) {
      case 'unused':
        return '未使用';
      case 'used':
        return '已使用';
      case 'expired':
        return '已过期';
      default:
        return status;
    }
  }

  factory UserCoupon.fromJson(Map<String, dynamic> json) {
    return UserCoupon(
      id: json['id'] ?? 0,
      userId: json['user_id'] ?? 0,
      couponId: json['coupon_id'] ?? 0,
      status: json['status'] ?? 'unused',
      usedAt: json['used_at']?.toString(),
      orderId: json['order_id'],
      createdAt: json['created_at']?.toString(),
      coupon: json['coupon'] != null
          ? Coupon.fromJson(json['coupon'] as Map<String, dynamic>)
          : null,
    );
  }
}
