"""
server.py - Command-line entrypoint to launch the Pipeline 1 API Server & Review Studio.
Usage:
    python server.py
    python server.py --host 0.0.0.0 --port 8001 --reload
"""

import sys
import os
import argparse
import uvicorn

# Set UTF-8 encoding for Windows console compatibility
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend/pipeline-one is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


def main():
    parser = argparse.ArgumentParser(description="Run CPSE Pipeline 1 API Server & Review Studio")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8001, help="Port number (default: 8001)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")

    args = parser.parse_args()

    import torch
    has_cuda = torch.cuda.is_available()
    print("=" * 70)
    print(">> CPSE MATERIAL MASTER PIPELINE 1 API SERVER")
    print(f">> Serving at       : http://{args.host}:{args.port}")
    print(f">> Web Review Studio: http://{args.host}:{args.port}/")
    print(f">> Swagger API Docs : http://{args.host}:{args.port}/docs")
    print(f">> Active Model     : Qwen2.5-3B-CPSE-LoRA-v2")
    print(f">> Python Runtime   : {sys.executable}")
    print(f">> PyTorch Version  : {torch.__version__}")
    if has_cuda:
        print(f">> Hardware Target  : CUDA ({torch.cuda.get_device_name(0)})")
    else:
        print(f">> Hardware Target  : CPU (Fallback)")
        root_venv_python = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".venv", "Scripts", "python.exe"))
        if os.path.exists(root_venv_python) and os.path.abspath(sys.executable).lower() != root_venv_python.lower():
            print("-" * 70)
            print(">> [WARNING] Running on system Python without CUDA support!")
            print(f">> Found GPU-ready virtual environment at: {root_venv_python}")
            print(">> To run with your NVIDIA RTX 3050 GPU, launch with:")
            print(f">>   ..\\..\\.venv\\Scripts\\python server.py --port {args.port}")
            print("-" * 70)
    print("=" * 70)

    uvicorn.run(
        "app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
