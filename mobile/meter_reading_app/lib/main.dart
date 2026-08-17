import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:workmanager/workmanager.dart';

import 'app/app.dart';
import 'app/providers.dart';
import 'core/database/app_database.dart';
import 'core/network/auth_service.dart';
import 'core/network/odoo_api_client.dart';
import 'core/network/reading_api_service.dart';
import 'core/sync/sync_engine.dart';
import 'core/sync/sync_settings_service.dart';
import 'features/readings/data/drift_reading_repository.dart';

// ──────────────────────────────────────────────────────────────────────────────
// ⚙️  اضبط هذا العنوان حسب بيئتك:
//   • محاكي Android ←  'http://10.0.2.2:8069'
//   • جهاز حقيقي على نفس الشبكة ← 'http://192.168.1.XX:8069'
//   • سيرفر إنتاج ← 'https://erp.example.com'
// ──────────────────────────────────────────────────────────────────────────────
const _kOdooBaseUrl = 'http://192.168.8.134:8170';

// اسم قاعدة البيانات في odoo.conf  ← يُستخدم في LoginScreen أيضاً
const kOdooDb = 'invoice_utility_erp';

// ──────────────────────────────────────────────────────────────────────────────
// Background sync dispatcher — يعمل في isolate منفصل عند إطلاق WorkManager
// ──────────────────────────────────────────────────────────────────────────────
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    if (task == 'sync_batch_task') {
      // في الـ background isolate نُنشئ كل شيء محلياً
      // (لا يوجد ProviderScope هنا)
      final db = AppDatabase();
      final apiClient = await OdooApiClient.create(
        defaultBaseUrl: _kOdooBaseUrl,
      );
      final repo = DriftReadingRepository(db);
      final readingApi = ReadingApiService(apiClient);
      final engine = SyncEngine(
        repo,
        db,
        SyncSettingsService(),
        readingApi,
      );
      try {
        await engine.syncNow();
      } finally {
        engine.dispose();
        await db.close();
      }
    }
    return true;
  });
}

// ──────────────────────────────────────────────────────────────────────────────
// main
// ──────────────────────────────────────────────────────────────────────────────
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 1️⃣ بناء HTTP client (يحمّل cookie jar المحفوظ من آخر جلسة)
  final apiClient = await OdooApiClient.create(
    defaultBaseUrl: _kOdooBaseUrl,
  );

  // 2️⃣ فتح قاعدة البيانات المحلية
  final db = AppDatabase();

  // 3️⃣ التحقق من وجود session cookie صالح → نتخطى شاشة Login إذا كان موجوداً
  final isLoggedIn = await AuthService(apiClient).isLoggedIn();

  // 4️⃣ تسجيل WorkManager للمزامنة الدورية في الخلفية
  await Workmanager().initialize(callbackDispatcher);
  await Workmanager().registerPeriodicTask(
    'sync-task-id',
    'sync_batch_task',
    frequency: const Duration(minutes: 15),
    existingWorkPolicy: ExistingPeriodicWorkPolicy.keep, // لا تُعيد التسجيل إذا كانت موجودة
    constraints: Constraints(networkType: NetworkType.connected),
  );

  runApp(
    ProviderScope(
      overrides: [
        // ✅ تمرير OdooApiClient الحقيقي بدلاً من UnimplementedError
        odooApiClientProvider.overrideWithValue(apiClient),

        // ✅ نفس instance قاعدة البيانات في كل التطبيق
        databaseProvider.overrideWithValue(db),

        // ✅ حالة تسجيل الدخول من الـ cookie الحقيقي
        authStateProvider.overrideWith((ref) => isLoggedIn),
      ],
      child: const MeterReadingApp(),
    ),
  );
}
