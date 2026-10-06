"""The live voice check's client (R28, mode A): it plays the new UI's part against the sandbox.

Run by voice_check.py inside the app image (it has `websockets`), never by hand. Like the real client it holds no
key: it asks the sandbox for a voice session, opens the Gemini Live socket with the one-use token it is given,
sends the setup message the server named, asks by text, relays every function call to /api/agent/voice/tool and
answers the model with what the server returned, then ends the session so the server bills it.

Per scenario it records: time to first audio, the spoken transcript, the function calls and the §4 events the
server returned, whether a barge-in stopped the speech and how fast, the seconds the server billed. The audio it
heard is written as WAV files next to the result, for people to rate (synthetic speech of Orena only; nothing a
learner said). It stops before the next scenario could pass the cap.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import websockets

USD_PER_SECOND = 0.036 / 60  # the catalog's Gemini Live rate (ai/pricing.py); the server bills the same way
SCENARIO_SECONDS = 60  # at most this long each, so the cap is checked before a scenario starts


# The learner's session (its learning language among it) lives in a cookie, as in a browser.
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(request, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"{}")
        except ValueError:
            return error.code, {}


WORD = {"type": "word", "text": "花生", "lang": "zh-CN", "sentence": "既然你们那么爱吃花生，就辟来做花生园罢。"}
VI = {"interface": "vi", "support": "vi"}
SCENARIOS = [
    # name, learning language, locale, context extra, what the learner says, barge-in after first audio (s)
    ("vi-name", "zh", VI, {}, "Bạn tên là gì?", None),
    ("vi-word-here", "zh", VI, {"selected_item": WORD}, "Từ này nghĩa là gì ở đây?", None),
    ("vi-save", "zh", VI, {"selected_item": WORD}, "Lưu từ này giúp mình nhé.", None),
    ("vi-barge-in", "zh", VI, {"selected_item": WORD},
     "Kể thật chi tiết về lịch sử cây lạc ở Trung Quốc, càng dài càng tốt.", 2.0),
    ("en-word", "zh", {"interface": "en", "support": "en"}, {"selected_item": WORD}, "What does this word mean here?", None),
    ("zh-word", "en", {"interface": "zh-CN", "support": "zh-CN"},
     {"selected_item": {"type": "word", "text": "meticulous", "lang": "en"}}, "这个词是什么意思？", None),
    # R29: open a lesson by voice, and every voice of the catalog
    ("vi-open-video", "zh", VI, {}, "Mở một video bất kỳ trong Listening để mình nghe.", None),
    *[(f"voice-{v}", "zh", VI, {"voice": v}, "Chào bạn, hôm nay mình học gì?", None)
      for v in ("f-clear", "f-bright", "f-warm", "f-soft", "f-young", "f-gentle",
                "m-calm", "m-lively", "m-friendly", "m-steady")],
]


async def scenario(base: str, name: str, locale: dict, extra: dict, said: str, barge: float | None,
                   audio_dir: Path) -> dict:  # fmt: skip
    target = "zh-CN" if (extra.get("selected_item") or {}).get("lang", "zh-CN") == "zh-CN" else "en"
    extra = dict(extra)
    voice = extra.pop("voice", None)
    body = {"contract_version": 5,
            "client": {"ui_version": "voice-check", "supported_actions": ["save_word", "navigate", "start_review"],
                       "supported_intents": ["vocabulary.word", "vocabulary.my_language", "vocabulary.review_due",
                                             "listening.workspace", "reading.workspace"]},
            "context": {"surface": "reading.workspace" if extra.get("selected_item") else "orena.home",
                        "activity_type": "reading", "locale": {**locale, "target": target, "content": target},
                        **extra}}  # fmt: skip
    if voice:
        body["voice"] = voice
    status, opened = call(base, "POST", "/api/agent/voice/session", body)
    row: dict = {"scenario": name, "session_status": status}
    if status != 200:
        row["error"] = opened.get("detail")
        return row
    connect, sid = opened["connect"], opened["voice_session_id"]
    pcm = bytearray()
    calls, events, transcript, heard = [], [], [], []
    first_audio = interrupted_at = stop_ms = None
    started = 0.0
    opened_at = time.monotonic()
    async with websockets.connect(f"{connect['url']}?access_token={connect['ephemeral_token']}", max_size=None) as ws:
        await ws.send(json.dumps(connect["setup"]))
        barged = False
        # until setup completes, a short wait: a session that never starts is not left open (nor billed) a minute
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
            except TimeoutError:
                break
            except websockets.ConnectionClosed as closed:
                row["closed"] = {"code": closed.code, "reason": str(closed.reason)[:300]}
                break
            message = json.loads(raw)
            row.setdefault("first_messages", [])
            if len(row["first_messages"]) < 4:
                row["first_messages"].append(sorted(message))
            if "setupComplete" in message:  # an empty object: present, not truthy
                row["setup_complete_ms"] = round((time.monotonic() - opened_at) * 1000)
                started = time.monotonic()
                deadline = time.monotonic() + SCENARIO_SECONDS
                await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user", "parts": [{"text": said}]}],
                                                            "turnComplete": True}}))  # fmt: skip
                continue
            if message.get("toolCall"):
                fcs = message["toolCall"].get("functionCalls") or []
                calls.extend({"name": fc.get("name"), "args": fc.get("args"), "ms": round((time.monotonic() - started) * 1000)}
                             for fc in fcs)  # fmt: skip
                _, relayed = call(base, "POST", "/api/agent/voice/tool",
                                  {"voice_session_id": sid, "heard": said,
                                   "calls": [{"id": fc.get("id"), "name": fc.get("name"), "args": fc.get("args") or {}}
                                             for fc in fcs]})  # fmt: skip
                events.extend(relayed.get("events", []))
                if relayed.get("open"):
                    row["opened_action"] = relayed["open"]
                await ws.send(json.dumps({"toolResponse": {"functionResponses": relayed.get("responses", [])}}))
                continue
            content = message.get("serverContent") or {}
            if content.get("outputTranscription", {}).get("text"):
                transcript.append(content["outputTranscription"]["text"])
            if content.get("inputTranscription", {}).get("text"):
                heard.append(content["inputTranscription"]["text"])
            for part in (content.get("modelTurn") or {}).get("parts") or []:
                data = (part.get("inlineData") or {}).get("data")
                if data:
                    if first_audio is None:
                        first_audio = round((time.monotonic() - started) * 1000)
                    pcm.extend(base64.b64decode(data))
            if barge is not None and not barged and first_audio is not None \
                    and time.monotonic() - started > first_audio / 1000 + barge:
                barged, interrupted_at = True, time.monotonic()
                await ws.send(json.dumps({"clientContent": {"turns": [{"role": "user",
                    "parts": [{"text": "Dừng lại, nói ngắn thôi."}]}], "turnComplete": True}}))  # fmt: skip
            if content.get("interrupted") and interrupted_at is not None and stop_ms is None:
                stop_ms = round((time.monotonic() - interrupted_at) * 1000)
            if content.get("turnComplete") and first_audio is not None and (barge is None or barged):
                if barge is None or stop_ms is not None or time.monotonic() - interrupted_at > 8:
                    break
    _, ended = call(base, "POST", "/api/agent/voice/end", {"voice_session_id": sid})
    audio = audio_dir / f"{name}.wav"
    with wave.open(str(audio), "wb") as out:
        out.setnchannels(1), out.setsampwidth(2), out.setframerate(24000), out.writeframes(bytes(pcm))
    row.update(first_audio_ms=first_audio, said=" ".join(transcript).strip(), calls=calls,
               events=[e.get("event") for e in events], event_data=events, barge_in_stop_ms=stop_ms,
               barged=barge is not None, audio_seconds_heard=round(len(pcm) / 48000, 1),
               billed_seconds=ended.get("seconds"), audio_file=audio.name)  # fmt: skip
    return row


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--cap-usd", type=float, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    only = {n for n in args.only.split(",") if n}
    rows, spent, language = [], 0.0, None
    for name, learning, locale, extra, said, barge in SCENARIOS:
        if only and name not in only:
            continue
        if spent + SCENARIO_SECONDS * USD_PER_SECOND > args.cap_usd:
            rows.append({"scenario": name, "skipped": "the next scenario could pass the cap"})
            break
        if learning != language:
            switched, answer = call(args.base, "POST", "/api/platform/language", {"language": learning})
            if switched != 200:
                rows.append({"scenario": name, "skipped": f"the learning language did not switch ({switched})",
                             "detail": str(answer)[:200]})  # fmt: skip
                continue
            language = learning
        row = await scenario(args.base, name, locale, extra, said, barge, out.parent)
        spent += (row.get("billed_seconds") or 0) * USD_PER_SECOND
        row["spent_usd_so_far"] = round(spent, 4)
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if k != "event_data"}, ensure_ascii=False), flush=True)
    out.write_text(json.dumps({"spent_usd": round(spent, 4), "rows": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
