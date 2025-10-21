#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_MAIN="$SCRIPT_DIR/src/cli/__main__.py"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

source "$SCRIPT_DIR/src/shared_toolkit/scripts/common_launcher_funcs.sh"

show_help() {
    echo "Tkonverter CLI - Command Line Interface"
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  convert -i <input> -o <output>  Convert JSON export to text"
    echo "  analyze -i <input>              Analyze chat statistics"
    echo "  info -i <input>                 Show file information"
    echo ""
    echo "Global options:"
    echo "  --debug, -d                     Enable debug logging"
    echo "  --help, -h                      Show this help"
    echo "  --version, -v                   Show version"
    echo ""
    echo "Examples:"
    echo "  $0 convert -i result.json -o output.txt"
    echo "  $0 convert -i result.json -o output.txt --profile personal --no-time"
    echo "  $0 analyze -i result.json --tokenizer google/gemma-2b"
    echo "  $0 info -i result.json --detailed"
    echo ""
    echo "For detailed help on specific commands:"
    echo "  $0 <command> --help"
}

if [[ "$1" == "--help" || "$1" == "-h" || "$1" == "help" ]]; then
    show_help
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

# Run CLI command
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
