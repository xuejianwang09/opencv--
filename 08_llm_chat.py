import os
import sys
import json
import requests

# ===== 请在此处填写你的 LLM 服务信息（下面三个值我留了占位，你填真实值即可）=====
# 采用 OpenAI 兼容接口格式，兼容绝大多数主流服务：
#   DeepSeek:    https://api.deepseek.com/v1   model: deepseek-chat
#   智谱 GLM:    https://open.bigmodel.cn/api/paas/v4  model: glm-4
#   Moonshot:    https://api.moonshot.cn/v1    model: moonshot-v1-8k
#   OpenAI:      https://api.openai.com/v1     model: gpt-4o-mini
#   本地 Ollama: http://localhost:11434/v1     model: qwen2.5
BASE_URL = "https://ws-rcodnqgshc6earzw.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
API_KEY  = "sk-ws-H.EMMPPML.Nfdj.MEUCIQDsRDXH2xypr-GqBcaIB_bY0IyPi2PdaGDiacv8UyYqZgIgLfzBV_z5utppgJF9OL5MUlnEkzcXNo1qDEZq-V2s_cE"
MODEL    = "qwen3.7-max"

# 系统提示词：决定助手人设与回答风格
SYSTEM_PROMPT = "你是一个乐于助人的助手，请用简洁的中文回答用户问题。"


def chat_once(messages, base, key, model):
    """调用 chat/completions，流式打印并返回完整回复文本"""
    url = f"{base.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,          # 流式输出，逐字打印体验更好
    }

    try:
        resp = requests.post(url, headers=headers, json=payload,
                             stream=True, timeout=120)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"\n[请求失败] {e}")
        try:
            print("服务端返回:", resp.text[:500])
        except Exception:
            pass
        return None

    full = ""
    # 解析 SSE（Server-Sent Events）流式响应
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta", {}).get("content", "")
        if delta:
            print(delta, end="", flush=True)
            full += delta
    print()  # 回车换行
    return full


def main():
    # 支持用环境变量覆盖，方便不改源码即可切换 key/服务
    base  = os.environ.get("LLM_BASE_URL") or BASE_URL
    key   = os.environ.get("LLM_API_KEY")  or API_KEY
    model = os.environ.get("LLM_MODEL")     or MODEL

    if "请填写" in base or "请填写" in key or "请填写" in model:
        print("请先在 08_llm_chat.py 顶部填写 BASE_URL / API_KEY / MODEL")
        print("或设置环境变量 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL")
        sys.exit(1)

    print(f"已连接: {base}  模型: {model}")
    print("输入问题开始对话 | q 退出 | clear 清空历史\n")

    # 多轮对话上下文：第一条放系统提示词
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user.lower() in ("q", "quit", "exit"):
            break
        if user.lower() == "clear":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("已清空历史\n")
            continue

        messages.append({"role": "user", "content": user})

        print("助手: ", end="", flush=True)
        reply = chat_once(messages, base, key, model)

        if reply is None:
            # 请求失败，回滚刚加入的用户消息，避免污染上下文
            messages.pop()
            continue
        if not reply.strip():
            print("(空回复)")
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
