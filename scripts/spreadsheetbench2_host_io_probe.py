"""Host/Windows encoding preflight for the exact DockerTools execution path.

Never calls a model API. Sends large UTF-8 and a deliberately undecodable byte
from inside the isolated sandbox to validate binary pipe capture/decoding.
"""
import argparse
import json
import tempfile
from pathlib import Path

from tooluse_pilot.sandbox import DockerTools

_PYTHON = (
    "import sys;"
    "sys.stdout.buffer.write(('中文✓—' * 14000).encode('utf-8') + b'\\x94');"
    "sys.stderr.buffer.write(('错误✓' * 4000).encode('utf-8') + b'\\x94')"
)
_SHELL = "python -c 'import sys;sys.stdout.buffer.write((\"中文✓\"*14000).encode(\"utf-8\")+bytes([148]))'"

def sandbox_io_preflight(image="tooluse-pilot-sandbox:py311-openpyxl", timeout=60):
    with tempfile.TemporaryDirectory(prefix="ssb2_sandbox_preflight_") as temp:
        workspace=Path(temp)
        (workspace/"input").mkdir()
        (workspace/"output").mkdir()
        (workspace/"instruction.md").write_text("Encoding preflight only; no model data.",encoding="utf-8")
        agent=DockerTools(workspace,image=image,timeout=timeout)
        try:
            reports={}
            for kind,payload in (("python",_PYTHON),("shell",_SHELL)):
                result=(agent.execute_python(payload) if kind=="python"
                        else agent.execute_shell(payload))
                output=result.get("stdout","")
                ok=(result.get("exit_code")==0 and "中文" in output
                    and "\ufffd" in output)
                reports[kind]={
                    "passed":ok,"exit_code":result.get("exit_code"),
                    "utf8_non_ascii_seen":"中文" in output,
                    "malformed_byte_safely_replaced":"\ufffd" in output,
                    "stderr_excerpt":str(result.get("stderr",""))[-160:]
                }
            return {"pass":all(v["passed"] for v in reports.values()),
                    "checks":reports,
                    "scope":"DockerTools UTF-8 binary pipe and replacement; not all host subprocess call sites"}
        finally:
            agent.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
    args=p.parse_args()
    result=sandbox_io_preflight(args.sandbox_image)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["pass"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
