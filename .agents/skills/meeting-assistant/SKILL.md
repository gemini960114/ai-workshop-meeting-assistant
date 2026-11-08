---
name: meeting-assistant
description: >-
  通用錄音檔轉文字與結構化紀錄產生器，適用會議、討論、訪談、課堂等各類錄音。當使用者提出要將錄音檔
  （.m4a, .mp3, .wav 等）轉成文字、產製會議紀錄、重點摘要、決議事項或待辦執行項目時，必須啟動此 Skill，
  透過互動式選單引導使用者選擇模型與輸出格式。
---

# 錄音轉寫與會議紀錄 Skill (`meeting-assistant`)

本 Skill 提供標準化的「環境檢查 ➔ 互動式引導 ➔ 音訊重疊切分與並行轉寫 ➔ 結構化紀錄產製」流程，支援 `portal.genai.nchc.org.tw/api/v1` 上的專職 ASR 模型與全模態 Chat 模型。不限定領域：錄音情境、領域術語等需求透過 `--custom-prompt` 補充，紀錄語言透過 `--language` 指定。

---

## 步驟零：前置環境檢查

執行轉寫前，請先確認系統已安裝 `ffmpeg` 與 `ffprobe`：
```powershell
ffmpeg -version
```
若未安裝，請先提示使用者安裝 `ffmpeg`。

---

## 步驟一：互動式需求引導（必做，禁止跳過猜測）

當使用者提供錄音檔或要求轉寫會議記錄，但尚未明確指定以下所有細節時，**必須先使用當前環境提供的互動提問工具（如 `ask_question` 或 `AskUserQuestion`）**，一次向使用者確認以下 4 個問題（每題皆控制在 4 個選項以內，使用者亦可透過 `Other` 輸入自訂需求）：

1. **語音轉文字（STT）模型選擇**（單選，4 選項）：
   - `Breeze-ASR-26：聯發科繁中/中英混合專職 ASR，速度快、準確率高 (Recommended)`
   - `whisper-Breeze-ASR-25：Whisper 架構專職 ASR 模型`
   - `Inkling-Small：輕量全模態 Chat 模型 input_audio 聽音轉寫`
   - `Muse-Spark-Open-816B-A42B：816B 大型全模態 MoE 模型 input_audio 聽音轉寫`
2. **紀錄需包含的內容區塊**（多選，4 選項）：
   - `📋 重點摘要與各發言者要點（summary,speakers） (Recommended)`
   - `⚖️ 決議與待確認事項（decisions,issues：決議、共識與尚待確認／協調的事項）`
   - `✅ 待辦與執行項目表（actions：負責人／期限／追蹤事項）`
   - `📝 保留完整時間軸原始逐字稿（transcript：附 [MM:SS - MM:SS] 標記）`
3. **負責摘要與結構化整理的 LLM 模型**（單選，3 選項；只在需要 LLM 時才問，見下方規則）：
   - `Muse-Spark-Open-816B-A42B：816B 全模態旗艦推理與長文整理 (Recommended)`
   - `Muse-Glimmer-30B：30B 視覺／文字模型，回應速度快`
   - `Inkling-Small：輕量全模態快速模型`
4. **結果輸出與檔案儲存方式**（單選，3 選項；建議路徑 `output/<音訊檔名>_會議紀錄.md`）：
   - `儲存 Markdown 檔案 ＋ 於對話視窗直接顯示（建議：output/<音訊檔名>_會議紀錄.md） (Recommended)`
   - `僅儲存 Markdown 檔案（建議：output/<音訊檔名>_會議紀錄.md）`
   - `僅在對話視窗直接輸出，不另存檔案`

**第 3 題的略過規則：** 只輸出逐字稿時不會呼叫 LLM，第 3 題沒有作用。

- 若使用者事先已表明只要逐字稿，提問時直接略過第 3 題。
- 若一次問完 4 題後，第 2 題只選了逐字稿，則忽略第 3 題的答案，也不傳 `--llm-model`。

**補充資訊：** 若使用者提到錄音情境（例如「這是醫學研討會」「這是英文訪談」）、領域術語或想要的紀錄語言，分別傳入 `--custom-prompt` 與 `--language`，不需要額外提問。

---

## 步驟二：執行轉寫與會議記錄生成腳本

確認使用者選項後，使用 `uv run` 呼叫本 Skill 內建的專用腳本 [transcribe_meeting.py](./scripts/transcribe_meeting.py)：

```powershell
$env:PYTHONIOENCODING="utf-8"
uv run .agents/skills/meeting-assistant/scripts/transcribe_meeting.py `
  --audio "<音訊檔案路徑>" `
  --stt-model "<選擇的 STT 模型>" `
  --llm-model "<選擇的 LLM 模型>" `
  --sections "<逗號分隔的區塊代碼: summary,speakers,decisions,actions,issues,transcript>" `
  --custom-prompt "<錄音情境、領域術語等補充需求（若有）>" `
  --language "<紀錄語言（選用，預設：台灣繁體中文）>" `
  --output "<輸出 .md 路徑（選用）>"
```

> 轉寫一律依錄音的原始語言逐字輸出（中文使用台灣繁體中文，英文等其他語言保留原文、不翻譯）；`--language` 只影響摘要與整理的撰寫語言。

### 輸出參數對照規則（依第 4 題選擇決定）
- **儲存檔案 ＋ 對話顯示**：同時傳入 `--output "output/<檔名>_會議紀錄.md"` 與 `--print-output`。
- **僅儲存 Markdown 檔案**：僅傳入 `--output "output/<檔名>_會議紀錄.md"`（**不要**加 `--print-output`）。
- **僅在對話視窗直接輸出**：**不傳** `--output`（腳本偵測到無 `--output` 時會自動印出完整內容）。

### 區塊代碼 (`--sections`) 對照表
- `summary`：📋 重點摘要
- `speakers`：💬 各發言者／段落要點
- `decisions`：⚖️ 決議與共識
- `actions`：✅ 待辦與執行項目（含負責人／期限／追蹤事項表格）
- `issues`：❓ 待確認與待協調事項
- `transcript`：📝 保留完整時間軸原始逐字稿

---

## 步驟三：檢視與交付結果

1. 腳本執行完成後，依據使用者在步驟一選擇的「輸出方式」：
   - 若有儲存檔案，請附上產出的 Markdown 檔案連結（例如 `[<音訊檔名>_會議紀錄.md](output/<音訊檔名>_會議紀錄.md)`）。
   - 若選擇在對話中顯示，請將整理好的結構化會議紀錄呈現給使用者。
2. 全程遵守專案根目錄 [AGENTS.md](../../../AGENTS.md) 安全規範，嚴禁讀取 `.env` 或印出 API Key。
