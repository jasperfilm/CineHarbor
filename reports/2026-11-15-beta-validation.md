# GC Labs 0.2.0 local beta verification

- Native app: `~/Applications/GC Labs.app`, Apple Silicon, macOS 13 or later.
- Self-contained runtime: copied CPython3.13 and official Colab SDK; no private projects, model weights or credentials in app bundle.
- Ad-hoc code signature verified after application startup and CLI use. Python bytecode writing disabled to preserve the signed bundle.
- DMG 149MB, image integrity verification succeeded. SHA256: `43e0a99949364f49fc73802f94c5bb007f5bf00c9a702edbf2f34859c461642f`.
- 34 Python tests passed before packaging, plus nullable-inspection/native-state, legacy runtime-state and benchmark Node tests.
- Additional clean-install verification, idle bridge and HEAD-media checks passed after packaging; test-only changes do not alter bundled application.
- Native runtime: current account verified;889.99CU,0CU/hour,0active sessions. No new cloud resources allocated or released during this app session.
- Project persistence and switching verified; disposable QA project recoverably removed and accepted six-shot project restored.
- Native screenshot evidence: gc-labs-manager.png, gc-labs-studio.png.
- ComfyUI button under no active G4 displays an actionable message rather than navigating to a dead URL.
- Full G4 restore/generate/backup/release and connected ComfyUI bridge are NOT yet verified under the new app.
- Initial OAuth login UI, backup import, general model adapters, cross-machine installation and notarization remain pending. This is a local private beta, not a public release candidate.
