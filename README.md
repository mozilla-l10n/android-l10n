# Android Cross-Product Localization Repository

This repository stores the unified English files from the Android projects participating, and the localized files for them.

Localization happens on [Pontoon](https://pontoon.mozilla.org/projects/android-l10n/). Please get in touch with delphine (at) mozilla (dot) com directly for more information.

## String Updates

Automation is used to extract daily new English strings from the code repositories. It’s possible to invoke [automation manually](https://github.com/mozilla-l10n/android-l10n/actions) for each individual project.

## TOML Files

Each project has its own [l10n project configuration](https://moz-l10n-config.readthedocs.io/en/latest/fileformat.html) file, e.g. `mozilla-mobile/android-components/l10n.toml` for `android-components`.

The TOML files in the root of the repository are used in Pontoon:
* `firefox.toml` maps to [Firefox for Android](https://pontoon.mozilla.org/projects/firefox-for-android/), which includes strings from both `fenix` and `android-components`.
* `focus.toml` maps to [Focus for Android](https://pontoon.mozilla.org/projects/focus-for-android/).
