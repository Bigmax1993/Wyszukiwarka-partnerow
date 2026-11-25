# -*- coding: utf-8 -*-
"""
Wdrożenie Wyszukiwarka-partnerow na Contabo VPS.

Host: 109.199.122.178 (ten sam co FAS)
Katalog: /opt/bots/Wyszukiwarka-partnerow
Klucz: ~/.ssh/id_ed25519_small

Użycie (z rootu repo):
  python scripts/deploy_contabo.py
  python scripts/deploy_contabo.py --skip-smoke
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

HOST = "109.199.122.178"
USER = "root"
KEY = Path.home() / ".ssh" / "id_ed25519_small"
LOCAL = Path(__file__).resolve().parents[1]
REMOTE = "/opt/bots/Wyszukiwarka-partnerow"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".cursor",
    "agent-transcripts",
    # Dane runtime na serwerze — nigdy nie nadpisuj z lokalnego laptopa
    "Wyniki",
    "wyslane",
    "logs",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo", ".log")
EXCLUDE_FILE_NAMES = {
    "contabo-root-pass.txt",
    ".DS_Store",
}


def _read_env(name: str) -> str:
    """Odczyt User → Process env (Windows-friendly)."""
    try:
        import winreg

        for root in (winreg.HKEY_CURRENT_USER,):
            try:
                with winreg.OpenKey(root, r"Environment") as key:
                    val, _ = winreg.QueryValueEx(key, name)
                    if val and str(val).strip():
                        return str(val).strip()
            except OSError:
                pass
    except ImportError:
        pass
    return (os.environ.get(name) or "").strip()


def build_dotenv() -> str:
    """Buduje .env Contabo z lokalnych zmiennych użytkownika."""
    serper = _read_env("SERPER_API_KEY")
    anth = _read_env("ANTHROPIC_API_KEY")
    gmail_user = _read_env("GMAIL_USER")
    gmail_pass = _read_env("GMAIL_APP_PASSWORD")
    mail_user = _read_env("MAIL_USER") or gmail_user
    mail_pass = _read_env("MAIL_PASSWORD") or gmail_pass
    excel_to = _read_env("EXCEL_REPORT_TO") or "svinchak1993@gmail.com"

    missing = [k for k, v in (("SERPER_API_KEY", serper), ("ANTHROPIC_API_KEY", anth)) if not v]
    if missing:
        raise SystemExit(f"Brak wymaganych zmiennych env: {', '.join(missing)}")

    lines = [
        "# Wygenerowane przez scripts/deploy_contabo.py — nie commitować",
        # B2B OFF na Contabo (unikamy dubli z GHA). Excel ON — pon 07:30 Contabo.
        "DISABLE_CONTRACTOR_EMAILS=1",
        "DISABLE_GOOGLE_DRIVE=1",
        "DISABLE_EXCEL_REPORT_EMAIL=0",
        "DISABLE_PIPELINE_NOTIFY=0",
        f"EXCEL_REPORT_TO={excel_to}",
        f"PIPELINE_NOTIFY_TO={excel_to}",
        "SCRAPER_TIMEZONE=Europe/Warsaw",
        "SERPER_DAILY_LIMIT=1000",
        f"SERPER_API_KEY={serper}",
        f"ANTHROPIC_API_KEY={anth}",
        f"MAIL_USER={mail_user}",
        f"MAIL_PASSWORD={mail_pass}",
        f"GMAIL_USER={gmail_user}",
        f"GMAIL_APP_PASSWORD={gmail_pass}",
        'MAIL_SENDER_NAME="FAS Spedycja"',
        f"KANBUD_PROJECT_ROOT={REMOTE}/libs",
        "FAS_EMAIL_ATTACHMENT_PATH=assets/campaign/FAS_zalacznik_kampania.pptx",
        "FAS_EMAIL_ATTACHMENT_EXTRA_PATH=assets/campaign/FAS_prezentacja.pptx",
    ]
    for opt in (
        "GDRIVE_FOLDER_ID",
        "GDRIVE_OAUTH_CLIENT_ID",
        "GDRIVE_OAUTH_CLIENT_SECRET",
        "GDRIVE_OAUTH_REFRESH_TOKEN",
        "CLAUDE_MODEL_FAST",
        "CLAUDE_MODEL_VERIFY",
    ):
        val = _read_env(opt)
        if val:
            lines.append(f"{opt}={val}")
    return "\n".join(lines) + "\n"


def should_exclude(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    name = rel.name
    if name in EXCLUDE_FILE_NAMES:
        return True
    if name.startswith("._"):
        return True
    if name.endswith(EXCLUDE_FILE_SUFFIXES):
        return True
    if name.startswith("_tmp_"):
        return True
    return False


def make_archive(dest: Path) -> int:
    count = 0
    with tarfile.open(dest, "w:gz") as tar:
        for path in LOCAL.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(LOCAL)
            if should_exclude(rel):
                continue
            arcname = str(rel).replace("\\", "/")
            # Skrypty bash z Windowsa → LF (inaczej bash: `set: pipefail\r`)
            if path.suffix == ".sh" or "schedule/contabo/" in arcname:
                data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                info.mode = 0o755
                tar.addfile(info, io.BytesIO(data))
            else:
                tar.add(path, arcname=arcname)
            count += 1
    return count


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 600) -> tuple[int, str]:
    print("$", cmd[:200])
    _, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", "replace")
    err = e.read().decode("utf-8", "replace")
    code = o.channel.recv_exit_status()
    text = (out + (("\n" + err) if err.strip() else "")).encode("ascii", "replace").decode(
        "ascii"
    )
    if text.strip():
        print(text[-12000:])
    print("exit", code)
    return code, text


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Wyszukiwarka-partnerow → Contabo")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--skip-crontab", action="store_true")
    args = parser.parse_args()

    if not KEY.is_file():
        raise SystemExit(f"Brak klucza SSH: {KEY}")

    dotenv = build_dotenv()
    print("ENV keys gotowe (B2B OFF, Drive OFF, Excel ON)")

    with tempfile.TemporaryDirectory(prefix="wp_contabo_") as tmp:
        archive = Path(tmp) / "payload.tgz"
        nfiles = make_archive(archive)
        size_mb = archive.stat().st_size / (1024 * 1024)
        print(f"Archiwum: {nfiles} plikow, {size_mb:.1f} MB")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            HOST,
            username=USER,
            key_filename=str(KEY),
            look_for_keys=False,
            allow_agent=False,
            timeout=30,
        )
        print("SSH_OK", HOST)

        remote_tgz = "/tmp/wyszukiwarka-partnerow-deploy.tgz"
        sftp = client.open_sftp()
        print("UPLOAD", remote_tgz)
        sftp.put(str(archive), remote_tgz)
        # .env osobno — nie w tarze z lokalnego (może go nie być)
        try:
            sftp.stat(REMOTE)
        except OSError:
            run(client, f"mkdir -p {REMOTE}")
        with sftp.file(f"{REMOTE}/.env", "w") as f:
            f.write(dotenv)
        sftp.chmod(f"{REMOTE}/.env", 0o600)
        sftp.close()
        print("PUT .env")

        code, _ = run(
            client,
            f"""
