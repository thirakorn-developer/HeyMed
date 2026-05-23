import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_endpoints.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

class ApiClient {
  late final Dio dio;
  final _storage = const FlutterSecureStorage();

  ApiClient() {
    dio = Dio(BaseOptions(
      baseUrl: ApiEndpoints.baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ));

    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'access_token');
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        if (error.response?.statusCode == 401) {
          final refreshed = await _refreshToken();
          if (refreshed) {
            final retryResponse = await _retry(error.requestOptions);
            return handler.resolve(retryResponse);
          }
        }
        handler.next(error);
      },
    ));
  }

  Future<bool> _refreshToken() async {
    try {
      final refreshToken = await _storage.read(key: 'refresh_token');
      if (refreshToken == null) return false;

      final response = await Dio().post(
        '${ApiEndpoints.baseUrl}${ApiEndpoints.refresh}',
        data: {'refresh_token': refreshToken},
      );

      await _storage.write(key: 'access_token', value: response.data['access_token']);
      await _storage.write(key: 'refresh_token', value: response.data['refresh_token']);
      return true;
    } catch (_) {
      await _storage.deleteAll();
      return false;
    }
  }

  Future<Response> _retry(RequestOptions requestOptions) async {
    final token = await _storage.read(key: 'access_token');
    requestOptions.headers['Authorization'] = 'Bearer $token';
    return dio.fetch(requestOptions);
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }

  Future<void> clearTokens() async {
    await _storage.deleteAll();
  }

  Future<bool> hasTokens() async {
    final token = await _storage.read(key: 'access_token');
    return token != null;
  }
}
