import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/chat/presentation/chat_screen.dart';
import '../../features/dashboard/presentation/dashboard_screen.dart';
import '../../features/drug_search/presentation/drug_detail_screen.dart';
import '../../features/drug_search/presentation/drug_search_screen.dart';
import '../../features/interactions/presentation/interaction_checker_screen.dart';
import '../../features/inventory/presentation/inventory_list_screen.dart';
import '../../features/prescriptions/presentation/prescription_list_screen.dart';
import '../auth/auth_provider.dart';
import '../widgets/shell_scaffold.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.maybeWhen(
        authenticated: (_) => true,
        orElse: () => false,
      );
      final isLoginRoute = state.matchedLocation == '/login';

      if (!isLoggedIn && !isLoginRoute) return '/login';
      if (isLoggedIn && isLoginRoute) return '/dashboard';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (_, __) => const LoginScreen(),
      ),
      ShellRoute(
        builder: (_, __, child) => ShellScaffold(child: child),
        routes: [
          GoRoute(
            path: '/dashboard',
            builder: (_, __) => const DashboardScreen(),
          ),
          GoRoute(
            path: '/drugs',
            builder: (_, __) => const DrugSearchScreen(),
            routes: [
              GoRoute(
                path: ':rxcui',
                builder: (_, state) => DrugDetailScreen(
                  rxcui: int.parse(state.pathParameters['rxcui']!),
                ),
              ),
            ],
          ),
          GoRoute(
            path: '/interactions',
            builder: (_, __) => const InteractionCheckerScreen(),
          ),
          GoRoute(
            path: '/inventory',
            builder: (_, __) => const InventoryListScreen(),
          ),
          GoRoute(
            path: '/prescriptions',
            builder: (_, __) => const PrescriptionListScreen(),
          ),
          GoRoute(
            path: '/chat',
            builder: (_, __) => const ChatScreen(),
          ),
        ],
      ),
    ],
  );
});

class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('Login Screen - TODO')),
    );
  }
}
