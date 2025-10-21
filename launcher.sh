#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_MAIN="$SCRIPT_DIR/src/__main__.py"
VENV_DIR="$SCRIPT_DIR/venv"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

source "$SCRIPT_DIR/src/shared_toolkit/scripts/common_launcher_funcs.sh"

enable_logging_action() {
    log_info "Attempting to enable logging..."
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        python "$APP_MAIN" --enable-logging
        deactivate_venv
        log_status "Logging settings updated" 0
    else
        log_status "Failed to prepare environment. Aborting." 1
        exit 1
    fi
}

disable_logging_action() {
    log_info "Attempting to disable logging..."
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        python "$APP_MAIN" --disable-logging
        deactivate_venv
        log_status "Logging settings updated" 0
    else
        log_status "Failed to prepare environment. Aborting." 1
        exit 1
    fi
}

show_help() {
    echo "Tkonverter - Telegram Chat Converter"
    echo "Usage: $0 <command> [options]"
    echo "       $0 [--debug|-d] [--theme <dark|light>]"
    echo ""
    echo "Commands:"
    echo "  run [args...]      Run the application with optional GUI arguments."
    echo "                     Additional flags for 'run' (also valid at top-level):"
    echo "                       --theme <dark|light>  Force a specific theme."
    echo "                       --debug, -d          Enable debug logging for this session only."
    echo "  install            Create the virtual environment and/or install dependencies."
    echo "  recreate           Forcibly recreate the virtual environment."
    echo "  delete             Delete the virtual environment and caches."
    echo "  --enable-logging   Permanently enable debug logging."
    echo "  --disable-logging  Permanently disable debug logging."
    echo "  help               Show this help message."
}

recreate_action() {
    log_info "Recreating virtual environment..."
    if [ -d "$VENV_DIR" ]; then
        log_info "Removing existing venv in '$VENV_DIR'..."
        deactivate_venv
        if rm -rf "$VENV_DIR"; then
            log_status "Existing venv removed" 0
        else
            log_status "Failed to remove venv. Remove manually" 1
            exit 1
        fi
    fi
    ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"
}

delete_action() {
    log_info "Starting cleanup..."
    if [ -d "$VENV_DIR" ]; then
        log_info "Removing virtual environment in '$VENV_DIR'..."
        deactivate_venv
        rm -rf "$VENV_DIR"
        log_status "Virtual environment removed" 0
    else
        log_info "Virtual environment not found, skipping."
    fi

    log_info "Removing '__pycache__' directories..."
    find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} +
    log_status "'__pycache__' directories removed" 0
    log_info "Cleanup completed."
}

if [[ "$1" == "--debug" || "$1" == "-d" || "$1" == "--theme" ]]; then
    set -- run "$@"
fi

COMMAND=$1
case "$COMMAND" in

install)
    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        log_info "Environment is ready."
    else
        log_status "Failed to set up environment." 1
        exit 1
    fi
    deactivate_venv
    ;;

run)
    shift
    gui_args=()
    THEME_TO_SET=""
    DEBUG_MODE="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
        --theme)
            if [[ -n "$2" && ("$2" == "dark" || "$2" == "light") ]]; then
                THEME_TO_SET="$2"
                shift 2
            else
                log_info "Error: --theme requires argument (dark or light)"
                exit 1
            fi
            ;;
        --debug | -d)
            DEBUG_MODE="true"
            shift
            ;;
        *)
            log_info "Error: Unknown option '$1' for run command."
            show_help
            exit 1
            ;;
        esac
    done

    if ensure_venv_is_ready "$VENV_DIR" "$REQUIREMENTS"; then
        log_info "Starting Tkonverter application..."
        export DEBUG="$DEBUG_MODE"
        export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"
        if [[ -n "$THEME_TO_SET" ]]; then
            APP_THEME="$THEME_TO_SET" PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH" python "$APP_MAIN"
        else
            PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH" python "$APP_MAIN"
        fi
        app_exit_code=$?
        deactivate_venv
        log_info "Application completed with exit code: $app_exit_code"
        exit $app_exit_code
    else
        deactivate_venv
        log_status "Failed to prepare environment. Aborting." 1
        exit 1
    fi
    ;;

recreate)
    recreate_action
    deactivate_venv
    ;;

delete)
    delete_action
    ;;
--enable-logging)
    enable_logging_action
    ;;

--disable-logging)
    disable_logging_action
    ;;
"" | help | --help)
    show_help
    ;;

*)
    log_info "Error: Unknown command '$COMMAND'"
    show_help
    exit 1
    ;;
esac

printf "${COLOR_RESET}"
exit 0
