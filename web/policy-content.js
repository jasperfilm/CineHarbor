window.CineHarborPolicyContent = {
  "en": {
    "privacy": {
      "title": "CineHarbor Privacy Policy",
      "sections": [
        {
          "title": "Scope and contact",
          "body": "This document applies to CineHarbor. Contact: contact@gachaframe.com."
        },
        {
          "title": "Local projects",
          "body": "Shot plans, prompts, references, media, task history and exports are managed on your Mac. Interface language selection does not itself send scripts to a translation service. Account authorization records are held separately from a project backup."
        },
        {
          "title": "Google sign-in and Drive access",
          "body": "Cloud features use the Google account you authorize. Account information identifies your account and runtime ownership. Mounting Google Drive requires a separate authorization; signing in or connecting compute does not automatically mount Drive. Review the permissions shown by Google."
        },
        {
          "title": "Generation and asset handoff",
          "body": "When you request generation or confirm an asset handoff, the required prompts, workflows, references and selected media are sent to your authorized Colab runtime. Original video, image and audio assets can be handed off with shot context; transfer does not automatically start generation. Custom nodes and API services can introduce additional destinations under their own policies."
        },
        {
          "title": "Project ZIPs and ComfyUI snapshots",
          "body": "A local project ZIP and a ComfyUI snapshot are separate backups. A snapshot saves the canvas and managed input/output/temp media on your Mac. Copying it to an authorized, mounted Drive is an explicit action, not continuous synchronization. Model weights, node installations and files outside managed locations are not included. Secrets manually typed into custom node text may remain in saved canvases; inspect files before sharing."
        },
        {
          "title": "Third-party components and diagnostics",
          "body": "The release configuration disables the bundled frontend’s optional Sentry error reporter. Google services, downloads and user-enabled extensions or API providers can still make network requests and process data under their own policies. This does not mean that every component or custom workflow has no data collection. CineHarbor does not automatically upload support logs to the developer. The bundled ComfyUI frontend may automatically check ComfyUI versions and model-file availability through Comfy services, Hugging Face and their delivery networks. These services can receive connection information such as your IP address and request metadata. An availability check does not itself download a model."
        },
        {
          "title": "Retention and deletion",
          "body": "Local files and cloud backups are managed separately. Releasing a runtime, quitting the app or deleting a local copy does not delete Drive backups. Use the controls for each storage location and provider to remove copies or revoke authorization. Removing authorization does not retract files already sent."
        },
        {
          "title": "Support and privacy requests",
          "body": "Support email and attachments are used to respond to your request and necessary follow-up. You may contact contact@gachaframe.com to request deletion of support information. Do not send passwords, tokens, authorization codes or payment details; redact screenshots and logs before sending. No fixed support-retention or response period is promised."
        }
      ]
    },
    "terms": {
      "title": "CineHarbor Terms of Use",
      "sections": [
        {
          "title": "Scope and contact",
          "body": "This document applies to CineHarbor. Contact: contact@gachaframe.com."
        },
        {
          "title": "A free workspace and your own resources",
          "body": "CineHarbor is a free production workspace, not a proprietary generation model or a compute subscription. You supply your own eligible Google Colab account and resources. Third-party charges and service limits apply separately; access to a particular GPU or model is not guaranteed."
        },
        {
          "title": "Authorized content and third-party licenses",
          "body": "Use only material you are entitled to process. Before using a selected third-party model, custom node, workflow, music, voice or other asset, check its applicable license, permitted uses, territorial restrictions and any required authorization. Using CineHarbor does not grant you additional third-party rights or transfer your original creative rights to the developer. Model outputs and example demonstrations remain subject to applicable terms; showing an example does not create an exemption. Review results and the permissions required for their intended use before publishing."
        },
        {
          "title": "MiniMax H3: models, integrations and examples",
          "body": "A model you obtain yourself is distinct from CineHarbor’s bundled integration code, supplied workflows, default model bindings and distributed examples. MiniMax H3 and related outputs remain subject to the applicable MiniMax license and any separate authorization. This notice is not an authorization from MiniMax and does not establish that a particular deployment or demonstration is licensed. Asking users to check their use does not waive the legal or license obligations that apply to the developer’s own integrations, configurations or distribution."
        },
        {
          "title": "Compute and saved data",
          "body": "Connecting, downloading, waiting and generating can consume your provider’s compute allowance while a runtime is active. Save and verify needed results, complete backup and Drive-flush checks, and release your runtime separately. Closing the app alone does not release compute."
        },
        {
          "title": "Handoff and recovery boundaries",
          "body": "Asset handoff is one-way and does not convert a completed editing timeline or provide live two-way synchronization. Optional original generation recipes are disabled by default. Models and custom-node installations are managed separately. Project ZIPs and ComfyUI snapshots serve different purposes; keep verified copies and inspect custom workflow text before sharing."
        },
        {
          "title": "Exports and support",
          "body": "The app provides local MP4 export. Check the exported film in your target player. For app support, privacy or licensing questions, contact contact@gachaframe.com. Google account, billing and resource issues are handled through Google. Apple’s Standard Licensed Application End User License Agreement applies to the App Store license."
        },
        {
          "title": "Open-source licenses",
          "body": "Open-source components remain governed by their respective licenses. The App Store license does not limit rights granted by those licenses. Original notices, corresponding sources and local modifications are available in the component license page."
        }
      ]
    },
    "support": {
      "title": "CineHarbor Support",
      "sections": [
        {
          "title": "Scope and contact",
          "body": "This document applies to CineHarbor. Contact: contact@gachaframe.com."
        },
        {
          "title": "Contact",
          "body": "Email contact@gachaframe.com with the app version, macOS version, attempted action and a redacted error description. Send only information needed for the request; support does not need your Google password, authorization code, token or private project archive."
        },
        {
          "title": "Connect compute and Drive separately",
          "body": "Check the Google account and runtime you intend to use. Drive mounting requires its own authorization. Check the Google consent screen and the chosen backup location. Generation uses your own eligible cloud resources."
        },
        {
          "title": "Save, verify and release",
          "body": "Keep local project ZIPs and ComfyUI snapshots separately. Copy a snapshot to mounted Drive explicitly if desired, verify it, and finish pending writes before releasing compute. Quitting the app is not a release action and does not delete Drive backups."
        },
        {
          "title": "Recovery and export",
          "body": "Preserve the original project while testing a recovered copy. Model weights, node installations and external files are not automatically rebuilt from a snapshot. For MP4 issues, include the export settings and a redacted error; do not send private media unless necessary and authorized."
        },
        {
          "title": "Support information",
          "body": "Your message and attachments are used to answer the request and necessary follow-up. You may ask contact@gachaframe.com to delete support information. No automatic support-log upload or fixed response time is offered."
        },
        {
          "title": "Model and license questions",
          "body": "Check the official license for the specific model and version you intend to use, including territory, output-use and authorization requirements. For a question about a CineHarbor integration or example, contact contact@gachaframe.com with the app version, model name and version, relevant official license link and intended use and region. Send only necessary information; do not send credentials or private project files. CineHarbor support cannot grant rights on behalf of a third-party rights holder."
        }
      ]
    }
  },
  "zh-Hans": {
    "privacy": {
      "title": "CineHarbor 隐私政策",
      "sections": [
        {
          "title": "适用范围与联系",
          "body": "本文适用于 CineHarbor。联系：contact@gachaframe.com。"
        },
        {
          "title": "本地工程",
          "body": "镜头规划、提示词、参考、媒体、任务历史与导出文件在 Mac 上管理。选择界面语言本身不会把剧本送往翻译服务。账号授权记录与工程备份分别保存。"
        },
        {
          "title": "Google 登录与 Drive 授权",
          "body": "云端功能使用你授权的 Google 账号，账号信息用于识别账号和运行时归属。挂载 Google Drive 需另行授权；登录账号或连接算力不等于自动挂载 Drive。请核对 Google 授权界面显示的权限。"
        },
        {
          "title": "生成与资产交接",
          "body": "请求生成或确认资产交接时，所需提示词、工作流、参考及选定媒体会发送到你授权的 Colab 运行时。原视频、图片和音频可连同镜头上下文交接；传输本身不会自动生成。自定义节点或 API 服务可能按其自身政策引入其他数据接收方。"
        },
        {
          "title": "工程 ZIP 与 ComfyUI 快照",
          "body": "本地工程 ZIP 和 ComfyUI 快照是两种独立备份。快照将画布及托管 input/output/temp 媒体保存在 Mac；复制到已授权挂载的 Drive 需主动操作，不是持续自动同步。不包含模型权重、节点安装和托管目录外文件。手动写入自定义节点文字的密钥可能保留在画布中，分享前请检查。"
        },
        {
          "title": "第三方组件与诊断",
          "body": "发行配置关闭内置前端的可选 Sentry 错误报告。Google 服务、下载及用户启用的扩展或 API 服务仍可能联网并按各自政策处理数据；这不表示所有组件或自定义工作流都不收集数据。CineHarbor 不会自动向开发者上传支持日志。 内置 ComfyUI 前端可能自动通过 Comfy 服务、Hugging Face 及其内容分发网络检查 ComfyUI 版本和模型文件可用性。这些服务可收到 IP 地址、请求元数据等连接信息；可用性检查本身不等于下载模型。"
        },
        {
          "title": "保存与删除",
          "body": "本地文件与云端备份需分别管理。释放运行时、退出软件或删除本地副本，不会删除 Drive 备份。请在各存储位置及服务商界面删除副本或撤销授权；撤销授权不会收回已经发送的文件。"
        },
        {
          "title": "支持与隐私请求",
          "body": "支持邮件及附件用于答复请求和必要的后续处理。可联系 contact@gachaframe.com 请求删除支持信息。不要发送密码、令牌、授权码或付款信息；发送截图和日志前请遮去隐私。不承诺固定的支持资料留存或回复期限。"
        }
      ]
    },
    "terms": {
      "title": "CineHarbor 用户条款",
      "sections": [
        {
          "title": "适用范围与联系",
          "body": "本文适用于 CineHarbor。联系：contact@gachaframe.com。"
        },
        {
          "title": "免费工作台与自有资源",
          "body": "CineHarbor 是免费制作工作台，不是自有生成模型或算力订阅。你需自行提供符合条件的 Google Colab 账号与资源。第三方费用和限制另行适用，不保证特定 GPU 或模型始终可用。"
        },
        {
          "title": "素材与第三方许可",
          "body": "请只处理你有权使用的内容。使用所选第三方模型、自定义节点、工作流、音乐、声音或其他素材前，请核对其适用许可、允许用途、地域限制及必要授权。使用 CineHarbor 不会额外授予第三方权利，也不表示开发者取得你的原创成果权利。模型输出及示例展示仍受适用条款约束；作为示例展示并不自动豁免相关限制。发布前，请检查结果及其预定用途所需的权限。"
        },
        {
          "title": "MiniMax H3：模型、集成与示例",
          "body": "你自行获取的模型，与 CineHarbor 内置的集成代码、提供的工作流、默认模型绑定及随附示例，是需要分别核对的对象。MiniMax H3 及相关输出仍适用相应 MiniMax 许可和任何另行取得的授权。本告知不构成 MiniMax 的授权，也不证明某项部署或示例已获许可。要求用户核对自身用途，不免除开发者对自身集成、配置及分发所承担的适用法律或许可义务。"
        },
        {
          "title": "算力与保存",
          "body": "运行时活跃期间，连接、下载、等待和生成均可能消耗服务商的算力额度。请保存并核验所需结果，完成备份和 Drive 刷新，再单独释放运行时。仅关闭软件不会释放算力。"
        },
        {
          "title": "交接与恢复范围",
          "body": "资产交接是单向的，不转换完整剪辑时间线，也不实时双向同步。可选的原生成配方默认禁用，模型与自定义节点安装需另行管理。工程 ZIP 与 ComfyUI 快照用途不同，请保留已核验的副本，分享前检查自定义工作流文字。"
        },
        {
          "title": "导出与支持",
          "body": "应用提供本地 MP4 导出，请在目标播放器检查成片。应用支持、隐私或许可问题可联系 contact@gachaframe.com；Google 账号、计费及资源问题由 Google 处理。App Store 应用许可适用 Apple 标准最终用户许可协议。"
        },
        {
          "title": "开源组件许可",
          "body": "开源组件继续适用各自许可证。App Store 应用许可不限制这些许可证授予的权利。组件许可页面提供原始声明、对应源码和本地修改说明。"
        }
      ]
    },
    "support": {
      "title": "CineHarbor 技术支持",
      "sections": [
        {
          "title": "适用范围与联系",
          "body": "本文适用于 CineHarbor。联系：contact@gachaframe.com。"
        },
        {
          "title": "联系支持",
          "body": "请向 contact@gachaframe.com 提供应用版本、macOS 版本、操作步骤及已遮去隐私的错误说明。只发送处理问题所必需的信息；支持无需你的 Google 密码、授权码、令牌或私人工程备份包。"
        },
        {
          "title": "分别连接算力与云盘",
          "body": "核对要使用的 Google 账号和运行时；Drive 挂载需单独授权。检查 Google 授权界面和备份位置。生成使用你自己的合资格云端资源。"
        },
        {
          "title": "保存、核验与释放",
          "body": "本地工程 ZIP 与 ComfyUI 快照分别保存；如需云端副本，主动复制到已挂载的 Drive，核验并完成写入后释放算力。退出软件不等于释放，也不会删除 Drive 备份。"
        },
        {
          "title": "恢复与导出",
          "body": "测试恢复副本时请保留原工程。快照不会自动重建模型权重、节点安装和外部文件。MP4 出现问题时，请提供导出设置及已遮去隐私的错误说明；非必要且未授权时不要发送私人媒体。"
        },
        {
          "title": "支持信息处理",
          "body": "邮件及附件用于答复请求与必要的后续处理，可联系 contact@gachaframe.com 请求删除。不自动上传支持日志，也不承诺固定回复时间。"
        },
        {
          "title": "模型与许可问题",
          "body": "请查阅你拟使用的具体模型及版本的官方许可，包括地域、输出用途和授权要求。如需咨询 CineHarbor 的某项集成或示例，请向 contact@gachaframe.com 提供应用版本、模型名称及版本、相关官方许可链接，以及预定用途与使用地区。只发送必要信息，不要发送凭据或私人工程文件。CineHarbor 支持不能代表第三方权利人授予许可。"
        }
      ]
    }
  },
  "zh-Hant": {
    "privacy": {
      "title": "CineHarbor 隱私權政策",
      "sections": [
        {
          "title": "適用範圍與聯絡",
          "body": "本文適用於 CineHarbor。聯絡：contact@gachaframe.com。"
        },
        {
          "title": "本機專案",
          "body": "鏡頭規劃、提示詞、參考、媒體、任務歷史與匯出檔案在 Mac 上管理。選擇介面語言本身不會將劇本送往翻譯服務。帳號授權記錄與專案備份分別儲存。"
        },
        {
          "title": "Google 登入與 Drive 授權",
          "body": "雲端功能使用你授權的 Google 帳號，帳號資訊用於識別帳號與執行環境歸屬。掛載 Google Drive 需另行授權；登入帳號或連接算力不代表自動掛載 Drive。請核對 Google 授權畫面顯示的權限。"
        },
        {
          "title": "生成與資產交接",
          "body": "請求生成或確認資產交接時，所需提示詞、工作流程、參考及選定媒體會傳送至你授權的 Colab 執行環境。原始影片、圖片與音訊可連同鏡頭脈絡交接；傳輸本身不會自動生成。自訂節點或 API 服務可能按自身政策引入其他資料接收方。"
        },
        {
          "title": "專案 ZIP 與 ComfyUI 快照",
          "body": "本機專案 ZIP 與 ComfyUI 快照是兩種獨立備份。快照將畫布及託管 input/output/temp 媒體儲存在 Mac；複製到已授權掛載的 Drive 需主動操作，不是持續自動同步。不包含模型權重、節點安裝和託管目錄外檔案。手動寫入自訂節點文字的金鑰可能保留在畫布中，分享前請檢查。"
        },
        {
          "title": "第三方元件與診斷",
          "body": "發行設定關閉內建前端的選用 Sentry 錯誤報告。Google 服務、下載及使用者啟用的擴充功能或 API 服務仍可能連網並按各自政策處理資料；這不表示所有元件或自訂工作流程都不收集資料。CineHarbor 不會自動向開發者上傳支援記錄。 內建 ComfyUI 前端可能自動透過 Comfy 服務、Hugging Face 及其內容傳遞網路檢查 ComfyUI 版本與模型檔案可用性。這些服務可收到 IP 位址、請求中繼資料等連線資訊；可用性檢查本身不等於下載模型。"
        },
        {
          "title": "儲存與刪除",
          "body": "本機檔案與雲端備份需分別管理。釋放執行環境、退出軟體或刪除本機副本，不會刪除 Drive 備份。請在各儲存位置及服務商介面刪除副本或撤銷授權；撤銷授權不會收回已傳送的檔案。"
        },
        {
          "title": "支援與隱私請求",
          "body": "支援郵件及附件用於答覆請求與必要的後續處理。可聯絡 contact@gachaframe.com 請求刪除支援資訊。不要傳送密碼、權杖、授權碼或付款資訊；傳送截圖與記錄前請遮去隱私。不承諾固定的支援資料保留或回覆期限。"
        }
      ]
    },
    "terms": {
      "title": "CineHarbor 使用條款",
      "sections": [
        {
          "title": "適用範圍與聯絡",
          "body": "本文適用於 CineHarbor。聯絡：contact@gachaframe.com。"
        },
        {
          "title": "免費工作台與自有資源",
          "body": "CineHarbor 是免費製作工作台，不是自有生成模型或算力訂閱。你需自行提供符合條件的 Google Colab 帳號與資源。第三方費用和限制另行適用，不保證特定 GPU 或模型始終可用。"
        },
        {
          "title": "素材與第三方授權",
          "body": "請只處理你有權使用的內容。使用所選第三方模型、自訂節點、工作流程、音樂、聲音或其他素材前，請核對其適用授權條款、允許用途、地域限制及必要授權。使用 CineHarbor 不會額外授予第三方權利，也不表示開發者取得你的原創成果權利。模型輸出及示例展示仍受適用條款約束；作為示例展示並不自動豁免相關限制。發布前，請檢查結果及其預定用途所需的權限。"
        },
        {
          "title": "MiniMax H3：模型、整合與示例",
          "body": "你自行取得的模型，與 CineHarbor 內建的整合程式碼、提供的工作流程、預設模型綁定及隨附示例，是需要分別核對的對象。MiniMax H3 及相關輸出仍適用相應 MiniMax 授權條款和任何另行取得的授權。本告知不構成 MiniMax 的授權，也不證明某項部署或示例已獲許可。要求使用者核對自身用途，不免除開發者對自身整合、設定及散布所承擔的適用法律或授權義務。"
        },
        {
          "title": "算力與儲存",
          "body": "執行環境啟用期間，連接、下載、等待和生成均可能消耗服務商的算力額度。請儲存並核驗所需結果，完成備份和 Drive 刷新，再單獨釋放執行環境。僅關閉軟體不會釋放算力。"
        },
        {
          "title": "交接與恢復範圍",
          "body": "資產交接是單向的，不轉換完整剪輯時間軸，也不即時雙向同步。選用的原生成配方預設停用，模型與自訂節點安裝需另行管理。專案 ZIP 與 ComfyUI 快照用途不同，請保留已核驗的副本，分享前檢查自訂工作流程文字。"
        },
        {
          "title": "匯出與支援",
          "body": "應用程式提供本機 MP4 匯出，請在目標播放器檢查成片。支援、隱私或授權問題可聯絡 contact@gachaframe.com；Google 帳號、計費及資源問題由 Google 處理。App Store 應用程式授權適用 Apple 標準最終使用者授權合約。"
        },
        {
          "title": "開源元件授權",
          "body": "開源元件仍適用各自的授權條款。App Store 應用程式授權不限制這些條款授予的權利。元件授權頁提供原始聲明、對應原始碼及本機修改說明。"
        }
      ]
    },
    "support": {
      "title": "CineHarbor 技術支援",
      "sections": [
        {
          "title": "適用範圍與聯絡",
          "body": "本文適用於 CineHarbor。聯絡：contact@gachaframe.com。"
        },
        {
          "title": "聯絡支援",
          "body": "請向 contact@gachaframe.com 提供應用程式版本、macOS 版本、操作步驟及已遮去隱私的錯誤說明。只傳送處理問題所必需的資訊；支援無需你的 Google 密碼、授權碼、權杖或私人專案備份包。"
        },
        {
          "title": "分別連接算力與雲端硬碟",
          "body": "核對要使用的 Google 帳號與執行環境；Drive 掛載需單獨授權。檢查 Google 授權畫面和備份位置。生成使用你自己的合資格雲端資源。"
        },
        {
          "title": "儲存、核驗與釋放",
          "body": "本機專案 ZIP 與 ComfyUI 快照分別儲存；如需雲端副本，主動複製到已掛載的 Drive，核驗並完成寫入後釋放算力。退出軟體不代表釋放，也不會刪除 Drive 備份。"
        },
        {
          "title": "恢復與匯出",
          "body": "測試恢復副本時請保留原專案。快照不會自動重建模型權重、節點安裝和外部檔案。MP4 出現問題時，請提供匯出設定及已遮去隱私的錯誤說明；非必要且未授權時不要傳送私人媒體。"
        },
        {
          "title": "支援資訊處理",
          "body": "郵件及附件用於答覆請求與必要的後續處理，可聯絡 contact@gachaframe.com 請求刪除。不自動上傳支援記錄，也不承諾固定回覆時間。"
        },
        {
          "title": "模型與授權問題",
          "body": "請查閱你擬使用的具體模型及版本的官方授權條款，包括地域、輸出用途和授權要求。如需諮詢 CineHarbor 的某項整合或示例，請向 contact@gachaframe.com 提供應用版本、模型名稱及版本、相關官方授權條款連結，以及預定用途與使用地區。只傳送必要資訊，不要傳送憑證或私人工程檔案。CineHarbor 支援不能代表第三方權利人授予許可。"
        }
      ]
    }
  },
  "ja": {
    "privacy": {
      "title": "CineHarbor プライバシーポリシー",
      "sections": [
        {
          "title": "適用範囲とお問い合わせ",
          "body": "本書は CineHarbor に適用されます。連絡先：contact@gachaframe.com。"
        },
        {
          "title": "ローカルプロジェクト",
          "body": "ショット設計、プロンプト、参照、メディア、タスク履歴、書き出しファイルは Mac で管理します。言語選択だけで脚本を翻訳サービスへ送信することはありません。アカウント認証記録とプロジェクトバックアップは別管理です。"
        },
        {
          "title": "Google ログインと Drive 認証",
          "body": "クラウド機能は認証した Google アカウントを利用し、アカウント情報で実行環境の所有者を確認します。Google Drive のマウントには別の認証が必要です。ログインや計算環境への接続だけではマウントされません。Google の同意画面で権限を確認してください。"
        },
        {
          "title": "生成と素材の引き継ぎ",
          "body": "生成要求や素材転送の確認時、必要なプロンプト、ワークフロー、参照、選択したメディアを認証済み Colab に送信します。元の動画・画像・音声をショットの文脈とともに引き継げますが、転送だけでは生成を開始しません。カスタムノードや API は独自のポリシーに基づき別の送信先を利用する場合があります。"
        },
        {
          "title": "プロジェクト ZIP とスナップショット",
          "body": "プロジェクト ZIP と ComfyUI スナップショットは別のバックアップです。スナップショットはキャンバスと管理対象 input/output/temp メディアを Mac に保存します。別途認証・マウントした Drive へのコピーは明示的な操作であり、常時自動同期ではありません。モデル、ノードのインストール、管理対象外ファイルは含まれません。ノードの文字列に入力したキーが保存される場合があるため、共有前に確認してください。"
        },
        {
          "title": "第三者コンポーネントと診断",
          "body": "配布設定では内蔵フロントエンドの任意の Sentry エラー報告を無効にします。Google、ダウンロード先、利用者が有効にした拡張機能や API は独自のポリシーで通信・処理を行う場合があります。すべてのコンポーネントやワークフローに収集がないという意味ではありません。開発者へのサポートログの自動送信は行いません。 内蔵の ComfyUI フロントエンドは、Comfy のサービス、Hugging Face、およびそれらの配信ネットワークを通じて、ComfyUI のバージョンやモデルファイルの利用可能性を自動確認する場合があります。これらのサービスには IP アドレスやリクエストのメタデータなどの接続情報が送られます。利用可能性の確認自体ではモデルはダウンロードされません。"
        },
        {
          "title": "保存と削除",
          "body": "ローカルファイルとクラウドのコピーは別管理です。実行環境の解放、アプリ終了、ローカルコピー削除では Drive バックアップは削除されません。各保存先の管理画面で削除や認証の取消しを行ってください。取消しによって送信済みファイルが回収されるわけではありません。"
        },
        {
          "title": "サポートとプライバシーの申出",
          "body": "メールと添付は回答と必要なフォローアップに使用します。削除のご相談は contact@gachaframe.com へ。パスワード、トークン、認証コード、決済情報は送らず、画像やログの個人情報を伏せてください。固定の保存期間や返信期限は約束しません。"
        }
      ]
    },
    "terms": {
      "title": "CineHarbor 利用規約",
      "sections": [
        {
          "title": "適用範囲とお問い合わせ",
          "body": "本書は CineHarbor に適用されます。連絡先：contact@gachaframe.com。"
        },
        {
          "title": "無料ワークスペースと利用者のリソース",
          "body": "CineHarbor は無料の制作ワークスペースであり、独自の生成モデルや計算資源のサブスクリプションではありません。利用者が対象の Colab アカウントとリソースを用意します。第三者の料金・制限は別途適用され、特定 GPU やモデルの利用可能性は保証しません。"
        },
        {
          "title": "素材と第三者ライセンス",
          "body": "処理する権利を持つ素材だけを使用してください。選択した第三者のモデル、カスタムノード、ワークフロー、音楽、音声などを使用する前に、適用ライセンス、許可される用途、地域制限、必要な許諾を確認してください。CineHarbor の利用によって第三者の権利が追加で許諾されることはなく、利用者のオリジナル作品の権利が開発者へ移転することもありません。モデルの出力やデモにも適用条件が及び、デモとして示すだけで制限が免除されることはありません。公開前に、結果と予定する用途に必要な権限を確認してください。"
        },
        {
          "title": "MiniMax H3：モデル、統合機能、デモ",
          "body": "利用者が自ら取得するモデルと、CineHarbor に同梱される統合コード、提供ワークフロー、既定のモデル設定、配布デモは、分けて確認する必要があります。MiniMax H3 と関連する出力には、適用される MiniMax のライセンスと別途取得した許諾が引き続き適用されます。この説明自体は MiniMax による許諾ではなく、特定の導入やデモが許諾済みであることを証明するものでもありません。利用者に用途の確認を求めても、開発者自身の統合、設定、配布に適用される法律上またはライセンス上の義務が免除されるわけではありません。"
        },
        {
          "title": "計算資源と保存",
          "body": "実行環境が有効な間は接続、ダウンロード、待機、生成が計算枠を消費する場合があります。結果を保存・検証し、バックアップと Drive の書き込みを完了してから解放してください。アプリの終了だけでは解放されません。"
        },
        {
          "title": "引き継ぎと復元の範囲",
          "body": "素材転送は一方向で、完成タイムラインの変換やリアルタイム双方向同期ではありません。任意の元生成レシピは初期状態で無効です。モデルとカスタムノードのインストールは別管理です。ZIP とスナップショットは目的が異なります。検証済みのコピーを保管し、共有前にワークフロー文字列を確認してください。"
        },
        {
          "title": "書き出しとサポート",
          "body": "ローカル MP4 書き出しを提供します。対象プレイヤーで動画を確認してください。操作、プライバシー、ライセンスの質問は contact@gachaframe.com へ。Google のアカウント・請求・リソースの問題は Google が扱います。App Store のライセンスには Apple 標準 EULA が適用されます。"
        },
        {
          "title": "オープンソースのライセンス",
          "body": "オープンソースの構成要素には、それぞれのライセンスが適用されます。App Store のアプリ使用許諾は、各ライセンスが認める権利を制限しません。原文の通知、対応するソースコード、ローカルでの変更内容は構成要素のライセンスページで確認できます。"
        }
      ]
    },
    "support": {
      "title": "CineHarbor サポート",
      "sections": [
        {
          "title": "適用範囲とお問い合わせ",
          "body": "本書は CineHarbor に適用されます。連絡先：contact@gachaframe.com。"
        },
        {
          "title": "お問い合わせ",
          "body": "contact@gachaframe.com にアプリ・macOS のバージョン、操作、個人情報を伏せたエラーをお知らせください。必要な情報のみ送信し、Google のパスワード、認証コード、トークン、私的なプロジェクトアーカイブは送らないでください。"
        },
        {
          "title": "計算環境と Drive を別々に認証",
          "body": "利用する Google アカウントと実行環境を確認してください。Drive は別途認証します。同意画面とバックアップ先を確認してください。生成には自分の対象クラウドリソースを利用します。"
        },
        {
          "title": "保存・検証・解放",
          "body": "プロジェクト ZIP と ComfyUI スナップショットを別々に保存します。必要に応じてマウント済み Drive へ明示的にコピーし、検証と書き込み完了後に解放してください。アプリ終了では解放や Drive 上の削除は行われません。"
        },
        {
          "title": "復元と書き出し",
          "body": "復元コピーの確認時も元のプロジェクトを残してください。モデル、ノード、外部ファイルは自動再構築されません。MP4 の問題は設定と個人情報を伏せたエラーを添えてください。不要・未許可の私的メディアは送らないでください。"
        },
        {
          "title": "サポート情報の取扱い",
          "body": "メールと添付は回答と必要なフォローアップに使用します。削除のご相談は contact@gachaframe.com へ。自動ログ送信や固定の返信期限はありません。"
        },
        {
          "title": "モデルとライセンスに関するお問い合わせ",
          "body": "使用予定のモデルとバージョンの公式ライセンスを確認し、地域、出力の利用、許諾に関する条件を確認してください。CineHarbor の統合機能やデモについてのお問い合わせは、アプリのバージョン、モデル名とバージョン、関連する公式ライセンスのリンク、予定する用途と利用地域を添えて contact@gachaframe.com へお送りください。必要な情報だけを送り、認証情報や非公開のプロジェクトファイルは送らないでください。CineHarbor サポートは第三者の権利者に代わって許諾を与えることはできません。"
        }
      ]
    }
  },
  "ko": {
    "privacy": {
      "title": "CineHarbor 개인정보 처리방침",
      "sections": [
        {
          "title": "적용 범위 및 문의",
          "body": "이 문서는 CineHarbor에 적용됩니다. 문의: contact@gachaframe.com."
        },
        {
          "title": "로컬 프로젝트",
          "body": "숏 계획, 프롬프트, 참고 자료, 미디어, 작업 기록과 내보낸 파일은 Mac에서 관리합니다. 언어 선택 자체로 대본을 번역 서비스에 보내지는 않습니다. 계정 인증 기록과 프로젝트 백업은 별도로 보관합니다."
        },
        {
          "title": "Google 로그인과 Drive 승인",
          "body": "클라우드 기능은 승인한 Google 계정을 사용하며 계정 정보로 런타임 소유권을 확인합니다. Google Drive 마운트는 별도 승인이 필요합니다. 로그인이나 연산 연결만으로 Drive가 마운트되지 않습니다. Google 동의 화면의 권한을 확인하세요."
        },
        {
          "title": "생성과 자산 전달",
          "body": "생성을 요청하거나 자산 전달을 확인하면 필요한 프롬프트, 워크플로, 참고 자료와 선택한 미디어를 승인한 Colab 런타임에 보냅니다. 원본 영상·이미지·오디오를 숏 맥락과 함께 전달할 수 있으나 전송만으로 생성하지 않습니다. 사용자 지정 노드와 API는 자체 정책에 따라 다른 대상으로 데이터를 보낼 수 있습니다."
        },
        {
          "title": "프로젝트 ZIP과 ComfyUI 스냅샷",
          "body": "프로젝트 ZIP과 ComfyUI 스냅샷은 별도 백업입니다. 스냅샷은 캔버스와 관리 대상 input/output/temp 미디어를 Mac에 저장합니다. 승인·마운트한 Drive로 복사하려면 직접 실행해야 하며 지속 자동 동기화가 아닙니다. 모델, 노드 설치와 관리 폴더 밖 파일은 포함하지 않습니다. 노드 텍스트에 입력한 키가 저장될 수 있으므로 공유 전에 확인하세요."
        },
        {
          "title": "제3자 구성 요소와 진단",
          "body": "배포 설정은 내장 프런트엔드의 선택적 Sentry 오류 보고를 비활성화합니다. Google, 다운로드 서비스와 사용자가 켠 확장 또는 API는 자체 정책으로 통신·처리할 수 있습니다. 모든 구성 요소나 워크플로에 수집이 없다는 뜻은 아닙니다. 개발자에게 지원 로그를 자동 업로드하지 않습니다. 내장 ComfyUI 프런트엔드는 Comfy 서비스, Hugging Face 및 해당 배포 네트워크를 통해 ComfyUI 버전과 모델 파일의 사용 가능 여부를 자동 확인할 수 있습니다. 해당 서비스는 IP 주소와 요청 메타데이터 등의 연결 정보를 받을 수 있습니다. 사용 가능 여부 확인 자체가 모델 다운로드를 의미하지는 않습니다."
        },
        {
          "title": "보관과 삭제",
          "body": "로컬 파일과 클라우드 백업은 별도로 관리합니다. 런타임 해제, 앱 종료 또는 로컬 복사본 삭제로 Drive 백업이 삭제되지는 않습니다. 각 저장 위치와 제공자의 관리 화면에서 복사본 삭제나 승인 취소를 수행하세요. 승인 취소로 이미 보낸 파일이 회수되지는 않습니다."
        },
        {
          "title": "지원과 개인정보 요청",
          "body": "지원 메일과 첨부는 문의 답변 및 필요한 후속 처리에 사용합니다. 삭제 요청은 contact@gachaframe.com으로 보내세요. 비밀번호, 토큰, 승인 코드나 결제 정보를 보내지 말고 이미지와 로그에서 개인정보를 가리세요. 고정 보관 기간이나 답변 기한을 약속하지 않습니다."
        }
      ]
    },
    "terms": {
      "title": "CineHarbor 이용 약관",
      "sections": [
        {
          "title": "적용 범위 및 문의",
          "body": "이 문서는 CineHarbor에 적용됩니다. 문의: contact@gachaframe.com."
        },
        {
          "title": "무료 작업 공간과 사용자 자원",
          "body": "CineHarbor는 무료 제작 작업 공간이며 자체 생성 모델이나 연산 구독이 아닙니다. 사용자가 적합한 Colab 계정과 자원을 제공합니다. 제3자 비용과 제한이 별도로 적용되며 특정 GPU나 모델의 가용성을 보장하지 않습니다."
        },
        {
          "title": "자료와 제3자 라이선스",
          "body": "처리할 권한이 있는 자료만 사용하세요. 선택한 제3자 모델, 사용자 지정 노드, 워크플로, 음악, 음성 또는 기타 자료를 사용하기 전에 적용 라이선스, 허용 용도, 지역 제한 및 필요한 허가를 확인하세요. CineHarbor 사용만으로 제3자의 권리가 추가로 허여되거나 사용자의 독창적 창작물 권리가 개발자에게 이전되지는 않습니다. 모델 출력과 예시에도 적용 조건이 유지되며, 예시로 보여 준다는 이유만으로 제한이 면제되지 않습니다. 게시 전에 결과와 예정된 용도에 필요한 권한을 확인하세요."
        },
        {
          "title": "MiniMax H3: 모델, 통합 기능 및 예시",
          "body": "사용자가 직접 구한 모델과 CineHarbor에 포함된 통합 코드, 제공 워크플로, 기본 모델 연결 및 배포 예시는 구분하여 검토해야 합니다. MiniMax H3와 관련 출력에는 적용되는 MiniMax 라이선스와 별도로 취득한 허가가 계속 적용됩니다. 이 안내 자체는 MiniMax의 허가가 아니며 특정 배포나 예시가 허가되었다는 증거도 아닙니다. 사용자에게 자신의 용도를 확인하도록 요구해도 개발자 자체의 통합, 설정 및 배포에 적용되는 법적 의무나 라이선스 의무가 면제되지는 않습니다."
        },
        {
          "title": "연산과 저장",
          "body": "런타임이 활성화된 동안 연결, 다운로드, 대기와 생성이 연산 한도를 소모할 수 있습니다. 결과를 저장·검증하고 백업 및 Drive 쓰기를 완료한 후 별도로 해제하세요. 앱을 닫는 것만으로 해제되지 않습니다."
        },
        {
          "title": "전달과 복원의 범위",
          "body": "자산 전달은 단방향이며 완성 타임라인 변환이나 실시간 양방향 동기화가 아닙니다. 선택적 원래 생성 레시피는 기본 비활성화됩니다. 모델과 사용자 지정 노드는 별도 설치가 필요합니다. ZIP과 스냅샷은 목적이 다르므로 검증한 사본을 유지하고 공유 전 워크플로 텍스트를 확인하세요."
        },
        {
          "title": "내보내기와 지원",
          "body": "로컬 MP4 내보내기를 제공합니다. 대상 플레이어에서 결과를 확인하세요. 앱, 개인정보나 라이선스 문의는 contact@gachaframe.com으로 보내세요. Google 계정·청구·자원 문제는 Google에서 처리합니다. App Store 라이선스에는 Apple 표준 EULA가 적용됩니다."
        },
        {
          "title": "오픈 소스 라이선스",
          "body": "오픈 소스 구성 요소에는 각 라이선스가 적용됩니다. App Store 앱 사용권은 해당 라이선스가 부여하는 권리를 제한하지 않습니다. 원본 고지, 대응 소스 코드 및 로컬 수정 사항은 구성 요소 라이선스 페이지에서 확인할 수 있습니다."
        }
      ]
    },
    "support": {
      "title": "CineHarbor 지원",
      "sections": [
        {
          "title": "적용 범위 및 문의",
          "body": "이 문서는 CineHarbor에 적용됩니다. 문의: contact@gachaframe.com."
        },
        {
          "title": "지원 문의",
          "body": "contact@gachaframe.com으로 앱·macOS 버전, 작업 단계와 개인정보를 가린 오류 설명을 보내세요. 필요한 정보만 보내고 Google 비밀번호, 승인 코드, 토큰 또는 개인 프로젝트 백업은 보내지 마세요."
        },
        {
          "title": "연산과 Drive를 별도로 연결",
          "body": "사용할 Google 계정과 런타임을 확인하세요. Drive 마운트는 별도 승인합니다. 동의 화면과 백업 위치를 확인하세요. 생성에는 자신의 적격 클라우드 자원을 사용합니다."
        },
        {
          "title": "저장·검증·해제",
          "body": "프로젝트 ZIP과 ComfyUI 스냅샷을 따로 저장하세요. 필요하면 마운트한 Drive로 직접 복사하고 검증 및 쓰기 완료 후 연산을 해제합니다. 앱 종료만으로 해제되거나 Drive 백업이 삭제되지는 않습니다."
        },
        {
          "title": "복원과 내보내기",
          "body": "복원 사본을 확인하는 동안 원본 프로젝트를 유지하세요. 모델, 노드와 외부 파일은 자동 재구성되지 않습니다. MP4 문제에는 설정과 개인정보를 가린 오류를 보내세요. 불필요하거나 허가받지 않은 개인 미디어는 보내지 마세요."
        },
        {
          "title": "지원 정보 처리",
          "body": "메일과 첨부는 답변 및 필요한 후속 처리에 사용합니다. 삭제 요청은 contact@gachaframe.com으로 보내세요. 지원 로그 자동 업로드나 고정 답변 기한은 제공하지 않습니다."
        },
        {
          "title": "모델 및 라이선스 문의",
          "body": "사용할 모델과 버전의 공식 라이선스에서 지역, 출력 사용 및 허가 조건을 확인하세요. CineHarbor 통합 기능이나 예시에 관한 문의는 앱 버전, 모델 이름과 버전, 관련 공식 라이선스 링크, 예정 용도와 사용 지역을 포함해 contact@gachaframe.com으로 보내세요. 필요한 정보만 보내고 인증 정보나 비공개 프로젝트 파일은 보내지 마세요. CineHarbor 지원은 제3자 권리자를 대신하여 사용권을 부여할 수 없습니다."
        }
      ]
    }
  }
};
