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

  // Function Buttons
  static const String chatFunctionButtons = '/api/chat/function-buttons';

  // Digital Human / Voice Call
  static const String voiceCallStart = '/api/chat/voice-call/start';
  static const String voiceCall = '/api/chat/voice-call';

  // Checkup (legacy)
  static const String checkupReports = '/api/health/checkup-reports';
  static const String uploadCheckup = '/api/health/checkup-reports';
  static const String analyzeCheckup = '/api/health/checkup-reports';

  // Report (new intelligent analysis)
  static const String reportUpload = '/api/report/upload';
  static const String reportAnalyze = '/api/report/analyze';
  static const String reportDetail = '/api/report/detail';
  static const String reportList = '/api/report/list';
  static const String reportTrend = '/api/report/trend';
  static const String reportTrendAnalysis = '/api/report/trend/analysis';
  static const String reportAlerts = '/api/report/alerts';
  static const String reportShare = '/api/report/share';
  static const String reportShareByPath = '/api/report';
  static const String reportCompare = '/api/report/compare';

  // Symptom (uses chat with session_type=symptom_check)
  static const String symptomCheck = '/api/chat/sessions';
  static const String symptomAnalyze = '/api/chat/sessions';

  // TCM
  static const String tcmDiagnose = '/api/tcm/diagnose';
  static const String tcmConstitution = '/api/tcm/constitution';

  // Drug
  static const String drugSearch = '/api/drugs/query';
  static const String drugIdentify = '/api/drugs/identify';
  static const String drugIdentifyHistory = '/api/drug-identify/history';
  static const String drugIdentifyShare = '/api/drug-identify';
  static const String drugIdentifyPersonalSuggestion = '/api/drug-identify';
  static const String ocrRecognize = '/api/ocr/recognize';
  static const String ocrBatchRecognize = '/api/ocr/batch-recognize';

  // Health Plan (legacy)
  static const String healthPlan = '/api/plans';
  static const String planTasks = '/api/plans';
  static const String taskCheckin = '/api/plans';

  // Health Plan V2 - Medications
  static const String hpMedications = '/api/health-plan/medications';

  // Health Plan V2 - Checkin Items
  static const String hpCheckinItems = '/api/health-plan/checkin-items';

  // Health Plan V2 - Custom Plans
  static const String hpTemplateCategories = '/api/health-plan/template-categories';
  static const String hpRecommendedPlans = '/api/health-plan/recommended-plans';
  static const String hpUserPlans = '/api/health-plan/user-plans';

  // Health Plan V2 - AI / Today / Statistics
  static const String hpAiGenerate = '/api/health-plan/ai-generate';
  static const String hpAiGenerateCategory = '/api/health-plan/ai-generate-category';
  static const String hpTodayTodos = '/api/health-plan/today-todos';
  static const String hpStatistics = '/api/health-plan/statistics';

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
  static const String familyMembers = '/api/family/members';
  static const String addFamilyMember = '/api/family/members';
  static const String removeFamilyMember = '/api/family/members';
  static const String relationTypes = '/api/relation-types';
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

  // Search
  static const String search = '/api/search';
  static const String searchSuggest = '/api/search/suggest';
  static const String searchHot = '/api/search/hot';
  static const String searchHistory = '/api/search/history';
  static const String searchLog = '/api/search/log';
  static const String asrToken = '/api/search/asr/token';
  static const String asrRecognize = '/api/search/asr/recognize';
  static const String drugKeywords = '/api/search/drug-keywords';

  // Font Setting
  static const String userFontSetting = '/api/user/font-setting';

  // Home dynamic config
  static const String homeConfig = '/api/home-config';
  static const String homeMenus = '/api/home-menus';
  static const String homeBanners = '/api/home-banners';

  // Disease Presets
  static const String diseasePresets = '/api/disease-presets';

  // Health Profile - Member
  static const String updateMemberHealthProfile = '/api/health/profile/member';

  // Health Guide
  static const String guideStatus = '/api/health/guide-status';

  // City
  static const String cityList = '/api/cities/list';
  static const String cityHot = '/api/cities/hot';
  static const String cityLocate = '/api/cities/locate';

  // Family Management
  static const String familyInvitation = '/api/family/invitation';
  static const String familyManagement = '/api/family/management';
  static const String familyManagedBy = '/api/family/managed-by';
}
