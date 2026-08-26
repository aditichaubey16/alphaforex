"""Entry point: run this to start FxDesk locally.

    python app.py

Opens the dashboard in your default browser at http://127.0.0.1:8020
"""
import threading
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORT = 8020


def _open_browser():
    webbrowser.open(f"http://{HOST}:{PORT}")


if __name__ == "__main__":
    threading.Timer(1.25, _open_browser).start()
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)
