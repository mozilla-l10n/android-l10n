#!/usr/bin/env python3
"""
Analyze locale coverage in Firefox Focus for Android.

Compares:
1. CLDR language names (English and self-names)
2. Pontoon completion data for Firefox Focus for Android
3. LocaleDescriptor.kt fillLanguageCodeAndNameMap entries

Reports:
- Locales present in Pontoon (approved_strings > 0) but missing from
  fillLanguageCodeAndNameMap, along with CLDR self-name if available.
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
PONTOON_URL = "https://pontoon.mozilla.org/api/v2/projects/focus-for-android/"
LOCALE_DESCRIPTOR_URL = (
    "https://raw.githubusercontent.com/mozilla-firefox/firefox/main"
    "/mobile/android/focus-android/app/src/main/java/org/mozilla/focus"
    "/locale/screen/LocaleDescriptor.kt"
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

    Tries the full code first (e.g. "pt-BR"), then the base language (e.g. "pt").
    """
    base_url = (
        "https://raw.githubusercontent.com/unicode-org/cldr-json/main"
        "/cldr-json/cldr-localenames-full/main"
    )
    base = code.split("-")[0]
    for try_code in dict.fromkeys([code, base]):  # deduplicate while preserving order
        url = f"{base_url}/{try_code}/languages.json"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            langs = data["main"][try_code]["localeDisplayNames"]["languages"]
            name = langs.get(code) or langs.get(base)
            if name:
                return name
        except Exception:
            continue
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


def parse_language_code_map(lines: list[str]) -> dict[str, str]:
    """
    Parse entries from fillLanguageCodeAndNameMap in LocaleDescriptor.kt.

    Matches lines of the form:
        languageCodeAndNameMap["key"] = "value"
    """
    entries: dict[str, str] = {}
    in_function = False
    for line in lines:
        if not in_function:
            if "fillLanguageCodeAndNameMap" in line and "private fun" in line:
                in_function = True
            continue
        # Stop at the closing brace of the function
        if line.strip() == "}":
            break
        m = re.search(r'languageCodeAndNameMap\["([^"]+)"\]\s*=\s*"([^"]*)"', line)
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

    print("Fetching LocaleDescriptor.kt …")
    kt_lines = fetch_url(LOCALE_DESCRIPTOR_URL).splitlines()
    locale_map = parse_language_code_map(kt_lines)

    # Apply exceptions
    pontoon_locales = {
        code: data for code, data in all_pontoon.items() if code not in EXCEPTIONS
    }

    print(f"\nActive locales on Pontoon (approved_strings > 0): {len(pontoon_locales)}")
    print(f"Entries in fillLanguageCodeAndNameMap              : {len(locale_map)}")

    # ------------------------------------------------------------------
    # Check: locales missing from fillLanguageCodeAndNameMap
    # ------------------------------------------------------------------
    # Focus falls back to locale.getDisplayName(locale) for locales not in the
    # map. Mainstream languages are handled correctly by Android/ICU. We only
    # flag locales where CLDR also has no self-name, as these are most likely
    # unknown to Android ICU and need an explicit entry in the map.

    # Collect all locales not covered by the map
    not_in_map = []
    for code in sorted(pontoon_locales):
        base = code.split("-")[0]
        if code not in locale_map and base not in locale_map:
            not_in_map.append(code)

    # Fetch CLDR self-names for candidates and split into two groups
    print(f"\nFetching CLDR self-names for {len(not_in_map)} locales not in map …")
    self_names = {code: fetch_cldr_self_name(code) for code in not_in_map}

    missing_no_cldr = [c for c in not_in_map if not self_names[c]]
    missing_has_cldr = [c for c in not_in_map if self_names[c]]

    print()
    print("=" * 75)
    print(
        "LOCALES MISSING FROM fillLanguageCodeAndNameMap — no CLDR self-name found"
    )
    print("(Android ICU likely can't display these; consider adding them to the map)")
    print("=" * 75)
    if missing_no_cldr:
        header = f"{'Code':<15} {'Pontoon name':<30} {'Missing strings':>15}"
        print(header)
        print("-" * len(header))
        for code in missing_no_cldr:
            data = pontoon_locales[code]
            print(f"{code:<15} {data['name']:<30} {data['missing']:>15}")
    else:
        print("  None.")

    print()
    print("=" * 75)
    print(
        "LOCALES MISSING FROM fillLanguageCodeAndNameMap — CLDR self-name available"
    )
    print("(Android ICU fallback likely works; listed for reference)")
    print("=" * 75)
    if missing_has_cldr:
        header = f"{'Code':<15} {'Pontoon name':<30} {'Missing strings':>15}  CLDR self-name"
        print(header)
        print("-" * len(header))
        for code in missing_has_cldr:
            data = pontoon_locales[code]
            print(
                f"{code:<15} {data['name']:<30} {data['missing']:>15}  {self_names[code]}"
            )
    else:
        print("  None.")

    if missing_no_cldr:
        sys.exit(1)


if __name__ == "__main__":
    main()
