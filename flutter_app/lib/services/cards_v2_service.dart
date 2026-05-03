/// 卡管理 v2.0（第 2~5 期）Flutter 端 API 客户端封装。
import 'package:dio/dio.dart';
import 'api_service.dart';

class CardsV2Service {
  final Dio _dio = ApiService().dio;

  Future<Map<String, dynamic>> purchase({required int cardDefinitionId, int? fromProductId, int? renewFromUserCardId}) async {
    final r = await _dio.post('/api/cards/purchase', data: {
      'card_definition_id': cardDefinitionId,
      if (fromProductId != null) 'from_product_id': fromProductId,
      if (renewFromUserCardId != null) 'renew_from_user_card_id': renewFromUserCardId,
    });
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> payCardOrder(int orderId) async {
    final r = await _dio.post('/api/orders/unified/$orderId/pay-card');
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> issueRedemptionCode(int userCardId) async {
    final r = await _dio.post('/api/cards/me/$userCardId/redemption-code');
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>?> getCurrentRedemptionCode(int userCardId) async {
    final r = await _dio.get('/api/cards/me/$userCardId/redemption-code/current');
    if (r.data == null) return null;
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> myUsageLogs(int userCardId, {int page = 1, int pageSize = 20}) async {
    final r = await _dio.get('/api/cards/me/$userCardId/usage-logs', queryParameters: {
      'page': page,
      'page_size': pageSize,
    });
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> renewCard(int userCardId) async {
    final r = await _dio.post('/api/cards/me/$userCardId/renew', data: {'payment_method': 'wechat'});
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> savingsTip(int productId) async {
    final r = await _dio.get('/api/products/$productId/savings-tip');
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> renewableCards() async {
    final r = await _dio.get('/api/cards/me/renewable');
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> refundCardOrder(int orderId) async {
    final r = await _dio.post('/api/orders/unified/$orderId/refund-card');
    return Map<String, dynamic>.from(r.data);
  }

  Future<Map<String, dynamic>> checkout(List<Map<String, dynamic>> items, {String? notes}) async {
    final r = await _dio.post('/api/orders/unified/checkout', data: {
      'items': items,
      if (notes != null) 'notes': notes,
    });
    return Map<String, dynamic>.from(r.data);
  }

  String sharePosterUrl(int cardId, {int? inviterUserId}) {
    final qs = inviterUserId != null ? '?inviter_user_id=$inviterUserId' : '';
    return '/api/cards/$cardId/share-poster$qs';
  }
}
