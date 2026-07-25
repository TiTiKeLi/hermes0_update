#!/usr/bin/env python3
"""
研究编排器（Research Harness Orchestrator）
当你需要为某个需求搜索 GitHub + arXiv 依据时，通过 delegate_task 调用此流程

用法: python3 research_orchestrator.py <topic> <requirement> [depth=1]
"""
import json, sys, os, time, subprocess, traceback
from datetime import datetime

TOPICS_DIR = "/opt/data/research/topics"
SOURCES_DIR = "/opt/data/research/sources"

def ensure_dirs():
    for d in [TOPICS_DIR, SOURCES_DIR]:
        os.makedirs(d, exist_ok=True)

def load_topic_state(topic_slug):
    path = f"{TOPICS_DIR}/{topic_slug}/state.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"topic": "", "requirement": "", "created": "", "iterations": [], "depth": 0}

def save_topic_state(topic_slug, state):
    path = f"{TOPICS_DIR}/{topic_slug}/state.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def log_finding(topic_slug, finding):
    dir_path = f"{TOPICS_DIR}/{topic_slug}/findings"
    os.makedirs(dir_path, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    path = f"{dir_path}/iteration-{ts}.md"
    with open(path, 'w') as f:
        f.write(finding)
    return path

def check_network():
    import socket
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect(('8.8.8.8', 53))
        s.close()
        return True
    except:
        s.close()
        return False

def run_search(query, source_type="github"):
    """Run a search and return parsed results"""
    script = f"/opt/data/scripts/search_{source_type}.py"
    try:
        result = subprocess.run(
            ["python3", script, query, "5"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode == 0:
            # Parse only the JSON part (before the "saved to" line)
            lines = result.stdout.strip().split('\n')
            json_lines = []
            for line in lines:
                if line.startswith('🗂️'):
                    break
                json_lines.append(line)
            parsed = json.loads('\n'.join(json_lines)) if json_lines else []
            return parsed
        else:
            return {"error": result.stderr[:200]}
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    except Exception as e:
        return {"error": str(e)}

def harness(topic, requirement, depth=1):
    ensure_dirs()
    topic_slug = topic.lower().replace(' ', '-').replace('/', '-')[:40]
    state = load_topic_state(topic_slug)
    
    # First run: init state
    if not state["created"]:
        state["topic"] = topic
        state["requirement"] = requirement
        state["created"] = datetime.now().isoformat()
        state["depth"] = depth
        save_topic_state(topic_slug, state)
    
    # Check network
    if not check_network():
        msg = f"❌ 网络不可用。harness 等待网络连接。\n需求: {requirement}\n主题: {topic}"
        with open(f"{TOPICS_DIR}/{topic_slug}/pending.txt", 'w') as f:
            f.write(msg)
        return {"status": "waiting_for_network", "message": msg}
    
    # Build search queries from requirement
    queries = [topic, requirement]
    if state["depth"] > 1 and state["iterations"]:
        # Deeper: use previous findings to refine
        last = state["iterations"][-1]
        if last.get("keywords"):
            queries.extend(last["keywords"])
    
    all_projects = []
    all_papers = []
    
    for query in queries[:3]:  # Max 3 queries per run
        # GitHub
        gh = run_search(query, "github")
        if isinstance(gh, list):
            all_projects.extend(gh)
        
        # arXiv
        arx = run_search(query, "arxiv")
        if isinstance(arx, list):
            all_papers.extend(arx)
    
    # Deduplicate
    seen_titles = set()
    unique_projects = []
    for p in all_projects:
        if p.get('name') not in seen_titles:
            seen_titles.add(p.get('name'))
            unique_projects.append(p)
    
    seen_arxiv = set()
    unique_papers = []
    for p in all_papers:
        if p.get('title') not in seen_arxiv:
            seen_arxiv.add(p.get('title'))
            unique_papers.append(p)
    
    # Build finding report
    finding = f"""## Research Iteration #{len(state['iterations'])+1}
**Topic**: {topic}
**Requirement**: {requirement}
**When**: {datetime.now().isoformat()}
**Depth**: {state['depth']}

### GitHub Projects
"""
    if unique_projects:
        for p in unique_projects[:5]:
            finding += f"- ⭐{p['stars']} {p['name']} — {p.get('description', '')[:100]}\n"
    else:
        finding += "(无结果)\n"
    
    finding += f"\n### arXiv Papers\n"
    if unique_papers:
        for p in unique_papers[:5]:
            finding += f"- {p['title']} ({p.get('published', '')[:10]})\n  {p.get('summary', '')[:150]}\n"
    else:
        finding += "(无结果)\n"
    
    finding += f"\n### Next Iteration Keywords\n"
    keywords = [q for q in queries]
    for p in unique_projects[:3]:
        for t in p.get('topics', [])[:3]:
            if t not in keywords:
                keywords.append(t)
    finding += ", ".join(keywords[:8])
    
    # Save
    path = log_finding(topic_slug, finding)
    
    # Update state
    state["iterations"].append({
        "num": len(state["iterations"]) + 1,
        "when": datetime.now().isoformat(),
        "projects_found": len(unique_projects),
        "papers_found": len(unique_papers),
        "keywords": keywords[:8],
        "finding_path": path
    })
    state["depth"] += 1
    save_topic_state(topic_slug, state)
    
    return {
        "status": "ok",
        "projects": len(unique_projects),
        "papers": len(unique_papers),
        "finding_path": path,
        "state_path": f"{TOPICS_DIR}/{topic_slug}/state.json",
        "keywords": keywords[:8]
    }

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python3 research_orchestrator.py <topic> <requirement> [depth]')
        sys.exit(1)
    topic = sys.argv[1]
    requirement = sys.argv[2]
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    result = harness(topic, requirement, depth)
    print(json.dumps(result, ensure_ascii=False, indent=2))
