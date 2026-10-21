import os
import sys
import argparse
import whisper


def main():
    parser = argparse.ArgumentParser(description="使用 Whisper 对 wav 音频做语音识别")
    parser.add_argument("--audio", type=str, default="output.wav",
                        help="待识别的音频文件，默认 output.wav")
    parser.add_argument("--model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小，默认 base")
    parser.add_argument("--language", type=str, default=None,
                        help="强制语言代码（如 zh / en），默认 None 自动检测")
    parser.add_argument("--txt", type=str, default=None,
                        help="同时把结果写入该文本文件，默认 <audio>.txt")
    args = parser.parse_args()

    # 输入文件校验
    if not os.path.isfile(args.audio):
        print(f"找不到音频文件: {args.audio}")
        sys.exit(1)

    # 加载模型（首次会自动下载，需联网，约 base ~145MB）
    print(f"加载模型: {args.model} ...")
    model = whisper.load_model(args.model)

    # 识别
    print(f"开始识别: {args.audio} (language={args.language})")
    result = model.transcribe(args.audio, language=args.language, fp16=False)

    text = result.get("text", "").strip()
    detected = result.get("language", "?")

    print("\n========== 识别结果 ==========")
    print(f"检测语言: {detected}")
    print(f"文本: {text}")
    print("==============================\n")

    # 写文本文件
    out_txt = args.txt or (os.path.splitext(args.audio)[0] + ".txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"已保存文本: {out_txt}")


if __name__ == "__main__":
    main()
