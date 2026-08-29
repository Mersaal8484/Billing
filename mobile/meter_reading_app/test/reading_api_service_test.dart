import 'package:flutter_test/flutter_test.dart';
import 'package:meter_reading_app/core/network/reading_api_service.dart';

void main() {
  test('batch payload sends the authoritative meter id', () {
    const payload = MeterReadingPayload(
      meterId: 712,
      meterNumber: '10/047519',
      resubmitReadingId: 91,
      readingValue: 456.5,
    );

    expect(payload.toJson(), containsPair('meter_id', 712));
    expect(payload.toJson(), containsPair('meter_number', '10/047519'));
    expect(payload.toJson(), containsPair('resubmit_reading_id', 91));
  });

  test('batch payload does not replace a missing meter number with an id', () {
    const payload = MeterReadingPayload(
      meterId: 712,
      readingValue: 456.5,
    );

    expect(payload.toJson(), containsPair('meter_id', 712));
    expect(payload.toJson().containsKey('meter_number'), isFalse);
  });
}
