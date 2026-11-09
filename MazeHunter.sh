#!/usr/bin/env bash
# Labirent Avcısı'nı başlatır (herhangi bir dizinden çalıştırılabilir).
cd "$(dirname "$0")" && exec python3 -m maze_hunter "$@"
