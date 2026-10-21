import os
import sys
import time
import wave
import json
import argparse
import subprocess
import importlib.util
import asyncio
import msvcrt

import pyaudio
import whisper
import edge_tts

# 当前脚本目录
DIR = os.path.dirname(os.path.abspath(__file__))

# ===== 复用 08_llm_chat.py 的配置与 chat_once =====
# 08 文件名以数字开头，无法用 import 直接导入，故用 importlib 加载
# 这样 BASE_URL / API_KEY / MODEL / SYSTEM_PROMPT 只维护在 08 一处
def _load_llm_chat():
    path = os.path.join(DIR, "08_llm_chat.py")
    spec = importlib.util.spec_from_file_location("llm_chat_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

llm = _load_llm_chat()

# ===== 录音参数（参考 03_audio.py） =====
RATE     = 16000              # 采样率 16kHz
CHANNELS = 1                  # 单声道
FORMAT   = pyaudio.paInt16    # 16-bit
CHUNK    = 1024               # 每次读取帧数

# ===== Whisper 模型缓存，避免每轮重新加载 =====
_asr_model = None


def get_asr_model(size="base"):
    global _asr_model
    if _asr_model is None:
        print(f"加载 Whisper 模型: {size} ...")
        _asr_model = whisper.load_model(size)
    return _asr_model


def record_once(out_path):
    """按 R 后进入此函数：开始录音，按 S 停止并保存 wav"""
    p = pyaudio.PyAudio()
    try:
        print("输入设备:", p.get_default_input_device_info()["name"])
    except Exception:
        print("未检测到默认输入设备")
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, frames_per_buffer=CHUNK)
    frames = []
    print(">>> 录音中 ... 按 S 停止")
    while True:
        if msvcrt.kbhit():
            k = msvcrt.getch().decode("utf-8", errors="ignore").lower()
            if k == "s":
                break
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
    stream.stop_stream()
    stream.close()
    sampwidth = p.get_sample_size(FORMAT)
    p.terminate()
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(sampwidth)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    print(f"录音已保存: {out_path}")


def asr_once(wav_path, model_size="base", language=None):
    """参考 04_whisper_asr.py：wav -> 文本"""
    model = get_asr_model(model_size)
    result = model.transcribe(wav_path, language=language, fp16=False)
    return result.get("text", "").strip()


async def _tts_save(text, voice, rate, out_mp3):
    """参考 06_edge_tts_demo.py：文本 -> mp3"""
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(out_mp3)


def tts_play(text, voice="zh-CN-XiaoxiaoNeural", rate="+0%",
             out_mp3="reply.mp3", play=True):
    """合成语音并用 ffplay 无窗口播放（阻塞至播完）"""
    asyncio.run(_tts_save(text, voice, rate, out_mp3))
    print(f"已合成语音: {out_mp3}")
    if play:
        # ffplay 无视频窗口、播放完自动退出、静默日志
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", out_mp3])


def main():
    parser = argparse.ArgumentParser(
        description="语音助手：录音(R) -> Whisper识别 -> LLM回答 -> EdgeTTS播放")
    parser.add_argument("--asr-model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小，默认 base")
    parser.add_argument("--language", type=str, default=None,
                        help="强制识别语言代码，如 zh，默认自动检测")
    parser.add_argument("--voice", type=str, default="zh-CN-XiaoxiaoNeural",
                        help="TTS 语音名，默认 zh-CN-XiaoxiaoNeural")
    parser.add_argument("--rate", type=str, default="+0%",
                        help="TTS 语速，如 +10%%，默认 +0%%")
    args = parser.parse_args()

    # 预加载 Whisper 模型（首次会自动下载，需联网）
    get_asr_model(args.asr_model)

    print("\n==== 语音助手就绪 ====")
    print("按 R 录音 -> S 停止 -> 自动识别+LLM回答+播放")
    print("按 Q 退出\n")

    # 多轮对话上下文：复用 08 的系统提示词
    messages = [{"role": "system", "content": llm.SYSTEM_PROMPT}]

    wav_path = os.path.join(DIR, "output.wav")
    mp3_path = os.path.join(DIR, "reply.mp3")

    while True:
        # 空闲轮询：等待按键
        if msvcrt.kbhit():
            key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
            if key == "q":
                print("退出")
                break
            if key == "r":
                # 1) 录音
                record_once(wav_path)

                # 2) ASR：wav -> 文本
                print("识别中...")
                user_text = asr_once(wav_path, args.asr_model, args.language)
                print(f"识别结果: {user_text}")
                if not user_text:
                    print("(未识别到内容，跳过本轮)\n")
                    continue

                # 3) LLM：文本 -> 回答（chat_once 会流式打印到终端）
                messages.append({"role": "user", "content": user_text})
                print("\n助手: ", end="", flush=True)
                reply = llm.chat_once(messages, llm.BASE_URL,
                                      llm.API_KEY, llm.MODEL)
                if reply is None:
                    # 请求失败，回滚用户消息
                    messages.pop()
                    continue
                if not reply.strip():
                    print("(空回复)")
                    continue
                messages.append({"role": "assistant", "content": reply})

                # 4) TTS：回答 -> mp3 -> 播放
                print("\n[合成语音播放中...]")
                tts_play(reply, args.voice, args.rate, mp3_path, play=True)
                print("[本轮结束] 按 R 下一轮\n")
        else:
            time.sleep(0.02)


if __name__ == "__main__":
    main()
