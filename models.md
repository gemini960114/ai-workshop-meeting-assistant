# Models 可用模型清單與多模態能力實測表

> **來源端點**：`GET https://portal.genai.nchc.org.tw/api/v1/models`  
> **金鑰設定**：透過 `.env` 的 `OPENAI_API_KEY` 載入（請參考 [`.env.example`](.env.example)）  
> **最後實測時間**：2026-11-08（已透過真實圖片、OCR 圖檔與「人工智慧測試一二三」語音檔進行真實驗證）

---

## 🌟 1. Chat / 多模態模型能力矩陣（`model_mode: chat`）

> 端點：`POST https://portal.genai.nchc.org.tw/api/v1/chat/completions`

| 模型 ID | 定位與說明 | 🗣️ 文字對話 | 🖼️ 看圖 (`image_url`) | 🎧 聽聲音 (`input_audio`) | 🛠️ 工具呼叫 (`tools`) | 實測狀態與延遲 |
|---|---|:---:|:---:|:---:|:---:|---|
| **`Inkling-Small`** | 輕量全能多模態（Omni）模型 | ✅ | ✅ 真實看圖 | ✅ **真實聽音** | ✅ `tool_calls` | ✅ 可用 (~0.45s) |
| **`Muse-Spark-Open-816B-A42B`** | 大型全能多模態 MoE（總 816B / 啟用 42B） | ✅ | ✅ 真實看圖 | ✅ **真實聽音** | ✅ `tool_calls` | ✅ 可用 (~0.35s) |
| **`Muse-Glimmer-30B`** | 30B 視覺語言（VLM）模型 | ✅ | ✅ 真實看圖 | ❌ 不支援音訊 | ✅ `tool_calls` | ✅ 可用 (~0.28s) |
| **`chandra-ocr-2`** | 文件與圖片 OCR 視覺辨識模型 | ✅ | ✅ **專精 OCR 辨字** | ❌ 不支援音訊 | ✅ `tool_calls` | ✅ 可用 (~0.50s) |

### 🔍 多模態實測細節說明
- **全能多模態（可看圖 + 可聽聲音）**：
  - **`Inkling-Small`** 與 **`Muse-Spark-Open-816B-A42B`** 皆支援在 `/chat/completions` 中同時或分別傳入圖片（`image_url`）與音訊（`input_audio`），實測傳入「人工智慧測試一二三」WAV 語音檔，兩者皆能精準聽出「人工智慧測試一二三」。
- **視覺多模態（可看圖，不可聽聲音）**：
  - **`Muse-Glimmer-30B`**：可精準辨識圖片顏色與內容，但傳入音訊時會回覆無法接收音訊檔案。
  - **`chandra-ocr-2`**：針對含有文字的圖片（如 `"NIAR 2026"`）能精準輸出 OCR 文字辨識結果，不支援音訊輸入。
- **工具呼叫（Function Calling）**：4 個 `chat` 模型全數支援 OpenAI 標準 `tools` 參數並能正確回傳 `tool_calls`。

---

## 🎙️ 2. ASR 專職語音辨識模型（`model_mode: audio-stt`）

> 端點：`POST https://portal.genai.nchc.org.tw/api/v1/audio/transcriptions`

| 模型 ID | 說明 | 實測轉錄結果（測試語音：「人工智慧測試一二三」） | 實測狀態與延遲 |
|---|---|---|---|
| **`Breeze-ASR-26`** | 聯發創新基地 Breeze ASR 26 台灣繁中/中英混合語音辨識 | `{"text": "人工智慧測試123"}` | ✅ 可用 (~1.04s) |
| **`whisper-Breeze-ASR-25`** | Whisper 架構 Breeze ASR 25 語音辨識模型 | `{"text": "人工智慧測試 123"}` | ✅ 可用 (~1.04s) |

---

## 🔊 3. TTS 專職語音合成模型（`model_mode: audio-tts`）

> 端點：`POST https://portal.genai.nchc.org.tw/api/v1/audio/speech`

| 模型 ID | 說明 | 實測狀態 | 備註 |
|---|---|---|---|
| **`BreezyVoice`** | 聯發創新基地 BreezyVoice（繁中語音合成） | ❌ 異常 (`502 Bad Gateway`) | 上游服務回傳 `Upstream Service Error: 後端模型服務暫時無法回應` |

---

## 📊 統計摘要

| 分類 | 模型數量 | 可看圖 | 可聽音 | 可用數量 |
|---|:---:|:---:|:---:|:---:|
| **Omni 全能多模態 (`Inkling-Small`, `Muse-Spark-Open-816B-A42B`)** | 2 | ✅ | ✅ | **2 / 2** ✅ |
| **VLM 視覺 / OCR (`Muse-Glimmer-30B`, `chandra-ocr-2`)** | 2 | ✅ | ❌ | **2 / 2** ✅ |
| **ASR 語音轉文字 (`Breeze-ASR-26`, `whisper-Breeze-ASR-25`)** | 2 | - | ✅ (專職 STT) | **2 / 2** ✅ |
| **TTS 文字轉語音 (`BreezyVoice`)** | 1 | - | - | **0 / 1** ⚠️ |
| **總計** | **7** | **4** | **4 (2 Chat + 2 ASR)** | **6 / 7 可用** |

---

## 🚀 多模態呼叫格式範例

### 1. 看圖理解（Vision：`Inkling-Small` / `Muse-Glimmer-30B` / `Muse-Spark-Open-816B-A42B` / `chandra-ocr-2`）
```json
{
  "model": "Inkling-Small",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "請描述這張圖片或辨識其中的文字"},
        {
          "type": "image_url",
          "image_url": {"url": "data:image/png;base64,<BASE64_ENCODED_PNG>"}
        }
      ]
    }
  ]
}
```

### 2. 聽聲音對話（Audio Chat：僅 `Inkling-Small` 與 `Muse-Spark-Open-816B-A42B` 支援）
> 注意：請使用 OpenAI 標準 `input_audio` 格式（`audio_url` 格式不會被解析）。
```json
{
  "model": "Inkling-Small",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "請聽這段音訊並回答裡面的內容"},
        {
          "type": "input_audio",
          "input_audio": {
            "data": "<BASE64_ENCODED_WAV>",
            "format": "wav"
          }
        }
      ]
    }
  ]
}
```

### 3. ASR 專職語音轉文字（`Breeze-ASR-26` / `whisper-Breeze-ASR-25`）
```bash
curl https://portal.genai.nchc.org.tw/api/v1/audio/transcriptions \
  -H "Authorization: Bearer your-api-key" \
  -F "model=Breeze-ASR-26" \
  -F "file=@sample.wav"
```
