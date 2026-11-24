# CineHarbor localization

English is the default. Supported UI options are English, Simplified Chinese,
Traditional Chinese, Japanese and Korean. Marketing and showreel copy stays English.

`web/i18n.js` translates only static JavaScript string literals and static parts
of tagged template literals. Interpolated project titles, prompts, scripts, media
names, file paths and authorization codes are never sent to or changed by the
translation layer. Locale preference is local browser storage; the native menu
uses the same preference through a main-frame, loopback-origin-checked message.

`source-fragments.json` is the versioned UI/policy inventory. Catalogs live in
`web/locales/`. Run `python3 tools/localization/pack.py` to check coverage and pack
`web/catalogs.js`. This needs only Python's standard library. The app bundles the
static catalogs; it never downloads a translator or requests a cloud GPU for UI
language changes. Native strings are in `assets/branding/native-locales.json`.

`prepare.cjs` is a developer migration helper (`npm install` in this folder,
Acorn pinned in package.json). It wraps static strings without parsing or
rewriting user data. It is not an app runtime dependency. `generate_catalogs.py`
is a developer-only offline draft translator using an Apache-2.0 local model.
Weights, translation tooling and caches are not shipped in the app. Editorial
English overrides are in `english-overrides.json`; native-speaker review of
translation drafts remains a release step.

Current catalog provenance is recorded in `translation-provenance.json`. The optional local model download was stopped before completion. Current drafts used only fixed UI/policy text in Google Translate, with edited terminology and separately authored eligibility/privacy messages. No user project content or credentials were translated or uploaded.
