import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../shared/models/billing.dart';
import '../api/billing_api.dart';
import 'alipay_native.dart';

class PaymentLaunchResult {
  const PaymentLaunchResult({required this.order, required this.usedNativeSdk});

  final PaymentOrder order;
  final bool usedNativeSdk;
}

class PaymentLauncher {
  PaymentLauncher(this._api, this._alipay);

  final BillingApi _api;
  final AlipayNative _alipay;

  Future<PaymentLaunchResult> launch(
    PaymentOrder order,
    PaymentProviderInfo provider,
  ) async {
    if (!order.pending) {
      return PaymentLaunchResult(order: order, usedNativeSdk: false);
    }

    if (provider.id == 'alipay' && provider.supportsAppCheckout) {
      try {
        final checkout = await _api.createAppCheckout(order.id);
        if (!checkout.order.pending || checkout.sdkPayload == null) {
          return PaymentLaunchResult(
            order: checkout.order,
            usedNativeSdk: true,
          );
        }
        await _alipay.pay(checkout.sdkPayload!);
        // The SDK result is advisory; only the signed server query below can
        // move the order to paid and credit the workspace.
        final refreshed = provider.supportsStatusQuery
            ? await _api.refreshOrder(order.id)
            : checkout.order;
        return PaymentLaunchResult(order: refreshed, usedNativeSdk: true);
      } on MissingPluginException {
        // A development simulator has no Alipay binary. Keep the browser
        // cashier usable for QA and for configurations predating app checkout.
      } on PlatformException catch (error) {
        if (error.code != 'SDK_UNAVAILABLE') rethrow;
      }
    }

    final withCheckout = order.checkoutUrl == null
        ? await _api.continueOrder(order.id)
        : order;
    final rawUrl = withCheckout.checkoutUrl;
    final uri = rawUrl == null ? null : Uri.tryParse(rawUrl);
    if (uri == null ||
        !await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      throw StateError('Unable to open payment checkout');
    }
    return PaymentLaunchResult(order: withCheckout, usedNativeSdk: false);
  }
}

final paymentLauncherProvider = Provider<PaymentLauncher>((ref) {
  return PaymentLauncher(
    ref.watch(billingApiProvider),
    ref.watch(alipayNativeProvider),
  );
});
