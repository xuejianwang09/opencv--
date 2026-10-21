import asyncio
import argparse
import os
import sys
import edge_tts

# 粤语语音（香港）：
#   HiuMaanNeural  女声
#   WanLungNeural  男声
CANTONESE_VOICES = {
    "female": "zh-HK-HiuMaanNeural",
    "male":   "zh-HK-WanLungNeural",
}

DEFAULT_TEXT = "你好，我是JM，一个智能助手,今天的天气真不错啊，适合去上海玩。"


async def list_voices():
    """仅列出粤语相关语音"""
    voices = await edge_tts.list_voices()
    print("粤语相关语音 (zh-HK):")
    for v in voices:
        if v["Locale"].startswith("zh-HK"):
            print(f"{v['ShortName']:32} {v['Gender']:8} {v['FriendlyName']}")


async def synthesize(text, voice, rate, volume, pitch, output):
    """合成语音并保存为 mp3"""
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, volume=volume, pitch=pitch)
    await communicate.save(output)


def main():
    parser = argparse.ArgumentParser(
        description="edge_tts 粤语（香港）文本转语音，需联网")
    parser.add_argument("--text", type=str, default=DEFAULT_TEXT,
                        help="要朗读的文本（建议粤语写法）")
    parser.add_argument("--gender", type=str, default="female",
                        choices=["female", "male"],
                        help="音色：female=HiuMaanNeural(女)，male=WanLungNeural(男)")
    parser.add_argument("--voice", type=str, default=None,
                        help="直接指定语音名，优先于 --gender，见 --list-voices")
    parser.add_argument("--rate", type=str, default="+0%",
                        help="语速，如 +10%% 或 -10%%，默认 +0%%")
    parser.add_argument("--volume", type=str, default="+0%",
                        help="音量，如 -20%%，默认 +0%%")
    parser.add_argument("--pitch", type=str, default="+0Hz",
                        help="音调，如 +10Hz，默认 +0Hz")
    parser.add_argument("--output", type=str, default="output_cantonese.mp3",
                        help="输出 mp3 文件名，默认 output_cantonese.mp3")
    parser.add_argument("--play", action="store_true",
                        help="生成后用系统默认播放器打开")
    parser.add_argument("--list-voices", action="store_true",
                        help="列出粤语相关语音后退出")
    args = parser.parse_args()

    if args.list_voices:
        asyncio.run(list_voices())
        return

    # 确定语音：--voice 优先，否则按 --gender 选粤语默认音
    voice = args.voice or CANTONESE_VOICES[args.gender]

    print(f"语音: {voice}  速率:{args.rate}  音量:{args.volume}  音调:{args.pitch}")
    print(f"文本: {args.text}")

    try:
        asyncio.run(synthesize(args.text, voice, args.rate,
                               args.volume, args.pitch, args.output))
    except Exception as e:
        print(f"合成失败: {e}")
        print("请检查网络是否可访问微软 TTS 服务")
        sys.exit(1)

    print(f"已保存: {args.output}")

    if args.play:
        if sys.platform == "win32":
            os.startfile(args.output)
        elif sys.platform == "darwin":
            os.system(f'open "{args.output}"')
        else:
            os.system(f'xdg-open "{args.output}"')


if __name__ == "__main__":
    main()
