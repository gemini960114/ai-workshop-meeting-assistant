"""通用會議錄音轉文字與結構化會議紀錄產生腳本。

支援：
1. 專職 ASR 模型（Breeze-ASR-26、whisper-Breeze-ASR-25，透過 /audio/transcriptions）
2. 全模態 Chat 模型（Inkling-Small、Muse-Spark-Open-816B-A42B，透過 /chat/completions input_audio）
3. 自動透過 ffmpeg 將長音訊（.m4a/.mp3/.wav 等）以重疊緩衝（Overlap）切分並行轉寫，並消除交界重複字詞
4. 支援超長會議逐字稿自動分段摘要再總結（Map-Reduce），避免逾時或截斷
"""

import argparse
import asyncio
import base64
import math
import os
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ASR_MODELS = {"Breeze-ASR-26", "whisper-Breeze-ASR-25"}
OMNI_CHAT_MODELS = {"Inkling-Small", "Muse-Spark-Open-816B-A42B"}
MAX_DIRECT_SUMMARY_CHARS = 12000


def get_api_config() -> tuple[str, str, str]:
    """從 .env 讀取標準 API 設定（遵循 .env.example，嚴禁印出金鑰內容）。"""
    load_dotenv(override=True)
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    base_url = (
        os.getenv("OPENAI_BASE_URL") or "https://portal.genai.nchc.org.tw/api/v1"
    ).strip().strip('"').strip("'").rstrip("/")
    default_model = (
        os.getenv("DEFAULT_MODEL") or "Muse-Spark-Open-816B-A42B"
    ).strip().strip('"').strip("'")

    if base_url.endswith("/models"):
        base_url = base_url[: -len("/models")].rstrip("/")

    if not api_key or api_key == "your-api-key":
        raise ValueError("未偵測到有效的 OPENAI_API_KEY，請確認專案目錄下 .env 檔案設定。")

    return api_key, base_url, default_model


def ensure_ffmpeg_available() -> None:
    """確認系統已安裝 ffmpeg 與 ffprobe。"""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("系統找不到 ffmpeg 或 ffprobe，請先安裝 ffmpeg 後再執行。")


