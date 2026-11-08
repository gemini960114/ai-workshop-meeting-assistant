# AI Workshop：會議錄音轉會議紀錄（meeting-assistant）

把會議錄音交給 AI 助理（Claude Code 或 Antigravity），用平常說話的方式，就能拿到逐字稿和整理好的會議紀錄，還可以接著追問會議內容，不需要寫程式。

## 可以做什麼

- 📝 錄音轉逐字稿，每段都附時間點，方便回頭聽原音
- 📋 自動整理重點摘要、決議事項、待辦清單（誰負責、期限）、待確認事項
- 💬 紀錄產生後可以繼續追問，例如「哪些單位被分配到工作？」「幫我寫成提醒信」
- 支援 .m4a、.mp3、.wav 等常見錄音格式，不限會議類型（業務會議、座談、訪談、教育訓練都可以）

> 第一次使用前，請先完成文件後半段的〈[第一次使用前的設定](#第一次使用前的設定可請講師協助)〉，或請講師協助。

## 第一步：產生會議紀錄

在 AI 助理的對話框輸入：

> 幫我把 example/台南市市政會議錄音檔案.m4a 整理成會議紀錄

AI 助理會跳出選單問你 4 個問題。**不確定怎麼選時，每題都選標有 (Recommended) 的選項就好。**

| 問題 | 白話說明 |
| --- | --- |
| 1. 語音轉文字模型 | 用哪個 AI 聽錄音。選建議的 `Breeze-ASR-26`，中文和中英夾雜都聽得準 |
| 2. 紀錄要包含哪些內容 | 可複選：重點摘要、決議與待確認事項、待辦清單、完整逐字稿 |
| 3. 整理紀錄的模型 | 用哪個 AI 寫紀錄。選建議的即可；只要逐字稿時不會問這題 |
| 4. 輸出方式 | 存成檔案（放在 `output/` 資料夾）、直接顯示在對話框，或兩者都要 |

一小時的錄音大約幾分鐘就能完成。完成後，AI 助理會顯示紀錄內容或檔案連結。

**想讓紀錄更準確，可以在第一句話就補充背景**，AI 會依照你的說明整理：

> 幫我把 example/台南市市政會議錄音檔案.m4a 整理成會議紀錄。這是市政會議，主持人是市長，請特別列出各局處被交辦的事項。

## 第二步：多輪追問會議內容

紀錄產生後，**不用重新開始**，直接在同一個對話繼續問。下面是一段示範，每一行是你可以輸入的一句話：

1. **找出分工**
   > 這場會議有哪些局處被交辦工作？用表格列出單位、工作內容和期限。

2. **追問細節**
   > 淨零永續條例接下來的時程是什麼？哪個單位是窗口？

3. **回頭查證原音**
   > 剛剛提到的「十六項相關法規」是在錄音的哪個時間點？我要回去聽原音確認。

4. **找出還沒定案的事**
   > 有哪些事情還沒定案、需要會後再確認？

5. **改寫成要發出去的文件**
   > 根據待辦事項，幫我寫一封寄給各局處的提醒信，語氣正式、條列清楚。

6. **調整格式後另存**
   > 把會議紀錄改成公文常用的格式（主旨、說明、決議），另存成新檔案。

7. **只看某一段**
   > 只幫我摘要錄音 10 分到 20 分這一段在講什麼。

**如果是隔天或新開的對話**，AI 不會記得之前的內容，先請它讀檔案再追問：

> 請先讀 output/台南市市政會議錄音檔案_會議紀錄.md，再回答：這場會議的主要決議是什麼？

## 使用小提醒

- **重要內容請對照原音。** AI 可能聽錯同音字、人名或數字。金額、日期、法規名稱這類關鍵資訊，請依紀錄上的時間點回頭聽原音確認。
- **AI 只整理錄音裡有講到的內容。** 錄音沒提到的事項會標示「未提及」，不會自行補上。
- **注意機密性。** 錄音會傳送到國網中心的 AI 服務處理，含機密或個資的會議錄音，請先依單位規定確認可否使用。
- **換成自己的錄音：** 把錄音檔放進 `example/` 資料夾（或任何位置），把對話中的檔名換掉即可。

---

## 第一次使用前的設定（可請講師協助）

以下步驟每台電腦只需要做一次，請開啟 PowerShell 依序執行。

0. **下載專案**，並進入專案資料夾（之後的指令都在這個資料夾執行）：

   ```powershell
   git clone https://github.com/gemini960114/ai-workshop-meeting-assistant.git
   cd ai-workshop-meeting-assistant
   ```

1. **安裝 [uv](https://docs.astral.sh/uv/)**（已安裝可跳過；裝完要重新開啟 PowerShell），再安裝專案需要的套件：

   ```powershell
   winget install astral-sh.uv
   uv sync
   ```

2. **設定 API 金鑰**：複製 `.env.example` 成 `.env`，把 `OPENAI_API_KEY` 改成自己的金鑰。`.env` 不會被上傳到 GitHub，請勿分享給他人。

   ```powershell
   Copy-Item .env.example .env
   ```

3. **安裝 ffmpeg**（處理錄音檔需要；已安裝可跳過），裝好後重新開啟 PowerShell 確認：

   ```powershell
   winget install Gyan.FFmpeg
   ffmpeg -version
   ```

4. **（只有 Claude Code 需要）讓 Claude Code 找到這個技能**：Antigravity 會從 `.agents/skills/` 載入技能，Claude Code 則是從 `.claude/skills/`。執行下列指令建立連結，讓兩邊共用同一份（不需要系統管理員權限）：

   ```powershell
   # 建立 .claude 資料夾，並把 .claude\skills 連到 .agents\skills
   New-Item -ItemType Directory -Force .claude
   New-Item -ItemType Junction -Path .claude\skills -Target (Resolve-Path .agents\skills)

   # 確認：有指向 .agents\skills，而且看得到 SKILL.md
   Get-Item .claude\skills | Select-Object LinkType, Target
   Get-ChildItem .claude\skills\meeting-assistant
   ```

   完成後重新開啟 Claude Code（或在 VS Code 按 `Ctrl+Shift+P`，選 `Developer: Reload Window`）。在對話框輸入 `/`，看得到 `meeting-assistant` 就代表設定成功，也可以直接輸入 `/meeting-assistant` 叫用。專案規則 `AGENTS.md` 會自動載入，不用另外設定。

   - `.claude/skills` 不會被上傳到 GitHub；技能只要在 `.agents/skills/` 維護即可。
   - 要移除連結（只刪連結，不會刪到技能內容）：

     ```powershell
     (Get-Item .claude\skills).Delete()
     ```

## 專案內容

| 路徑 | 說明 |
| --- | --- |
| [example/](example/) | 範例錄音檔 |
| `output/` | 產生的會議紀錄（不會上傳到 GitHub） |
| [.agents/skills/meeting-assistant/](.agents/skills/meeting-assistant/) | 會議紀錄技能本體（`SKILL.md` ＋ 處理程式） |
| [AGENTS.md](AGENTS.md) | AI 助理在這個專案中要遵守的規則 |
| [models.md](models.md) | 國網中心 GenAI Portal 可用的 AI 模型與能力實測 |
| `.env.example` | 金鑰設定範本 |

<details>
<summary>進階：不透過 AI 助理，直接執行處理程式</summary>

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run .agents/skills/meeting-assistant/scripts/transcribe_meeting.py `
  --audio "example/台南市市政會議錄音檔案.m4a" `
  --stt-model "Breeze-ASR-26" `
  --llm-model "Muse-Spark-Open-816B-A42B" `
  --sections "summary,speakers,decisions,actions,issues,transcript" `
  --output "output/台南市市政會議錄音檔案_會議紀錄.md" `
  --print-output
```

| 參數 | 說明 |
| --- | --- |
| `--stt-model` | 語音轉文字模型：`Breeze-ASR-26`（預設）、`whisper-Breeze-ASR-25`、`Inkling-Small`、`Muse-Spark-Open-816B-A42B` |
| `--llm-model` | 摘要模型；未指定時使用 `.env` 的 `DEFAULT_MODEL` |
| `--sections` | 要輸出的區塊：`summary`、`speakers`、`decisions`、`actions`、`issues`、`transcript` |
| `--custom-prompt` | 補充錄音情境或領域術語，例如 `"這是醫學研討會，藥名保留英文"` |
| `--language` | 紀錄的撰寫語言，預設「台灣繁體中文」 |
| `--output` | 存檔路徑；不指定時直接印在終端機 |
| `--print-output` | 有存檔時也同時印在終端機 |

完整說明見 [SKILL.md](.agents/skills/meeting-assistant/SKILL.md)，或執行時加 `--help`。

</details>
