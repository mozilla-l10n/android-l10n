#!/usr/bin/env python3
"""
Analyze locale coverage in Firefox for Android.

Compares:
1. CLDR language names (English)
2. Pontoon completion data for Firefox for Android
3. LocaleUtils.kt maps:
   - LOCALE_TO_DISPLAY_NATIVE_NAME_MAP
   - LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP

Reports:
- Locales present in Pontoon (approved_strings > 0) but missing from
  LOCALE_TO_DISPLAY_NATIVE_NAME_MAP.
- Locales present in LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP whose name either
  has no CLDR equivalent or differs from the CLDR English name.
"""

import json
import re
import sys
import urllib.request
from urllib.error import URLError

# Locale codes to skip in all checks
EXCEPTIONS = [
    "en-CA",
    "en-GB",
    "es-AR",
    "es-CL",
    "es-ES",
    "es-MX",
    "zh-CN",
    "zh-TW",
]

CLDR_URL = (
    "https://raw.githubusercontent.com/unicode-org/cldr-json/main"
    "/cldr-json/cldr-localenames-full/main/en/languages.json"
)
PONTOON_URL = "https://pontoon.mozilla.org/api/v2/projects/firefox-for-android/"
LOCALE_UTILS_URL = (
    "https://raw.githubusercontent.com/mozilla-firefox/firefox/main"
    "/mobile/android/fenix/app/src/main/java/org/mozilla/fenix/utils/LocaleUtils.kt"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fetch_url(url: str) -> str:
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode("utf-8")
    except URLError as exc:
        print(f"ERROR fetching {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def fetch_cldr_languages() -> dict[str, str]:
    """Return {locale_code: english_name} from CLDR en/languages.json."""
    data = json.loads(fetch_url(CLDR_URL))
    return data["main"]["en"]["localeDisplayNames"]["languages"]


def fetch_cldr_self_name(code: str) -> str | None:
    """
    Return the locale's own-language name from its CLDR languages.json, or None
    if the file doesn't exist or the self-entry is absent.
    """
    base_url = (
        "https://raw.githubusercontent.com/unicode-org/cldr-json/main"
        "/cldr-json/cldr-localenames-full/main"
    )
    url = f"{base_url}/{code}/languages.json"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        langs = data["main"][code]["localeDisplayNames"]["languages"]
        return langs.get(code)
    except Exception:
        return None


def fetch_pontoon_locales() -> dict[str, dict]:
    """
    Return locales with approved_strings > 0 from Pontoon.

    Each entry: {
        "name": str,          # locale display name from Pontoon
        "approved": int,
        "total": int,
        "missing": int,       # total - approved
    }
    """
    locales: dict[str, dict] = {}
    url: str | None = PONTOON_URL

    while url:
        data = json.loads(fetch_url(url))
        for loc in data.get("localizations", []):
            approved = loc.get("approved_strings", 0)
            if approved <= 0:
                continue
            code = loc["locale"]["code"]
            total = loc.get("total_strings", 0)
            locales[code] = {
                "name": loc["locale"].get("name", ""),
                "approved": approved,
                "total": total,
                "missing": total - approved,
            }
        url = data.get("next")

    return locales


def parse_kotlin_map(lines: list[str], map_name: str) -> dict[str, str]:
    """Find map_name in lines, then collect "key" to "value" pairs until a lone ')'."""
    entries: dict[str, str] = {}
    collecting = False
    for line in lines:
        if not collecting:
            if map_name in line:
                collecting = True
            continue
        if line.strip() == ")":
            break
        m = re.search(r'"([^"]+)"\s+to\s+"([^"]*)"', line)
        if m:
            entries[m.group(1)] = m.group(2)
    return entries


def cldr_name_for(cldr_languages: dict[str, str], code: str) -> str | None:
    """
    Look up the CLDR English name for a locale code.

    Tries the full code first (e.g. "pt-BR"), then the base language (e.g. "pt").
    """
    if code in cldr_languages:
        return cldr_languages[code]
    base = code.split("-")[0]
    return cldr_languages.get(base)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Fetching CLDR language names …")
    cldr_languages = fetch_cldr_languages()

    print("Fetching Pontoon completion data …")
    all_pontoon = fetch_pontoon_locales()

    print("Fetching LocaleUtils.kt …")
    kt_lines = fetch_url(LOCALE_UTILS_URL).splitlines()
    native_map = parse_kotlin_map(
        kt_lines, "private val LOCALE_TO_DISPLAY_NATIVE_NAME_MAP"
    )
    english_map = parse_kotlin_map(kt_lines, "val LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP")

    # Apply exceptions
    pontoon_locales = {
        code: data for code, data in all_pontoon.items() if code not in EXCEPTIONS
    }

    print(f"\nActive locales on Pontoon (approved_strings > 0): {len(pontoon_locales)}")
    print(f"Entries in LOCALE_TO_DISPLAY_NATIVE_NAME_MAP : {len(native_map)}")
    print(f"Entries in LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP: {len(english_map)}")

    # ------------------------------------------------------------------
    # Check 1: locales missing from LOCALE_TO_DISPLAY_NATIVE_NAME_MAP
    # ------------------------------------------------------------------
    missing_native_no_cldr = []  # (code, self_name_or_None) — no English CLDR name
    missing_native_has_cldr = []  # missing from map but CLDR name exists

    for code in sorted(pontoon_locales):
        if code in native_map:
            continue
        cldr = cldr_name_for(cldr_languages, code)
        if cldr and cldr != pontoon_locales[code]["name"]:
            missing_native_has_cldr.append((code, cldr))
        else:
            missing_native_no_cldr.append(code)

    print()
    print("=" * 75)
    print(
        "LOCALES MISSING FROM LOCALE_TO_DISPLAY_NATIVE_NAME_MAP (no English CLDR name)"
    )
    print("=" * 75)
    if missing_native_no_cldr:
        # Fetch CLDR self-names for each locale
        self_names = {
            code: fetch_cldr_self_name(code) for code in missing_native_no_cldr
        }
        header = (
            f"{'Code':<15} {'Pontoon name':<30} {'Missing strings':>15}  CLDR self-name"
        )
        print(header)
        print("-" * len(header))
        for code in missing_native_no_cldr:
            data = pontoon_locales[code]
            self_name = self_names[code] or "(not found)"
            print(f"{code:<15} {data['name']:<30} {data['missing']:>15}  {self_name}")
    else:
        print("  None.")

    print()
    print("=" * 75)
    print(
        "LOCALES MISSING FROM LOCALE_TO_DISPLAY_NATIVE_NAME_MAP (CLDR name available)"
    )
    print("=" * 75)
    if missing_native_has_cldr:
        header = f"{'Code':<15} {'Pontoon name':<30} {'Missing strings':>15}  CLDR name"
        print(header)
        print("-" * len(header))
        for code, cldr in missing_native_has_cldr:
            data = pontoon_locales[code]
            print(f"{code:<15} {data['name']:<30} {data['missing']:>15}  {cldr}")
    else:
        print("  None.")

    # ------------------------------------------------------------------
    # Check 2: LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP vs CLDR
    # ------------------------------------------------------------------
    print()
    print("=" * 75)
    print("LOCALE_TO_DISPLAY_ENGLISH_NAME_MAP: NOT IN CLDR OR NAME MISMATCH")
    print("=" * 75)

    issues: list[
        tuple[str, str, str, str]
    ] = []  # (code, issue_type, kt_name, cldr_name)

    for code in sorted(pontoon_locales):
        if code not in english_map:
            continue
        kt_name = english_map[code]
        cldr = cldr_name_for(cldr_languages, code)
        if cldr is None:
            issues.append((code, "not in CLDR", kt_name, ""))
        elif kt_name != cldr:
            issues.append((code, "name mismatch", kt_name, cldr))

    if issues:
        header = f"{'Code':<15} {'Issue':<15} {'Kotlin name':<35} {'CLDR name'}"
        print(header)
        print("-" * len(header))
        for code, issue, kt_name, cldr in issues:
            print(f"{code:<15} {issue:<15} {kt_name!r:<35} {cldr!r}")
    else:
        print("  No issues found.")

    if missing_native_no_cldr or missing_native_has_cldr or issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