def format_timestamp(seconds: float) -> str:
    """將秒數轉為 MM:SS 或 HH:MM:SS 格式。"""
    total_sec = max(0, int(seconds))
    mins, secs = divmod(total_sec, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def _is_ignorable_char(ch: str) -> bool:
    """判斷字元是否為比對重疊時應忽略的空白或標點（ASR 在切點處的斷詞與標點常不一致）。"""
    return ch.isspace() or unicodedata.category(ch).startswith("P")


def deduplicate_overlap_segments(
    segments: list[dict[str, Any]],
    window: int = 20,
    min_overlap: int = 3,
) -> list[dict[str, Any]]:
    """消除相鄰分段因 Overlap 產生的首尾重複字詞（忽略空白、標點與英文大小寫差異後比對）。"""
    for i in range(1, len(segments)):
        prev_seg = segments[i - 1]
        curr_seg = segments[i]
        if prev_seg.get("failed") or curr_seg.get("failed"):
            continue
        prev_txt = prev_seg["text"].strip()
        curr_txt = curr_seg["text"].strip()
        if not prev_txt or not curr_txt:
            continue

        # 前段結尾：去除空白與標點後取最後 window 個字
        tail = "".join(ch for ch in prev_txt if not _is_ignorable_char(ch)).lower()[-window:]
        # 後段開頭：保留每個有效字元在原字串中的位置，方便比對後回推裁切點
        head_chars: list[tuple[str, int]] = []
        for pos, ch in enumerate(curr_txt):
            if len(head_chars) >= window:
                break
            if not _is_ignorable_char(ch):
                head_chars.append((ch.lower(), pos))
        head = "".join(ch for ch, _ in head_chars)

        for k in range(min(len(tail), len(head)), min_overlap - 1, -1):
            if tail.endswith(head[:k]):
                # 裁掉重複字，並去除裁切點後殘留的開頭空白與標點
                rest = curr_txt[head_chars[k - 1][1] + 1 :]
                while rest and _is_ignorable_char(rest[0]):
                    rest = rest[1:]
                curr_seg["text"] = rest
                break
    return segments


def get_audio_duration(audio_path: Path) -> float:
    """透過 ffprobe 取得音訊總秒數。"""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(proc.stdout.strip())
    except Exception as exc:
        raise RuntimeError(f"無法讀取音訊長度 ({type(exc).__name__})") from exc


def extract_wav_chunk(audio_path: Path, start_sec: float, duration_sec: float) -> bytes:
    """透過 ffmpeg 擷取指定區間並轉為 16kHz 單聲道 WAV bytes。"""
    try:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-ss",
                f"{start_sec:.2f}",
                "-t",
                f"{duration_sec:.2f}",
                "-i",
                str(audio_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
        )
        return proc.stdout
    except Exception as exc:
        raise RuntimeError(f"音訊切片轉換失敗 ({type(exc).__name__})") from exc


async def post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    json_payload: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    timeout: float = 90.0,
    max_retries: int = 3,
    context_label: str = "API",
) -> dict[str, Any]:
    """統一底層 HTTP POST 封裝：管理逾時、狀態碼報錯與退避重試（4xx 不重試，429/5xx 重試）。"""
    last_error_msg = ""
    for attempt in range(max_retries):
        try:
            resp = await client.post(
                url,
                json=json_payload,
                data=data,
                files=files,
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp.json()

            # 4xx（除 429 外）屬於用戶端或權限錯誤，不進行重試
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise RuntimeError(f"{context_label} 失敗 (HTTP {resp.status_code})")

            last_error_msg = f"HTTP {resp.status_code}"
        except RuntimeError:
            raise
        except httpx.TimeoutException:
            last_error_msg = f"連線逾時 (Timeout > {int(timeout)}s)"
        except Exception as exc:
            last_error_msg = type(exc).__name__

        if attempt < max_retries - 1:
            await asyncio.sleep(2.0 * (attempt + 1))

    raise RuntimeError(f"{context_label} 重試 {max_retries} 次後仍失敗 ({last_error_msg})")


async def call_chat_completion(
    client: httpx.AsyncClient,
    base_url: str,
    model_id: str,
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    timeout: float = 300.0,
    context_label: str = "LLM 呼叫",
) -> str:
    """專用封裝：統一管理 Chat Completions 呼叫、模型參數與錯誤處理。"""
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = await post_with_retry(
        client,
        f"{base_url}/chat/completions",
        json_payload=payload,
        timeout=timeout,
        context_label=f"{context_label} [{model_id}]",
    )
    try:
        msg = data["choices"][0]["message"]
        return (msg.get("content") or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"{context_label} 回傳格式異常 ({type(exc).__name__})") from exc


async def call_asr_transcription(
    client: httpx.AsyncClient,
    base_url: str,
    model_id: str,
    wav_bytes: bytes,
    chunk_idx: int,
) -> str:
    """專用封裝：呼叫 /audio/transcriptions 進行語音轉文字。"""
    data = await post_with_retry(
        client,
        f"{base_url}/audio/transcriptions",
        data={"model": model_id},
        files={"file": (f"chunk_{chunk_idx}.wav", wav_bytes, "audio/wav")},
        timeout=90.0,
        context_label=f"分段 #{chunk_idx + 1} ASR 轉寫 [{model_id}]",
    )
    return (data.get("text") or "").strip()


async def call_omni_audio_transcription(
    client: httpx.AsyncClient,
    base_url: str,
    model_id: str,
    wav_bytes: bytes,
    chunk_idx: int,
) -> str:
    """專用封裝：呼叫全模態 Chat 模型 (/chat/completions + input_audio) 進行聽音逐字轉寫。"""
    wav_b64 = base64.b64encode(wav_bytes).decode("ascii")
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一位精準的語音逐字稿速記員。請依音訊的原始語言逐字轉寫，不要翻譯、不要摘要，"
                "也不要加入任何解釋或額外開頭。中文內容一律使用台灣繁體中文；"
                "英文等其他語言、專有名詞與術語保留原文。"
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "請將這段錄音完整轉寫為逐字稿（依原始語言，僅輸出聽到的語音內容）：",
                },
                {
                    "type": "input_audio",
                    "input_audio": {"data": wav_b64, "format": "wav"},
                },
            ],
        },
    ]
    return await call_chat_completion(
        client,
        base_url,
        model_id,
        messages,
        max_tokens=2048,
        temperature=0.1,
        timeout=120.0,
        context_label=f"分段 #{chunk_idx + 1} 多模態聽音轉寫",
    )


