# GhostGate

Full-auto **Xray VLESS + Reality** setup tool with a modern terminal UI and a smart SNI picker.

One command installs prerequisites, installs Xray, finds the best working SNI, generates keys, configures the firewall, and prints a ready-to-import client link with a QR code.

## Features

- Automatic prerequisites (curl, openssl, chrony, qrencode, ...)
- Clock sync and BBR network tuning
- Xray-core install via the official XTLS installer
- Tests 20 SNI candidates (TLS 1.3 + h2) and picks the fastest
- Port conflict detection (nginx/apache) with safe fallbacks (8443, 2053, 2083, ...)
- Auto firewall rules (ufw, firewalld, iptables)
- Generates UUID, x25519 keys, shortId
- Config backup before every change, config test before restart
- Menu: change SNI, change port, regenerate keys, status/logs, uninstall

## Requirements

- A VPS with root access and a public IP
- Ubuntu / Debian recommended (also supports dnf, yum, apk)
- Python 3.8+ and systemd
- A truecolor-capable terminal for the best look (most modern SSH apps)

## Quick start

### Option 1: one-line command

Run it straight from the repo:

```bash
curl -fsSL https://raw.githubusercontent.com/Agravix/GhostGate/main/ghostgate.py -o ghostgate.py && sudo python3 ghostgate.py
```

### Option 2: wget

```bash
wget -O ghostgate.py https://raw.githubusercontent.com/Agravix/GhostGate/main/ghostgate.py
sudo python3 ghostgate.py
```

### Option 3: copy the file from your computer

```bash
scp ghostgate.py root@YOUR_SERVER_IP:/root/
ssh root@YOUR_SERVER_IP
python3 ghostgate.py
```

### Option 4: paste manually

```bash
nano ghostgate.py      # paste the code, save with Ctrl+O, exit with Ctrl+X
sudo python3 ghostgate.py
```

If Python is missing:

```bash
apt update && apt install -y python3
```

## Usage

1. Run the tool and choose **1) Full auto setup**.
2. Press Enter to accept port `8443` (works on most ISPs) or type another.
3. Copy the `vless://` link it prints, or scan the QR code.
4. In **v2rayNG**: `+` → *Import config from clipboard* → connect.

The link is also saved to `/root/ghostgate_link.txt`. Show it again anytime with menu option **3**.

## If it doesn't connect

| Problem | Fix |
|---|---|
| Ping/real-delay times out, but server is fine | Use menu **2** (Change SNI) or **4** (Change port), then re-import the new link |
| Works on one network but not another | Try a different SNI (menu **5** gives candidate links) |
| Client error "failed to start service" | Update v2rayNG to the latest version, delete the old profile, re-import |
| Nothing reaches the server | Open the port in your hosting provider's own firewall / security group |

Tip: the SNI test runs from the server, so it only proves the SNI is healthy there. The best SNI for your ISP must be confirmed on your phone.

## Files

| Path | Purpose |
|---|---|
| `/usr/local/etc/xray/config.json` | Xray config (backed up on every change) |
| `/usr/local/etc/xray/ghostgate.json` | Saved keys and settings (chmod 600) |
| `/root/ghostgate_link.txt` | Your client link |

## Security notes

- Never share your private key, UUID, or client link publicly.
- Use menu **6** to regenerate keys if anything leaks.
- Use this tool only on servers you own, and follow the laws of your country and your hosting provider's terms.

## Uninstall

Menu option **8**, or manually:

```bash
bash -c "$(curl -fsSL https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ remove --purge
```

## Credits

Built on [Xray-core](https://github.com/XTLS/Xray-core) and the [Xray-install](https://github.com/XTLS/Xray-install) script. UI powered by [rich](https://github.com/Textualize/rich).
