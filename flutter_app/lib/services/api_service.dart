import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;

  late Dio _dio;

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

  // Auth
  Future<Response> getRegisterSettings() async {
    return _dio.get(ApiConfig.registerSettings);
  }

  Future<Response> login(String phone, String code) async {
    return _dio.post(ApiConfig.login, data: {'phone': phone, 'code': code});
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
  Future<Response> getUserProfile() async {
    return _dio.get(ApiConfig.userProfile);
  }

  Future<Response> updateProfile(Map<String, dynamic> data) async {
    return _dio.put(ApiConfig.updateProfile, data: data);
  }

  Future<Response> uploadAvatar(String filePath) async {
    final formData = FormData.fromMap({
      'avatar': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.uploadAvatar, data: formData);
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

  Future<Response> uploadCheckupReport(String filePath) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.uploadCheckup, data: formData);
  }

  Future<Response> analyzeCheckup(String reportId) async {
    return _dio.post(ApiConfig.analyzeCheckup, data: {'report_id': int.tryParse(reportId) ?? reportId});
  }

  // Report (intelligent analysis)
  Future<Response> uploadReport(String filePath) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath),
    });
    return _dio.post(ApiConfig.reportUpload, data: formData);
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
  Future<Response> tcmDiagnose(String imagePath, String type) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(imagePath),
      'type': type,
    });
    return _dio.post(ApiConfig.tcmDiagnose, data: formData);
  }

  Future<Response> getConstitutionTest() async {
    return _dio.get(ApiConfig.tcmConstitution);
  }

  Future<Response> submitConstitutionTest(Map<String, dynamic> answers) async {
    return _dio.post(ApiConfig.tcmConstitution, data: answers);
  }

  // Drug
  Future<Response> searchDrug(String keyword) async {
    return _dio.get(ApiConfig.drugSearch, queryParameters: {'keyword': keyword});
  }

  Future<Response> identifyDrug(String imagePath) async {
    final formData = FormData.fromMap({
      'image': await MultipartFile.fromFile(imagePath),
    });
    return _dio.post(ApiConfig.drugIdentify, data: formData);
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

  Future<Response> ocrRecognizeDrug(String imagePath) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imagePath),
      'scene_name': '拍照识药',
    });
    return _dio.post(ApiConfig.ocrRecognize, data: formData);
  }

  Future<Response> ocrBatchRecognize(List<String> imagePaths, {String? sceneName}) async {
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
    return _dio.post(ApiConfig.ocrBatchRecognize, data: formData);
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

  Future<Response> checkinUserPlanTask(int planId, int taskId) async {
    return _dio.post('${ApiConfig.hpUserPlans}/$planId/tasks/$taskId/checkin');
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

  Future<Response> getPointsMall({int page = 1}) async {
    return _dio.get(ApiConfig.pointsMall, queryParameters: {'page': page});
  }

  Future<Response> exchangePoints(String itemId) async {
    return _dio.post(ApiConfig.pointsExchange, data: {'item_id': itemId});
  }

  // Content
  Future<Response> getArticles({String? category, int page = 1}) async {
    return _dio.get(ApiConfig.articles, queryParameters: {
      if (category != null) 'category': category,
      'page': page,
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

  Future<Map<String, dynamic>> asrRecognize(String filePath, String format) async {
    final formData = FormData.fromMap({
      'audio_file': await MultipartFile.fromFile(filePath),
      'format': format,
      'sample_rate': '16000',
    });
    final response = await _dio.post(ApiConfig.asrRecognize, data: formData);
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
}
