import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AlipayNative {
  const AlipayNative();

  static const _channel = MethodChannel('com.bossip.bipmobile/alipay');

  /// The map is informational only. Workspace credit is refreshed from the
  /// server because a native SDK callback is not proof of settlement.
  Future<Map<String, dynamic>> pay(String orderString) async {
    final result = await _channel.invokeMapMethod<String, dynamic>('pay', {
      'orderString': orderString,
    });
    return result ?? const {};
  }
}

final alipayNativeProvider = Provider<AlipayNative>(
  (_) => const AlipayNative(),
);
