import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/chat_provider.dart';
import 'providers/health_provider.dart';
import 'providers/font_provider.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/main_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/ai/ai_home_screen.dart';
import 'screens/ai/chat_screen.dart';
import 'screens/health/checkup_screen.dart';
import 'screens/health/report_detail_screen.dart';
import 'screens/health/report_compare_screen.dart';
import 'screens/health/trend_screen.dart';
import 'screens/health/symptom_screen.dart';
import 'screens/health/tcm_screen.dart';
import 'screens/health/drug_screen.dart';
import 'screens/health/drug_chat_screen.dart';
import 'screens/health/tcm_diagnosis_detail_screen.dart';
import 'screens/health/health_profile_screen.dart';
import 'screens/health/health_guide_screen.dart';
import 'screens/family/family_screen.dart';
import 'screens/family/family_invite_screen.dart';
import 'screens/family/family_auth_screen.dart';
import 'screens/family/family_bindlist_screen.dart';
import 'screens/services/services_screen.dart';
import 'screens/services/service_detail_screen.dart';
import 'screens/services/expert_list_screen.dart';
import 'screens/services/expert_detail_screen.dart';
import 'screens/order/orders_screen.dart';
import 'screens/order/order_detail_screen.dart';
import 'screens/points/points_screen.dart';
import 'screens/points/points_records_screen.dart';
import 'screens/points/points_mall_screen.dart';
import 'screens/plan/health_plan_screen.dart';
import 'screens/plan/medication_list_screen.dart';
import 'screens/plan/medication_form_screen.dart';
import 'screens/plan/checkin_list_screen.dart';
import 'screens/plan/checkin_form_screen.dart';
import 'screens/plan/template_categories_screen.dart';
import 'screens/plan/category_detail_screen.dart';
import 'screens/plan/recommended_plan_detail_screen.dart';
import 'screens/plan/create_plan_screen.dart';
import 'screens/plan/user_plan_detail_screen.dart';
import 'screens/plan/statistics_screen.dart';
import 'screens/content/articles_screen.dart';
import 'screens/content/article_detail_screen.dart';
import 'screens/profile/profile_screen.dart';
import 'screens/invite/invite_screen.dart';
import 'screens/profile/settings_screen.dart';
import 'screens/notifications/notifications_screen.dart';
import 'screens/customer_service/cs_screen.dart';
import 'screens/search/search_screen.dart';
import 'screens/search/search_result_screen.dart';
import 'screens/city/city_select_screen.dart';
import 'screens/digital_human/digital_human_call_screen.dart';
import 'screens/messages/messages_screen.dart';
import 'screens/product/product_list_screen.dart';
import 'screens/product/product_detail_screen.dart';
import 'screens/product/checkout_screen.dart';
import 'screens/order/unified_orders_screen.dart';
import 'screens/order/unified_order_detail_screen.dart';
import 'screens/order/review_screen.dart';
import 'screens/order/refund_screen.dart';
import 'screens/member/member_card_screen.dart';
import 'screens/coupon/my_coupons_screen.dart';
import 'screens/coupon/coupon_center_screen.dart';
import 'screens/favorites/favorites_screen.dart';
import 'screens/address/address_list_screen.dart';
import 'screens/address/address_edit_screen.dart';
import 'services/logo_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));

  final fontProvider = FontProvider();
  await fontProvider.init();

  LogoService().fetchLogo();

  runApp(BiniHealthApp(fontProvider: fontProvider));
}

class BiniHealthApp extends StatelessWidget {
  final FontProvider fontProvider;
  const BiniHealthApp({super.key, required this.fontProvider});

  static const Color primaryColor = Color(0xFF52C41A);
  static const Color secondaryColor = Color(0xFF13C2C2);

