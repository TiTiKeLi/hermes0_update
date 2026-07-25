#!/usr/bin/env python3
"""
call_vibe.py — 调本地 VibeThinker-3B 子 Agent
用法:
  python3 call_vibe.py <prompt> [system_prompt]
  python3 call_vibe.py "分类这些日志" "你是日志分析助手"

环境: OLLAMA_HOST (默认 http://host.docker.internal:11434)
"""
import json, sys, os, urllib.request, time

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
MODEL = "VibeThinker-3B:latest"

class VibeAgent:
    def __init__(self, system=""):
        self.system = system

    def ask(self, prompt, temperature=0.1, max_tokens=512):
        """调 3B 模型，返回响应文本"""
        payload = json.dumps({
            "model": MODEL,
            "prompt": prompt,
            "system": self.system or "你擅长分类、提取、摘要、格式化。只输出结果，不解释。",
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }).encode()

        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        start = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        elapsed = time.time() - start

        return {
            "response": result.get("response", ""),
            "elapsed_s": round(elapsed, 2),
            "tokens": result.get("eval_count", 0)
        }

    # ---- 工作模板 ----

    def classify_logs(self, raw_logs: str):
        """工作1：日志分类"""
        prompt = f"""将以下日志按严重级别分类，输出格式：
致命: N
错误: N
警告: N
信息: N

日志内容：
{raw_logs[-2000:]}"""
        return self.ask(prompt, temperature=0.1)

    def compress_memory(self, content: str, target_chars: int = 1800):
        """工作2：压缩MEMORY.md"""
        prompt = f"""压缩以下内容到 {target_chars} 字符以内。
保留所有实体名、数字、关系、ID。
去掉自然语言水词（"是...的"、"可以..."、"用于..."，"需要"可省略）。
只输出压缩结果，不解释。

原文：
{content}"""
        return self.ask(prompt, temperature=0.1, max_tokens=600)

    def classify_message(self, message: str):
        """工作3：消息预分类"""
        prompt = f"""判断用户消息类型，只输出分类名：
- chat: 闲聊/问候/情绪表达
- task: 明确需求/命令
- research_request: 需要搜索外部资料
- question: 知识性问题
- feedback: 对之前结果的评价

消息: {message}
分类:"""
        return self.ask(prompt, temperature=0.05, max_tokens=20)

    def health_summary(self, context: str):
        """工作4：状态摘要"""
        prompt = f"""基于以下系统状态，生成一行摘要（格式：✅/❌ 组件 | 关键数字 | 异常）。
只输出摘要，不解释。

数据：
{context[-1500:]}"""
        return self.ask(prompt, temperature=0.1, max_tokens=100)

    def compress_session(self, history: str):
        """工作5：会话压缩（迭代上下文）"""
        prompt = f"""将以下对话历史压缩为结构化摘要：

━━━ 已解决 ━━━
（列出已解决的问题/决定）

━━━ 待办 ━━━
（列出未完成的任务）

━━━ 关键决定 ━━━
（列出重要的架构/设计决策）

要求：保留所有实体名、ID、数字。不解释。

对话：
{history[-3000:]}"""
        return self.ask(prompt, temperature=0.1, max_tokens=400)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python3 call_vibe.py <prompt> [system]")
        sys.exit(1)

    prompt = args[0]
    system = args[1] if len(args) > 1 else ""
    agent = VibeAgent(system=system)
    result = agent.ask(prompt)
    print(f"[{result['elapsed_s']:.1f}s | {result['tokens']} tokens]")
    print(result["response"])
