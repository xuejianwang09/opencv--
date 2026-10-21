"""
12_voice_mcp_assistant.py
带 MCP 工具调用的语音助手（标准 MCP Host 模式）

流程：录音(R) → Whisper ASR → LLM(可调 MCP 工具) → edge-TTS 播放
  - LLM 通过 function calling 自行决定是否调用 10_mcp_add_server.py 暴露的工具
  - 例如用户问"2+3 等于多少"，LLM 会调 add(2,3) 拿到 5，再回答"2+3=5"并播放

============================================================
  运行（mujoco 环境）
============================================================
    python 12_voice_mcp_assistant.py
    python 12_voice_mcp_assistant.py --asr-model base --language zh

  操作：R 录音 / S 停止录音 / Q 退出

============================================================
  设计要点
============================================================
  1) 复用 08_llm_chat.py 的 BASE_URL/API_KEY/MODEL/SYSTEM_PROMPT（importlib 加载）
     但不复用 chat_once（它不支持 tools/tool_calls），LLM 调用在本文件重写
  2) 复用 09_voice_assistant.py 的 record_once/asr_once/tts_play/get_asr_model
  3) MCP 用 stdio：本脚本拉起 10 作为子进程，会话期间保活
  4) LLM 用非流式 + tools 参数：完整拿到 message.tool_calls 后调 MCP 工具，
     把结果作为 role=tool 喂回 LLM，循环直到 LLM 给出最终文本回答
  5) async/同步混合：录音/ASR/LLM/TTS 都是同步阻塞，用 asyncio.to_thread 包到
     工作线程，主循环在 await 处挂起，async with 不退出 → MCP 子进程保活
============================================================
"""
import os
import sys
import json
import argparse
import asyncio
import importlib.util
import msvcrt

import requests
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(DIR, "10_mcp_add_server.py")


def _load_mod(filename, mod_name):
    """数字开头的文件无法用 import 导入，用 importlib 按路径加载。"""
    path = os.path.join(DIR, filename)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 复用 08 的配置（BASE_URL/API_KEY/MODEL/SYSTEM_PROMPT），不复用其 chat_once
llm = _load_mod("08_llm_chat.py", "llm_chat_mod")
# 复用 09 的录音/ASR/TTS 函数
voice = _load_mod("09_voice_assistant.py", "voice_mod")


def mcp_tools_to_openai(tools_result):
    """把 MCP list_tools 结果转成 OpenAI tools 参数格式。通用，不硬编码 add。"""
    openai_tools = []
    for t in tools_result.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                # MCP 的 input_schema 已是标准 JSON Schema，直接作 parameters
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        })
    return openai_tools


def _llm_request_sync(url, headers, payload):
    """同步发 chat/completions（非流式），返回 JSON dict 或 None。"""
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"\n[LLM 请求失败] {e}")
        try:
            print("服务端返回:", resp.text[:500])
        except Exception:
            pass
        return None


def _probe_tools_support(base, key, model, openai_tools):
    """启动期探测 LLM 是否支持 function calling。返回 True/False。"""
    if not openai_tools:
        return False
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "2+3等于多少？请调用 add 工具。"}],
        "tools": openai_tools,
        "tool_choice": "auto",
        "stream": False,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            msg = resp.json().get("choices", [{}])[0].get("message", {})
            return msg.get("tool_calls") is not None
        body = resp.text.lower()
        return not ("tool" in body or "function" in body)
    except Exception as e:
        print(f"[探测失败] {e}")
        return False


async def chat_with_tools(session, openai_tools, messages, base, key, model, use_tools=True):
    """
    带 function calling 的多轮对话。返回最终文本回答，失败返回 None。
    非流式：完整拿到 message.tool_calls 后再循环调用 MCP 工具。
    """
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "stream": False}
    if use_tools and openai_tools:
        payload["tools"] = openai_tools
        payload["tool_choice"] = "auto"

    data = await asyncio.to_thread(_llm_request_sync, url, headers, payload)
    if data is None:
        return None

    msg = data["choices"][0]["message"]

    # 工具调用循环（最多 8 轮防死循环）
    for _ in range(8):
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            break  # 无工具调用，content 即最终回答

        # 1) 把 assistant 的 tool_calls 消息原样追加（tool_call_id 必须保留以匹配）
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })

        # 2) 逐个执行 tool_call
        for tc in tool_calls:
            tc_id = tc["id"]
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError as e:
                fn_args = {}
                print(f"  [参数解析失败 {fn_name}] {e}")

            print(f"  [调用工具] {fn_name}({fn_args})")
            try:
                result = await session.call_tool(fn_name, fn_args)
            except Exception as e:
                tool_text = f"[MCP 调用异常: {e}]"
            else:
                if result.is_error:
                    tool_text = "[工具执行报错]"
                else:
                    texts = [getattr(b, "text", None) for b in result.content]
                    tool_text = "\n".join(t for t in texts if t) or "(空结果)"
            print(f"  [工具返回] {tool_text}")

            messages.append({"role": "tool", "tool_call_id": tc_id, "content": tool_text})

        # 3) 把工具结果喂回 LLM，拿下一轮 message
        payload["messages"] = messages
        data = await asyncio.to_thread(_llm_request_sync, url, headers, payload)
        if data is None:
            return None
        msg = data["choices"][0]["message"]

    reply = (msg.get("content") or "").strip()
    messages.append({"role": "assistant", "content": reply})
    return reply