  static final MaterialColor primarySwatch = MaterialColor(
    primaryColor.value,
    const <int, Color>{
      50: Color(0xFFF0F9EB),
      100: Color(0xFFD9F0C4),
      200: Color(0xFFC0E69D),
      300: Color(0xFFA7DD76),
      400: Color(0xFF8ED44F),
      500: Color(0xFF52C41A),
      600: Color(0xFF49B016),
      700: Color(0xFF3F9B13),
      800: Color(0xFF35870F),
      900: Color(0xFF2B720C),
    },
  );

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
        ChangeNotifierProvider(create: (_) => HealthProvider()),
        ChangeNotifierProvider.value(value: fontProvider),
      ],
      child: MaterialApp(
        title: '宾尼小康',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          primarySwatch: primarySwatch,
          primaryColor: primaryColor,
          colorScheme: ColorScheme.fromSeed(
            seedColor: primaryColor,
            secondary: secondaryColor,
            brightness: Brightness.light,
          ),
          scaffoldBackgroundColor: const Color(0xFFF5F7FA),
          appBarTheme: const AppBarTheme(
            backgroundColor: primaryColor,
            foregroundColor: Colors.white,
            elevation: 0,
            centerTitle: true,
            titleTextStyle: TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w600,
            ),
            iconTheme: IconThemeData(color: Colors.white),
          ),
          elevatedButtonTheme: ElevatedButtonThemeData(
            style: ElevatedButton.styleFrom(
              backgroundColor: primaryColor,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
              textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
          ),
          cardTheme: CardTheme(
            elevation: 0,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            color: Colors.white,
          ),
          bottomNavigationBarTheme: const BottomNavigationBarThemeData(
            backgroundColor: Colors.white,
            selectedItemColor: primaryColor,
            unselectedItemColor: Color(0xFF999999),
            type: BottomNavigationBarType.fixed,
            elevation: 8,
          ),
          fontFamily: 'PingFang SC',
          useMaterial3: true,
        ),
        initialRoute: '/splash',
        routes: {
          '/splash': (context) => const SplashScreen(),
          '/login': (context) {
            final referrerNo = ModalRoute.of(context)?.settings.arguments as String?;
            return LoginScreen(referrerNo: referrerNo);
          },
          '/main': (context) => const MainScreen(),
          '/home': (context) => const HomeScreen(),
          '/ai': (context) => const AiHomeScreen(),
          '/chat': (context) => const ChatScreen(),
          '/checkup': (context) => const CheckupScreen(),
          '/report-detail': (context) {
            final id = ModalRoute.of(context)!.settings.arguments as int;
            return ReportDetailScreen(reportId: id);
          },
          '/trend': (context) {
            final name = ModalRoute.of(context)!.settings.arguments as String;
            return TrendScreen(indicatorName: name);
          },
          '/report-compare': (context) {
            final args = ModalRoute.of(context)!.settings.arguments as Map<String, int>;
            return ReportCompareScreen(
              reportId1: args['reportId1']!,
              reportId2: args['reportId2']!,
            );
          },
          '/symptom': (context) => const SymptomScreen(),
          '/tcm': (context) => const TcmScreen(),
          '/drug': (context) => const DrugScreen(),
          '/drug-chat': (context) => const DrugChatScreen(),
          '/tcm-diagnosis-detail': (context) => const TcmDiagnosisDetailScreen(),
          '/health-profile': (context) => const HealthProfileScreen(),
          '/health-guide': (context) {
            final memberId = ModalRoute.of(context)?.settings.arguments as int?;
            return HealthGuideScreen(memberId: memberId);
          },
          '/family': (context) => const FamilyScreen(),
          '/family-invite': (context) {
            final memberId = ModalRoute.of(context)!.settings.arguments as int;
            return FamilyInviteScreen(memberId: memberId);
          },
          '/family-auth': (context) {
            final code = ModalRoute.of(context)!.settings.arguments as String;
            return FamilyAuthScreen(code: code);
          },
          '/family-bindlist': (context) => const FamilyBindListScreen(),
          '/services': (context) => const ServicesScreen(),
          '/service-detail': (context) => const ServiceDetailScreen(),
          '/experts': (context) => const ExpertListScreen(),
          '/expert-detail': (context) => const ExpertDetailScreen(),
          '/orders': (context) => const OrdersScreen(),
          '/order-detail': (context) => const OrderDetailScreen(),
          '/points': (context) => const PointsScreen(),
          '/points-mall': (context) => const PointsMallScreen(),
          '/points-records': (context) => const PointsRecordsScreen(),
          '/health-plan': (context) => const HealthPlanScreen(),
          '/hp-medications': (context) => const MedicationListScreen(),
          '/hp-medication-form': (context) => const MedicationFormScreen(),
          '/hp-checkins': (context) => const CheckinListScreen(),
          '/hp-checkin-form': (context) => const CheckinFormScreen(),
          '/hp-template-categories': (context) => const TemplateCategoriesScreen(),
          '/hp-category-detail': (context) => const CategoryDetailScreen(),
          '/hp-recommended-plan': (context) => const RecommendedPlanDetailScreen(),
          '/hp-create-plan': (context) => const CreatePlanScreen(),
          '/hp-user-plan': (context) => const UserPlanDetailScreen(),
          '/hp-statistics': (context) => const StatisticsScreen(),
          '/articles': (context) => const ArticlesScreen(),
          '/article-detail': (context) => const ArticleDetailScreen(),
          '/profile': (context) => const ProfileScreen(),
          '/settings': (context) => const SettingsScreen(),
          '/notifications': (context) => const NotificationsScreen(),
          '/customer-service': (context) => const CsScreen(),
          '/search': (context) => const SearchScreen(),
          '/search-result': (context) => const SearchResultScreen(),
          '/city-select': (context) => const CitySelectScreen(),
          '/digital-human-call': (context) => const DigitalHumanCallScreen(),
          '/invite': (context) => const InviteScreen(),
          '/messages': (context) => const MessagesScreen(),
          '/product-list': (context) => const ProductListScreen(),
          '/product-detail': (context) => const ProductDetailScreen(),
          '/checkout': (context) => const CheckoutScreen(),
          '/unified-orders': (context) => const UnifiedOrdersScreen(),
          '/unified-order-detail': (context) => const UnifiedOrderDetailScreen(),
          '/review': (context) => const ReviewScreen(),
          '/refund': (context) => const RefundScreen(),
          '/member-card': (context) => const MemberCardScreen(),
          '/my-coupons': (context) => const MyCouponsScreen(),
          '/coupon-center': (context) => const CouponCenterScreen(),
          '/favorites': (context) => const FavoritesScreen(),
          '/address-list': (context) => const AddressListScreen(),
          '/address-edit': (context) => const AddressEditScreen(),
        },
      ),
    );
  }
}
