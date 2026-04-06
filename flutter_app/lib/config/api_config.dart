class ApiConfig {
  // 当前构建默认直连本项目部署根路径；各接口常量已自带 /api 前缀。
  static const String baseUrl = 'https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857';

  // Auth
  static const String registerSettings = '/api/auth/register-settings';
  static const String login = '/api/auth/sms-login';
  static const String sendSmsCode = '/api/auth/sms-code';
  static const String register = '/api/auth/register';
  static const String logout = '/api/auth/logout';
  static const String refreshToken = '/api/auth/refresh';
  static const String wechatLogin = '/api/auth/wechat';
  static const String appleLogin = '/api/auth/apple';

  // User
  static const String userProfile = '/api/auth/me';
  static const String updateProfile = '/api/auth/me';
  static const String uploadAvatar = '/api/upload/image';

  // Health Profile
  static const String healthProfile = '/api/health/profile';
  static const String updateHealthProfile = '/api/health/profile';
  static const String healthRecords = '/api/health/checkup-reports';

  // Chat
  static const String chatSessions = '/api/chat/sessions';
  static const String chatMessages = '/api/chat/sessions';
  static const String sendMessage = '/api/chat/sessions';
  static const String createSession = '/api/chat/sessions';

  // Chat History (new endpoints)
  static const String chatSessionsList = '/api/chat-sessions';

  /// 知识库命中反馈（见 knowledge 路由）
  static const String chatKnowledgeFeedback = '/api/chat/feedback';

  // Checkup
  static const String checkupReports = '/api/health/checkup-reports';
  static const String uploadCheckup = '/api/health/checkup-reports';
  static const String analyzeCheckup = '/api/health/checkup-reports';

  // Symptom (uses chat with session_type=symptom_check)
  static const String symptomCheck = '/api/chat/sessions';
  static const String symptomAnalyze = '/api/chat/sessions';

  // TCM
  static const String tcmDiagnose = '/api/tcm/diagnose';
  static const String tcmConstitution = '/api/tcm/constitution';

  // Drug
  static const String drugSearch = '/api/drugs/query';
  static const String drugIdentify = '/api/drugs/identify';

  // Health Plan
  static const String healthPlan = '/api/plans';
  static const String planTasks = '/api/plans';
  static const String taskCheckin = '/api/plans';

  // Services
  static const String serviceCategories = '/api/services/categories';
  static const String serviceList = '/api/services/items';
  static const String serviceDetail = '/api/services/items';

  // Experts
  static const String expertList = '/api/experts';
  static const String expertDetail = '/api/experts';
  static const String expertSchedule = '/api/experts';

  // Orders
  static const String createOrder = '/api/orders';
  static const String orderList = '/api/orders';
  static const String orderDetail = '/api/orders';
  static const String cancelOrder = '/api/orders';
  static const String payOrder = '/api/orders';

  // Family
  static const String familyMembers = '/api/family';
  static const String addFamilyMember = '/api/family';
  static const String removeFamilyMember = '/api/family';
  static const String sosAlert = '/api/family/sos';

  // Points
  static const String pointsBalance = '/api/points/balance';
  static const String pointsRecords = '/api/points/records';
  static const String pointsCheckin = '/api/points/signin';
  static const String pointsMall = '/api/points/mall';
  static const String pointsExchange = '/api/points/exchange';

  // Content
  static const String articles = '/api/content/articles';
  static const String articleDetail = '/api/content/articles';
  static const String collectArticle = '/api/content/favorites';

  // Notifications
  static const String notifications = '/api/notifications';
  static const String readNotification = '/api/notifications';

  // Home (these are composite endpoints, may need frontend assembly)
  static const String banners = '/api/content/articles';
  static const String recommendations = '/api/content/articles';
}