async def main_async(args):
    # 1) 预加载 Whisper（启动期一次性，避免运行期卡顿）
    voice.get_asr_model(args.asr_model)

    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT], env=None)
    wav_path = os.path.join(DIR, "output.wav")
    mp3_path = os.path.join(DIR, "reply.mp3")

    # 2) 拉起 MCP server 子进程 + 建立 session（贯穿整个会话，期间子进程保活）
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"已连接 MCP Server: {init.server_info.name} (proto {init.protocol_version})")
            tools_result = await session.list_tools()
            openai_tools = mcp_tools_to_openai(tools_result)
            print(f"已加载 {len(openai_tools)} 个工具: "
                  f"{[t['function']['name'] for t in openai_tools]}")

            # 3) 探测 LLM 是否支持 function calling
            llm_supports_tools = await asyncio.to_thread(
                _probe_tools_support, llm.BASE_URL, llm.API_KEY, llm.MODEL, openai_tools)
            if llm_supports_tools:
                print("LLM 支持 function calling，将按需调用 MCP 工具。")
            else:
                print("[警告] LLM 似乎不支持 function calling，退化为纯文本对话（不调用工具）。")

            # 4) 对话上下文
            messages = [
                {"role": "system", "content": llm.SYSTEM_PROMPT},
                {"role": "system", "content":
                    "你可以调用提供的工具完成计算等任务。需要时调用工具，"
                    "拿到结果后用简洁中文回答用户。"},
            ]

            print("\n==== 语音 MCP 助手就绪 ====")
            print("按 R 录音 -> S 停止 -> 自动识别+LLM(可调工具)+TTS播放")
            print("按 Q 退出\n")

            # 5) 主轮询循环（async + msvcrt 非阻塞，让出循环保活 session）
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    if key == "q":
                        print("退出")
                        break
                    if key == "r":
                        # 录音（阻塞，放线程池，主循环挂起、session 保活）
                        await asyncio.to_thread(voice.record_once, wav_path)

                        # ASR
                        print("识别中...")
                        user_text = await asyncio.to_thread(
                            voice.asr_once, wav_path, args.asr_model, args.language)
                        print(f"识别结果: {user_text}")
                        if not user_text:
                            print("(未识别到内容，跳过本轮)\n")
                            continue

                        # LLM + 工具调用
                        messages.append({"role": "user", "content": user_text})
                        print("\n助手: ", end="", flush=True)
                        reply = await chat_with_tools(
                            session, openai_tools, messages,
                            llm.BASE_URL, llm.API_KEY, llm.MODEL,
                            use_tools=llm_supports_tools)

                        if reply is None:
                            messages.pop()  # 回滚 user 消息，避免污染上下文
                            continue
                        if not reply.strip():
                            print("(空回复)")
                            continue
                        print(reply)

                        # TTS 播放（阻塞，放线程池；ffplay 期间 session 空闲保活）
                        print("\n[合成语音播放中...]")
                        await asyncio.to_thread(
                            voice.tts_play, reply, args.voice, args.rate, mp3_path, True)
                        print("[本轮结束] 按 R 下一轮\n")
                else:
                    await asyncio.sleep(0.02)  # 让出循环，避免忙转、保活 session


def main():
    parser = argparse.ArgumentParser(description="带 MCP 工具调用的语音助手")
    parser.add_argument("--asr-model", type=str, default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper 模型大小，默认 base")
    parser.add_argument("--language", type=str, default=None,
                        help="强制识别语言代码，如 zh")
    parser.add_argument("--voice", type=str, default="zh-CN-XiaoxiaoNeural",
                        help="TTS 语音名")
    parser.add_argument("--rate", type=str, default="+0%",
                        help="TTS 语速，如 +10%%")
    args = parser.parse_args()

    if not os.path.isfile(SERVER_SCRIPT):
        print(f"找不到 MCP server 脚本: {SERVER_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n已中断")


if __name__ == "__main__":
    main()
