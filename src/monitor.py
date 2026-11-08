import time
import platform
import socket
from datetime import datetime

import psutil

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.align import Align
from rich import box

console = Console()


# ---------- CONFIGURATION ----------

REFRESH_RATE = 1
CPU_WARNING = 85
RAM_WARNING = 85
DISK_WARNING = 90


# ---------- SYSTEM INFORMATION ----------

def get_uptime():
    seconds = int(time.time() - psutil.boot_time())

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    return f"{hours}h {minutes}m"


def get_bar(value):
    filled = int(value / 5)
    empty = 20 - filled

    if value >= 85:
        color = "red"
    elif value >= 65:
        color = "yellow"
    else:
        color = "green"

    return (
        f"[{color}]{'━' * filled}[/]"
        f"[dim]{'━' * empty}[/]"
    )


def get_status(value, limit):
    if value >= limit:
        return "[bold red]CRITICAL[/]"
    elif value >= limit - 20:
        return "[yellow]WARNING[/]"
    return "[green]NORMAL[/]"


def get_system_info():

    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")

    battery = psutil.sensors_battery()

    return {
        "cpu": cpu,
        "ram": ram.percent,
        "ram_used": ram.used / (1024 ** 3),
        "ram_total": ram.total / (1024 ** 3),
        "disk": disk.percent,
        "disk_used": disk.used / (1024 ** 3),
        "disk_free": disk.free / (1024 ** 3),
        "disk_total": disk.total / (1024 ** 3),
        "battery": battery.percent if battery else None,
        "hostname": socket.gethostname(),
        "os": platform.system() + " " + platform.release(),
        "processor": platform.processor(),
        "cores": psutil.cpu_count(logical=True),
        "uptime": get_uptime(),
    }


# ---------- DASHBOARD ----------

def create_dashboard(data):

    # Header
    header = Panel(
        Align.center(
            Text("SYS-SENTINEL", style="bold cyan", justify="center")
            + Text("\nSYSTEM INTELLIGENCE & HEALTH MONITOR M.1",
                   style="dim white"),
            vertical="middle"
        ),
        border_style="bright_blue"
    )

    # Resource table
    table = Table(
        box=box.ROUNDED,
        expand=True,
        border_style="blue"
    )

    table.add_column("RESOURCE", style="bold cyan")
    table.add_column("USAGE", justify="right")
    table.add_column("VISUAL MONITOR", min_width=25)
    table.add_column("STATUS", justify="center")

    resources = [
        ("CPU", data["cpu"], CPU_WARNING),
        ("MEMORY", data["ram"], RAM_WARNING),
        ("DISK (C:)", data["disk"], DISK_WARNING),
    ]

    for name, value, limit in resources:
        table.add_row(
            name,
            f"{value:.1f}%",
            get_bar(value),
            get_status(value, limit)
        )

    # Hardware details
    details = Table.grid(expand=True, padding=(0, 2))
    details.add_column(style="cyan")
    details.add_column(style="white")

    details.add_row("COMPUTER", data["hostname"])
    details.add_row("OPERATING SYSTEM", data["os"])
    details.add_row("PROCESSOR", data["processor"] or "Unknown")
    details.add_row("LOGICAL CORES", str(data["cores"]))
    details.add_row("SYSTEM UPTIME", data["uptime"])

    # Memory and storage details
    storage = Table.grid(expand=True, padding=(0, 1))
    storage.add_column(style="cyan")
    storage.add_column(style="white")

    storage.add_row(
        "RAM",
        f"{data['ram_used']:.2f} / {data['ram_total']:.2f} GB"
    )

    storage.add_row(
        "DISK USED",
        f"{data['disk_used']:.2f} GB"
    )

    storage.add_row(
        "DISK FREE",
        f"{data['disk_free']:.2f} GB"
    )

    battery = (
        f"{data['battery']}%"
        if data["battery"] is not None
        else "Not available"
    )

    storage.add_row("BATTERY", battery)

    # Alerts
    alerts = []

    for name, value, limit in resources:
        if value >= limit:
            alerts.append(f"[bold red]!! {name} usage is high[/]")

    alert_text = (
        "\n".join(alerts)
        if alerts
        else "[bold green]ALL SYSTEMS OPERATIONAL[/]"
    )

    # Complete layout
    layout = Table.grid(expand=True)
    layout.add_row(header)
    layout.add_row(
        Panel(
            table,
            title="[bold white]THE LIVE MONITOR[/]",
            border_style="bright_red"
        )
    )

    bottom = Table.grid(expand=True)
    bottom.add_column(ratio=1)
    bottom.add_column(ratio=1)

    bottom.add_row(
        Panel(details, title="HARDWARE INFORMATION",
              border_style="cyan"),
        Panel(storage, title="MEMORY & STORAGE",
              border_style="magenta")
    )

    layout.add_row(bottom)

    layout.add_row(
        Panel(
            Align.center(Text.from_markup(alert_text)),
            title="SYSTEM ALERTS",
            border_style="red" if alerts else "green"
        )
    )

    footer = (
        f"[dim]LAST UPDATED: {datetime.now():%H:%M:%S} "
        f"| REFRESH: {REFRESH_RATE}s "
        f"| PRESS CTRL+C TO EXIT[/]"
    )

    layout.add_row(Align.center(Text.from_markup(footer)))

    return layout


# ---------- MAIN PROGRAM ----------

def main():

    console.clear()

    console.print(
        Panel(
            "[bold cyan]INITIALIZING SYS-SENTINEL...[/]\n"
            "[dim]Loading system intelligence modules[/]",
            border_style="bright_blue",
            expand=True
        )
    )

    try:
        with Live(
            create_dashboard(get_system_info()),
            console=console,
            refresh_per_second=2,
            screen=True
        ) as live:

            while True:
                data = get_system_info()
                live.update(create_dashboard(data))
                time.sleep(REFRESH_RATE)

    except KeyboardInterrupt:
        console.print(
            "\n[bold red]SHUTDOWN COMPLETE[/]"
        )


if __name__ == "__main__":
    main()
