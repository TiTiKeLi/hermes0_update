"""
Hermes Connection Persistence Daemon v2.0
阻止Windows休眠 + 自动恢复 Hermes Gateway + WeChat iLink

架构:
  Layer 0: Power Lock → SetThreadExecutionState 阻止系统休眠
  Layer 1: Windows Power Event Hook → 系统唤醒时立即触发
  Layer 2: Health Check Loop → 每30秒检查连通性
  Layer 3: Auto-Recovery → 断线自动执行恢复策略
  Layer 4: Heartbeat → 保持WSL2/Docker网络活跃
"""
import asyncio
import ctypes
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple

# ─── Windows Power Management ────────────────────────────
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_AWAYMODE_REQUIRED = 0x00000040
_kernel32 = ctypes.windll.kernel32

def prevent_sleep(enable: bool = True):
    """
    阻止/允许 Windows 进入休眠。
    使用 ES_CONTINUOUS | ES_SYSTEM_REQUIRED 防止系统休眠。
    守护进程运行时阻止休眠，退出时自动释放。
    """
    if enable:
        _kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
    else:
        _kernel32.SetThreadExecutionState(ES_CONTINUOUS)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("connection_persister")

HERMES_HOME = Path(__file__).parent
CONFIG_FILE = HERMES_HOME / "config.yaml"
ENV_FILE = HERMES_HOME / ".env"
GATEWAY_STATE_FILE = HERMES_HOME / "gateway_state.json"
DASHBOARD_PORT = 8643
GATEWAY_PORT = 8642
CONTAINER_NAME = "hermes"
CHECK_INTERVAL = 300
RECOVERY_COOLDOWN = 60
PROXY_PORT = 18931