set -e
mkdir -p {REMOTE} /opt/bots
# zachowaj lokalne Wyniki/logs na serwerze jeśli już są
if [ -d {REMOTE}/Wyniki ]; then cp -a {REMOTE}/Wyniki /tmp/wp_wyniki_bak || true; fi
if [ -d {REMOTE}/logs ]; then cp -a {REMOTE}/logs /tmp/wp_logs_bak || true; fi
tar -xzf {remote_tgz} -C {REMOTE}
rm -f {remote_tgz}
if [ -d /tmp/wp_wyniki_bak ]; then
  mkdir -p {REMOTE}/Wyniki
  cp -an /tmp/wp_wyniki_bak/. {REMOTE}/Wyniki/ || true
  rm -rf /tmp/wp_wyniki_bak
fi
if [ -d /tmp/wp_logs_bak ]; then
  mkdir -p {REMOTE}/logs
  cp -an /tmp/wp_logs_bak/. {REMOTE}/logs/ || true
  rm -rf /tmp/wp_logs_bak
fi
mkdir -p {REMOTE}/Wyniki {REMOTE}/wyslane {REMOTE}/logs {REMOTE}/assets/campaign
chmod +x {REMOTE}/schedule/contabo/*.sh
# venv
if [ ! -x {REMOTE}/.venv/bin/python ]; then
  python3 -m venv {REMOTE}/.venv
fi
{REMOTE}/.venv/bin/pip install -U pip wheel
{REMOTE}/.venv/bin/pip install -r {REMOTE}/requirements.txt
# Playwright + system deps (idempotent)
{REMOTE}/.venv/bin/playwright install-deps chromium || true
{REMOTE}/.venv/bin/playwright install chromium
# Chrome/Chromium pod Selenium Google Maps discovery
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq chromium-browser chromium-chromedriver 2>/dev/null \
  || apt-get install -y -qq chromium chromium-driver 2>/dev/null \
  || true
# Prefer system chromium; fallback: Playwright chrome binary via CHROME_BIN
if [ -x /usr/bin/chromium ]; then echo CHROME_BIN=/usr/bin/chromium >> {REMOTE}/.env.chrome; fi
if [ -x /usr/bin/chromium-browser ]; then echo CHROME_BIN=/usr/bin/chromium-browser >> {REMOTE}/.env.chrome; fi
if [ -x /usr/bin/google-chrome ]; then echo CHROME_BIN=/usr/bin/google-chrome >> {REMOTE}/.env.chrome; fi
echo DEPLOY_FILES_OK
""",
            timeout=900,
        )
        if code != 0:
            client.close()
            return code

        if not args.skip_crontab:
            code, _ = run(
                client,
                f"bash {REMOTE}/schedule/contabo/install_crontab.sh",
                timeout=60,
            )
            if code != 0:
                client.close()
                return code

        if not args.skip_smoke:
            code, _ = run(
                client,
                f"""
set -e
cd {REMOTE}
set -a; source .env; set +a
export KANBUD_PROJECT_ROOT={REMOTE}/libs
.venv/bin/python pl_fas_spedycja_scraper.py --test
.venv/bin/python -c "import pl_spedycja_keywords, pl_spedycja_filter; print('IMPORT_OK')"
echo SMOKE_OK
""",
                timeout=180,
            )
            if code != 0:
                client.close()
                return code

        run(
            client,
            f"ls -la {REMOTE} | head -40; echo '---'; du -sh {REMOTE}; echo '---'; crontab -l | sed -n '/wyszukiwarka-partnerow/,/END wyszukiwarka/p'",
            timeout=30,
        )
        client.close()

    print(f"\nGOTOWE: {USER}@{HOST}:{REMOTE}")
    print("Harmonogram: pon-pt 07:00 discovery | nd 06:00 backfill | pon/wt 09:00 send (B2B OFF) | nd 09:00 Excel")
    print("B2B: DISABLE_CONTRACTOR_EMAILS=1 (żeby nie dublować z GHA). Zmień w .env na 0 gdy przełączysz produkcję.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
