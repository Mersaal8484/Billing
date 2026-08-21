import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'odoo_api_client.dart';

class OdooUserInfo {
  final int uid;
  final String name;
  final String login;
  final String db;
  final Map<String, bool>? roles;
  
  const OdooUserInfo({
    required this.uid,
    required this.name,
    required this.login,
    required this.db,
    this.roles,
  });
}

/// Handles login/logout against Odoo's built-in session controller.
/// This is separate from the custom `/api/v1/utility/*` routes: Odoo's
/// session cookie, once set here, is what makes `auth='user'` routes work.
class AuthService {
  static const _dbKey = 'odoo_db';
  static const _loginKey = 'odoo_login';

  final OdooApiClient _client;
  final FlutterSecureStorage _storage;
  
  OdooUserInfo? _currentUser;
  OdooUserInfo? get currentUser => _currentUser;

  AuthService(this._client, {FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  /// Logs in against `/web/session/authenticate` (standard Odoo endpoint,
  /// present in every Odoo instance, no custom code needed).
  Future<OdooUserInfo> login({
    required String db,
    required String login,
    required String password,
  }) async {
    final result = await _client.postJson('/web/session/authenticate', {
      'db': db,
      'login': login,
      'password': password,
    });

    final uid = result['uid'];
    if (uid == null || uid == false) {
      throw OdooApiException('Invalid credentials or database name');
    }

    await _storage.write(key: _dbKey, value: db);
    await _storage.write(key: _loginKey, value: login);

    Map<String, bool>? userRoles;
    try {
      final roleResult = await _client.postJson('/api/v1/utility/auth/roles', {});
      if (roleResult['success'] == true) {
        final r = roleResult['roles'] as Map<String, dynamic>?;
        if (r != null) {
          userRoles = r.map((k, v) => MapEntry(k, v == true));
        }
      }
    } catch (_) {
      // Ignore if roles API fails, user will have basic access
    }

    _currentUser = OdooUserInfo(
      uid: uid as int,
      name: (result['name'] as String?) ?? login,
      login: login,
      db: db,
      roles: userRoles,
    );
    return _currentUser!;
  }

  Future<void> logout() async {
    try {
      await _client.postJson('/web/session/destroy', {});
    } catch (_) {
      // Ignore network errors on logout; clear locally regardless.
    }
    await _client.clearSession();
    await _storage.delete(key: _dbKey);
    await _storage.delete(key: _loginKey);
  }

  /// Quick check used at app startup to decide Login vs Home screen.
  Future<bool> isLoggedIn() => _client.hasSessionCookie();

  /// Restores session user info and roles if cookie is still valid
  Future<bool> restoreSession() async {
    final hasCookie = await isLoggedIn();
    if (!hasCookie) return false;

    final db = await _storage.read(key: _dbKey);
    final login = await _storage.read(key: _loginKey);
    if (db == null || login == null) return false;

    Map<String, bool>? userRoles;
    try {
      final roleResult = await _client.postJson('/api/v1/utility/auth/roles', {});
      if (roleResult['success'] == true) {
        final r = roleResult['roles'] as Map<String, dynamic>?;
        if (r != null) {
          userRoles = r.map((k, v) => MapEntry(k, v == true));
        }
      }
    } catch (_) {}

    _currentUser = OdooUserInfo(
      uid: 0,
      name: login,
      login: login,
      db: db,
      roles: userRoles,
    );
    return true;
  }

  Future<String?> get savedDb => _storage.read(key: _dbKey);
  Future<String?> get savedLogin => _storage.read(key: _loginKey);
}
