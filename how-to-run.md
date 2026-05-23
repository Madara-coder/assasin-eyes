# One-Time Setup
You only needed these once. Next time you start the app, skip straight to the two cd + run commands above.

# Backend (done once)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend (done once)
cd frontend
npm install

## To set up for your router change these
From
PING_TARGET = "192.168.1.1" (test-mode)(on config.py file) to
PING_TARGET = "Your router ip"

From
SCANNER_MODE = "mock" (test-mode-activated) to
SCANNER_MODE = "ping" (for testing with ping)