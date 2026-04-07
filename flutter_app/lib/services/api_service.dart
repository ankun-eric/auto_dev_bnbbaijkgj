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
    return _dio.post(ApiConfig.reportShare, data: {'report_id': reportId});
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

  Future<Response> ocrRecognizeDrug(String imagePath) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(imagePath),
      'scene_name': '拍照识药',
    });
    return _dio.post(ApiConfig.ocrRecognize, data: formData);
  }

  // Health Plan
  Future<Response> getHealthPlan() async {
    return _dio.get(ApiConfig.healthPlan);
  }

  Future<Response> getPlanTasks(String planId) async {
    return _dio.get(ApiConfig.planTasks, queryParameters: {'plan_id': planId});
  }

  Future<Response> checkinTask(String taskId) async {
    return _dio.post(ApiConfig.taskCheckin, data: {'task_id': taskId});
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

  Future<Response> removeFamilyMember(String memberId) async {
    return _dio.post(ApiConfig.removeFamilyMember, data: {'member_id': memberId});
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
}
