import 'odoo_api_client.dart';

/// خدمة API الفوترة والتحصيل — تتصل بـ Odoo مباشرة
/// تعكس آلية عمل Elecollect App لكن عبر endpoints نظامك
class BillingApiService {
  final OdooApiClient _client;
  BillingApiService(this._client);

  // ─── استعلام الرصيد والفاتورة الحالية ────────────────────────────────────

  /// استعلام المحصل عن حساب واحد ضمن المسارات المصرح بها.
  Future<Map<String, dynamic>> getCollectorAccount({
    String? customerNumber,
    String? qrReference,
  }) {
    return _client.postJson('/api/v1/utility/collector/account', {
      if (customerNumber != null) 'customer_number': customerNumber,
      if (qrReference != null) 'external_qr_reference': qrReference,
    });
  }

  // ─── تسجيل التحصيل ───────────────────────────────────────────────────────

  /// يسجل تحصيلاً نقدياً على فاتورة محاسبية محددة.
  Future<Map<String, dynamic>> collectCash({
    required int orderId,
    required int invoiceId,
    required double amount,
    required String idempotencyKey,
  }) {
    return _client.postJson('/api/v1/utility/collector/collect_cash', {
      'order_id': orderId,
      'invoice_id': invoiceId,
      'amount': amount,
      'idempotency_key': idempotencyKey,
    });
  }

}
