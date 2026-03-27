# Android Cross-Product Localization Repository

This repository contains the source locale messages for Android projects. They are extracted from the active branches (Nightly, Beta, Release) by scheduled [GitHub actions](https://github.com/mozilla-l10n/android-l10n/actions), which produce pull requests that are reviewed by the L10n team before merging.

Localization happens on [Pontoon](https://pontoon.mozilla.org/projects/). Please get in touch with the [program manager](https://mozilla-l10n.github.io/localizer-documentation/products/l10n_project_managers.html) directly for more information.

## String Updates and Linters

Automation currently runs a separate workflow for each project, creating distinct pull requests. The goal is to allow PMs to merge updates to each project independently, without being blocked by an issue in another.

A linter runs automatically on each PR to catch issues like hard-coded brand names and missing variable comments. In case of errors, comments will be added to the open pull request, automatically flagging the original developer where possible. The [linter configuration](https://github.com/mozilla-l10n/android-l10n/blob/main/.github/scripts/linter_config.json) provides a way to add exceptions. If a developer flags a string as an exception for hard-coded brand names, the update workflow will automatically carry over the exception in the local config. Such changes should be reviewed as part of the string review process.

## TOML Files

Each project has its own [l10n project configuration](https://moz-l10n-config.readthedocs.io/en/latest/fileformat.html) file, e.g. `mozilla-mobile/android-components/l10n.toml` for `android-components`.

The TOML files in the root of the repository are used in Pontoon:
* `firefox.toml` maps to [Firefox for Android](https://pontoon.mozilla.org/projects/firefox-for-android/), which includes strings from both `fenix` and `android-components`.
* `focus.toml` maps to [Focus for Android](https://pontoon.mozilla.org/projects/focus-for-android/).
