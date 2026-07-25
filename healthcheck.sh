#!/bin/bash
LOGFILE="/opt/data/healthcheck.log"
STATE_FILE="/opt/data/gateway_state.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
log() { echo "[$TIMESTAMP] $*" | tee -a "$LOGFILE"; }

check_gateway() {
  hermes gateway status 2>&1 | grep -q "is running"
}

check_wechat_state() {
  if [ -f "$STATE_FILE" ]; then
    local state=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('platforms',{}).get('weixin',{}).get('state','unknown'))" 2>/dev/null)
    echo "$state"
    [ "$state" = "connected" ]
    return $?
  fi
  return 1
}

restart_wechat_platform() {
  log "Restarting WeChat platform..."
  hermes platform restart weixin 2>&1 | head -5 >> "$LOGFILE"
  sleep 3
  if check_wechat_state; then
    log "WeChat restarted: OK"; return 0
  fi
  log "WeChat restart: failed"; return 1
}

log "=== Health Check ==="
if ! check_gateway; then
  log "CRITICAL: Gateway not running"; exit 1
fi
log "Gateway: OK"
WECHAT_STATE=$(check_wechat_state)
log "WeChat state: $WECHAT_STATE"
if [ "$WECHAT_STATE" != "connected" ]; then
  log "WECHAT DISCONNECTED - recovering..."
  restart_wechat_platform
fi
log "=== Health Check Complete ==="
