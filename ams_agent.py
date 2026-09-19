#!/usr/bin/env python3
"""
AMS Automatisierungs- & Bewerbungs-Agent (eAMS Österreich)
Regionalgeschäftsstelle: AMS Hietzinger Kai | PSTNR: 4368522
Verwaltet persistente Browser-Sessions, Gmail-Benachrichtigungen, Fristen in TASKS.md,
Bewerbungsnachweise in ACTIONS.md und KI-Bewerbungsschreiben via Ollama (qwen2.5:14b).
"""

import sys
import os
import json
import argparse
import subprocess
import urllib.request
import urllib.error
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
AGENTS_DIR = os.path.join(PROJECT_ROOT, ".agents")
TASKS_JSON_PATH = os.path.join(AGENTS_DIR, "tasks.json")
TASKS_MD_PATH = os.path.join(PROJECT_ROOT, "TASKS.md")
ACTIONS_JSON_PATH = os.path.join(AGENTS_DIR, "actions.json")
ACTIONS_MD_PATH = os.path.join(PROJECT_ROOT, "ACTIONS.md")
BROWSER_PROFILE_DIR = os.path.join(PROJECT_ROOT, ".browser-profile")
POSTFACH_DIR = os.path.join(PROJECT_ROOT, "postfach")
BEWERBUNGEN_DIR = os.path.join(PROJECT_ROOT, "bewerbungen")
VERMITTLUNGEN_DIR = os.path.join(PROJECT_ROOT, "vermittlungsvorschlaege")

OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:14b"
DEFAULT_AMS_URL = "https://www.ams.at/arbeitsuchende/meinams/nachrichten/eingang/"
PSTNR = "4368522"
RGS = "AMS Hietzinger Kai"
CANDIDATE_NAME = "Roland Sauer"
CANDIDATE_EMAIL = "r.sauer007@gmail.com"

# ---------------------------------------------------------------------------
# Storage & Data Management
# ---------------------------------------------------------------------------

def ensure_storage():
    for d in [AGENTS_DIR, POSTFACH_DIR, BEWERBUNGEN_DIR, VERMITTLUNGEN_DIR, BROWSER_PROFILE_DIR]:
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(TASKS_JSON_PATH):
        with open(TASKS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)
    if not os.path.exists(ACTIONS_JSON_PATH):
        with open(ACTIONS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2, ensure_ascii=False)