async def transcribe_full_audio(
    client: httpx.AsyncClient,
    base_url: str,
    audio_path: Path,
    stt_model: str,
    chunk_seconds: int = 60,
    overlap_seconds: float = 1.5,
    concurrency: int = 4,
) -> list[dict[str, Any]]:
    """將長音訊切分（含前後重疊緩衝）後並行轉寫，單段失敗時保留其餘成功段落。"""
    duration = get_audio_duration(audio_path)
    num_chunks = max(1, math.ceil(duration / chunk_seconds))
    print(
        f"🎙️ 音訊總長度：{format_timestamp(duration)} ({duration:.1f}s)，"
        f"分為 {num_chunks} 段（每段 {chunk_seconds}s，重疊緩衝 {overlap_seconds}s），"
        f"使用模型：{stt_model}",
        flush=True,
    )

    sem = asyncio.Semaphore(concurrency)

    async def process_one(idx: int) -> dict[str, Any]:
        nominal_start = idx * chunk_seconds
        nominal_end = min(duration, (idx + 1) * chunk_seconds)
        actual_start = max(0.0, nominal_start - (overlap_seconds if idx > 0 else 0.0))
        actual_end = min(duration, nominal_end + (overlap_seconds if idx < num_chunks - 1 else 0.0))
        time_label = f"{format_timestamp(nominal_start)} - {format_timestamp(nominal_end)}"

        async with sem:
            t0 = time.perf_counter()
            try:
                wav_bytes = await asyncio.to_thread(
                    extract_wav_chunk, audio_path, actual_start, actual_end - actual_start
                )
                if stt_model in ASR_MODELS:
                    text = await call_asr_transcription(client, base_url, stt_model, wav_bytes, idx)
                else:
                    text = await call_omni_audio_transcription(client, base_url, stt_model, wav_bytes, idx)
                elapsed = round(time.perf_counter() - t0, 2)
                print(f"  ✅ [{idx + 1}/{num_chunks}] ({time_label}) 完成 ({elapsed}s)", flush=True)
                return {"index": idx, "time_label": time_label, "text": text, "failed": False}
            except Exception as exc:
                elapsed = round(time.perf_counter() - t0, 2)
                print(f"  ⚠️ [{idx + 1}/{num_chunks}] ({time_label}) 失敗 ({elapsed}s) -> {exc}", flush=True)
                return {
                    "index": idx,
                    "time_label": time_label,
                    "text": f"[⚠️ 此段轉寫失敗：{exc}]",
                    "failed": True,
                }

    tasks = [process_one(i) for i in range(num_chunks)]
    segments = sorted(await asyncio.gather(*tasks), key=lambda x: x["index"])
    return deduplicate_overlap_segments(segments)


def build_section_instructions(sections: list[str]) -> str:
    """根據使用者勾選之區塊代碼組合提示詞指令。"""
    instructions: list[str] = []
    if "summary" in sections:
        instructions.append(
            "### 📋 重點摘要 (Summary)\n"
            "- 以精煉條列整理這段錄音的背景、主要討論主題與整體結論。"
        )
    if "speakers" in sections:
        instructions.append(
            "### 💬 各發言者／段落要點\n"
            "- 依發言順序、發言者或所屬單位（若可辨識），歸納各段落的重點、論點與關鍵數據（可附時間區間）。"
        )
    if "decisions" in sections:
        instructions.append(
            "### ⚖️ 決議與共識 (Decisions)\n"
            "- 列出討論中達成的決議、共識、通過的提案，或主持人／負責人的明確裁定；若無則註明「未提及」。"
        )
    if "actions" in sections:
        instructions.append(
            "### ✅ 待辦與執行項目 (Action Items)\n"
            "- 請以 Markdown 表格列出：| 執行事項 | 負責人/單位 | 時程/期限 | 備註/後續追蹤 |；未提及的欄位填「未提及」，不要自行推測。"
        )
    if "issues" in sections:
        instructions.append(
            "### ❓ 待確認與待協調事項 (Open Issues)\n"
            "- 列出討論中尚未定案、需補充資料，或需會後進一步確認／協調的事項。"
        )
    return "\n\n".join(instructions)


