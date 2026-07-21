// ────────────────────────────────────────────────────────────────────────────
// constants/currency.dart
//
// تهيئة العملة للجمهورية اليمنية.
// Country  : Yemen (YE)
// Currency : Yemeni Rial
// Code     : YER
// Symbol   : ﷼
// Locale   : ar-YE
// Timezone : Asia/Aden
// ────────────────────────────────────────────────────────────────────────────

/// تنسيق مبلغ مالي بالريال اليمني.
///
/// مثال: `formatYer(5400)` → `"5,400 ﷼"`
String formatYer(double amount) {
  // تنسيق بسيط بدون حزمة intl إضافية؛ سيُستبدل بـ NumberFormat('ar-YE') عند ربط API.
  final parts = amount.toStringAsFixed(0).split('').reversed.toList();
  final buffer = StringBuffer();
  for (var i = 0; i < parts.length; i++) {
    if (i > 0 && i % 3 == 0) buffer.write(',');
    buffer.write(parts[i]);
  }
  return '${buffer.toString().split('').reversed.join()} ﷼';
}

/// رمز العملة الرسمي.
const String kCurrencyCode   = 'YER';

/// رمز العملة للعرض.
const String kCurrencySymbol = '﷼';

/// اسم العملة بالعربية.
const String kCurrencyName   = 'ريال يمني';

/// بلد التشغيل.
const String kCountryName    = 'الجمهورية اليمنية';

/// توقيت التشغيل.
const String kTimezone       = 'Asia/Aden';

/// Locale للتطبيق.
const String kLocale         = 'ar-YE';

/// المؤسسة المشغِّلة (يمكن تخصيصها لكل محافظة).
const String kOrganizationName = 'المؤسسة العامة للكهرباء';
