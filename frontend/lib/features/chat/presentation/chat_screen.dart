import 'package:flutter/material.dart';

class ChatScreen extends StatelessWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Assistant')),
      body: const Center(child: Text('AI Pharmacist Assistant - Coming Soon')),
    );
  }
}
