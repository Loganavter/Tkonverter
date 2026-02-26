#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_MAIN="$SCRIPT_DIR/src/cli/__main__.py"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS="$SCRIPT_DIR/requirements-gui.txt"

source "$SCRIPT_DIR/src/shared_toolkit/scripts/common_launcher_funcs.sh"

if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        python "$CLI_MAIN" --help
        deactivate_venv
    fi
    exit 0
fi

if [[ "$1" == "--version" || "$1" == "-v" ]]; then
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        python "$CLI_MAIN" --version
        deactivate_venv
    fi
    exit 0
fi

if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
    log_info "Starting Tkonverter CLI..."
    export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
    python "$CLI_MAIN" "$@"
    app_exit_code=$?
    deactivate_venv
    log_info "CLI completed with exit code: $app_exit_code"
    exit $app_exit_code
else
    deactivate_venv
    log_status "Failed to prepare environment. Aborting." 1
    exit 1
fi
