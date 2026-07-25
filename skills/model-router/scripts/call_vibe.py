#!/usr/bin/env python3
"""
VibeThinker-3B 通用调用函数
用法:
  from call_vibe import call_vibe
  result = call_vibe("你好", system="中文回复", temp=0.1)

  # 命令行模式（供 cron no_agent=true 使用）
  python3 call_vibe.py "提示词" [温度]

端点: http://host.docker.internal:11434/api/generate
"""

import urllib.request, json, sys, os

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434")
MODEL = "VibeThinker-3B:latest"
TIMEOUT = 15


def call_vibe(prompt, system="", max_tokens=512, temp=0.1):
    """调用 VibeThinker-3B 并返回响应文本。

    Args:
        prompt: 输入提示
        system: 系统指令（默认：简洁中文输出，只输出结果）
        max_tokens: 最大生成token数
        temp: 温度（routine任务用0.1，分类任务用0.0）
    Returns:
        str: 模型响应，去除前后空白
    Raises:
        urllib.error.URLError: 网络不可达
        json.JSONDecodeError: 响应格式异常
    """
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system or "你是Hermes子Agent，中文回复，只输出结果不输出思考过程",
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temp,
            "stop": ["\n\n\n"]
        }
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())["response"].strip()


def health_check():
    """健康检查 — 返回 (连通: bool, 详情: str)"""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/tags",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            found = [m for m in models if "vibethinker" in m.lower() or "3b" in m.lower()]
            if found:
                return True, f"✅ VibeThinker-3B 就绪 (可用模型: {', '.join(found)})"
            else:
                return True, f"✅ Ollama 在线，但未找到 VibeThinker-3B (可用: {', '.join(models)})"
    except Exception as e:
        return False, f"❌ 不通: {e}"


if __name__ == "__main__":
    # 命令行模式
    if len(sys.argv) >= 2:
        prompt = sys.argv[1]
        temp = float(sys.argv[2]) if len(sys.argv) >= 3 else 0.1
        result = call_vibe(prompt, temp=temp)
        print(result)
    else:
        # 无参数 → 健康检查
        ok, msg = health_check()
        print(msg)
