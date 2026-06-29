# mc-shot-sync

**Auto-detect new Minecraft screenshots → copy to clipboard → commit & push to a public GitHub repo.**
Cross-platform (Windows · Linux · macOS), with a one-command installer and a system-tray GUI helper.

Take a screenshot in Minecraft (default `F2`). A second later it's on your clipboard ready to paste into Discord/chat, **and** committed and pushed to your own public GitHub repo — a permanent, shareable gallery of your shots.

---

## What it does

When a new image appears in your Minecraft `screenshots/` folder, mc-shot-sync:

1. **Copies the image to your system clipboard** (paste straight into Discord, docs, chat…).
2. **Copies it into a local git repo**, commits it, and **pushes to GitHub**.

It auto-detects the screenshots folder for vanilla Minecraft and popular launchers (Prism/MultiMC, Modrinth, CurseForge, Flatpak), and the first run can **create the public GitHub repo for you** via the GitHub CLI.

---

## One-command install

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/codingmachineedge/mc-shot-sync/main/install.ps1 | iex
```

### Linux / macOS (bash)

```bash
curl -fsSL https://raw.githubusercontent.com/codingmachineedge/mc-shot-sync/main/install.sh | bash
```

The installer creates an isolated Python virtualenv, installs everything, puts a `mc-shot-sync` launcher on your PATH, and runs the interactive setup (`init`) which detects your screenshots folder and creates the public GitHub repo.

> **From a local clone instead?**
> ```bash
> git clone https://github.com/codingmachineedge/mc-shot-sync.git
> cd mc-shot-sync
> ./install.sh           # or:  ./install.ps1   on Windows
> ```

---

## Prerequisites

- **Python 3.9+**
- **git**
- **[GitHub CLI](https://cli.github.com/) (`gh`)**, logged in (`gh auth login`) — only needed if you want mc-shot-sync to *create* the public repo for you. If you already have a repo, pass `--remote <url>` and you don't need `gh`.
- **Linux clipboard tool** — `wl-clipboard` (Wayland) or `xclip` (X11):
  ```bash
  sudo apt install wl-clipboard      # Wayland
  sudo apt install xclip             # X11
  ```
  Windows and macOS need nothing extra.

---

## Usage

```text
mc-shot-sync init      Detect screenshots, create the public repo, write config
mc-shot-sync tray      Run the system-tray GUI helper (recommended)
mc-shot-sync watch     Run the watcher in the foreground (headless)
mc-shot-sync once FILE Process one image now (test clipboard + push)
mc-shot-sync status    Show current configuration
mc-shot-sync --version
```

### Tray GUI helper

```bash
mc-shot-sync tray
```

A small tray icon (green when watching, grey when stopped) with a menu to:

- Start / stop watching
- Toggle **auto-push** and **copy-to-clipboard**
- Open the repo folder, or the repo on GitHub
- See recent activity (last few synced screenshots)
- Quit

### Setup options

```bash
# Fully automatic: detect folder + create a public repo named after the repo dir
mc-shot-sync init

# Choose the repo name and local folder
mc-shot-sync init --name my-mc-shots --repo-dir ~/MinecraftShots

# Watch a specific folder (e.g. a modded instance)
mc-shot-sync init --watch "~/.local/share/PrismLauncher/instances/Fabric/.minecraft/screenshots"

# Use a repo you already created (no gh needed)
mc-shot-sync init --remote https://github.com/you/my-mc-shots.git

# Configure but don't create any GitHub repo
mc-shot-sync init --no-create
```

---

## How it works

| Concern        | Windows                              | Linux                                  | macOS                         |
| -------------- | ------------------------------------ | -------------------------------------- | ----------------------------- |
| File watching  | `watchdog` (ReadDirectoryChangesW)   | `watchdog` (inotify)                   | `watchdog` (FSEvents)         |
| Clipboard image| PowerShell + `System.Windows.Forms`  | `wl-copy` (Wayland) / `xclip` (X11)    | `osascript` (AppleScript)     |
| Tray GUI       | `pystray` + `Pillow`                 | `pystray` (AppIndicator/GTK)           | `pystray`                     |
| Git push       | `git` + `gh`                         | `git` + `gh`                           | `git` + `gh`                  |

Screenshots are copied into `<repo>/screenshots/` and committed one-per-file with a timestamped message, then pushed to `origin`.

**Config file** (`mc-shot-sync status` prints the exact path):
- Windows: `%APPDATA%\mc-shot-sync\config.json`
- Linux/macOS: `~/.config/mc-shot-sync/config.json`

---

## Auto-start on login (optional)

**Linux (systemd user service):**
```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/mc-shot-sync.service <<'EOF'
[Unit]
Description=mc-shot-sync watcher
[Service]
ExecStart=%h/.local/bin/mc-shot-sync watch
Restart=on-failure
[Install]
WantedBy=default.target
EOF
systemctl --user enable --now mc-shot-sync
```

**Windows:** put a shortcut to `mc-shot-sync tray` in
`shell:startup` (Win+R → `shell:startup`).

---

## Troubleshooting

- **`gh is not authenticated`** — run `gh auth login` (needs the `repo` scope), then re-run `mc-shot-sync init`.
- **Clipboard does nothing on Linux** — install `wl-clipboard` or `xclip` (see prerequisites).
- **Nothing happens on screenshot** — confirm the watched folder with `mc-shot-sync status`; if you use a launcher with per-instance folders, add it with `init --watch <path>`.
- **Push rejected / no remote** — set one with `mc-shot-sync init --remote <git-url>`.

---

## Development

```bash
python -m pip install -e .
python -m pytest -q
```

CI (GitHub Actions) byte-compiles, smoke-tests the CLI, and runs the test suite on Windows + Linux across Python 3.9 and 3.12.

## License

MIT — see [LICENSE](LICENSE).
