#!/bin/bash
# Wrapper для check_and_run_bot.sh для зворотної сумісності

# Знайти check_and_run_bot.sh
SCRIPT_DIR="$(dirname "$0")"
CHECK_SCRIPT="$SCRIPT_DIR/check_and_run_bot.sh"

if [ -f "$CHECK_SCRIPT" ]; then
    # Запустити з командою start або check
    "$CHECK_SCRIPT" start
else
    echo "ERROR: check_and_run_bot.sh not found!"
    exit 1
fi
