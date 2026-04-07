import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'providers/auth_provider.dart';
import 'providers/chat_provider.dart';
import 'providers/health_provider.dart';
import 'screens/splash_screen.dart';
import 'screens/login_screen.dart';
import 'screens/main_screen.dart';
import 'screens/home/home_screen.dart';
import 'screens/ai/ai_home_screen.dart';
import 'screens/ai/chat_screen.dart';
import 'screens/health/checkup_screen.dart';
import 'screens/health/report_detail_screen.dart';
import 'screens/health/trend_screen.dart';
import 'screens/health/symptom_screen.dart';
import 'screens/health/tcm_screen.dart';
import 'screens/health/drug_screen.dart';
import 'screens/health/drug_chat_screen.dart';
import 'screens/health/health_profile_screen.dart';
import 'screens/family/family_screen.dart';
import 'screens/services/services_screen.dart';
import 'screens/services/service_detail_screen.dart';
import 'screens/services/expert_list_screen.dart';
import 'screens/services/expert_detail_screen.dart';
import 'screens/order/orders_screen.dart';
import 'screens/order/order_detail_screen.dart';
import 'screens/points/points_screen.dart';
import 'screens/points/points_mall_screen.dart';
import 'screens/plan/health_plan_screen.dart';
import 'screens/content/articles_screen.dart';
import 'screens/content/article_detail_screen.dart';
import 'screens/profile/profile_screen.dart';
import 'screens/profile/settings_screen.dart';
import 'screens/notifications/notifications_screen.dart';
import 'screens/customer_service/cs_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));
  runApp(const BiniHealthApp());
}

class BiniHealthApp extends StatelessWidget {
  const BiniHealthApp({super.key});

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
          '/login': (context) => const LoginScreen(),
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
          '/symptom': (context) => const SymptomScreen(),
          '/tcm': (context) => const TcmScreen(),
          '/drug': (context) => const DrugScreen(),
          '/drug-chat': (context) => const DrugChatScreen(),
          '/health-profile': (context) => const HealthProfileScreen(),
          '/family': (context) => const FamilyScreen(),
          '/services': (context) => const ServicesScreen(),
          '/service-detail': (context) => const ServiceDetailScreen(),
          '/experts': (context) => const ExpertListScreen(),
          '/expert-detail': (context) => const ExpertDetailScreen(),
          '/orders': (context) => const OrdersScreen(),
          '/order-detail': (context) => const OrderDetailScreen(),
          '/points': (context) => const PointsScreen(),
          '/points-mall': (context) => const PointsMallScreen(),
          '/health-plan': (context) => const HealthPlanScreen(),
          '/articles': (context) => const ArticlesScreen(),
          '/article-detail': (context) => const ArticleDetailScreen(),
          '/profile': (context) => const ProfileScreen(),
          '/settings': (context) => const SettingsScreen(),
          '/notifications': (context) => const NotificationsScreen(),
          '/customer-service': (context) => const CsScreen(),
        },
      ),
    );
  }
}
