#!/usr/bin/env bash
# Gate: the Flutter locale bundle is a byte-for-byte mirror of frontend-v2.
# Run from anywhere in the repository.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
WEB_DIR="$ROOT_DIR/frontend-v2/src/locales"
MOBILE_DIR="$ROOT_DIR/mobile/assets/locales"
I18N_FILE="$ROOT_DIR/mobile/lib/shared/i18n/i18n.dart"

if ! diff -qr "$WEB_DIR" "$MOBILE_DIR"; then
  echo "FAIL: mobile locales differ from frontend-v2; copy them verbatim" >&2
  exit 1
fi

while IFS= read -r locale_file; do
  namespace="$(basename "$locale_file" .json)"
  if ! grep -Eq "^[[:space:]]*'$namespace',[[:space:]]*$" "$I18N_FILE"; then
    echo "FAIL: namespace '$namespace' is not registered in i18n.dart" >&2
    exit 1
  fi
done < <(find "$WEB_DIR/en-US" -maxdepth 1 -type f -name '*.json' | sort)

echo "OK: mobile locales match frontend-v2 byte for byte"
