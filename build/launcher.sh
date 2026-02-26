#!/bin/sh
# Launcher for system-wide install (e.g. /usr/lib/tkonverter or AUR).
# Set TKONVERTER_LIB to the directory containing src/ and shared_toolkit/ if not in /usr/lib/tkonverter.
: "${TKONVERTER_LIB:=/usr/lib/tkonverter}"
export PYTHONPATH="${TKONVERTER_LIB}"
exec python3 -m src "$@"