async def summarize_transcript(
    client: httpx.AsyncClient,
    base_url: str,
    llm_model: str,
    audio_name: str,
    stt_model: str,
    segments: list[dict[str, Any]],
    sections: list[str],
    custom_prompt: str = "",
    language: str = "台灣繁體中文",
) -> str:
    """將逐字稿整理為結構化會議紀錄；若逐字稿過長則自動先分段提煉再總結（Map-Reduce）。"""
    req_sections_str = build_section_instructions(sections)
    if not req_sections_str and not custom_prompt:
        return ""

    valid_lines = [
        f"[{seg['time_label']}] {seg['text']}"
        for seg in segments
        if seg["text"] and not seg.get("failed")
    ]
    if not valid_lines:
        raise RuntimeError("所有音訊分段皆轉寫失敗或無有效文字，無法產製會議摘要。")

    full_transcript = "\n".join(valid_lines)
    system_prompt = (
        "你是一位專業的會議紀錄整理員，擅長整理各類會議、討論、訪談與課堂等錄音內容。"
        f"請根據提供的逐字稿，使用{language}撰寫結構清楚、條理分明、忠於原意的 Markdown 紀錄；"
        "專有名詞與術語可保留原文。只整理逐字稿中實際出現的內容，不要臆測或補充不存在的資訊。"
        "注意：語音辨識可能存在同音錯字或分段重疊字詞，請根據前後文語意修正專有名詞與通順度。"
    )

    source_material = full_transcript
    if len(full_transcript) > MAX_DIRECT_SUMMARY_CHARS:
        print(
            f"📚 逐字稿較長（共 {len(full_transcript)} 字），啟動兩階段分段提煉與總結...",
            flush=True,
        )
        batches: list[str] = []
        current_batch: list[str] = []
        current_len = 0
        for line in valid_lines:
            if current_len + len(line) > MAX_DIRECT_SUMMARY_CHARS and current_batch:
                batches.append("\n".join(current_batch))
                current_batch = [line]
                current_len = len(line)
            else:
                current_batch.append(line)
                current_len += len(line) + 1
        if current_batch:
            batches.append("\n".join(current_batch))

        partial_notes: list[str] = []
        for b_idx, batch_text in enumerate(batches):
            print(f"  🔄 正在提煉第 {b_idx + 1}/{len(batches)} 部分會議要點...", flush=True)
            note = await call_chat_completion(
                client,
                base_url,
                llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"請詳細保留以下逐字稿片段中的發言者／單位、主要論點、關鍵數據、決議與待辦事項（保留時間標記）：\n\n{batch_text}"
                        ),
                    },
                ],
                max_tokens=4096,
                temperature=0.2,
                timeout=300.0,
                context_label=f"階段提煉 ({b_idx + 1}/{len(batches)})",
            )
            partial_notes.append(f"#### 會議階段 {b_idx + 1} 詳細紀錄\n{note}")
        source_material = "\n\n".join(partial_notes)

    custom_block = f"\n\n【使用者額外指定需求】：\n{custom_prompt}" if custom_prompt else ""
    user_prompt = (
        f"以下為「{audio_name}」經由 `{stt_model}` 轉寫之會議內容。\n"
        f"請依照下列指定區塊結構產出完整 Markdown 會議報告：\n\n"
        f"{req_sections_str}{custom_block}\n\n"
        f"--- 會議內容開始 ---\n{source_material}\n--- 會議內容結束 ---"
    )

    print(f"🧠 正在使用 {llm_model} 生成最終結構化會議報告...", flush=True)
    return await call_chat_completion(
        client,
        base_url,
        llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=8192,
        temperature=0.2,
        timeout=360.0,
        context_label="最終會議摘要生成",
    )


