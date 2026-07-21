import 'package:flutter/material.dart';

/// Design goals dictated by field conditions, not office conditions:
/// direct sunlight (high contrast, no low-contrast greys-on-white),
/// gloved or wet fingers (min 48dp targets, 56dp for primary actions),
/// one-handed use (primary actions bottom-anchored), and minimal
/// training (status conveyed by color + icon + text, never color alone).
class AppTheme {
  static const seed = Color(
      0xFF0B5D3B); // utility-green, distinct from Odoo purple to avoid confusion with the ERP UI

  static ThemeData light() {
    final scheme =
        ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.light);
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      visualDensity: VisualDensity.comfortable,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        centerTitle: false,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size.fromHeight(56),
          textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(56),
          textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      listTileTheme: const ListTileThemeData(
        minVerticalPadding: 14,
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withOpacity(0.4),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        color: scheme.surfaceContainerLow,
      ),
    );
  }
}

/// Status colors used consistently across sync center, queue monitor, and
/// assignment lists so a reader learns the palette once.
class StatusColors {
  static const pending = Color(0xFF9E7A00);
  static const synced = Color(0xFF0B5D3B);
  static const inProgress = Color(0xFF1565C0);
  static const error = Color(0xFFB3261E);
  static const offline = Color(0xFF5C5C5C);
}
