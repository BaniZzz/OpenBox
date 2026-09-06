import 'package:bossip_mobile/features/chat/empty_chat_screen.dart';
import 'package:bossip_mobile/features/chat/state/config_providers.dart';
import 'package:bossip_mobile/features/chat/widgets/composer/composer.dart';
import 'package:bossip_mobile/shared/api/containers_api.dart';
import 'package:bossip_mobile/shared/appearance/tokens.dart';
import 'package:bossip_mobile/shared/i18n/i18n.dart';
import 'package:bossip_mobile/shared/models/app_config.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

I18nBundle _bundle() => I18nBundle({
  'en-US': {
    'workspace': {
      'greeting': {
        'morning': 'Good morning.',
        'afternoon': 'Good afternoon.',
        'evening': 'Good evening.',
      },
      'suggestions': <dynamic>[],
      'sandbox': {
        'title': 'A sandbox is needed',
        'body': 'Create one now?',
        'create': 'Create sandbox',
      },
    },
    'chat': {
      'composer': {'placeholder': 'Message'},
      'reasoning': {'default': 'Default'},
    },
  },
});

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('empty chat never offers the legacy manual sandbox action', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'bossip:lang': 'en-US'});
    final prefs = await SharedPreferences.getInstance();

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          i18nProvider.overrideWith(() => I18nController(_bundle(), prefs)),
          appConfigProvider.overrideWith(
            (ref) async => const AppConfig(models: []),
          ),
          runningContainerProvider.overrideWith((ref) async => null),
        ],
        child: MaterialApp(
          theme: ThemeData(
            extensions: [
              BossipTokens.resolve(BossipThemeName.default_, Brightness.light),
            ],
          ),
          home: const Scaffold(body: EmptyChatScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(Composer), findsOneWidget);
    expect(find.text('A sandbox is needed'), findsNothing);
    expect(find.text('Create sandbox'), findsNothing);
  });
}
