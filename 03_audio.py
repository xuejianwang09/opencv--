import wave
import argparse
import time
import msvcrt
import pyaudio

# ===== 命令行参数：仅保留输出文件名（时长改为按键控制） =====
parser = argparse.ArgumentParser(description="Pyaudio 录音，16kHz，R 开始 / S 停止，保存为 wav")
parser.add_argument("--output", type=str, default="output.wav",
                    help="输出文件名，默认 output.wav")
args = parser.parse_args()

# ===== 录音参数 =====
RATE     = 16000              # 采样率 16kHz
CHANNELS = 1                  # 单声道（语音场景常用）
FORMAT   = pyaudio.paInt16    # 16-bit
CHUNK    = 1024               # 每次读取的帧数

# 运行时状态
p = None            # PyAudio 实例
stream = None       # 输入流
frames = []         # 采集到的数据块
recording = False   # 是否在录音


def start_recording():
    """按 R：打开设备并开始采集"""
    global p, stream, frames, recording
    p = pyaudio.PyAudio()
    try:
        dev = p.get_default_input_device_info()
        print(f"输入设备: {dev['name']}")
    except Exception:
        print("未检测到默认输入设备")
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    frames = []
    recording = True
    print(">>> 录音中 ... 按 S 停止")


def stop_recording():
    """按 S：停止采集并写文件"""
    global stream, p, recording
    stream.stop_stream()
    stream.close()
    # 提前算好 sampwidth，避免 terminate 后实例状态不确定
    sampwidth = p.get_sample_size(FORMAT)
    p.terminate()
    recording = False

    print(f"录音结束，{len(frames)} chunks，正在写入 {args.output} ...")
    with wave.open(args.output, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(sampwidth)
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    print(f"已保存: {args.output}")


print("按 R 开始录音 | S 停止并保存 | Q 退出")

while True:
    # 非阻塞读取按键（Windows 内置 msvcrt，无需额外依赖）
    if msvcrt.kbhit():
        key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
        if key == "r" and not recording:
            start_recording()
        elif key == "s" and recording:
            stop_recording()
        elif key == "q":
            if recording:           # 退出前若有未保存录音，先保存
                stop_recording()
            print("退出")
            break

    # 录音中持续从设备拉数据，不阻塞键盘监听
    if recording:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
    else:
        time.sleep(0.01)            # 空闲时让出 CPU