async def run_pipeline(args: argparse.Namespace) -> None:
    """整合執行音訊轉寫、LLM 會議摘要與 Markdown 輸出。"""
    ensure_ffmpeg_available()
    api_key, base_url, default_model = get_api_config()
    llm_model = args.llm_model or default_model

    audio_path = Path(args.audio).resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"找不到音訊檔案：{audio_path}")

    sections = [s.strip().lower() for s in args.sections.split(",") if s.strip()]
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(headers=headers, verify=True) as client:
        segments = await transcribe_full_audio(
            client=client,
            base_url=base_url,
            audio_path=audio_path,
            stt_model=args.stt_model,
            chunk_seconds=args.chunk_seconds,
            overlap_seconds=args.overlap_seconds,
            concurrency=args.concurrency,
        )

        llm_sections = [s for s in sections if s != "transcript"]
        need_llm = bool(llm_sections or args.custom_prompt)
        llm_report = ""
        if need_llm:
            llm_report = await summarize_transcript(
                client=client,
                base_url=base_url,
                llm_model=llm_model,
                audio_name=audio_path.stem,
                stt_model=args.stt_model,
                segments=segments,
                sections=llm_sections,
                custom_prompt=args.custom_prompt,
                language=args.language,
            )

    failed_count = sum(1 for seg in segments if seg.get("failed"))
    md_parts: list[str] = [
        f"# 📝 會議記錄：{audio_path.stem}",
        "",
        f"- **原始音訊檔案**：`{audio_path.name}`",
        f"- **語音轉寫模型 (STT)**：`{args.stt_model}`",
    ]
    if need_llm:
        md_parts.append(f"- **摘要分析模型 (LLM)**：`{llm_model}`")
    md_parts.extend(
        [
            f"- **分段轉寫狀態**：成功 {len(segments) - failed_count} / {len(segments)} 段",
            f"- **產製時間**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]
    )

    if llm_report:
        md_parts.append(llm_report)
        md_parts.append("\n---\n")

    if "transcript" in sections:
        md_parts.append("## 🗣️ 原始會議逐字稿（附時間軸）\n")
        for seg in segments:
            if seg["text"]:
                md_parts.append(f"- **`[{seg['time_label']}]`** {seg['text']}")
        md_parts.append("")

    final_md = "\n".join(md_parts)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(final_md, encoding="utf-8")
        print(f"\n💾 會議記錄已成功儲存至：{out_path}", flush=True)

    if args.print_output or not args.output:
        print("\n================ 會議記錄內容輸出 ================\n", flush=True)
        print(final_md, flush=True)


def parse_args() -> argparse.Namespace:
    """解析命令列參數。"""
    parser = argparse.ArgumentParser(description="智慧會議錄音轉寫與結構化紀錄產生器")
    parser.add_argument("--audio", required=True, help="輸入音訊檔案路徑 (.m4a, .mp3, .wav 等)")
    parser.add_argument(
        "--stt-model",
        default="Breeze-ASR-26",
        choices=["Breeze-ASR-26", "whisper-Breeze-ASR-25", "Inkling-Small", "Muse-Spark-Open-816B-A42B"],
        help="選擇語音轉文字模型",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        choices=["Muse-Spark-Open-816B-A42B", "Muse-Glimmer-30B", "Inkling-Small"],
        help="選擇會議摘要與結構化整理之 LLM 模型（未指定時預設讀取 .env 的 DEFAULT_MODEL）",
    )
    parser.add_argument(
        "--sections",
        default="summary,speakers,decisions,actions,issues,transcript",
        help="要輸出的區塊代碼（逗號分隔：summary,speakers,decisions,actions,issues,transcript）",
    )
    parser.add_argument(
        "--custom-prompt",
        default="",
        help="使用者自訂額外提示或整理需求（例如錄音情境、領域術語、要保留原文的名詞）",
    )
    parser.add_argument("--language", default="台灣繁體中文", help="會議紀錄的撰寫語言（預設：台灣繁體中文）")
    parser.add_argument("--output", default="", help="儲存 Markdown 檔案之路徑（留空則僅直接輸出至終端機）")
    parser.add_argument("--chunk-seconds", type=int, default=60, help="音訊切片秒數（預設 60 秒）")
    parser.add_argument("--overlap-seconds", type=float, default=1.5, help="切片前後重疊秒數（預設 1.5 秒）")
    parser.add_argument("--concurrency", type=int, default=4, help="並行轉寫請求數")
    parser.add_argument("--print-output", action="store_true", help="是否於終端機印出完整 Markdown")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        asyncio.run(run_pipeline(parse_args()))
    except Exception as err:
        print(f"\n❌ 執行失敗：{err}", file=sys.stderr, flush=True)
        sys.exit(1)
