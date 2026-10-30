"""GPT comparison runner; reads three variables from the current CMD window."""
import os
import sys
from spreadsheetbench2_batch_qwen import main

if __name__ == "__main__":
    missing=[name for name in ("MODEL_BASE_URL","MODEL_API_KEY","MODEL_ID") if not os.getenv(name)]
    if missing:
        raise SystemExit("Missing environment variable(s): "+", ".join(missing))
    if "--api-type" not in sys.argv:
        sys.argv.extend(["--api-type","responses"])
    main()