def load_tasks() -> List[Dict[str, Any]]:
    ensure_storage()
    try:
        with open(TASKS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_tasks(tasks: List[Dict[str, Any]]):
    ensure_storage()
    with open(TASKS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

    lines = [
        "# AMS Projektaufgaben (eAMS & Bewerbungs-Taskboard)",
        "",
        f"> Zuletzt synchronisiert: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        "",
        "## Offene Aufgaben",
        ""
    ]

    open_tasks = [t for t in tasks if not t.get("done", False)]
    done_tasks = [t for t in tasks if t.get("done", False)]

    if not open_tasks:
        lines.append("_Aktuell keine offenen Aufgaben vorhanden._\n")
    else:
        for t in open_tasks:
            pri = t.get("priority", "HOCH")
            cat = t.get("category", "eAMS")
            tid = t.get("id", "N/A")
            src = t.get("source_subject", "")
            due = f" | Frist: {t['due_date']}" if t.get("due_date") else ""
            lines.append(f"- [ ] **[#{tid}] [{cat}] [{pri}{due}]** {t.get('title')}")
            if t.get("description"):
                lines.append(f"  - *Details:* {t.get('description')}")
            if src:
                lines.append(f"  - *Quelle:* {src} ({t.get('source_sender', '')})")
            lines.append("")

    lines.append("## Erledigte Aufgaben\n")
    if not done_tasks:
        lines.append("_Keine erledigten Aufgaben._\n")
    else:
        for t in done_tasks:
            tid = t.get("id", "N/A")
            lines.append(f"- [x] **[#{tid}]** {t.get('title')} *(Erledigt am: {t.get('completed_at', 'k.A.')})*")

    with open(TASKS_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def load_actions() -> List[Dict[str, Any]]:
    ensure_storage()
    try:
        with open(ACTIONS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_actions(actions: List[Dict[str, Any]]):
    ensure_storage()
    with open(ACTIONS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(actions, f, indent=2, ensure_ascii=False)

    lines = [
        "# AMS Aktions- & Bewerbungsprotokoll (ACTIONS.md)",
        "",
        f"> Zuletzt synchronisiert: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        "",
        "Lückenloses Nachweisprotokoll aller externen Konversationen, Bewerbungen, eAMS-Eingaben und behördlichen Kontakte (gemäß Vorgabe `RULE[user_global]`). Dient als offizieller AMS-Aktivitäts- und Bewerbungsnachweis.",
        "",
        "---",
        "",
        "## Chronologische Übersicht der Aktionen",
        ""
    ]

    if not actions:
        lines.append("_Bisher keine Aktionen protokolliert._\n")
    else:
        sorted_actions = sorted(actions, key=lambda x: x.get("id", 0), reverse=True)
        for a in sorted_actions:
            aid = a.get("id", "N/A")
            dt = a.get("timestamp", "k.A.")
            channel = a.get("channel", "eAMS")
            status = a.get("status", "Erfasst")
            recipient = a.get("recipient", "AMS Österreich")
            subject = a.get("subject", "Ohne Betreff")
            summary = a.get("summary", "")
            task_id = a.get("task_id")
            msg_id = a.get("message_id")

            lines.append(f"### [#{aid}] {dt} | {channel} | {status}")
            lines.append(f"- **Partner / Organisation:** {recipient}")
            lines.append(f"- **Betreff / Kontext:** {subject}")
            if task_id:
                lines.append(f"- **Verknüpfte Aufgabe:** [#{task_id}](TASKS.md)")
            if msg_id:
                lines.append(f"- **Message-ID:** `{msg_id}`")
            if summary:
                lines.append(f"- **Inhalt / Auszug:**\n  > {summary.replace(chr(10), chr(10) + '  > ')}")
            lines.append("")

    with open(ACTIONS_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

def record_action(channel: str, recipient: str, subject: str, summary: str, status: str = "Erfasst", task_id: Optional[int] = None, message_id: Optional[str] = None) -> Dict[str, Any]:
    actions = load_actions()
    next_id = max([a.get("id", 0) for a in actions], default=0) + 1
    new_action = {
        "id": next_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channel": channel,
        "recipient": recipient,
        "subject": subject,
        "summary": summary,
        "status": status,
        "task_id": task_id,
        "message_id": message_id
    }
    actions.append(new_action)
    save_actions(actions)
    return new_action

# ---------------------------------------------------------------------------
# Browser Workflow (ID Austria Persistent Session)
# ---------------------------------------------------------------------------

def launch_browser(url: Optional[str] = None):
    ensure_storage()
    target_url = url or DEFAULT_AMS_URL
    chrome_bin = "/usr/bin/google-chrome"
    if not os.path.exists(chrome_bin):
        # Fallback search
        res = subprocess.run(["which", "google-chrome"], capture_output=True, text=True)
        if res.returncode == 0:
            chrome_bin = res.stdout.strip()
        else:
            print("❌ Google Chrome konnte nicht gefunden werden.")
            return

    cmd = [
        chrome_bin,
        f"--user-data-dir={BROWSER_PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        target_url
    ]

    print(f"🚀 Starte eAMS Chrome-Browser mit persistentem Profil:")
    print(f"   Profil-Verzeichnis: {BROWSER_PROFILE_DIR}")
    print(f"   Ziel-URL:           {target_url}")
    print("\n👉 Bitte melde dich im geöffneten Browser-Fenster via ID Austria / Digitales Amt an.")
    print("   Die Session-Cookies bleiben im Profil gespeichert.\n")

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    record_action(
        channel="Browser / ID Austria",
        recipient=f"{RGS} (PSTNR: {PSTNR})",
        subject="MeinAMS Portal geöffnet",
        summary=f"Chrome gestartet mit Ziel-URL: {target_url}",
        status="Sitzung gestartet"
    )

# ---------------------------------------------------------------------------
# Gmail Scanner
# ---------------------------------------------------------------------------

def scan_emails(limit: int = 10):
    ensure_storage()
    print(f"🔍 Scanne Gmail nach Benachrichtigungen von {RGS} / AMS Österreich...")

    cmd = ["gmail-cli", "search", "ams.at", "-n", str(limit), "--json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        emails = json.loads(res.stdout)
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der E-Mails via gmail-cli: {e}")
        return

    if not emails:
        print("ℹ️ Keine neuen E-Mails von ams.at gefunden.")
        return

    tasks = load_tasks()
    tracked_msg_ids = {t.get("message_id") for t in tasks if t.get("message_id")}
    next_task_id = max([t.get("id", 0) for t in tasks], default=0) + 1

    new_count = 0
    for em in emails:
        sender = em.get("from", "")
        subject = em.get("subject", "")
        msg_id = em.get("id", "")
        date_str = em.get("date", "")
        snippet = em.get("snippet", "")

        # Only process actual AMS notifications directly from @ams.at
        sender_clean = sender.lower().strip("<> ")
        if not (sender_clean.endswith("@ams.at") or "@ams.at" in sender_clean):
            continue

        if msg_id in tracked_msg_ids:
            continue

        # Determine category & title
        category = "eAMS Postfach"
        if "termin" in subject.lower() or "kontroll" in subject.lower():
            category = "AMS Termin"
        elif "vermittlung" in subject.lower() or "stellen" in subject.lower():
            category = "Vermittlung"

        title = f"Neue Nachricht in MeinAMS prüfen: {subject}"
        description = f"Nachricht eingegangen am {date_str}. Bitte via `ams-agent browser` im eAMS-Postfach abrufen.\nVorschau: {snippet}"

        new_task = {
            "id": next_task_id,
            "title": title,
            "category": category,
            "priority": "HOCH",
            "done": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "due_date": None,
            "message_id": msg_id,
            "source_sender": sender,
            "source_subject": subject,
            "description": description
        }
        tasks.append(new_task)
        tracked_msg_ids.add(msg_id)
        next_task_id += 1
        new_count += 1

    if new_count > 0:
        save_tasks(tasks)
        print(f"✅ {new_count} neue AMS-Nachricht(en) erfasst und in TASKS.md eingetragen!")
    else:
        print("ℹ️ Alle aktuellen AMS-E-Mails sind bereits in TASKS.md erfasst.")

    # Always show latest emails
    print(f"\n📧 Gefundene AMS-E-Mails (letzte {len(emails)}):")
    for idx, em in enumerate(emails[:5], 1):
        print(f"[{idx}] Datum:   {em.get('date')}")
        print(f"    Von:     {em.get('from')}")
        print(f"    Betreff: {em.get('subject')}")
        print(f"    ID:      {em.get('id')}")
        print("-" * 50)

# ---------------------------------------------------------------------------
# Task & Action Handlers
# ---------------------------------------------------------------------------

def list_tasks(show_all: bool = False):
    tasks = load_tasks()
    if not show_all:
        tasks = [t for t in tasks if not t.get("done", False)]

    if not tasks:
        print("ℹ️ Keine offenen Aufgaben vorhanden.")
        return

    print(f"\n📋 Aktuelle AMS-Aufgaben ({'Alle' if show_all else 'Offen'}):")
    print("=" * 60)
    for t in tasks:
        status_icon = "✅" if t.get("done") else "⏳"
        pri = t.get("priority", "HOCH")
        cat = t.get("category", "eAMS")
        tid = t.get("id")
        print(f"{status_icon} [#{tid}] [{cat}] [{pri}] {t.get('title')}")
        if t.get("description"):
            for line in t.get("description").splitlines():
                print(f"    {line}")
        print("-" * 60)

def mark_done(task_id: int):
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t.get("id") == task_id:
            t["done"] = True
            t["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            found = True
            print(f"✅ Aufgabe [#{task_id}] '{t.get('title')}' als erledigt markiert.")
            break
    if found:
        save_tasks(tasks)
    else:
        print(f"❌ Aufgabe mit ID {task_id} wurde nicht gefunden.")

def list_actions():
    actions = load_actions()
    if not actions:
        print("ℹ️ Noch keine Aktionen in ACTIONS.md protokolliert.")
        return

    print(f"\n📜 AMS Bewerbungs- & Aktivitäts-Protokoll (letzte 10):")
    print("=" * 65)
    sorted_actions = sorted(actions, key=lambda x: x.get("id", 0), reverse=True)
    for a in sorted_actions[:10]:
        print(f"[#{a.get('id')}] {a.get('timestamp')} | {a.get('channel')} | {a.get('status')}")
        print(f"    Empfänger: {a.get('recipient')}")
        print(f"    Betreff:   {a.get('subject')}")
        if a.get("summary"):
            first_line = a.get("summary").splitlines()[0]
            print(f"    Inhalt:    {first_line[:80]}...")
        print("-" * 65)

# ---------------------------------------------------------------------------
# AI Cover Letter Generator via Ollama (qwen2.5:14b)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_BEWERBUNG = f"""Du bist ein hochqualifizierter Karriere- & Bewerbungsberater für den österreichischen IT- & Arbeitsmarkt.
Deine Aufgabe ist es, ein maßgeschneidertes, professionelles und überzeugendes Bewerbungsschreiben (Anschreiben) für Roland Sauer zu verfassen.

Kandidaten-Profil:
- Name: {CANDIDATE_NAME}
- E-Mail: {CANDIDATE_EMAIL}
- Profil: Erfahrener Senior Software Architect, Fullstack-Entwickler & CRM-Spezialist.
- Kernkompetenzen:
  * Moderne Web- und Enterprise-Architekturen (PHP, Python, JavaScript/TypeScript, Docker, Linux, REST-APIs).
  * CRM-Systeme, Automatisierung, Datenbanken (MySQL/PostgreSQL) und Cloud-Deployments.
  * Agiles Projektmanagement (Scrum, Kanban), eigenverantwortliche Problemlösung und lösungsorientierte Arbeitsweise.
  * Langjährige Erfahrung in Konzeption, Umsetzung und technischer Leitung.

Standards für das Bewerbungsschreiben:
1. Stil & Tonalität: Professionell, selbstbewusst, wertschätzend, österreichischer Standard (keine bundesdeutschen Floskeln wie "zeitnah", "gerne möchte ich").
2. Struktur:
   - Kontaktdaten des Bewerbers
   - Empfängerdaten / Unternehmen
   - Datum
   - Betreffzeile (präzise mit Referenznummer oder Berufsbezeichnung)
   - Individuelle Einleitung (Bezug zur Ausschreibung)
   - Kernkompetenzen & Passung zum Anforderungsprofil (konkreter Mehrwert für das Unternehmen)
   - Motivation & Arbeitsweise
   - Schlusssatz mit Gesprächsbereitschaft
   - Grußformel: "Mit freundlichen Grüßen" + Name
3. Gib das Schreiben formatiert in sauberem Markdown aus.
"""

def generate_application(job_input: str, company: Optional[str] = None, position: Optional[str] = None, to_email: Optional[str] = None, create_draft: bool = False):
    ensure_storage()
    # If job_input is a file path, read it
    job_text = job_input
    if os.path.isfile(job_input):
        with open(job_input, "r", encoding="utf-8") as f:
            job_text = f.read()

    print(f"🤖 Generiere Bewerbungsschreiben mit lokalem KI-Modell ({DEFAULT_MODEL})...")

    prompt = f"Stellenausschreibung / Vermittlungsvorschlag:\n\"\"\"\n{job_text}\n\"\"\"\n\n"
    if company:
        prompt += f"Unternehmen: {company}\n"
    if position:
        prompt += f"Position: {position}\n"
    prompt += "Erstelle nun das vollständige, maßgeschneiderte Bewerbungsschreiben nach österreichischem Standard."

    payload = {
        "model": DEFAULT_MODEL,
        "system": SYSTEM_PROMPT_BEWERBUNG,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("response", "").strip()
    except Exception as e:
        print(f"❌ Fehler bei der Kommunikation mit Ollama: {e}")
        return

    # Extract clean company name for filename
    clean_company = re.sub(r'[^a-zA-Z0-9_-]', '_', (company or "Bewerbung").lower())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(BEWERBUNGEN_DIR, f"Bewerbung_{clean_company}_{timestamp}.md")

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Bewerbungsschreiben erfolgreich erstellt und gespeichert:")
    print(f"   Datei: {out_file}")

    action_status = "Bewerbungsschreiben erstellt"

    # Optional: create draft in Gmail
    if create_draft:
        if not to_email:
            # Try to find email in job_text
            emails_found = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', job_text)
            to_email = emails_found[0] if emails_found else None

        if to_email:
            subj = f"Bewerbung als {position or 'Software Entwickler / IT-Spezialist'} – Roland Sauer"
            print(f"✉️ Erstelle Gmail-Entwurf an {to_email}...")
            draft_cmd = [
                "gmail-cli", "draft",
                "--to", to_email,
                "--subject", subj,
                "--body", content
            ]
            try:
                subprocess.run(draft_cmd, check=True)
                print("✅ Gmail-Entwurf erfolgreich angelegt!")
                action_status = "Bewerbung als Gmail-Entwurf angelegt"
            except Exception as ex:
                print(f"⚠️ Konnte Entwurf nicht erstellen: {ex}")
        else:
            print("⚠️ Keine Empfänger-E-Mail angegeben/gefunden. Entwurf wurde übersprungen.")

    record_action(
        channel="E-Mail / Bewerbung",
        recipient=company or "Arbeitgeber",
        subject=f"Bewerbung {position or ''}",
        summary=f"Bewerbungsschreiben erstellt (Datei: {os.path.basename(out_file)}).\nStatus: {action_status}",
        status=action_status
    )

    print("\n" + "=" * 60)
    print(content)
    print("=" * 60)

def launch_app(port: int = 8765, open_browser: bool = False):
    import uvicorn
    app_url = f"http://127.0.0.1:{port}"
    print(f"🚀 Starte NEXUS // eAMS ÖSTERREICH TERMINAL V241.0:")
    print(f"   URL: {app_url}")
    print(f"   AlVG Compliance Standard: AKTIV")
    if open_browser:
        subprocess.Popen(["google-chrome", app_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)

# ---------------------------------------------------------------------------
# CLI Argument Parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="eAMS Automatisierungs- & Bewerbungs-Suite (Roland Sauer, PSTNR 4368522)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Verfügbare Befehle")

    # browser / open
    p_browser = subparsers.add_parser("browser", aliases=["open"], help="Startet MeinAMS mit persistentem Chrome-Profil")
    p_browser.add_argument("--url", help="Optionale Ziel-URL", default=DEFAULT_AMS_URL)

    # scan
    p_scan = subparsers.add_parser("scan", help="Scannt Gmail nach neuen AMS-Mails und aktualisiert TASKS.md")
    p_scan.add_argument("-n", "--limit", type=int, default=10, help="Anzahl abzufragender Mails (Standard: 10)")

    # tasks
    p_tasks = subparsers.add_parser("tasks", help="Zeigt das aktuelle Aufgaben-Board")
    p_tasks.add_argument("-a", "--all", action="store_true", help="Auch erledigte Aufgaben anzeigen")

    # done
    p_done = subparsers.add_parser("done", help="Markiert eine Aufgabe als erledigt")
    p_done.add_argument("task_id", type=int, help="ID der Aufgabe")

    # actions
    subparsers.add_parser("actions", help="Zeigt das AMS-Aktivitäts- & Bewerbungsprotokoll")

    # log-action
    p_log = subparsers.add_parser("log-action", help="Manuelle Erfassung einer AMS-Aktion")
    p_log.add_argument("--channel", default="Telefon", help="Kanal (Telefon, eAMS, E-Mail, Persönlich)")
    p_log.add_argument("--recipient", default=RGS, help="Gesprächspartner / Organisation")
    p_log.add_argument("--subject", required=True, help="Betreff / Thema")
    p_log.add_argument("--summary", required=True, help="Inhalt / Zusammenfassung")
    p_log.add_argument("--status", default="Durchgeführt", help="Status")

    # apply
    p_apply = subparsers.add_parser("apply", help="Generiert Bewerbungsschreiben via lokalem Ollama qwen2.5:14b")
    p_apply.add_argument("job", help="Stellentext oder Pfad zur Stellenausschreibung")
    p_apply.add_argument("--company", help="Name des Unternehmens")
    p_apply.add_argument("--position", help="Bezeichnung der Stelle")
    p_apply.add_argument("--to", help="E-Mail-Adresse für Bewerbungsentwurf")
    p_apply.add_argument("--draft", action="store_true", help="Direkt als Gmail-Entwurf speichern")

    # app / serve
    p_app = subparsers.add_parser("app", aliases=["serve"], help="Startet die NEXUS Web-Anwendung (FastAPI + Visium UI)")
    p_app.add_argument("-p", "--port", type=int, default=8765, help="Port für die Web-Anwendung (Standard: 8765)")
    p_app.add_argument("--open", action="store_true", help="Öffnet die Web-Anwendung automatisch im Browser")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command in ["app", "serve"]:
        launch_app(port=args.port, open_browser=args.open)
    elif args.command in ["browser", "open"]:
        launch_browser(args.url)
    elif args.command == "scan":
        scan_emails(args.limit)
    elif args.command == "tasks":
        list_tasks(args.all)
    elif args.command == "done":
        mark_done(args.task_id)
    elif args.command == "actions":
        list_actions()
    elif args.command == "log-action":
        record_action(
            channel=args.channel,
            recipient=args.recipient,
            subject=args.subject,
            summary=args.summary,
            status=args.status
        )
        print(f"✅ Aktion erfolgreich in ACTIONS.md protokolliert.")
    elif args.command == "apply":
        generate_application(
            job_input=args.job,
            company=args.company,
            position=args.position,
            to_email=args.to,
            create_draft=args.draft
        )

if __name__ == "__main__":
    main()
