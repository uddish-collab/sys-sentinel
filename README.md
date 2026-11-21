# SYS-SENTINEL 🤖⚡

**An intelligent, futuristic desktop companion and real-time hardware telemetry HUD built with Python & PySide6.**

SYS-SENTINEL reimagines system monitoring by combining a live desktop mascot ("Senti"), a sleek dynamic Top Island HUD, and a deep 8-tab subsystem analytics dashboard into an intuitive, cyberpunk-styled workstation companion.

---

## 🌟 Key Features

### 🐾 Senti — The Desktop Mascot
- **Expressive Eye Physics**: Smooth gaze tracking, blinking, squinting, and reactive facial animations.
- **Hardware-Aware Mood States**: Senti dynamically reacts to real-time CPU/GPU load, memory bottlenecks, and thermal spikes.
- **Interactive & Draggable**: Hover animations, speech bubbles, and effortless desktop placement.

### 🏝️ Dynamic Top Island HUD
- **Minimalist Workstation Pill**: Unobtrusive top-of-screen bar showcasing real-time CPU, GPU, RAM, and Disk metrics.
- **Expandable Telemetry Pills**: Hover or click metrics for instant popouts, live status dots, and warnings.
- **Seamless Docking**: Automatically stays accessible without obstructing your workflow.

### 📊 Comprehensive 8-Panel Dashboard
- **Overview**: System health index, quick vitals, OS details, and uptime.
- **CPU**: Per-core breakdown, clock speeds, and live frequency graphing.
- **GPU**: NVIDIA and integrated graphics telemetry (VRAM usage, core load, temperatures).
- **RAM & Memory**: Physical memory breakdown, commit charges, and swap stats.
- **Storage**: Multi-drive capacity bars and real-time read/write disk throughput.
- **Network**: Active adapter detection, IP configs, and live upstream/downstream speedometers.
- **Processes**: Live task manager displaying top CPU and memory consumers.
- **Settings & Studio**: Customizable control center and HUD layout configuration.

### 🔊 Audio & Alert Synthesizer
- Procedural alert chimes, system sound cues, and interactive feedback.

---

## 🛠️ Tech Stack

- **Python 3.10+**
- **[PySide6](https://doc.qt.io/qtforpython-6/)** (Qt6 GUI engine, QPainter canvas, QPropertyAnimation)
- **[psutil](https://github.com/giampaolo/psutil)** (Cross-platform system hardware & process telemetry)

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have **Python 3.10 or higher** installed on Windows.

### 2. Clone the Repository
```bash
git clone https://github.com/uddish-collab/sys-sentinel.git
cd sys-sentinel
```

### 3. Setup Virtual Environment
```bash
py -m venv .venv
.venv\Scripts\activate
```

### 4. Install Dependencies
```bash
py -m pip install -r requirements.txt
```

### 5. Launch SYS-SENTINEL
```bash
py src/senti_app.py
```

---

## 🧪 Running Tests

The test suite validates companion windows, dashboard tabs, telemetry collection, and state management:

```bash
py -m unittest discover -s tests -v
```

---

## 📁 Project Structure

```text
sys-sentinel/
├── src/
│   ├── senti_app.py         # Application entry point, window coordinator & tray
│   ├── senti_mascot.py      # Animated desktop pet widget & reactive eye physics
│   ├── senti_island.py      # Top Dynamic Island HUD overlay & telemetry pills
│   ├── senti_dashboard.py   # Full 8-tab subsystem monitor & analytics dashboard
│   ├── senti_control.py     # Quick settings & companion control flyout
│   ├── senti_hud.py         # HUD status cards & telemetry overlays
│   ├── senti_widgets.py     # Reusable custom UI components (meters, graphs, bars)
│   ├── senti_sound.py       # Procedural audio effects & sound feedback engine
│   ├── senti_settings.py    # Persistent app settings & user configurations
│   ├── senti_state.py       # Centralized telemetry store & companion state
│   └── system_monitor.py    # Asynchronous background hardware metrics & temp daemons
├── tests/
│   ├── test_companion.py      # Tests for window coordination and companion setup
│   ├── test_dashboard.py      # Tests for subsystem dashboard tabs and views
│   ├── test_pill_toggle.py    # Tests for Top Island telemetry pill interactions
│   ├── test_senti_state.py    # Tests for central state metrics and thresholds
│   ├── test_sound.py          # Tests for sound synthesizer cues and effects
│   ├── test_system_monitor.py # Tests for hardware polling resilience and structure
│   └── test_temperature.py   # Tests for thermal sensor parsing and fallbacks
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🛡️ License

Built with ❤️ by the Sys-Sentinel Team.
