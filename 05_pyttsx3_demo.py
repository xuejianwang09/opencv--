import argparse
import pyttsx3


def main():
    parser = argparse.ArgumentParser(description="pyttsx3 文本转语音 (TTS) demo")
    parser.add_argument("--text", type=str,
                        default="你好，这是一个文本转语音的演示。",
                        help="要朗读的文本")
    parser.add_argument("--rate", type=int, default=180,
                        help="语速（字/分钟），默认 180")
    parser.add_argument("--volume", type=float, default=1.0,
                        help="音量 0.0-1.0，默认 1.0")
    parser.add_argument("--voice", type=int, default=None,
                        help="语音索引，见 --list 输出，默认自动选择")
    parser.add_argument("--save", type=str, default=None,
                        help="保存为 wav 文件（需引擎支持，Windows SAPI5 支持）")
    parser.add_argument("--list", action="store_true",
                        help="列出系统可用语音后退出")
    args = parser.parse_args()

    # 初始化引擎（Windows 走 SAPI5，macOS 走 NSSpeechSynthesizer，Linux 走 espeak）
    engine = pyttsx3.init()

    # 获取可用语音
    voices = engine.getProperty("voices")

    if args.list:
        print(f"共 {len(voices)} 个语音:")
        for i, v in enumerate(voices):
            langs = ""
            try:
                langs = ",".join(v.languages) if v.languages else ""
            except Exception:
                pass
            print(f"[{i}] id={v.id}")
            print(f"      name={v.name}  gender={getattr(v, 'gender', '?')}  lang={langs}")
        engine.stop()
        return

    # 设置语速、音量
    engine.setProperty("rate", args.rate)
    engine.setProperty("volume", max(0.0, min(1.0, args.volume)))

    # 选择语音
    if args.voice is not None and 0 <= args.voice < len(voices):
        engine.setProperty("voice", voices[args.voice].id)
        print(f"使用语音[{args.voice}]: {voices[args.voice].name}")
    else:
        print(f"使用默认语音: {voices[0].name if voices else '?'}")

    print(f"朗读: {args.text}  (rate={args.rate}, volume={args.volume})")

    if args.save:
        # 保存到文件
        engine.save_to_file(args.text, args.save)
        engine.runAndWait()
        print(f"已保存: {args.save}")
    else:
        engine.say(args.text)
        engine.runAndWait()
        print("朗读结束")

    engine.stop()


if __name__ == "__main__":
    main()
