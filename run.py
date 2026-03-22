#!/usr/bin/env python3
"""
RealLink Ecosystem - Main Runner
Starts both backend and frontend servers
"""

import os
import sys
import subprocess
import signal
import time

def main():
    """Run both backend and frontend servers"""
    print("=" * 60)
    print("  RealLink Ecosystem - Starting Servers")
    print("=" * 60)

    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(script_dir, "backend")
    frontend_dir = os.path.join(script_dir, "frontend")

    processes = []

    def signal_handler(sig, frame):
        """Handle Ctrl+C to stop all processes"""
        print("\n")
        print("Stopping servers...")
        for p in processes:
            try:
                p.terminate()
                p.wait(timeout=5)
            except:
                p.kill()
        print("All servers stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Backend
    print("\n[1/2] Starting Backend (FastAPI on port 8000)...")
    backend_process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(backend_process)
    print("      Backend started (PID: {})".format(backend_process.pid))

    # Wait a moment for backend to initialize
    time.sleep(2)

    # Start Frontend
    print("\n[2/2] Starting Frontend (Flask on port 5000)...")
    frontend_process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(frontend_process)
    print("      Frontend started (PID: {})".format(frontend_process.pid))

    print("\n" + "=" * 60)
    print("  All servers running!")
    print("=" * 60)
    print()
    print("  Frontend:    http://localhost:5000")
    print("  Backend:     http://localhost:8000")
    print("  API Docs:    http://localhost:8000/docs")
    print()
    print("  Press Ctrl+C to stop all servers")
    print("=" * 60)

    # Monitor processes and print output
    while True:
        for i, p in enumerate(processes):
            if p.poll() is not None:
                # Process has exited
                name = "Backend" if i == 0 else "Frontend"
                print(f"\n[!] {name} server stopped unexpectedly!")
                signal_handler(None, None)

        # Read and print output
        for i, p in enumerate(processes):
            name = "Backend" if i == 0 else "Frontend"
            try:
                # Non-blocking read
                import select
                if select.select([p.stdout], [], [], 0)[0]:
                    line = p.stdout.readline()
                    if line:
                        print(f"[{name}] {line.rstrip()}")
            except:
                pass

        time.sleep(0.1)


if __name__ == "__main__":
    main()
