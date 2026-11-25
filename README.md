# CineHarbor

A local-first video production workspace for macOS, formerly GC Labs. Plan shots and references on your Mac, generate with your own Google Colab runtime, and cut the selected takes into a finished video.

[简体中文](README.zh-CN.md) · [Build 32 release notes](https://github.com/jasperfilm/CineHarbor/releases/tag/v1.2.12-b32-h3) · [Download the Apple Silicon DMG](https://github.com/jasperfilm/CineHarbor/releases/download/v1.2.12-b32-h3/CineHarbor-1.2.12-Build32-arm64.dmg)

Requires macOS 13 or later. This GitHub development build uses ad-hoc signing and has not been notarized by Apple.

![CineHarbor Build 32 storyboard and shot settings](assets/screenshots/01-project-and-shot-board.jpg)

## What you can do

| Stage | In CineHarbor |
| --- | --- |
| Plan | Break a script into shots, write prompts, and attach reference images and character or scene cards. |
| Prepare | Browse model candidates, import ComfyUI canvas or API JSON, and define model files and pinned custom nodes. Templates can be inspected locally. |
| Generate | Connect an eligible Google Colab runtime, prepare its environment, and submit shots individually or in a batch. Review multiple takes and extract the last frame to continue the next shot. |
| Edit and export | Arrange accepted clips on the timeline, trim them, add music and subtitles, and export an MP4 on your Mac. |
| Back up and stop | Save and verify results in your Google Drive before releasing the runtime managed by CineHarbor. |

Use **Media Library** and **Reference Cards** to reuse visual references across shots.

![Local project media and reference cards](assets/screenshots/02-media-and-reference-cards.jpg)

## Models and workflows

**This GitHub development release is 1.2.12 Build 32**, the development version with a built-in MiniMax H3 image-to-video adapter. The H3 restore flow reads a compatible BF16 model backup and manifest from your own Drive. Check the [MiniMax H3 license](assets/licenses/models/MiniMax-H3-LICENSE.txt) for eligible uses and regions.

The workflow library includes Wan 2.2, LTX 2.5, Qwen Image, Qwen Image Edit, and ACE-Step templates. A template defines a workflow. The actual model files, installed nodes, and compute still need to be available in the selected runtime.

Six full-precision presets ship with those templates: Wan 2.2 I2V FP16, LTX 2.5 22B BF16, Qwen Image 2512 BF16, Qwen Image Edit 2511 BF16, ACE-Step 1.5, and ACE-Step 1.5 XL.

![Build 32 model catalog showing MiniMax H3, LTX and Wan](assets/screenshots/04-model-catalog.jpg)

![Built-in ComfyUI workflow templates and the canvas or API JSON import](assets/screenshots/05-workflow-templates.jpg)

## Final cut

Use **Edit & Deliver** to assemble your chosen takes with sound and subtitles, then export locally.

![Edit & Deliver with timeline, audio and export controls](assets/screenshots/03-edit-and-export.jpg)

## Browser mode (macOS, Linux, and Windows)

Run the local workbench in a browser on macOS, Linux, or Windows. Google Colab integration requires the official CLI on macOS or Linux. Video probing, last-frame extraction, and MP4 rendering use the native Apple Silicon AVFoundation helper.

```bash
python -B gclabs_cli.py
```

In a Python 3.12+ virtual environment, use `python -m pip install .` from the checkout. Both `cineharbor` and `gclabs` then start the workbench. The Python distribution stays named `gc-labs` for in-place upgrades. `python -m pip install -e .` is also available for development. When replacing an installed copy with the same version, use `python -m pip install --force-reinstall .`.

`--port` defaults to 8766. `--page studio` opens the shot board instead of Colab Control. `--no-browser` skips opening a window. `--data-dir` chooses the workspace folder. `CINEHARBOR_DATA` is the environment override, and an existing `GC_LABS_DATA` value is still read when `CINEHARBOR_DATA` is unset.

The launcher keeps the existing platform folders: `~/Library/Application Support/Jasper Workstation` on macOS, `%APPDATA%\GC Labs` on Windows, and `~/.local/share/gc-labs` on Linux. If you used `python -B server.py` with its default checkout `data/` directory, point the browser launcher at that same directory with `--data-dir`. The native Mac app uses its own existing Application Support path.

## Get started

Running from source, including the browser launcher above, needs Python 3.12 or newer. That matches `google-colab-cli`, which requires 3.12. Building the native macOS app needs Apple Silicon, macOS 13 or later, Xcode command-line tools, and CPython 3.13, because that build copies the 3.13 runtime into the app.

1. Install the source package into a virtual environment for the [official Google Colab CLI](https://github.com/googlecolab/google-colab-cli) on macOS and Linux. The package selects version 0.7.5 for the current sign-in flow. For the optional local ComfyUI bridge or a separately compiled macOS media helper, run the launcher from the checkout that contains those dependencies. The Python installation does not include those components.
2. Use a browser launcher above, or run `python -B server.py` from the source directory and open [the local workspace](http://127.0.0.1:8766). You can create a project and review workflows before allocating a GPU.
3. For a native development build, set `CINEHARBOR_SDK_PYTHON` to the Python 3.13 executable in the environment with Colab CLI 0.7.5. The local bridge's pinned build dependencies are in [requirements-local.lock](macos/requirements-local.lock). `GC_LABS_SDK_PYTHON` is still accepted. Supply the separately licensed ComfyUI frontend 1.59.1 archive as `vendor/comfy_frontend.zip`. See [component source references](assets/licenses/component-sources.json). Run `python -B macos/build_app.py --stage-only` to stage the app.

Cloud tasks use your own eligible paid Google Colab service. G4 availability and compute charges depend on your account and [Google Colab's limits](https://research.google.com/colaboratory/faq.html). Closing CineHarbor does not stop the runtime. Use **Save and shut down GPU** when your work is finished.

The source release contains code, templates, and documentation. Model weights are supplied separately under their upstream terms. Workspace code is Apache-2.0. Third-party notices and source references are in [assets/licenses](assets/licenses).

CineHarbor is an independent GachaFrame project. Support: contact@gachaframe.com.
