# MEMORY
## IDENTITY
- host:Windows11+WSL2(Ubuntu)+DockerDesktop
- ollama:host.docker.internal:11434
- model:VibeThinker-3B:latest(local,nokey)
- interface:WeChat(iLinkgateway)
- lang:zh-CN
→ 📦 Archive: /opt/data/memories/archive/2026-07-25.md

## FACTS
id:1 [host]     Windows11+WSL2+DockerDesktop
- 用户的测试验证码是 ZebraX_2026_Verify (id:13 [test-verify-code] [test])
- LLM 通过 host.docker.internal:11434 访问宿主 Ollama (id:4 [ollama])
- 默认模型是VibeThinker-3B:latest 本地模型 (id:5 [model])
- 用户操作系统是Windows 11 + WSL2 (Ubuntu) + Docker Desktop (id:2 [host])
- 用户要求深度需求思维模式：
1. 每次询问要洞察本质需求，不只回答问题表面
2. 识别用户未发现的技术/实现阻塞点
3. 每个实现视为正式项目
4. 重复需求 → 生成SKILL固化
5. 反复问题 → 提炼关键词... (id:19 [deep-need-analysis] [thinking,deep_need,skill_gen])
- 用户要求记忆反馈绑定 memory_write_occurred 参数，仅本会话有写入时激活，无写入时完全沉默 (id:21 [memory-confirmation-feedback] [feedback_protocol])
- 记忆确认反馈协议 v4 已固定为基线版本，格式：✅ id:N [tag] 摘要 ~ id:M [tag] (理由)，多条用 · 分隔。绑定 memory_write_occurred 参数，仅写入时激活 (id:22 [memory-confirmation-feedback] [feedback_protocol,v4])
- 休眠恢复由宿主机 connection_persister.py 守护 (id:8 [resilience])
§
技能体系体检 2026-07-25: 21技能在盘，手动加载，无关键词触发，无hooks系统。caveman-reply已加 frontmatter + 标记为3B only。SKILL_REGISTRY 已补登 caveman-compress
