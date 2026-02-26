

import argparse
import json
import logging
import os
import sys
import warnings

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
logging.getLogger("transformers").setLevel(logging.CRITICAL)

def _reply(obj: dict) -> None:
    print(json.dumps(obj), flush=True)

def run_daemon(tokenizer, model_name: str) -> None:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _reply({"ok": False, "error": f"Invalid JSON: {e}"})
            continue
        action = req.get("action")
        if action == "quit":
            break
        if action == "count":
            text = req.get("text", "")
            try:
                n = len(tokenizer.encode(text))
                _reply({"ok": True, "count": n})
            except Exception as e:
                _reply({"ok": False, "error": str(e)})
            continue
        if action == "info":
            v = getattr(tokenizer, "vocab_size", None)
            m = getattr(tokenizer, "model_max_length", None)
            _reply({"ok": True, "vocab_size": v, "model_max_length": m})
            continue
        _reply({"ok": False, "error": f"Unknown action: {action}"})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Tokenizer model name")
    parser.add_argument("--check", action="store_true", help="Only check that model loads")
    parser.add_argument("--count", action="store_true", help="Read text from stdin, print token count")
    parser.add_argument("--info", action="store_true", help="Print vocab_size and model_max_length (JSON)")
    parser.add_argument("--daemon", action="store_true", help="Keep model in memory, serve JSON commands from stdin")
    parser.add_argument("--download", action="store_true", help="Allow download from Hugging Face if not in cache")
    args = parser.parse_args()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            import transformers  # noqa: F401
            transformers.logging.set_verbosity_error()
            from transformers import AutoTokenizer
        except ImportError:
            print("ERROR: transformers not installed", file=sys.stderr)
            sys.exit(2)

    local_files_only = not args.download

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or None
    if not args.download:
        hf_token = False
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            local_files_only=local_files_only,
            token=hf_token,
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.check:
        sys.exit(0)

    if args.info:
        v = getattr(tokenizer, "vocab_size", None)
        m = getattr(tokenizer, "model_max_length", None)
        print(json.dumps({"vocab_size": v, "model_max_length": m}))
        sys.exit(0)

    if args.daemon:
        run_daemon(tokenizer, args.model)
        sys.exit(0)

    if args.count:
        text = sys.stdin.read()
        n = len(tokenizer.encode(text))
        print(n)
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