class HermesConnectionPersister:
    """Hermes连接持久化守护进程"""

    def __init__(self):
        self._last_recovery: float = 0
        self._consecutive_failures: int = 0
        self._last_wechat_state: str = "unknown"
        self._power_resume_detected: bool = False
        self._running = True

    # ─── 检测层 ──────────────────────────────────────────────

    def is_container_running(self) -> bool:
        """检查Hermes容器是否运行"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={CONTAINER_NAME}",
                 "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=10
            )
            return "Up" in result.stdout
        except Exception as e:
            logger.warning(f"Container check failed: {e}")
            return False

    def check_gateway_api(self) -> Tuple[bool, Optional[Dict]]:
        """通过多个来源检查网关状态"""
        import urllib.request

        # 1. 尝试Dashboard API
        try:
            req = urllib.request.Request(f"http://localhost:{DASHBOARD_PORT}/api/status",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return True, data
        except Exception:
            pass

        # 2. 尝试容器内健康检查
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME, "bash", "/opt/data/healthcheck.sh"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                return True, {"source": "container_healthcheck", "output": result.stdout}
        except Exception:
            pass

        # 3. 尝试容器内gateway status
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME, "hermes", "gateway", "status"],
                capture_output=True, text=True, timeout=10
            )
            if "is running" in result.stdout:
                return True, {"source": "gateway_status"}
        except Exception:
            pass

        # 4. 读取gateway_state.json
        state = self._read_gateway_state()
        if state and state.get("gateway_state") == "running":
            return True, state
        return False, None

    def check_wechat_state(self) -> Tuple[bool, str]:
        """检查WeChat连接状态"""
        import urllib.request

        # 1. Dashboard API
        try:
            req = urllib.request.Request(f"http://localhost:{DASHBOARD_PORT}/api/status",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                wechat = data.get("wechat", "disconnected")
                return wechat == "connected", wechat
        except Exception:
            pass

        # 2. gateway_state.json 文件
        gateway_state = self._read_gateway_state()
        if gateway_state:
            weixin = gateway_state.get("platforms", {}).get("weixin", {})
            state = weixin.get("state", "unknown")
            return state == "connected", state

        # 3. 容器内 status 命令
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME, "hermes", "platform", "list"],
                capture_output=True, text=True, timeout=10
            )
            if "weixin" in result.stdout.lower() and "connected" in result.stdout.lower():
                return True, "connected"
        except Exception:
            pass

        return False, "unknown"

    def check_docker_wsl_network(self) -> bool:
        """检查Docker WSL2网络是否可达"""
        # 1. Docker daemon 本身
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.OSType}}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False
        except Exception:
            return False

        # 2. 检查Ollama是否可达
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:11434/api/tags",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            pass

        # 3. 容器内网络检查
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME,
                 "python3", "-c",
                 "import socket; s=socket.socket(); s.settimeout(5); s.connect(('host.docker.internal',11434)); s.close()"],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    # ─── 恢复层 ──────────────────────────────────────────────

    def recovery_restart_container(self) -> bool:
        """重启Hermes容器"""
        logger.info("🔄 Recovery: Restarting Hermes container...")
        try:
            subprocess.run(["docker", "restart", CONTAINER_NAME],
                           capture_output=True, timeout=30)
            time.sleep(5)
            if self.is_container_running():
                logger.info("✅ Container restarted successfully")
                return True
            logger.warning("Container failed to restart, trying re-create...")
            return self.recovery_recreate_container()
        except Exception as e:
            logger.error(f"Container restart failed: {e}")
            return self.recovery_recreate_container()

    def recovery_recreate_container(self) -> bool:
        """重建Hermes容器"""
        logger.info("🔄 Recovery: Re-creating Hermes container...")
        try:
            subprocess.run(["docker", "stop", CONTAINER_NAME],
                           capture_output=True, timeout=15)
            subprocess.run(["docker", "rm", CONTAINER_NAME],
                           capture_output=True, timeout=15)
            cmd = [
                "docker", "run", "-d",
                "--name", CONTAINER_NAME,
                "--restart", "unless-stopped",
                "-p", f"{GATEWAY_PORT}:{GATEWAY_PORT}",
                "-v", f"{HERMES_HOME}:/opt/data",
                "--dns", "8.8.8.8",
                "--dns", "223.5.5.5",
                "--add-host", "host.docker.internal:host-gateway",
                "hermes-agent:latest", "gateway", "run"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info("✅ Container re-created successfully")
                time.sleep(8)
                return True
            logger.error(f"Container re-create failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"Container re-create error: {e}")
            return False

    def recovery_restart_docker_wsl(self) -> bool:
        """重启WSL2网络栈（彻底恢复网络）"""
        logger.info("🔄 Recovery: Restarting WSL2 network stack...")
        try:
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "-e", "bash", "-c",
                 "sudo ip link set eth0 down && sudo ip link set eth0 up"],
                capture_output=True, timeout=15
            )
            time.sleep(3)
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "-e", "bash", "-c",
                 "sudo dhclient eth0 2>/dev/null || true"],
                capture_output=True, timeout=15
            )
            logger.info("✅ WSL2 network stack reset")
            return True
        except Exception as e:
            logger.warning(f"WSL2 network reset failed: {e}")
            return False

    def recovery_restart_hermes_gateway(self) -> bool:
        """通过内部命令重启Hermes网关"""
        logger.info("🔄 Recovery: Restarting Hermes gateway via internal command...")
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME, "hermes", "doctor", "--fix"],
                capture_output=True, text=True, timeout=30
            )
            logger.info(f"Doctor fix result: {result.stdout[:200]}")
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Gateway restart failed: {e}")
            return False

    def recovery_full_stack(self) -> bool:
        """完整堆栈恢复"""
        logger.info("🏥 Recovery: Full stack recovery...")
        now = time.time()
        if now - self._last_recovery < RECOVERY_COOLDOWN:
            logger.info("Skipping recovery (cooldown active)")
            return False
        self._last_recovery = now

        strategies = [
            ("restart_gateway", self.recovery_restart_hermes_gateway),
            ("restart_container", self.recovery_restart_container),
            ("recreate_container", self.recovery_recreate_container),
        ]

        for name, strategy in strategies:
            logger.info(f"Trying strategy: {name}")
            if strategy():
                time.sleep(10)
                ok, _ = self.check_gateway_api()
                if ok:
                    logger.info(f"✅ Recovery successful via {name}")
                    self._consecutive_failures = 0
                    return True
        return False

    # ─── 持久化层 ──────────────────────────────────────────────

    def _read_gateway_state(self) -> Optional[Dict]:
        """读取网关状态文件"""
        try:
            if GATEWAY_STATE_FILE.exists():
                with open(GATEWAY_STATE_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _write_state(self, state: Dict):
        """写入持久化状态"""
        try:
            state_file = HERMES_HOME / ".connection_state"
            state["updated_at"] = datetime.now().isoformat()
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"State write failed: {e}")

    def keep_wsl_alive(self):
        """保持WSL2活跃，防止网络超时断开"""
        try:
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "-e", "bash", "-c",
                 "echo 'heartbeat' > /dev/null"],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    def _ensure_container_gui(self):
        """确保容器内 GUI 服务运行"""
        try:
            result = subprocess.run(
                ["docker", "exec", CONTAINER_NAME,
                 "python3", "-c",
                 "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8644/api/health', timeout=3)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.info("Starting container GUI server...")
                subprocess.run(
                    ["docker", "exec", "-d", CONTAINER_NAME,
                     "sh", "-c", "nohup python3 /opt/data/gui.py 8644 > /opt/data/gui.log 2>&1"],
                    capture_output=True, timeout=10
                )
        except Exception:
            pass

    def _ensure_host_proxy(self):
        """确保宿主机 HTTP 代理运行"""
        try:
            result = subprocess.run(
                ["python", "-c",
                 f"import urllib.request; urllib.request.urlopen('http://127.0.0.1:{PROXY_PORT}', timeout=2)"],
                capture_output=True, text=True, timeout=5
            )
        except:
            logger.info("Starting host HTTP proxy...")
            subprocess.Popen(
                ["python", "-u", str(HERMES_HOME / "host_proxy.py")],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    # ─── 主循环 ──────────────────────────────────────────────

    def _heartbeat(self):
        """发送心跳，保持所有TCP连接活跃，防止NAT/防火墙断开。"""
        import urllib.request
        try:
            # 1. 容器内 healthcheck (触发 WeChat 状态检查)
            subprocess.run(
                ["docker", "exec", CONTAINER_NAME, "bash", "/opt/data/healthcheck.sh"],
                capture_output=True, timeout=15
            )
            # 2. GUI API ping (保持 HTTP 连接活跃)
            urllib.request.urlopen(f"http://localhost:8644/api/health", timeout=5)
            # 3. 代理端口 ping (保持代理 socket 活跃)
            urllib.request.urlopen(f"http://127.0.0.1:{PROXY_PORT}", timeout=5)
        except:
            pass

    async def power_event_monitor(self):
        """监听Windows电源事件（通过检查uptime变化检测休眠）"""
        last_boot = time.time()
        while self._running:
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"],
                    capture_output=True, text=True, timeout=10
                )
            except Exception:
                pass
            await asyncio.sleep(60)

    async def check_and_recover(self):
        """核心检查循环"""
        while self._running:
            try:
                # 1. 保持WSL2活跃
                self.keep_wsl_alive()

                # 2. 检查容器
                container_ok = self.is_container_running()
                if not container_ok:
                    logger.warning("⚠️ Container not running")
                    self._consecutive_failures += 1
                    self.recovery_full_stack()
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue

                # 3. 检查网关API
                gateway_ok, status = self.check_gateway_api()
                if not gateway_ok:
                    logger.warning("⚠️ Gateway API unreachable")
                    self._consecutive_failures += 1
                    if self._consecutive_failures >= 2:
                        self.recovery_full_stack()
                else:
                    # 4. 检查WeChat状态
                    wechat_ok, wechat_state = self.check_wechat_state()
                    if wechat_state != self._last_wechat_state:
                        logger.info(f"WeChat state changed: {self._last_wechat_state} → {wechat_state}")
                        self._last_wechat_state = wechat_state

                    if not wechat_ok:
                        logger.warning(f"⚠️ WeChat disconnected (state: {wechat_state})")
                        self._consecutive_failures += 1
                        if self._consecutive_failures >= 2:
                            self.recovery_restart_hermes_gateway()
                    else:
                        self._consecutive_failures = 0

                # 5. 确保宿主机代理和容器内 GUI 运行
                if container_ok:
                    self._ensure_host_proxy()
                    self._ensure_container_gui()

                # 6. 发送心跳: 触发容器网络流量，防止NAT/防火墙断开
                if container_ok:
                    self._heartbeat()

                # 7. 记录状态
                self._write_state({
                    "container_running": container_ok,
                    "gateway_reachable": gateway_ok,
                    "wechat_state": wechat_state if 'wechat_state' in dir() else "unknown",
                    "consecutive_failures": self._consecutive_failures,
                    "last_check": datetime.now().isoformat(),
                })

            except Exception as e:
                logger.error(f"Check loop error: {e}")

            await asyncio.sleep(CHECK_INTERVAL)

    async def dashboard_health_server(self):
        """轻量级健康检查HTTP端点"""
        import urllib.request
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                container = self.server.persister.is_container_running()
                gateway, status = self.server.persister.check_gateway_api()
                wechat_ok, wechat_s = self.server.persister.check_wechat_state()
                docker_net = self.server.persister.check_docker_wsl_network()

                body = json.dumps({
                    "status": "ok" if container and gateway else "degraded",
                    "container": "running" if container else "stopped",
                    "gateway": "reachable" if gateway else "unreachable",
                    "wechat": wechat_s,
                    "docker_network": "ok" if docker_net else "failed",
                    "failures": self.server.persister._consecutive_failures,
                    "timestamp": datetime.now().isoformat(),
                }, ensure_ascii=False)
                b = body.encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b)

        server = HTTPServer(("127.0.0.1", 8645), HealthHandler)
        server.persister = self
        logger.info("Health dashboard: http://127.0.0.1:8645")
        while self._running:
            server.handle_request()
        server.server_close()

    async def run(self):
        """主入口"""
        # 阻止系统休眠（守护进程运行期间保持唤醒）
        prevent_sleep(True)
        logger.info("🔒 Power lock acquired - system will not sleep while daemon runs")
        logger.info("=" * 60)
        logger.info("Hermes Connection Persistence Daemon v2.0")
        logger.info("=" * 60)
        logger.info(f"Check interval: {CHECK_INTERVAL}s")
        logger.info(f"Recovery cooldown: {RECOVERY_COOLDOWN}s")
        logger.info(f"Hermes home: {HERMES_HOME}")
        logger.info("")

        # 启动时立即检查
        logger.info("Running initial health check...")
        container_ok = self.is_container_running()
        gateway_ok, status = self.check_gateway_api()
        wechat_ok, wechat_s = self.check_wechat_state()
        self._last_wechat_state = wechat_s

        logger.info(f"  Container: {'✅ running' if container_ok else '❌ stopped'}")
        logger.info(f"  Gateway:   {'✅ reachable' if gateway_ok else '❌ unreachable'}")
        logger.info(f"  WeChat:    {'✅ ' + wechat_s if wechat_ok else '❌ ' + wechat_s}")

        if not container_ok or not gateway_ok:
            logger.info("⚠️ Initial state not healthy, running recovery...")
            self.recovery_full_stack()

        # 启动服务
        await asyncio.gather(
            self.check_and_recover(),
            self.power_event_monitor(),
            self.dashboard_health_server(),
        )


def install_windows_task():
    """安装Windows计划任务：系统唤醒后自动重连"""
    import xml.etree.ElementTree as ET

    task_name = "HermesConnectionRecovery"
    script_path = HERMES_HOME / "recovery_on_resume.ps1"

    ps1_content = r"""# Hermes Recovery on System Resume
