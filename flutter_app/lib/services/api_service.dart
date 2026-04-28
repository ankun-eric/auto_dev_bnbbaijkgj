import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;

  late Dio _dio;
  Dio get dio => _dio;

  ApiService._internal() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final prefs = await SharedPreferences.getInstance();
        final token = prefs.getString('access_token');
        if (token != null && token.isNotEmpty) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        return handler.next(options);
      },
      onResponse: (response, handler) {
        return handler.next(response);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          final refreshed = await _refreshToken();
          if (refreshed) {
            final retryResponse = await _retry(error.requestOptions);
            return handler.resolve(retryResponse);
          }
        }
        return handler.next(error);
      },
    ));

    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
    ));
  }

  Future<bool> _refreshToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final refreshToken = prefs.getString('refresh_token');
      if (refreshToken == null || refreshToken.isEmpty) return false;

      final response = await Dio().post(
        '${ApiConfig.baseUrl}${ApiConfig.refreshToken}',
        data: {'refresh_token': refreshToken},
      );

      if (response.statusCode == 200 && response.data is Map) {
        final body = response.data as Map;
        final at = body['access_token']?.toString();
        if (at == null || at.isEmpty) return false;
        await prefs.setString('access_token', at);
        final rt = body['refresh_token']?.toString();
        if (rt != null && rt.isNotEmpty) {
          await prefs.setString('refresh_token', rt);
        }
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<Response> _retry(RequestOptions requestOptions) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    final options = Options(
      method: requestOptions.method,
      headers: {...requestOptions.headers, 'Authorization': 'Bearer $token'},
    );
    return _dio.request(
      requestOptions.path,
      data: requestOptions.data,
      queryParameters: requestOptions.queryParameters,
      options: options,
    );
  }

  // 通用 HTTP 便捷方法 — 供新页面（积分商品详情、评论）直接调用任意 URL
  Future<Response> get(String path, {Map<String, dynamic>? query}) async {
    return _dio.get(path, queryParameters: query);
  }

  Future<Response> post(String path, {dynamic data, Map<String, dynamic>? query}) async {
    return _dio.post(path, data: data, queryParameters: query);
  }

  // Auth
  Future<Response> getRegisterSettings() async {
    return _dio.get(ApiConfig.registerSettings);
  }

  Future<Response> login(String phone, String code, {String? referrerNo}) async {
    final data = <String, dynamic>{'phone': phone, 'code': code};
    if (referrerNo != null && referrerNo.isNotEmpty) {
      data['referrer_no'] = referrerNo;
    }
    return _dio.post(ApiConfig.login, data: data);
  }

  Future<Response> sendSmsCode(String phone) async {
    return _dio.post(ApiConfig.sendSmsCode, data: {'phone': phone, 'type': 'login'});
  }

  Future<Response> wechatLogin(String code) async {
    return _dio.post(ApiConfig.wechatLogin, data: {'code': code});
  }

  Future<Response> appleLogin(String identityToken) async {
    return _dio.post(ApiConfig.appleLogin, data: {'identity_token': identityToken});
  }

  Future<Response?> logout() async {
    try {
      return await _dio.post(ApiConfig.logout);
    } catch (_) {
      return null;
    }
  }

  // User
  Future<Response> getShareLink() async {
    return _dio.get(ApiConfig.shareLink);
  }

  Future<Response> getUserProfile() async {
    return _dio.get(ApiConfig.userProfile);
  }

  Future<Response> updateProfile(Map<String, dynamic> data) async {
    return _dio.put(ApiConfig.updateProfile, data: data);
  }

  Future<Response> uploadAvatar(String filePath, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'avatar': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.uploadAvatar, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> getMyStats() async {
    return _dio.get(ApiConfig.myStats);
  }

  // Health
  Future<Response> getHealthProfile() async {
    return _dio.get(ApiConfig.healthProfile);
  }

  Future<Response> updateHealthProfile(Map<String, dynamic> data) async {
    return _dio.put(ApiConfig.updateHealthProfile, data: data);
  }

  Future<Response> updateMemberHealthProfile(int memberId, Map<String, dynamic> data) async {
    return _dio.put('${ApiConfig.updateMemberHealthProfile}/$memberId', data: data);
  }

  Future<Response> getMemberHealthProfile(int memberId) async {
    return _dio.get('${ApiConfig.updateMemberHealthProfile}/$memberId');
  }

  Future<Response> getDiseasePresets(String category) async {
    return _dio.get(ApiConfig.diseasePresets, queryParameters: {'category': category});
  }

  Future<Response> postGuideStatus() async {
    return _dio.post(ApiConfig.guideStatus);
  }

  Future<Response> getHealthRecords({int page = 1, int pageSize = 20}) async {
    return _dio.get(ApiConfig.healthRecords, queryParameters: {'page': page, 'page_size': pageSize});
  }

  // Chat
  Future<Response> getChatSessions() async {
    return _dio.get(ApiConfig.chatSessions);
  }

  Future<Response> getChatMessages(String sessionId, {int page = 1}) async {
    return _dio.get('${ApiConfig.chatSessions}/$sessionId/messages', queryParameters: {'page': page});
  }

  Future<Response> sendMessage(String sessionId, String content, {String type = 'text'}) async {
    return _dio.post('${ApiConfig.chatSessions}/$sessionId/messages', data: {
      'content': content,
      'message_type': type,
    });
  }

  Future<Response> createChatSession(String type) async {
    return _dio.post(ApiConfig.createSession, data: {'session_type': type});
  }

  Future<Response> postChatKnowledgeFeedback(int hitLogId, String feedback) async {
    return _dio.post(
      ApiConfig.chatKnowledgeFeedback,
      data: {'hit_log_id': hitLogId, 'feedback': feedback},
    );
  }

  // Chat History
  Future<Response> getChatSessionsList({int page = 1, int pageSize = 100}) async {
    return _dio.get(ApiConfig.chatSessionsList, queryParameters: {'page': page, 'page_size': pageSize});
  }

  Future<Response> getChatSessionDetail(String sessionId) async {
    return _dio.get('${ApiConfig.chatSessionsList}/$sessionId');
  }

  Future<Response> deleteChatSession(String sessionId) async {
    return _dio.delete('${ApiConfig.chatSessionsList}/$sessionId');
  }

  Future<Response> renameChatSession(String sessionId, String title) async {
    return _dio.put('${ApiConfig.chatSessionsList}/$sessionId', data: {'title': title});
  }

  Future<Response> pinChatSession(String sessionId, bool isPinned) async {
    return _dio.put('${ApiConfig.chatSessionsList}/$sessionId/pin', data: {'is_pinned': isPinned});
  }

  Future<Response> shareChatSession(String sessionId) async {
    return _dio.post('${ApiConfig.chatSessionsList}/$sessionId/share');
  }

  // Checkup
  Future<Response> getCheckupReports({int page = 1}) async {
    return _dio.get(ApiConfig.checkupReports, queryParameters: {'page': page});
  }

  Future<Response> uploadCheckupReport(String filePath, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.uploadCheckup, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> analyzeCheckup(String reportId) async {
    return _dio.post(ApiConfig.analyzeCheckup, data: {'report_id': int.tryParse(reportId) ?? reportId});
  }

  // Report (intelligent analysis)
  Future<Response> uploadReport(String filePath, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.reportUpload, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> analyzeReport(int reportId) async {
    return _dio.post(ApiConfig.reportAnalyze, data: {'report_id': reportId});
  }

  Future<Response> getReportDetail(int id) async {
    return _dio.get('${ApiConfig.reportDetail}/$id');
  }

  Future<Response> getReportList({int page = 1, int pageSize = 20}) async {
    return _dio.get(ApiConfig.reportList, queryParameters: {
      'page': page,
      'page_size': pageSize,
    });
  }

  Future<Response> getIndicatorTrend(String indicatorName) async {
    return _dio.get('${ApiConfig.reportTrend}/$indicatorName');
  }

  Future<Response> getTrendAnalysis(String indicatorName) async {
    return _dio.post(ApiConfig.reportTrendAnalysis, data: {
      'indicator_name': indicatorName,
    });
  }

  Future<Response> getReportAlerts() async {
    return _dio.get(ApiConfig.reportAlerts);
  }

  Future<Response> markAlertRead(int id) async {
    return _dio.put('${ApiConfig.reportAlerts}/$id/read');
  }

  Future<Response> shareReport(int reportId) async {
    return _dio.post('${ApiConfig.reportShareByPath}/$reportId/share');
  }

  Future<Response> compareReports(int id1, int id2) async {
    return _dio.post(ApiConfig.reportCompare, data: {
      'report_id_1': id1,
      'report_id_2': id2,
    });
  }

  // Symptom
  Future<Response> checkSymptom(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.symptomCheck, data: data);
  }

  Future<Response> analyzeSymptom(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.symptomAnalyze, data: data);
  }

  // TCM
  Future<Response> tcmDiagnose(String imagePath, String type, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(imagePath),
      'type': type,
    });
    return _dio.post(ApiConfig.tcmDiagnose, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> getConstitutionTest() async {
    return _dio.get(ApiConfig.tcmConstitution);
  }

  Future<Response> submitConstitutionTest(Map<String, dynamic> answers) async {
    return _dio.post(ApiConfig.tcmConstitution, data: answers);
  }

  Future<Response> getTcmConfig() async {
    return _dio.get(ApiConfig.tcmConfig);
  }

  Future<Response> postConstitutionTest(Map<String, dynamic> answers) async {
    return _dio.post(ApiConfig.tcmConstitutionTest, data: answers);
  }

  /// 获取体质测评 6 屏结果页聚合数据
  Future<Response> getConstitutionResult(int diagnosisId) async {
    return _dio.get('/api/constitution/result/$diagnosisId');
  }

  /// 领取 AI 精准检测体验券
  Future<Response> claimConstitutionCoupon() async {
    return _dio.post('/api/constitution/coupon/claim');
  }

  /// 查询体质档案列表
  Future<Response> getConstitutionArchive() async {
    return _dio.get('/api/constitution/archive');
  }

  Future<Response> getTcmDiagnosisList({int page = 1, int pageSize = 20}) async {
    return _dio.get(ApiConfig.tcmDiagnosisList, queryParameters: {
      'page': page,
      'page_size': pageSize,
    });
  }

  // Drug
  Future<Response> searchDrug(String keyword) async {
    return _dio.get(ApiConfig.drugSearch, queryParameters: {'keyword': keyword});
  }

  Future<Response> identifyDrug(String imagePath, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(imagePath),
    });
    return _dio.post(ApiConfig.drugIdentify, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> getDrugIdentifyHistory({int page = 1, int pageSize = 20}) async {
    return _dio.get(ApiConfig.drugIdentifyHistory, queryParameters: {
      'page': page,
      'page_size': pageSize,
    });
  }

  Future<Response> shareDrugIdentify(int recordId) async {
    return _dio.post('${ApiConfig.drugIdentifyShare}/$recordId/share');
  }

  Future<Response> getDrugPersonalSuggestion(int recordId) async {
    return _dio.get('${ApiConfig.drugIdentifyPersonalSuggestion}/$recordId/personal-suggestion');
  }

  // 用药对话 v1.2
  Future<Response> drugChatInit(int sessionId, {int? memberId}) async {
    return _dio.post('/api/chat/drug/init', data: {
      'session_id': sessionId,
      if (memberId != null) 'member_id': memberId,
    });
  }

  Future<Response> drugChatRegenerateOpening(int sessionId) async {
    return _dio.post('/api/chat/drug/regenerate_opening', data: {
      'session_id': sessionId,
    });
  }

  /// 单张图片识别追加到已有 session（用于对话页 "再加一个药一起对比"）
  Future<Response> ocrAppendSingleDrug(
    String imagePath, {
    required String sessionId,
    int? familyMemberId,
    ProgressCallback? onSendProgress,
  }) async {
    final formData = FormData();
    formData.files.add(MapEntry('files', await MultipartFile.fromFile(imagePath)));
    formData.fields.addAll([
      const MapEntry('scene_name', '拍照识药'),
      MapEntry('session_id', sessionId),
      if (familyMemberId != null) MapEntry('family_member_id', familyMemberId.toString()),
    ]);
    return _dio.post(ApiConfig.ocrBatchRecognize, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> ocrRecognizeDrug(String imagePath, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imagePath),
      'scene_name': '拍照识药',
    });
    return _dio.post(ApiConfig.ocrRecognize, data: formData, onSendProgress: onSendProgress);
  }

  Future<Response> ocrBatchRecognize(List<String> imagePaths, {String? sceneName, int? familyMemberId, ProgressCallback? onSendProgress}) async {
    final files = await Future.wait(
      imagePaths.map((p) => MultipartFile.fromFile(p)),
    );
    final formData = FormData();
    for (final f in files) {
      formData.files.add(MapEntry('files', f));
    }
    if (sceneName != null) {
      formData.fields.add(MapEntry('scene_name', sceneName));
    }
    if (familyMemberId != null) {
      formData.fields.add(MapEntry('family_member_id', familyMemberId.toString()));
    }
    return _dio.post(ApiConfig.ocrBatchRecognize, data: formData, onSendProgress: onSendProgress);
  }

  // Health Plan (legacy)
  Future<Response> getHealthPlan() async {
    return _dio.get(ApiConfig.healthPlan);
  }

  Future<Response> getPlanTasks(String planId) async {
    return _dio.get(ApiConfig.planTasks, queryParameters: {'plan_id': planId});
  }

  Future<Response> checkinTask(String taskId) async {
    return _dio.post(ApiConfig.taskCheckin, data: {'task_id': taskId});
  }

  // Health Plan V2 - Medications
  Future<Response> createMedication(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.hpMedications, data: data);
  }

  Future<Response> getMedications() async {
    return _dio.get(ApiConfig.hpMedications);
  }

  Future<Response> updateMedication(int id, Map<String, dynamic> data) async {
    return _dio.put('${ApiConfig.hpMedications}/$id', data: data);
  }

  Future<Response> deleteMedication(int id) async {
    return _dio.delete('${ApiConfig.hpMedications}/$id');
  }

  Future<Response> pauseMedication(int id, bool isPaused) async {
    return _dio.put('${ApiConfig.hpMedications}/$id/pause', data: {'is_paused': isPaused});
  }

  Future<Response> checkinMedication(int id) async {
    return _dio.post('${ApiConfig.hpMedications}/$id/checkin');
  }

  // Health Plan V2 - Checkin Items
  Future<Response> createCheckinItem(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.hpCheckinItems, data: data);
  }

  Future<Response> getCheckinItems() async {
    return _dio.get(ApiConfig.hpCheckinItems);
  }

  Future<Response> updateCheckinItem(int id, Map<String, dynamic> data) async {
    return _dio.put('${ApiConfig.hpCheckinItems}/$id', data: data);
  }

  Future<Response> deleteCheckinItem(int id) async {
    return _dio.delete('${ApiConfig.hpCheckinItems}/$id');
  }

  Future<Response> checkinCheckinItem(int id, {double? actualValue, bool? isCompleted}) async {
    final data = <String, dynamic>{};
    if (actualValue != null) data['actual_value'] = actualValue;
    if (isCompleted != null) data['is_completed'] = isCompleted;
    return _dio.post('${ApiConfig.hpCheckinItems}/$id/checkin', data: data);
  }

  // Health Plan V2 - Template Categories & Custom Plans
  Future<Response> getTemplateCategories() async {
    return _dio.get(ApiConfig.hpTemplateCategories);
  }

  Future<Response> getTemplateCategoryDetail(int id) async {
    return _dio.get('${ApiConfig.hpTemplateCategories}/$id');
  }

  Future<Response> getRecommendedPlanDetail(int id) async {
    return _dio.get('${ApiConfig.hpRecommendedPlans}/$id');
  }

  Future<Response> joinRecommendedPlan(int id) async {
    return _dio.post('${ApiConfig.hpRecommendedPlans}/$id/join');
  }

  Future<Response> createUserPlan(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.hpUserPlans, data: data);
  }

  Future<Response> getUserPlans() async {
    return _dio.get(ApiConfig.hpUserPlans);
  }

  Future<Response> getUserPlanDetail(int id) async {
    return _dio.get('${ApiConfig.hpUserPlans}/$id');
  }

  Future<Response> checkinUserPlanTask(int planId, int taskId, {double? actualValue}) async {
    final data = <String, dynamic>{};
    if (actualValue != null) data['actual_value'] = actualValue;
    return _dio.post('${ApiConfig.hpUserPlans}/$planId/tasks/$taskId/checkin', data: data);
  }

  // Health Plan V2 - AI
  Future<Response> aiGeneratePlan(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.hpAiGenerate, data: data);
  }

  Future<Response> aiGenerateCategoryPlan(int categoryId, {Map<String, dynamic>? data}) async {
    return _dio.post('${ApiConfig.hpAiGenerateCategory}/$categoryId', data: data ?? {});
  }

  // Health Plan V2 - Today / Statistics
  Future<Response> getTodayTodos() async {
    return _dio.get(ApiConfig.hpTodayTodos);
  }

  Future<Response> quickCheckin(int itemId, String type, {double? value}) async {
    final data = <String, dynamic>{'type': type};
    if (value != null) data['value'] = value;
    return _dio.post('${ApiConfig.hpTodayTodos}/$itemId/check', data: data);
  }

  Future<Response> getHpStatistics() async {
    return _dio.get(ApiConfig.hpStatistics);
  }

  // Services
  Future<Response> getServiceCategories() async {
    return _dio.get(ApiConfig.serviceCategories);
  }

  Future<Response> getServiceList({String? categoryId, int page = 1}) async {
    return _dio.get(ApiConfig.serviceList, queryParameters: {
      if (categoryId != null) 'category_id': categoryId,
      'page': page,
    });
  }

  Future<Response> getServiceDetail(String serviceId) async {
    return _dio.get(ApiConfig.serviceDetail, queryParameters: {'id': serviceId});
  }

  // Experts
  Future<Response> getExpertList({String? specialty, int page = 1}) async {
    return _dio.get(ApiConfig.expertList, queryParameters: {
      if (specialty != null) 'specialty': specialty,
      'page': page,
    });
  }

  Future<Response> getExpertDetail(String expertId) async {
    return _dio.get(ApiConfig.expertDetail, queryParameters: {'id': expertId});
  }

  Future<Response> getExpertSchedule(String expertId) async {
    return _dio.get(ApiConfig.expertSchedule, queryParameters: {'expert_id': expertId});
  }

  // Orders
  Future<Response> createOrder(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.createOrder, data: data);
  }

  Future<Response> getOrderList({String? status, int page = 1}) async {
    return _dio.get(ApiConfig.orderList, queryParameters: {
      if (status != null) 'status': status,
      'page': page,
    });
  }

  Future<Response> getOrderDetail(String orderId) async {
    return _dio.get(ApiConfig.orderDetail, queryParameters: {'id': orderId});
  }

  Future<Response> cancelOrder(String orderId) async {
    return _dio.post(ApiConfig.cancelOrder, data: {'id': orderId});
  }

  Future<Response> payOrder(String orderId, String payMethod) async {
    return _dio.post(ApiConfig.payOrder, data: {'id': orderId, 'pay_method': payMethod});
  }

  // Family
  Future<Response> getFamilyMembers() async {
    return _dio.get(ApiConfig.familyMembers);
  }

  Future<Response> addFamilyMember(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.addFamilyMember, data: data);
  }

  Future<Response> getRelationTypes() async {
    return _dio.get(ApiConfig.relationTypes);
  }

  Future<Response> removeFamilyMember(String memberId) async {
    return _dio.delete('${ApiConfig.removeFamilyMember}/$memberId');
  }

  Future<Response> sendSosAlert(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.sosAlert, data: data);
  }

  // Points
  Future<Response> getPointsBalance() async {
    return _dio.get(ApiConfig.pointsBalance);
  }

  Future<Response> getPointsRecords({int page = 1}) async {
    return _dio.get(ApiConfig.pointsRecords, queryParameters: {'page': page});
  }

  Future<Response> pointsCheckin() async {
    return _dio.post(ApiConfig.pointsCheckin);
  }

  Future<Response> getPointsSummary() async {
    return _dio.get('/api/points/summary');
  }

  Future<Response> getPointsTasks() async {
    return _dio.get('/api/points/tasks');
  }

  Future<Response> getPointsMallGoods({int page = 1, int pageSize = 50}) async {
    return _dio.get('/api/points/mall', queryParameters: {'page': page, 'page_size': pageSize});
  }

  // PRD F4：积分商品详情（含用户已兑次数、按钮状态等）
  Future<Response> getPointsMallProductDetail(int id) async {
    return _dio.get('/api/points/mall/items/$id');
  }

  Future<Response> exchangePointsGoods({required int goodsId, int quantity = 1}) async {
    return _dio.post('/api/points/mall/exchange', data: {
      'goods_id': goodsId,
      'quantity': quantity,
    });
  }

  Future<Response> getPointsExchangeRecords({int page = 1, int pageSize = 20, String? goodsType}) async {
    final qp = <String, dynamic>{'page': page, 'page_size': pageSize};
    if (goodsType != null && goodsType.isNotEmpty) qp['goods_type'] = goodsType;
    return _dio.get('/api/points/exchange-records', queryParameters: qp);
  }

  Future<Response> getInviteStats({int page = 1, int pageSize = 50}) async {
    return _dio.get('/api/users/invite-stats', queryParameters: {'page': page, 'page_size': pageSize});
  }

  Future<Response> getPointsMall({int page = 1}) async {
    return _dio.get(ApiConfig.pointsMall, queryParameters: {'page': page});
  }

  Future<Response> exchangePoints(String itemId) async {
    return _dio.post(ApiConfig.pointsExchange, data: {'item_id': itemId});
  }

  Future<Map<String, dynamic>> getCheckinTodayProgress() async {
    try {
      final response = await _dio.get(ApiConfig.checkinTodayProgress);
      return response.data is Map<String, dynamic>
          ? response.data as Map<String, dynamic>
          : <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  // Content
  Future<Response> getArticles({String? category, int page = 1, int? pageSize}) async {
    return _dio.get(ApiConfig.articles, queryParameters: {
      if (category != null) 'category': category,
      'page': page,
      if (pageSize != null) 'page_size': pageSize,
    });
  }

  Future<Response> getArticleDetail(String articleId) async {
    return _dio.get(ApiConfig.articleDetail, queryParameters: {'id': articleId});
  }

  Future<Response> collectArticle(String articleId) async {
    return _dio.post(ApiConfig.collectArticle, data: {'article_id': articleId});
  }

  // Notifications
  Future<Response> getNotifications({int page = 1}) async {
    return _dio.get(ApiConfig.notifications, queryParameters: {'page': page});
  }

  Future<Response> readNotification(String notificationId) async {
    return _dio.post(ApiConfig.readNotification, data: {'id': notificationId});
  }

  // Home
  Future<Response> getBanners() async {
    return _dio.get(ApiConfig.banners);
  }

  Future<Response> getRecommendations() async {
    return _dio.get(ApiConfig.recommendations);
  }

  // Search
  Future<Map<String, dynamic>> search({
    String q = '',
    String type = 'all',
    int page = 1,
    int pageSize = 20,
    String source = 'text',
  }) async {
    final response = await _dio.get(ApiConfig.search, queryParameters: {
      'q': q,
      'type': type,
      'page': page,
      'page_size': pageSize,
      'source': source,
    });
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : <String, dynamic>{};
  }

  Future<List<dynamic>> searchSuggest(String q) async {
    final response = await _dio.get(ApiConfig.searchSuggest, queryParameters: {'q': q});
    final data = response.data;
    if (data is Map && data['items'] is List) return data['items'] as List;
    if (data is List) return data;
    return [];
  }

  Future<List<dynamic>> searchHot() async {
    final response = await _dio.get(ApiConfig.searchHot);
    final data = response.data;
    if (data is Map && data['items'] is List) return data['items'] as List;
    if (data is List) return data;
    return [];
  }

  Future<List<dynamic>> searchHistory() async {
    final response = await _dio.get(ApiConfig.searchHistory);
    final data = response.data;
    if (data is Map && data['items'] is List) return data['items'] as List;
    if (data is List) return data;
    return [];
  }

  Future<void> deleteSearchHistory(int id) async {
    await _dio.delete('${ApiConfig.searchHistory}/$id');
  }

  Future<void> clearSearchHistory() async {
    await _dio.delete(ApiConfig.searchHistory);
  }

  Future<Map<String, dynamic>> getAsrToken() async {
    final response = await _dio.post(ApiConfig.asrToken);
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : <String, dynamic>{};
  }

  Future<Map<String, dynamic>> asrRecognize(String filePath, String format, {ProgressCallback? onSendProgress}) async {
    final formData = FormData.fromMap({
      'audio_file': await MultipartFile.fromFile(filePath),
      'format': format,
      'sample_rate': '16000',
    });
    final response = await _dio.post(ApiConfig.asrRecognize, data: formData, onSendProgress: onSendProgress);
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : <String, dynamic>{};
  }

  // Font Setting
  Future<Map<String, dynamic>> getUserFontSetting() async {
    try {
      final response = await _dio.get(ApiConfig.userFontSetting);
      return response.data is Map<String, dynamic>
          ? response.data as Map<String, dynamic>
          : <String, dynamic>{};
    } catch (_) {
      return <String, dynamic>{};
    }
  }

  Future<bool> updateUserFontSetting(String level) async {
    try {
      await _dio.put(ApiConfig.userFontSetting, data: {'font_size_level': level});
      return true;
    } catch (_) {
      return false;
    }
  }

  // City
  Future<Map<String, dynamic>> getCityList({String? keyword}) async {
    final response = await _dio.get(
      ApiConfig.cityList,
      queryParameters: keyword != null ? {'keyword': keyword} : null,
    );
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : {};
  }

  Future<Map<String, dynamic>> getHotCities() async {
    final response = await _dio.get(ApiConfig.cityHot);
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : {};
  }

  Future<Map<String, dynamic>> locateCity(double lng, double lat) async {
    final response = await _dio.get(
      ApiConfig.cityLocate,
      queryParameters: {'lng': lng, 'lat': lat},
    );
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : {};
  }

  // Function Buttons
  Future<Response> getFunctionButtons() async {
    return _dio.get(ApiConfig.chatFunctionButtons);
  }

  // Voice Call (Digital Human)
  Future<Response> startVoiceCall({int? digitalHumanId, String? chatSessionId}) async {
    final data = <String, dynamic>{};
    if (digitalHumanId != null) data['digital_human_id'] = digitalHumanId;
    if (chatSessionId != null) data['chat_session_id'] = chatSessionId;
    return _dio.post(ApiConfig.voiceCallStart, data: data);
  }

  Future<Response> sendVoiceCallMessage(int callId, String userText) async {
    return _dio.post('${ApiConfig.voiceCall}/$callId/message', data: {'user_text': userText});
  }

  Future<Response> endVoiceCall(int callId, {List<Map<String, dynamic>>? dialogContent}) async {
    return _dio.post('${ApiConfig.voiceCall}/$callId/end', data: {
      'dialog_content': dialogContent ?? [],
    });
  }

  // Messages
  Future<Response> getMessages({int page = 1, int pageSize = 20, String? messageType}) async {
    final params = <String, dynamic>{'page': page, 'page_size': pageSize};
    if (messageType != null) params['message_type'] = messageType;
    return _dio.get(ApiConfig.messages, queryParameters: params);
  }

  Future<Response> markMessageRead(int messageId) async {
    return _dio.put('${ApiConfig.messages}/$messageId/read');
  }

  Future<Response> markAllMessagesRead() async {
    return _dio.put(ApiConfig.messagesReadAll);
  }

  Future<Response> getUnreadMessageCount() async {
    return _dio.get(ApiConfig.messagesUnreadCount);
  }

  // Family Management
  Future<Response> createFamilyInvitation(int memberId) async {
    return _dio.post(ApiConfig.familyInvitation, data: {'member_id': memberId});
  }

  Future<Response> getFamilyInvitation(String code) async {
    return _dio.get('${ApiConfig.familyInvitation}/$code');
  }

  Future<Response> acceptFamilyInvitation(String code) async {
    return _dio.post('${ApiConfig.familyInvitation}/$code/accept');
  }

  Future<Response> rejectFamilyInvitation(String code) async {
    return _dio.post('${ApiConfig.familyInvitation}/$code/reject');
  }

  Future<Response> getFamilyManagementList() async {
    return _dio.get(ApiConfig.familyManagement);
  }

  Future<Response> getManagedByList() async {
    return _dio.get(ApiConfig.familyManagedBy);
  }

  Future<Response> deleteFamilyManagement(int id) async {
    return _dio.delete('${ApiConfig.familyManagement}/$id');
  }

  Future<Response> getFamilyManagementLogs(int id) async {
    return _dio.get('${ApiConfig.familyManagement}/$id/logs');
  }

  // Home dynamic config
  Future<Map<String, dynamic>> getHomeConfig() async {
    final response = await _dio.get(ApiConfig.homeConfig);
    return response.data is Map<String, dynamic>
        ? response.data as Map<String, dynamic>
        : <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> getHomeMenus() async {
    final response = await _dio.get(ApiConfig.homeMenus);
    final data = response.data;
    if (data is Map && data['items'] is List) {
      return (data['items'] as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return [];
  }

  Future<List<Map<String, dynamic>>> getHomeBanners() async {
    final response = await _dio.get(ApiConfig.homeBanners);
    final data = response.data;
    if (data is Map && data['items'] is List) {
      return (data['items'] as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    }
    return [];
  }

  Future<Response> streamChatMessage(String sessionId, String content, {String type = 'text'}) async {
    return _dio.post(
      '${ApiConfig.chatSessions}/$sessionId/stream',
      data: {'content': content, 'message_type': type},
      options: Options(
        responseType: ResponseType.stream,
        headers: {'Accept': 'text/event-stream'},
      ),
    );
  }

  Future<Response> generateSharePoster(String sessionId, String messageId) async {
    return _dio.post('/api/chat/share/poster', data: {
      'session_id': sessionId,
      'message_id': messageId,
    });
  }

  // Products
  Future<Response> getProductCategories() async {
    return _dio.get(ApiConfig.productCategories);
  }

  Future<Response> getProducts({
    int? categoryId,
    String? fulfillmentType,
    bool? pointsExchangeable,
    String? keyword,
    int page = 1,
    int pageSize = 20,
  }) async {
    final params = <String, dynamic>{'page': page, 'page_size': pageSize};
    if (categoryId != null) params['category_id'] = categoryId;
    if (fulfillmentType != null) params['fulfillment_type'] = fulfillmentType;
    if (pointsExchangeable != null) params['points_exchangeable'] = pointsExchangeable;
    if (keyword != null) params['keyword'] = keyword;
    return _dio.get(ApiConfig.products, queryParameters: params);
  }

  Future<Response> getProductsByStringCategory({
    required String categoryId,
    int page = 1,
    int pageSize = 20,
  }) async {
    final params = <String, dynamic>{
      'page': page,
      'page_size': pageSize,
      'category_id': categoryId,
    };
    return _dio.get(ApiConfig.products, queryParameters: params);
  }

  Future<Response> getProductsByParentCategory({
    required int parentCategoryId,
    int page = 1,
    int pageSize = 100,
  }) async {
    return _dio.get(ApiConfig.products, queryParameters: {
      'parent_category_id': parentCategoryId,
      'page': page,
      'page_size': pageSize,
    });
  }

  Future<Response> getProductDetail(int productId) async {
    return _dio.get('${ApiConfig.products}/$productId');
  }

  // Unified Orders
  Future<Response> createUnifiedOrder(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.unifiedOrders, data: data);
  }

  Future<Response> getUnifiedOrders({
    String? status,
    String? refundStatus,
    int page = 1,
    int pageSize = 20,
  }) async {
    final params = <String, dynamic>{'page': page, 'page_size': pageSize};
    if (status != null) params['status'] = status;
    if (refundStatus != null) params['refund_status'] = refundStatus;
    return _dio.get(ApiConfig.unifiedOrders, queryParameters: params);
  }

  Future<Response> getUnifiedOrderDetail(int orderId) async {
    return _dio.get('${ApiConfig.unifiedOrders}/$orderId');
  }

  Future<Response> payUnifiedOrder(int orderId, {String paymentMethod = 'wechat'}) async {
    return _dio.post('${ApiConfig.unifiedOrders}/$orderId/pay', data: {
      'payment_method': paymentMethod,
    });
  }

  Future<Response> confirmReceipt(int orderId) async {
    return _dio.post('${ApiConfig.unifiedOrders}/$orderId/confirm');
  }

  Future<Response> cancelUnifiedOrder(int orderId, {String? cancelReason}) async {
    return _dio.post('${ApiConfig.unifiedOrders}/$orderId/cancel', data: {
      if (cancelReason != null) 'cancel_reason': cancelReason,
    });
  }

  Future<Response> submitReview(int orderId, {required int rating, String? content, List<String>? images}) async {
    return _dio.post('${ApiConfig.unifiedOrders}/$orderId/review', data: {
      'rating': rating,
      if (content != null) 'content': content,
      if (images != null) 'images': images,
    });
  }

  Future<Response> applyRefund(int orderId, {String? reason, double? refundAmount, int? orderItemId}) async {
    return _dio.post('${ApiConfig.unifiedOrders}/$orderId/refund', data: {
      if (reason != null) 'reason': reason,
      if (refundAmount != null) 'refund_amount': refundAmount,
      if (orderItemId != null) 'order_item_id': orderItemId,
    });
  }

  // Member QR Code
  Future<Response> getMemberQRCode() async {
    return _dio.get(ApiConfig.memberQrcode);
  }

  // Favorites
  Future<Response> toggleFavorite(int contentId, String contentType) async {
    return _dio.post(ApiConfig.favorites, queryParameters: {
      'content_id': contentId,
      'content_type': contentType,
    });
  }

  Future<Response> getFavorites({String tab = 'product', int page = 1, int pageSize = 20}) async {
    return _dio.get(ApiConfig.favorites, queryParameters: {
      'tab': tab,
      'page': page,
      'page_size': pageSize,
    });
  }

  Future<Response> getFavoriteStatus(int contentId, String contentType) async {
    return _dio.get('${ApiConfig.favorites}/status', queryParameters: {
      'content_id': contentId,
      'content_type': contentType,
    });
  }

  // Coupons
  Future<Response> getAvailableCoupons({int page = 1}) async {
    return _dio.get(ApiConfig.availableCoupons, queryParameters: {'page': page});
  }

  Future<Response> claimCoupon(int couponId) async {
    return _dio.post(ApiConfig.claimCoupon, data: {'coupon_id': couponId});
  }

  Future<Response> getMyCoupons({String tab = 'unused', int page = 1, bool? excludeExpired}) async {
    final params = <String, dynamic>{'tab': tab, 'page': page};
    if (excludeExpired == true) {
      params['exclude_expired'] = true;
    }
    return _dio.get(ApiConfig.myCoupons, queryParameters: params);
  }

  // Addresses
  Future<Response> getAddresses() async {
    return _dio.get(ApiConfig.addresses);
  }

  Future<Response> createAddress(Map<String, dynamic> data) async {
    return _dio.post(ApiConfig.addresses, data: data);
  }

  Future<Response> updateAddress(int addressId, Map<String, dynamic> data) async {
    return _dio.put('${ApiConfig.addresses}/$addressId', data: data);
  }

  Future<Response> deleteAddress(int addressId) async {
    return _dio.delete('${ApiConfig.addresses}/$addressId');
  }
}
