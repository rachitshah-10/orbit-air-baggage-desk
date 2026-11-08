#!/usr/bin/env bash
# STRETCH GOAL 1
# PreToolUse hook blocking edits to the tests folder

TARGET_PATH="$1"
if [[ "$TARGET_PATH" == *"tests/"* ]]; then
    echo "Edit blocked: Modifying tests is prohibited by test-protection hook (STRETCH GOAL 1)." >&2
    exit 2
fi

exit 0
