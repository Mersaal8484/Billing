import 'odoo_api_client.dart';

/// خدمة API الفوترة والتحصيل — تتصل بـ Odoo مباشرة
/// تعكس آلية عمل Elecollect App لكن عبر endpoints نظامك
class BillingApiService {
  final OdooApiClient _client;
  BillingApiService(this._client);

  // ─── استعلام الرصيد والفاتورة الحالية ────────────────────────────────────

  /// جلب الرصيد الإجمالي وتفاصيل الفواتير للمشترك
  Future<Map<String, dynamic>> getBillInquiry(int customerId) {
    return _client.postJson('/api/v1/utility/billing/balance', {
      'customer_id': customerId,
    });
  }

  /// جلب قائمة الفواتير غير المدفوعة للمشترك
  Future<Map<String, dynamic>> getBills(int customerId) {
    return _client.postJson('/api/v1/utility/billing/bills', {
      'customer_id': customerId,
    });
  }

  // ─── تسجيل التحصيل ───────────────────────────────────────────────────────

  /// تسجيل عملية تحصيل
  Future<Map<String, dynamic>> pay({
    required int customerId,
    required double amount,
    required double dueAmount,
    required String paymentMethod,
    required String transactionId,
    String? reference,
  }) {
    return _client.postJson('/api/v1/utility/billing/pay', {
      'customer_id': customerId,
      'amount': amount,
      'due_amount': dueAmount,
      'payment_method': paymentMethod,
      'transaction_id': transactionId,
      if (reference != null) 'reference': reference,
    });
  }

  /// جلب تقرير تحصيل اليوم للمحصل الحالي
  Future<Map<String, dynamic>> getDailyReport() {
    return _client.postJson('/api/v1/utility/reports/daily', {
      'date': DateTime.now().toIso8601String().substring(0, 10),
    });
  }

  /// جلب سجل عمليات التحصيل للمحصل
  Future<Map<String, dynamic>> getCollectionHistory() {
    return _client.postJson('/api/v1/utility/billing/collection_history', {});
  }
}
