# niar_class_20261109

NIAR 課程範例專案：使用國網中心 GenAI Portal（`https://portal.genai.nchc.org.tw/api/v1`）提供的模型，搭配 AI coding agent（Claude Code／Antigravity）的 Skill，把錄音檔轉成逐字稿與結構化會議紀錄。

## 目錄說明

| 路徑 | 說明 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Agent 規則：環境、資安、程式風格、可用模型（Claude Code 與 Antigravity 都會讀取） |
| [models.md](models.md) | Portal 上可用模型的清單與多模態能力實測結果 |
| [.agents/skills/meeting-assistant/](.agents/skills/meeting-assistant/) | 錄音轉寫與會議紀錄 Skill（`SKILL.md` ＋ `scripts/transcribe_meeting.py`） |
| [example/](example/) | 範例錄音檔 |
| `.env.example` | 環境變數範本（複製成 `.env` 後填入金鑰） |
| `output/` | Skill 產出的會議紀錄（已列在 `.gitignore`，不會被 commit） |

## 環境準備

1. **安裝 [uv](https://docs.astral.sh/uv/)**，並安裝專案套件：

   ```powershell
   uv sync
   ```

2. **設定 API 金鑰**：複製 `.env.example` 成 `.env`，把 `OPENAI_API_KEY` 改成自己的金鑰。`.env` 已列在 `.gitignore`，請勿 commit 或分享。

   ```powershell
   Copy-Item .env.example .env
   ```

3. **安裝 ffmpeg**（錄音切段與轉檔需要），裝好後確認指令可用：

   ```powershell
   winget install Gyan.FFmpeg
   ffmpeg -version
   ```

## 讓 Claude Code 讀到 `.agents/skills`

Antigravity 會從 `.agents/skills/` 載入 skill，Claude Code 則是從 `.claude/skills/`。clone 下來之後，在專案根目錄用 PowerShell 執行下列指令，建立 junction 讓兩邊共用同一份 skill（不需要系統管理員權限）：

```powershell
# 建立 .claude 資料夾，並把 .claude\skills 用 junction 連到 .agents\skills
New-Item -ItemType Directory -Force .claude
New-Item -ItemType Junction -Path .claude\skills -Target (Resolve-Path .agents\skills)

# 確認：junction 有指向 .agents\skills，而且看得到 SKILL.md
Get-Item .claude\skills | Select-Object LinkType, Target
Get-ChildItem .claude\skills\meeting-assistant
```

執行完後，重新開啟 Claude Code session 或重新載入 VS Code 視窗，Claude Code 就會載入這些 skill。

- `.claude/skills` 已經列在 `.gitignore`，不會被 commit；skill 只要放在 `.agents/skills/` 維護即可。
- 移除連結（只刪連結，不會動到 `.agents\skills` 的內容）：

  ```powershell
  (Get-Item .claude\skills).Delete()
  ```

## 使用 `meeting-assistant` Skill

### 在 Agent 裡使用

直接用自然語言提出需求，agent 會自動啟用 skill，並用選單詢問 STT 模型、紀錄區塊、LLM 模型與輸出方式。例如：

> 幫我把 example/台南市市政會議錄音檔案.m4a 轉成會議紀錄

在 Claude Code 也可以輸入 `/meeting-assistant` 直接叫用。

### 直接執行腳本

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

常用參數（完整說明見 [SKILL.md](.agents/skills/meeting-assistant/SKILL.md)，或執行時加 `--help`）：

| 參數 | 說明 |
| --- | --- |
| `--stt-model` | 語音轉文字模型：`Breeze-ASR-26`（預設）、`whisper-Breeze-ASR-25`、`Inkling-Small`、`Muse-Spark-Open-816B-A42B` |
| `--llm-model` | 摘要模型；未指定時使用 `.env` 的 `DEFAULT_MODEL` |
| `--sections` | 要輸出的區塊：`summary`、`speakers`、`decisions`、`actions`、`issues`、`transcript` |
| `--custom-prompt` | 補充錄音情境或領域術語，例如 `"這是醫學研討會，藥名保留英文"` |
| `--language` | 紀錄的撰寫語言，預設「台灣繁體中文」 |
| `--output` | 存檔路徑；不指定時直接印在終端機 |
| `--print-output` | 有存檔時也同時印在終端機 |
