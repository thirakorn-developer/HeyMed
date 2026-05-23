import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api/api_client.dart';
import '../api/api_endpoints.dart';
import 'auth_state.dart';

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(apiClientProvider));
});

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiClient _api;

  AuthNotifier(this._api) : super(const AuthState.initial()) {
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final hasTokens = await _api.hasTokens();
    if (hasTokens) {
      try {
        final response = await _api.dio.get(ApiEndpoints.me);
        state = AuthState.authenticated(response.data);
      } catch (_) {
        await _api.clearTokens();
        state = const AuthState.unauthenticated();
      }
    } else {
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> login(String email, String password) async {
    state = const AuthState.loading();
    try {
      final response = await _api.dio.post(
        ApiEndpoints.login,
        data: {'email': email, 'password': password},
      );
      await _api.saveTokens(
        response.data['access_token'],
        response.data['refresh_token'],
      );
      final userResponse = await _api.dio.get(ApiEndpoints.me);
      state = AuthState.authenticated(userResponse.data);
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> logout() async {
    await _api.clearTokens();
    state = const AuthState.unauthenticated();
  }
}