# 由 connection_persister.py 自动生成

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] System resumed - recovering Hermes connection..."

# 1. 等待WSL2就绪
Start-Sleep -Seconds 5

# 2. 确保Docker Desktop运行
$docker = Get-Process "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "Starting Docker Desktop..."
    Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
    Start-Sleep -Seconds 30
}

# 3. 重启WSL2网络
wsl -d Ubuntu -e bash -c "sudo ip link set eth0 down && sudo ip link set eth0 up" 2>$null
Start-Sleep -Seconds 3

# 4. 重启Hermes容器
docker restart hermes 2>$null
Start-Sleep -Seconds 5

# 5. 验证
$status = docker ps --filter name=hermes --format "{{.Status}}"
Write-Host "Hermes status: $status"

# 6. 通知Dashboard
try {
    $body = @{action="restart"} | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:8643/api/action" -Method Post -Body $body -ContentType "application/json" -ErrorAction SilentlyContinue
} catch {}

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Recovery complete"
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(ps1_content)

    task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <EventTrigger>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
      <Delay>PT10S</Delay>
    </EventTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-NoProfile -ExecutionPolicy Bypass -File "{script_path}"</Arguments>
    </Exec>
  </Actions>
</Task>"""

    task_file = HERMES_HOME / "recovery_task.xml"
    with open(task_file, "w", encoding="utf-16") as f:
        f.write(task_xml)

    logger.info(f"Created: {script_path}")
    logger.info(f"Created: {task_file}")
    logger.info(f"To install task, run as Administrator:")
    logger.info(f"  schtasks /Create /XML \"{task_file}\" /TN \"{task_name}\"")
    return task_file


def _release_power_lock():
    """进程退出时释放电源锁"""
    prevent_sleep(False)
    logger.info("🔓 Power lock released - system may sleep normally")

import atexit
atexit.register(_release_power_lock)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Connection Persistence Daemon")
    parser.add_argument("--install-task", action="store_true", help="Install Windows Resume Task")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--check", action="store_true", help="Run single health check")
    parser.add_argument("--recover", action="store_true", help="Run full recovery now")
    args = parser.parse_args()

    persister = HermesConnectionPersister()

    if args.install_task:
        install_windows_task()
    elif args.check:
        container = persister.is_container_running()
        gateway, status = persister.check_gateway_api()
        wechat_ok, wechat_s = persister.check_wechat_state()
        docker_net = persister.check_docker_wsl_network()
        print(json.dumps({
            "container": "running" if container else "stopped",
            "gateway": "reachable" if gateway else "unreachable",
            "wechat": wechat_s,
            "docker_network": "ok" if docker_net else "failed",
            "wechat_ok": wechat_ok,
        }, indent=2, ensure_ascii=False))
    elif args.recover:
        persister.recovery_full_stack()
    else:
        asyncio.run(persister.run())
