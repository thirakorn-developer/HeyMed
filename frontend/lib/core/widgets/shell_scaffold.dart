import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class ShellScaffold extends StatelessWidget {
  final Widget child;

  const ShellScaffold({super.key, required this.child});

  int _currentIndex(BuildContext context) {
    final location = GoRouterState.of(context).matchedLocation;
    if (location.startsWith('/drugs')) return 1;
    if (location.startsWith('/interactions')) return 2;
    if (location.startsWith('/inventory')) return 3;
    if (location.startsWith('/prescriptions')) return 4;
    if (location.startsWith('/chat')) return 5;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: child,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex(context),
        onDestinationSelected: (index) {
          switch (index) {
            case 0:
              context.go('/dashboard');
            case 1:
              context.go('/drugs');
            case 2:
              context.go('/interactions');
            case 3:
              context.go('/inventory');
            case 4:
              context.go('/prescriptions');
            case 5:
              context.go('/chat');
          }
        },
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.medication), label: 'Drugs'),
          NavigationDestination(icon: Icon(Icons.warning_amber), label: 'DDI'),
          NavigationDestination(icon: Icon(Icons.inventory_2), label: 'Stock'),
          NavigationDestination(icon: Icon(Icons.receipt_long), label: 'Rx'),
          NavigationDestination(icon: Icon(Icons.chat), label: 'AI'),
        ],
      ),
    );
  }
}
