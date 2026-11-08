# SYS-SENTINEL

**A real-time system health monitor built with Python.**

SYS-SENTINEL is a terminal-based dashboard that monitors your computer's performance and displays live system statistics in a clean interface.

## Features

- Live CPU usage monitoring
- RAM utilization tracking
- Disk usage monitoring
- System information and uptime
- Battery status (when available)
- Automatic performance warnings
- Real-time dashboard refresh

## Tech Stack

- Python 3
- psutil
- Rich

## Installation

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/sys-sentinel.git
cd sys-sentinel
```

Create and activate a virtual environment:

```bash
py -m venv venv
venv\Scripts\activate
```

Install dependencies:

```bash
py -m pip install -r requirements.txt
```

## Run

```bash
py src/monitor.py
```

Press `Ctrl + C` to exit.

## Run Tests

```bash
py -m unittest discover -s tests -v
```

## Project Structure

```text
sys-sentinel/
├── src/
│   └── monitor.py
├── tests/
│   └── test_monitor.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

Built with Python.