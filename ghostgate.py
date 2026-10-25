#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GhostGate v3 - Xray VLESS + Reality full-auto setup tool (modern TUI)
Run on your server as root:  python3 ghostgate.py
"""
import json, os, platform, re, secrets, shutil, socket, ssl, subprocess, sys, time, uuid
import urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============ Bootstrap the UI engine (rich) ============
def ensure_rich():
    try:
        import rich  # noqa
        return
    except ImportError:
        pass
    print("\n  Installing UI engine (rich) ...")
    cmds = [
        "apt-get update -qq && apt-get install -y -qq python3-rich",
        "pip3 install -q rich --break-system-packages",
        "pip3 install -q rich",
        "dnf install -y python3-rich",
    ]
    for cmd in cmds:
        subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            import rich  # noqa
            return
        except ImportError:
            continue
    print("  Could not install 'rich'. Run:  pip3 install rich --break-system-packages")
    sys.exit(1)


ensure_rich()

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.markup import escape as esc
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

VERSION = "3.1"
XRAY_DIR = "/usr/local/etc/xray"
XRAY_CONF = f"{XRAY_DIR}/config.json"
STATE = f"{XRAY_DIR}/ghostgate.json"
LINK_FILE = "/root/ghostgate_link.txt"
PORT_CANDIDATES = [8443, 2053, 2083, 2087, 2096, 443]

SNI_LIST = [
    "www.cloudflare.com", "www.microsoft.com", "www.apple.com",
    "www.samsung.com", "www.amazon.com", "www.nvidia.com",
    "www.intel.com", "www.amd.com", "www.oracle.com", "www.cisco.com",
    "www.asus.com", "www.mozilla.org", "addons.mozilla.org",
    "www.lovelive-anime.jp", "www.speedtest.net", "dl.google.com",
    "www.bing.com", "www.ebay.com", "www.sap.com", "www.tesla.com",
]

console = Console(highlight=False)

# ============ UI ============
LETTERS = {
    "G": [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "O": [" ██████╗ ", "██╔═══██╗", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
}
C1, C2 = (168, 85, 247), (34, 211, 238)  # violet -> cyan


def grad_rgb(p):
    p = max(0.0, min(1.0, p))
    return tuple(int(C1[i] + (C2[i] - C1[i]) * p) for i in range(3))


def grad(p, k=1.0):
    r, g, b = grad_rgb(p)
    return f"#{int(r * k):02x}{int(g * k):02x}{int(b * k):02x}"


def render_word(word):
    rows = [""] * 6
    for ch in word:
        w = max(len(x) for x in LETTERS[ch])
        for i in range(6):
            rows[i] += LETTERS[ch][i].ljust(w)
    return rows


def banner():
    console.clear()
    words = ["GHOSTGATE"] if console.width >= 80 else ["GHOST", "GATE"]
    rows = []
    for i, w in enumerate(words):
        rows += render_word(w)
        if i < len(words) - 1:
            rows.append("")
    width = max(len(r) for r in rows)
    if console.width < width + 2:
        console.print(Text("G H O S T G A T E", style=f"bold {grad(0.5)}"), justify="center")
    else:
        t = Text()
        h = len(rows)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch == " ":
                    t.append(" ")
                    continue
                p = x / width * 0.75 + y / h * 0.25
                if ch == "█":
                    t.append(ch, style=f"bold {grad(p)}")
                else:
                    t.append(ch, style=grad(p, 0.45))  # darker "shadow" edges
            t.append("\n")
        console.print(Align.center(t))
        line = Text()
        n = min(width, console.width - 4)
        for i in range(n):
            line.append("━", style=grad(i / n))
        console.print(Align.center(line))
    console.print(Align.center(Text("S T E A L T H   T U N N E L S   ·   Z E R O   C O N F I G",
                                    style="grey58")), end="\n")
    sub = Text()
    sub.append(" VLESS ", style="bold white on #7c3aed")
    sub.append(" REALITY ", style="bold black on #22d3ee")
    sub.append(" FULL AUTO ", style="bold white on #0f766e")
    sub.append(f"  v{VERSION}", style="grey50")
    console.print(Align.center(sub))
    console.print()


def ok(m): console.print(f"  [bold green]✔[/] {m}")
def info(m): console.print(f"  [bold cyan]●[/] {m}")
def warn(m): console.print(f"  [bold yellow]▲[/] {m}")
def err(m): console.print(f"  [bold red]✖[/] {m}")


_step = {"n": 0, "total": 0}


def steps(total):
    _step["n"], _step["total"] = 0, total


def step(title):
    _step["n"] += 1
    console.print()
    console.print(Rule(
        f"[bold #a855f7]STEP {_step['n']}/{_step['total']}[/]  [bold white]{title}[/]",
        style="grey30", align="left"))


def ask(prompt, default=None):
    v = Prompt.ask(f"  [bold #a855f7]❯[/] {prompt}",
                   default=str(default) if default is not None else "",
                   show_default=default is not None, console=console)
    return v.strip()


def yesno(prompt, default=True):
    return Confirm.ask(f"  [bold #a855f7]❯[/] {prompt}", default=default, console=console)


def pause():
    console.input("\n  [grey50]Press Enter to continue…[/]")


def run(cmd, timeout=600):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def spin(label, cmd, timeout=600):
    with console.status(f"[cyan]{label}[/]", spinner="dots"):
        return run(cmd, timeout)


# ============ System ============
def need_root():
    if os.geteuid() != 0:
        err("Run as root:  [bold]sudo python3 ghostgate.py[/]")
        sys.exit(1)


def pkg_manager():
    for pm in ("apt-get", "dnf", "yum", "apk"):
        if shutil.which(pm):
            return pm
    return None


def read_os():
    try:
        d = dict(l.strip().split("=", 1) for l in open("/etc/os-release") if "=" in l)
        return d.get("PRETTY_NAME", "linux").strip('"')
    except Exception:
        return platform.platform()


def has_internet():
    for host in ("1.1.1.1", "8.8.8.8", "9.9.9.9"):
        try:
            socket.create_connection((host, 443), timeout=4).close()
            return True
        except Exception:
            continue
    return False


def can_reach_github():
    try:
        urllib.request.urlopen("https://github.com", timeout=8)
        return True
    except Exception:
        return False


def port_owner(port):
    out = run(f"ss -tlnpH 'sport = :{port}'").stdout.strip()
    if not out:
        return None
    m = re.search(r'users:\(\("([^"]+)"', out)
    return m.group(1) if m else "unknown"


# ============ Steps ============
def preflight():
    step("Preflight checks")
    ram = run("free -m | awk '/Mem:/{print $2}'").stdout.strip()
    disk = run("df -h / | awk 'NR==2{print $4}'").stdout.strip()
    t = Table.grid(padding=(0, 2))
    t.add_column(style="grey62")
    t.add_column(style="bold white")
    t.add_row("System", read_os())
    t.add_row("Arch", platform.machine())
    t.add_row("Memory", f"{ram} MB")
    t.add_row("Disk free", disk)
    t.add_row("Python", platform.python_version())
    console.print(Panel(t, box=box.ROUNDED, border_style="grey37", padding=(0, 2),
                        title="[grey62]server[/]", title_align="left"))
    pm = pkg_manager()
    if not pm:
        err("No supported package manager (apt / dnf / yum / apk).")
        return False
    ok(f"Package manager: [bold]{pm}[/]")
    if run("command -v systemctl").returncode != 0:
        err("systemd is required.")
        return False
    ok("systemd available")
    with console.status("[cyan]Checking connectivity…[/]", spinner="dots"):
        net = has_internet()
        gh = can_reach_github() if net else False
    if not net:
        err("Server has no internet access.")
        return False
    ok("Internet reachable")
    (ok if gh else warn)("GitHub reachable" if gh else "GitHub unreachable, Xray install may fail")
    return True


def install_prereqs():
    step("Installing prerequisites")
    pm = pkg_manager()
    if pm == "apt-get":
        pkgs = ["curl", "wget", "openssl", "ca-certificates", "unzip", "tar", "qrencode", "iproute2", "chrony"]
        install = lambda p: run(f"DEBIAN_FRONTEND=noninteractive apt-get install -y {p}")
        spin("Updating package index…", "DEBIAN_FRONTEND=noninteractive apt-get update -y")
    elif pm in ("dnf", "yum"):
        pkgs = ["curl", "wget", "openssl", "ca-certificates", "unzip", "tar", "iproute", "chrony"]
        install = lambda p: run(f"{pm} install -y {p}")
    else:
        pkgs = ["curl", "wget", "openssl", "ca-certificates", "unzip", "tar", "libqrencode-tools"]
        install = lambda p: run(f"apk add --no-cache {p}")
    results = []
    with Progress(SpinnerColumn(style="#a855f7"), TextColumn("{task.description}"),
                  BarColumn(bar_width=None, complete_style="#a855f7", finished_style="green"),
                  TextColumn("[grey62]{task.completed}/{task.total}"),
                  console=console, transient=True) as prog:
        t = prog.add_task("starting", total=len(pkgs))
        for p in pkgs:
            prog.update(t, description=f"Installing [cyan]{p}[/]")
            results.append((p, install(p).returncode == 0))
            prog.advance(t)
    if pm in ("dnf", "yum"):
        run(f"{pm} install -y epel-release && {pm} install -y qrencode")
    chips = [f"[green]✔[/] {p}" if good else f"[yellow]▲[/] {p}" for p, good in results]
    console.print(Columns(chips, padding=(0, 3), equal=True), style="grey85")
    return True


def sync_time():
    step("Clock sync  [grey50](Reality needs accurate time)[/]")
    run("timedatectl set-ntp true")
    run("systemctl enable --now chrony chronyd")
    time.sleep(2)
    out = run("timedatectl").stdout
    if re.search(r"synchronized:\s*yes", out, re.I):
        ok("Clock synchronized")
    else:
        warn("Not yet synchronized (will sync shortly)")
    info("Server time (UTC): [bold]" + time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + "[/]")


def enable_bbr():
    step("Network tuning  [grey50](BBR + fq + TCP fast open)[/]")
    cur = run("sysctl -n net.ipv4.tcp_congestion_control").stdout.strip()
    if cur == "bbr":
        ok("BBR already enabled")
        return
    open("/etc/sysctl.d/99-ghostgate.conf", "w").write(
        "net.core.default_qdisc=fq\nnet.ipv4.tcp_congestion_control=bbr\nnet.ipv4.tcp_fastopen=3\n")
    run("sysctl --system")
    now = run("sysctl -n net.ipv4.tcp_congestion_control").stdout.strip()
    (ok if now == "bbr" else warn)(f"Congestion control: [bold]{now}[/]")


def xray_bin():
    return shutil.which("xray") or ("/usr/local/bin/xray" if os.path.exists("/usr/local/bin/xray") else None)


XRAY_INSTALL = 'bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install'


def install_xray():
    step("Xray-core")
    if xray_bin():
        v = run(f"{xray_bin()} version").stdout.splitlines()
        ok("Already installed: [bold]" + esc(v[0] if v else "xray") + "[/]")
        if yesno("Update to latest version?", False):
            spin("Updating Xray…", XRAY_INSTALL)
        return True
    r = spin("Downloading and installing Xray…", XRAY_INSTALL)
    if r.returncode != 0 or not xray_bin():
        err("Xray install failed:\n" + esc((r.stderr or r.stdout)[-500:]))
        return False
    ok("Installed: [bold]" + esc(run(f"{xray_bin()} version").stdout.splitlines()[0]) + "[/]")
    return True


def free_port(preferred):
    step("Port selection and conflict check")
    ports = [preferred] + [p for p in PORT_CANDIDATES if p != preferred]
    for p in ports:
        owner = port_owner(p)
        if owner in (None, "xray"):
            ok(f"Port [bold]{p}[/] is free" + (" (used by old xray)" if owner else ""))
            return p
        warn(f"Port {p} is used by [bold]{esc(owner)}[/]")
        if owner in ("nginx", "apache2", "httpd", "caddy") and p == preferred:
            if yesno(f"Stop {owner} to free port {p}?", False):
                run(f"systemctl stop {owner}")
                run(f"systemctl disable {owner}")
                if port_owner(p) is None:
                    ok(f"{owner} stopped, port {p} is free")
                    return p
    err("No free port found.")
    return None


def open_firewall(port):
    step("Firewall")
    done = False
    if shutil.which("ufw"):
        if "inactive" in run("ufw status").stdout.lower():
            info("ufw installed but inactive (nothing blocked)")
        else:
            run(f"ufw allow {port}/tcp")
            ok(f"ufw: allowed [bold]{port}/tcp[/]")
        done = True
    if shutil.which("firewall-cmd") and run("firewall-cmd --state").stdout.strip() == "running":
        run(f"firewall-cmd --permanent --add-port={port}/tcp")
        run("firewall-cmd --reload")
        ok(f"firewalld: allowed [bold]{port}/tcp[/]")
        done = True
    if "policy DROP" in run("iptables -L INPUT -n | head -1").stdout:
        run(f"iptables -I INPUT -p tcp --dport {port} -j ACCEPT")
        ok(f"iptables: allowed [bold]{port}/tcp[/]")
        done = True
    if not done:
        ok("No local firewall is blocking")
    warn("If your host has a cloud firewall / security group, open the port there too.")


# ============ SNI ============
def test_sni(host, timeout=4):
    try:
        ctx = ssl.create_default_context()
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        t = time.time()
        with socket.create_connection((host, 443), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                if ss.version() == "TLSv1.3" and ss.selected_alpn_protocol() == "h2":
                    return host, round((time.time() - t) * 1000)
    except Exception:
        pass
    return host, None


def rank_snis(show=True):
    res = []
    with Progress(SpinnerColumn(style="#22d3ee"), TextColumn("[cyan]Probing SNIs (TLS 1.3 + h2)[/]"),
                  BarColumn(bar_width=None, complete_style="#22d3ee", finished_style="green"),
                  TextColumn("[grey62]{task.completed}/{task.total}"),
                  console=console, transient=True) as prog:
        t = prog.add_task("p", total=len(SNI_LIST))
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = [ex.submit(test_sni, h) for h in SNI_LIST]
            for f in as_completed(futs):
                res.append(f.result())
                prog.advance(t)
    good = sorted([r for r in res if r[1] is not None], key=lambda x: x[1])
    bad = [r for r in res if r[1] is None]
    if show:
        tb = Table(box=box.ROUNDED, border_style="grey37", header_style="bold grey62", pad_edge=True)
        tb.add_column("#", justify="right", style="grey50")
        tb.add_column("SNI", style="white")
        tb.add_column("Latency", min_width=18)
        tb.add_column("", justify="right")
        top = max([ms for _, ms in good] or [1])
        for i, (h, ms) in enumerate(good, 1):
            n = max(1, int(14 * ms / top))
            bar = f"[{'green' if i == 1 else '#22d3ee'}]{'█' * n}[/][grey23]{'█' * (14 - n)}[/]"
            tag = "[bold green]★ best[/]" if i == 1 else ""
            tb.add_row(str(i), f"[bold green]{h}[/]" if i == 1 else h, f"{bar} [grey62]{ms} ms[/]", tag)
        for h, _ in bad:
            tb.add_row("–", f"[grey50]{h}[/]", "[red]unreachable[/]", "")
        console.print(tb)
    return [h for h, _ in good]


# ============ Config ============
def gen_keys():
    out = run(f"{xray_bin()} x25519").stdout
    priv = re.search(r"Private\s*Key\s*:\s*(\S+)", out, re.I)
    pub = re.search(r"(?:Public\s*Key|Password(?:\s*\(PublicKey\))?)\s*:\s*(\S+)", out, re.I)
    if not (priv and pub):
        raise RuntimeError("Could not parse x25519 output:\n" + out)
    return priv.group(1), pub.group(1)


def server_ip():
    with console.status("[cyan]Detecting public IP…[/]", spinner="dots"):
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
            try:
                return urllib.request.urlopen(url, timeout=5).read().decode().strip()
            except Exception:
                continue
    return ask("Could not detect server IP, enter it")


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return None


def save_state(s):
    os.makedirs(XRAY_DIR, exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=2)
    os.chmod(STATE, 0o600)


def build_config(s):
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [{
            "listen": "0.0.0.0", "port": s["port"], "protocol": "vless",
            "settings": {"clients": [{"id": s["uuid"], "flow": "xtls-rprx-vision"}],
                         "decryption": "none"},
            "streamSettings": {
                "network": "tcp", "security": "reality",
                "realitySettings": {
                    "dest": f"{s['sni']}:443", "serverNames": [s["sni"]],
                    "privateKey": s["private"], "shortIds": [s["short_id"]],
                },
            },
            "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"]},
        }],
        "outbounds": [{"protocol": "freedom"}],
    }


def apply(s):
    step("Writing config and starting service")
    os.makedirs(XRAY_DIR, exist_ok=True)
    if os.path.exists(XRAY_CONF):
        bak = f"{XRAY_CONF}.bak.{int(time.time())}"
        shutil.copy(XRAY_CONF, bak)
        ok(f"Old config backed up → [grey62]{bak}[/]")
    json.dump(build_config(s), open(XRAY_CONF, "w"), indent=2)
    ok(f"Config written → [grey62]{XRAY_CONF}[/]")
    t = run(f"{xray_bin()} run -test -config {XRAY_CONF}")
    if t.returncode != 0:
        err("Config test failed:\n" + esc((t.stdout + t.stderr)[-500:]))
        return False
    ok("Config syntax test passed")
    run("systemctl daemon-reload")
    run("systemctl enable xray")
    with console.status("[cyan]Restarting Xray…[/]", spinner="dots"):
        run("systemctl restart xray")
        time.sleep(2)
    if run("systemctl is-active xray").stdout.strip() != "active":
        err("Xray is not running:\n" + esc(run("journalctl -u xray -n 15 --no-pager").stdout))
        return False
    ok("Service is [bold green]active[/] and enabled on boot")
    save_state(s)
    return True


def verify(s):
    step("Post-install verification")
    tb = Table(box=box.ROUNDED, border_style="grey37", show_header=False, pad_edge=True)
    tb.add_column(style="grey62")
    tb.add_column()
    o = port_owner(s["port"])
    tb.add_row("Listening", f"[green]✔ {o}[/] on port {s['port']}" if o == "xray" else f"[red]✖ {o}[/]")
    try:
        socket.create_connection((s["ip"], s["port"]), timeout=5).close()
        tb.add_row("Self-connect", f"[green]✔ {s['ip']}:{s['port']}[/]")
    except Exception as e:
        tb.add_row("Self-connect", f"[yellow]▲ failed ({esc(str(e))})[/]")
    _, ms = test_sni(s["sni"])
    tb.add_row("SNI handshake", f"[green]✔ {s['sni']} · {ms} ms[/]" if ms else f"[yellow]▲ {s['sni']} unreachable[/]")
    console.print(tb)


def make_link(s, sni=None, name="GhostGate"):
    sni = sni or s["sni"]
    q = urllib.parse.urlencode({
        "security": "reality", "encryption": "none", "flow": "xtls-rprx-vision",
        "type": "tcp", "sni": sni, "fp": "chrome",
        "pbk": s["public"], "sid": s["short_id"],
    })
    return f"vless://{s['uuid']}@{s['ip']}:{s['port']}?{q}#{urllib.parse.quote(name + '-' + sni)}"


def show_link(s):
    link = make_link(s)
    open(LINK_FILE, "w").write(link + "\n")
    info_t = Table.grid(padding=(0, 3))
    info_t.add_column(style="grey62")
    info_t.add_column(style="bold white")
    info_t.add_row("Server", s["ip"])
    info_t.add_row("Port", str(s["port"]))
    info_t.add_row("SNI", s["sni"])
    info_t.add_row("Flow", "xtls-rprx-vision")
    info_t.add_row("Fingerprint", "chrome")
    console.print()
    console.print(Panel(Group(info_t, Text(), Text(link, style="bold #4ade80", overflow="fold")),
                        title="[bold #a855f7] ◆ CLIENT LINK [/]", title_align="left",
                        subtitle="[grey50]v2rayNG → + → Import config from clipboard[/]",
                        box=box.HEAVY, border_style="#a855f7", padding=(1, 2)))
    if shutil.which("qrencode"):
        subprocess.run(["qrencode", "-t", "ANSIUTF8", link])
    console.print(f"  [grey50]Saved to {LINK_FILE}  ·  keep your phone's v2rayNG up to date[/]")


# ============ Actions ============
def full_auto():
    banner()
    t0 = time.time()
    steps(11)
    if not preflight():
        return
    install_prereqs()
    sync_time()
    enable_bbr()
    if not install_xray():
        return
    port = free_port(int(ask("Port [grey50](8443 works on most ISPs)[/]", 8443)))
    if not port:
        return
    step("Finding the best SNI")
    good = rank_snis()
    if not good:
        err("No SNI passed the test.")
        return
    sni = good[0]
    ok(f"Selected: [bold green]{sni}[/]")
    step("Generating identity")
    priv, pub = gen_keys()
    s = {"uuid": str(uuid.uuid4()), "private": priv, "public": pub,
         "short_id": secrets.token_hex(8), "port": port, "sni": sni, "ip": server_ip()}
    ok(f"UUID     [grey62]{s['uuid']}[/]")
    ok(f"ShortID  [grey62]{s['short_id']}[/]")
    ok(f"Server   [grey62]{s['ip']}[/]")
    open_firewall(port)
    if not apply(s):
        return
    verify(s)
    show_link(s)
    console.print(f"\n  [bold green]All done in {round(time.time() - t0)}s[/]")


def change_sni():
    s = load_state()
    if not s:
        warn("No setup found. Run full auto setup first.")
        return
    steps(2)
    step("Choose new SNI")
    console.print(f"  Current: [bold yellow]{s['sni']}[/]\n")
    console.print("  [cyan]1[/] Auto-pick best    [cyan]2[/] Pick from list    [cyan]3[/] Enter manually\n")
    ch = Prompt.ask("  [bold #a855f7]❯[/] Choice", choices=["1", "2", "3"], default="1", console=console)
    good = rank_snis() if ch in ("1", "2") else []
    if ch == "1" and good:
        s["sni"] = good[0]
    elif ch == "2" and good:
        n = int(ask("Row number", 1))
        s["sni"] = good[max(1, min(n, len(good))) - 1]
    elif ch == "3":
        s["sni"] = ask("SNI")
    else:
        err("Nothing selected")
        return
    if apply(s):
        show_link(s)


def change_port():
    s = load_state()
    if not s:
        warn("No setup found.")
        return
    steps(3)
    p = free_port(int(ask("New port", 2053)))
    if not p:
        return
    s["port"] = p
    open_firewall(p)
    if apply(s):
        show_link(s)


def multi_links():
    s = load_state()
    if not s:
        warn("No setup found.")
        return
    steps(1)
    step("Candidate SNI links for phone testing")
    good = rank_snis(show=False)[:5]
    info("Server accepts only its current SNI. Apply a winner via [bold]Change SNI[/].")
    for h in good:
        console.print(Panel(Text(make_link(s, h), style="green", overflow="fold"),
                            title=f"[bold yellow]{h}[/]", title_align="left",
                            box=box.ROUNDED, border_style="grey37"))


def reset_keys():
    s = load_state()
    if not s:
        warn("No setup found.")
        return
    steps(1)
    s["uuid"] = str(uuid.uuid4())
    s["private"], s["public"] = gen_keys()
    s["short_id"] = secrets.token_hex(8)
    if apply(s):
        show_link(s)


def status():
    s = load_state()
    active = run("systemctl is-active xray").stdout.strip()
    style = "green" if active == "active" else "red"
    console.print(Panel(f"[bold {style}]● {active}[/]" + (f"   {s['ip']}:{s['port']}   {s['sni']}" if s else ""),
                        title="[grey62]xray.service[/]", title_align="left", box=box.ROUNDED, border_style="grey37"))
    console.print(Panel(esc(run("journalctl -u xray -n 12 --no-pager").stdout.strip() or "no logs"),
                        title="[grey62]last logs[/]", title_align="left", box=box.ROUNDED,
                        border_style="grey37", style="grey70"))


def uninstall():
    if not yesno("Remove Xray and all GhostGate data?", False):
        return
    run("systemctl stop xray; systemctl disable xray")
    spin("Removing Xray…", XRAY_INSTALL.replace("@ install", "@ remove --purge"))
    for f in (STATE, LINK_FILE):
        if os.path.exists(f):
            os.remove(f)
    ok("Removed.")


# ============ Menu ============
def status_bar():
    s = load_state()
    active = run("systemctl is-active xray").stdout.strip() == "active"
    g = Table.grid(expand=True, padding=(0, 2))
    if s:
        g.add_column(justify="left")
        g.add_column(justify="center")
        g.add_column(justify="right")
        dot = "[bold green]● ONLINE[/]" if active else "[bold red]○ OFFLINE[/]"
        g.add_row(dot, f"[white]{s['ip']}[/][grey50]:[/][cyan]{s['port']}[/]", f"[grey62]SNI[/] [white]{s['sni']}[/]")
    else:
        g.add_column(justify="center")
        g.add_row("[grey62]No config yet, start with[/] [bold #a855f7]⚡ Full auto setup[/]")
    console.print(Panel(g, box=box.ROUNDED, border_style="grey37", padding=(0, 2)))


MENU = [
    ("1", "⚡", "Full auto setup", "prereqs · xray · best SNI · link", full_auto),
    ("2", "⇄", "Change SNI", "auto / list / manual", change_sni),
    ("3", "◈", "Show client link", "+ QR code", None),
    ("4", "⚙", "Change port", "", change_port),
    ("5", "◎", "Candidate links", "test SNIs on your phone", multi_links),
    ("6", "⟳", "Regenerate keys", "new UUID + x25519", reset_keys),
    ("7", "▤", "Status and logs", "", status),
    ("8", "✖", "Uninstall", "", uninstall),
    ("0", "⏻", "Exit", "", None),
]


def menu():
    while True:
        banner()
        status_bar()
        tb = Table.grid(padding=(0, 2))
        tb.add_column(justify="right")
        tb.add_column()
        tb.add_column()
        tb.add_column()
        for k, ico, name, desc, _ in MENU:
            kc = "bold red" if k == "0" else "bold black on #22d3ee"
            tb.add_row(f"[{kc}] {k} [/]", f"[#a855f7]{ico}[/]", f"[bold white]{name}[/]", f"[grey50]{desc}[/]")
        console.print(Panel(tb, box=box.ROUNDED, border_style="#7c3aed", padding=(1, 3),
                            title="[bold white] MENU [/]", title_align="left"))
        ch = Prompt.ask("  [bold #a855f7]❯[/] Select", choices=[m[0] for m in MENU],
                        show_choices=False, console=console)
        console.print()
        try:
            if ch == "0":
                console.print("  [grey50]Bye 👻[/]\n")
                break
            if ch == "3":
                s = load_state()
                show_link(s) if s else warn("No setup found.")
            else:
                dict((m[0], m[4]) for m in MENU)[ch]()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            err(esc(str(e)))
        pause()


if __name__ == "__main__":
    need_root()
    menu()
