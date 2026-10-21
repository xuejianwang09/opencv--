import asyncio
import argparse
import os
import sys
import edge_tts

# 默认使用晓晓（中文女声，神经语音）
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


async def list_voices():
    """列出 Edge TTS 所有可用语音"""
    voices = await edge_tts.list_voices()
    print(f"共 {len(voices)} 个语音:\n")
    for v in voices:
        print(f"{v['ShortName']:32} {v['Gender']:8} {v['Locale']:10} {v['FriendlyName']}")


async def synthesize(text, voice, rate, volume, pitch, output):
    """合成语音并保存为 mp3"""
    communicate = edge_tts.Communicate(
        text, voice, rate=rate, volume=volume, pitch=pitch)
    await communicate.save(output)


def main():
    parser = argparse.ArgumentParser(
        description="edge_tts 文本转语音（微软 Edge 神经语音，需联网）")
    parser.add_argument("--text", type=str,
                        default="你好，这是基于 edge_tts 的文本转语音演示。",
                        help="要朗读的文本")
    parser.add_argument("--voice", type=str, default=DEFAULT_VOICE,
                        help=f"语音名称，见 --list-voices，默认 {DEFAULT_VOICE}")
    parser.add_argument("--rate", type=str, default="+0%",
                        help="语速，如 +10%% 或 -10%%，默认 +0%%")
    parser.add_argument("--volume", type=str, default="+0%",
                        help="音量，如 -20%%，默认 +0%%")
    parser.add_argument("--pitch", type=str, default="+0Hz",
                        help="音调，如 +10Hz，默认 +0Hz")
    parser.add_argument("--output", type=str, default="output.mp3",
                        help="输出 mp3 文件名，默认 output.mp3")
    parser.add_argument("--play", action="store_true",
                        help="生成后用系统默认播放器打开")
    parser.add_argument("--list-voices", action="store_true",
                        help="列出可用语音后退出")
    args = parser.parse_args()

    # 仅列出语音
    if args.list_voices:
        asyncio.run(list_voices())
        return

    print(f"语音: {args.voice}  速率:{args.rate}  音量:{args.volume}  音调:{args.pitch}")
    print(f"文本: {args.text}")

    try:
        asyncio.run(synthesize(args.text, args.voice, args.rate,
                               args.volume, args.pitch, args.output))
    except Exception as e:
        print(f"合成失败: {e}")
        print("请检查网络是否可访问微软 TTS 服务")
        sys.exit(1)

    print(f"已保存: {args.output}")

    # 可选：调系统默认播放器播放
    if args.play:
        if sys.platform == "win32":
            os.startfile(args.output)
        elif sys.platform == "darwin":
            os.system(f'open "{args.output}"')
        else:
            os.system(f'xdg-open "{args.output}"')


if __name__ == "__main__":
    main()
