#!/bin/bash
# Wrapper: run hooks watchdog from /opt/data/hooks/
exec python3 /opt/data/hooks/hooks_watchdog.py "$@"
