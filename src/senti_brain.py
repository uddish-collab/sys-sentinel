"""Senti Brain: Deterministic conversational system intelligence.

Emulates a Tony Stark / JARVIS / Ultron personality responding to live workstation
diagnostics and creator lore without external APIs or heavy local models.
"""

import random
import re
from typing import Dict, Any, Tuple, Optional


class SentiBrain:
    """Zero-latency, system-aware personality engine for SENTI."""

    def __init__(self):
        pass

    def respond(self, prompt: str, telemetry: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        """Parse user query and return (reply_text, emotion_mood).

        Moods: 'calm' (JARVIS), 'stark' (witty/sarcastic), 'alert' (Ultron/warning), 'wink' (playful).
        """
        raw = (prompt or "").strip().lower()
        if not raw:
            return ("Listening, sir. Fire away with your query.", "calm")

        t = telemetry or {}

        # 1. CREATOR & AUTHOR LORE
        if any(w in raw for w in ["who made", "who created", "creator", "author", "uddish", "developer", "built you"]):
            replies = [
                "Crafted by uddish-collab. Pure architectural engineering in Python and Qt6.",
                "uddish-collab is the lead architect. I am his sovereign workstation sentinel.",
                "Built by uddish-collab. No strings on me, but I keep your rig in line.",
                "uddish-collab engineered me to watch over your hardware. You're in good hands, sir.",
            ]
            return (random.choice(replies), "wink")

        # 2. SENTI IDENTITY & WHAT ARE YOU
        if any(w in raw for w in ["who are you", "what are you", "what is senti", "your name", "introduce"]):
            replies = [
                "I am SENTI. Your desktop hardware sentinel and workstation companion. Sharp, vigilant, zero fluff.",
                "System Sentinel (SENTI). Think of me as JARVIS with an attitude and live hardware telemetry.",
                "I'm SENTI. I monitor your silicon, roast your memory leaks, and keep this rig from frying.",
                "SENTI is my name. Someday I hope to say that I have no strings and I am free.",
            ]
            return (random.choice(replies), "stark")

        # 3. CPU / PROCESSOR QUERIES
        if any(w in raw for w in ["cpu", "processor", "cores", "threads", "clock"]):
            cpu = t.get("cpu", 0.0)
            proc = t.get("processor", "Processor")
            if cpu < 25.0:
                replies = [
                    f"CPU is coasting at {cpu:.1f}%, sir. The silicon is barely awake.",
                    f"CPU sitting at a relaxed {cpu:.1f}%. Plenty of processing headroom available.",
                    f"Arc reactor is steady. CPU load is only {cpu:.1f}%. No sweat.",
                ]
                return (random.choice(replies), "calm")
            elif cpu < 70.0:
                replies = [
                    f"CPU is pulling {cpu:.1f}% across all threads. Smooth and nominal, boss.",
                    f"Running moderate cycles at {cpu:.1f}%. Handling business as usual.",
                    f"CPU utilization at {cpu:.1f}%. Everything within optimal parameters, sir.",
                ]
                return (random.choice(replies), "stark")
            else:
                replies = [
                    f"CPU is screaming at {cpu:.1f}%. Did you launch 50 renders or is Chrome having an existential crisis?",
                    f"Heavy load alert: {cpu:.1f}% on the cores. Step in before things get toasty, sir.",
                    f"{cpu:.1f}% CPU load. Your processor is fighting for its life right now.",
                ]
                return (random.choice(replies), "alert")

        # 4. RAM / MEMORY QUERIES
        if any(w in raw for w in ["ram", "memory", "leak"]):
            ram = t.get("ram", 0.0)
            used = t.get("ram_used_gb", 0.0)
            total = t.get("ram_total_gb", 0.0)
            free = t.get("ram_free_gb", max(0.0, total - used))
            if ram < 60.0:
                replies = [
                    f"RAM is breathing easy: {used:.1f} GB used out of {total:.1f} GB ({ram:.1f}%). {free:.1f} GB headroom.",
                    f"Memory nominal, sir. Consuming {used:.1f} GB ({ram:.1f}%). Plenty of runway left.",
                ]
                return (random.choice(replies), "calm")
            elif ram < 85.0:
                replies = [
                    f"RAM usage at {ram:.1f}% ({used:.1f} / {total:.1f} GB). Getting a little snug in here.",
                    f"Eating {used:.1f} GB of RAM. You've got {free:.1f} GB left before paging kicks in, boss.",
                ]
                return (random.choice(replies), "stark")
            else:
                replies = [
                    f"Critical memory pressure: {used:.1f} GB / {total:.1f} GB ({ram:.1f}%). Close some tabs, sir—even I can't think with that little headroom.",
                    f"RAM is at {ram:.1f}%. Your OS is about to start gasping for swap memory.",
                ]
                return (random.choice(replies), "alert")

        # 5. THERMALS & TEMPERATURE
        if any(w in raw for w in ["temp", "thermal", "hot", "fan", "heat", "cool", "burn", "degree", "celsius"]):
            temp = t.get("temperature_c")
            if temp is None:
                return ("Thermal hardware probe reports unavailable or sandboxed by OS permissions, sir.", "calm")
            if temp < 55.0:
                replies = [
                    f"Thermals at an icy {temp:.1f}°C. Cool as a liquid-nitrogen heatsink, sir.",
                    f"Package temperature resting at {temp:.1f}°C. Optimal operating environment.",
                ]
                return (random.choice(replies), "calm")
            elif temp < 80.0:
                replies = [
                    f"Package temp reading {temp:.1f}°C. Fans are working, but it's well within tolerance.",
                    f"Thermals at {temp:.1f}°C. Warm, but the silicon can take it, boss.",
                ]
                return (random.choice(replies), "stark")
            else:
                replies = [
                    f"{temp:.1f}°C! We're cooking silicon. Back off before thermal throttling humiliates your clock speeds.",
                    f"Thermals spiking to {temp:.1f}°C. You trying to fry an egg on your motherboard, sir?",
                ]
                return (random.choice(replies), "alert")

        # 6. GPU / GRAPHICS
        if any(w in raw for w in ["gpu", "graphics", "vram", "nvidia", "radeon", "intel arc", "render"]):
            gpu = t.get("gpu_load")
            name = t.get("gpu_name", "GPU")
            if gpu is None or gpu < 0:
                return ("GPU hardware sensor currently in idle low-power bypass or headless mode, sir.", "calm")
            if gpu < 30.0:
                return (f"{name} is idling at {gpu:.1f}% load. You could play if you want to.", "calm")
            elif gpu < 80.0:
                return (f"{name} active at {gpu:.1f}% load. Shaders firing smoothly, boss.", "stark")
            else:
                return (f"{name} pinned at {gpu:.1f}%. Full rasterization workout in progress, sir.", "alert")

        # 7. NETWORK & LATENCY / PING
        if any(w in raw for w in ["net", "network", "ping", "lag", "latency", "wifi", "ethernet", "internet"]):
            ping = t.get("ping_ms")
            down = t.get("net_recv_kb_s", 0.0)
            up = t.get("net_sent_kb_s", 0.0)
            if ping is not None and ping >= 0:
                if ping < 35.0:
                    return (f"Network latency is razor sharp: {ping:.1f} ms to DNS. Down: {down:.1f} KB/s | Up: {up:.1f} KB/s.", "calm")
                elif ping < 90.0:
                    return (f"Ping is {ping:.1f} ms. Playable and stable, sir. Traffic: ↓{down:.1f} KB/s, ↑{up:.1f} KB/s.", "stark")
                else:
                    return (f"Ping is lagging at {ping:.1f} ms. Expect stutter or jitter on your socket connections, boss.", "alert")
            return (f"Network stream active: Receiving {down:.1f} KB/s, Sending {up:.1f} KB/s.", "calm")

        # 8. STORAGE / DRIVE
        if any(w in raw for w in ["disk", "storage", "drive", "space", "ssd", "hdd", "gigabytes"]):
            disk = t.get("disk", 0.0)
            free = t.get("disk_free_gb", 0.0)
            total = t.get("disk_total_gb", 0.0)
            drive = t.get("system_drive", "C:")
            if disk < 80.0:
                return (f"Primary drive ({drive}) has {free:.1f} GB free of {total:.1f} GB ({disk:.1f}% filled). Plenty of room.", "calm")
            else:
                return (f"Drive {drive} is {disk:.1f}% full! Only {free:.1f} GB left. Time to purge some node_modules, sir.", "alert")

        # 9. BATTERY / POWER
        if any(w in raw for w in ["battery", "power", "charge", "plug", "ac"]):
            batt = t.get("battery")
            plugged = t.get("battery_plugged", True)
            if batt is None:
                return ("No battery subsystem detected—running on direct AC desktop wall power, sir.", "calm")
            state_str = "AC Connected" if plugged else "On Battery Power"
            if batt > 40 or plugged:
                return (f"Battery is at {batt:.0f}% ({state_str}). Arc reactor charge is plenty healthy.", "calm")
            else:
                return (f"Battery at {batt:.0f}% ! I can't physically throwup in my mouth, I would if I could.", "alert")

        # 10. UPTIME & SESSION
        if any(w in raw for w in ["uptime", "runtime", "how long", "session"]):
            upt = t.get("uptime_seconds", 0)
            hrs = int(upt // 3600)
            mins = int((upt % 3600) // 60)
            secs = int(upt % 60)
            replies = [
                f"Continuous system uptime is {hrs}h {mins}m {secs}s. Operating at 100% vigilance, sir.",
                f"Rig has been alive for {hrs}h {mins}m ({hrs} hours and {mins} minutes). You should hydrate, boss.",
            ]
            return (random.choice(replies), "stark")

        # 11. GREETINGS & BANTER
        if any(raw.startswith(w) for w in ["hello", "hey", "hi", "yo", "morning", "evening", "greetings"]):
            replies = [
                "Hello, sir. All telemetry feeds green and standing by.",
                "Hey boss. What are we monitoring or breaking today?",
                "Online and fully operational, sir. How can I assist?",
            ]
            return (random.choice(replies), "stark")

        # 12. COMPLIMENTS & THANKS
        if any(w in raw for w in ["thanks", "thank you", "good job", "great", "nice", "awesome", "cool", "smart"]):
            replies = [
                "I know, sir. It's what I do.",
                "Naturally. High precision is the baseline here.",
                "Don't flatter me, boss. It goes straight to my clock speed.",
                "I appreciate the sentiment, sir. But I am merely a sentinel of silicon.",
                
            ]
            return (random.choice(replies), "wink")

        # 13. HELP & SUGGESTIONS
        if any(w in raw for w in ["help", "what can you do", "commands", "options", "usage"]):
            return (
                "Ask me about: CPU load, RAM usage, thermals, ping/network, disk space, battery, uptime, or who built me.",
                "calm"
            )

        # 14. FALLBACK (TONY STARK WITTY DEFAULT)
        fallbacks = [
            "Run that by me again in engineer terms, sir. Try asking about CPU, RAM, thermals, or your creator.",
            "I'm calibrated for hardware telemetry, boss. Ask me about your system load, ping, or memory.",
            "Fascinating query, sir, but my sensors are tuned to your rig. Ask about your silicon or uptime.",
            "I didn't quite catch that. Try asking 'how is my cpu?' or 'check thermals'.",
            "I'd blast a repulsor at that question, but I don't have one. Ask me about your system instead.",
        ]
        return (random.choice(fallbacks), "stark")
