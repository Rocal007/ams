#!/usr/bin/env python3
"""
NEXUS // AMS-APPLICATION V241.0 [RADICAL OBJECTIVITY & AlVG COMPLIANCE STANDARD]
Standalone FastAPI Backend & Local Bunker Server für Roland Sauer (PSTNR: 4368522)
"""

import os
import sys
import json
import subprocess
import urllib.request
import urllib.error
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ams_agent

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "templates")
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")

os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = FastAPI(title="NEXUS // AMS Application", version="241.0")

# ---------------------------------------------------------------------------
# Telemetry Helpers
# ---------------------------------------------------------------------------

def get_gpu_telemetry() -> Dict[str, Any]:
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            return {
                "available": True,
                "name": parts[0],
                "mem_total_mb": int(parts[1]),
                "mem_used_mb": int(parts[2]),
                "temp_c": int(parts[3]),
                "util_pct": int(parts[4])
            }
    except Exception:
        pass
    return {"available": False, "name": "N/A", "mem_total_mb": 0, "mem_used_mb": 0, "temp_c": 0, "util_pct": 0}

def get_ollama_status() -> Dict[str, Any]:
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "online": True,
                "default_model": ams_agent.DEFAULT_MODEL,
                "has_default": any(ams_agent.DEFAULT_MODEL in m for m in models),
                "all_models": models
            }
    except Exception:
        return {"online": False, "default_model": ams_agent.DEFAULT_MODEL, "has_default": False, "all_models": []}

def is_browser_running() -> bool:
    try:
        res = subprocess.run(["pgrep", "-f", "user-data-dir=.*\\.browser-profile"], capture_output=True)
        return res.returncode == 0
    except Exception:
        return False

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_system_status():
    tasks = ams_agent.load_tasks()
    actions = ams_agent.load_actions()
    open_tasks = [t for t in tasks if not t.get("done", False)]
    done_tasks = [t for t in tasks if t.get("done", False)]

    # AlVG Compliance Score
    # 1.0 if all high priority tasks under 7 days old
    compliance_score = 1.0
    warning_count = 0
    now = datetime.now()
    for t in open_tasks:
        c_at = t.get("created_at")
        if c_at:
            try:
                dt = datetime.strptime(c_at, "%Y-%m-%d %H:%M:%S")
                if (now - dt).days > 7:
                    warning_count += 1
            except Exception:
                pass
    if warning_count > 0:
        compliance_score = max(0.5, 1.0 - (warning_count * 0.15))

    return {
        "axiom": {
            "candidate": ams_agent.CANDIDATE_NAME,
            "pstnr": ams_agent.PSTNR,
            "rgs": ams_agent.RGS,
            "email": ams_agent.CANDIDATE_EMAIL,
            "alvg_compliance_score": compliance_score,
            "v_gate": 1.0 if compliance_score >= 0.7 else 0.1
        },
        "stats": {
            "open_tasks": len(open_tasks),
            "done_tasks": len(done_tasks),
            "total_tasks": len(tasks),
            "total_actions": len(actions),
            "applications_count": len([a for a in actions if "Bewerbung" in a.get("channel", "") or "Bewerbung" in a.get("subject", "")])
        },
        "browser_running": is_browser_running(),
        "gpu": get_gpu_telemetry(),
        "ollama": get_ollama_status(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/tasks")
def get_tasks():
    return ams_agent.load_tasks()

@app.post("/api/tasks/{task_id}/toggle")
def toggle_task(task_id: int):
    tasks = ams_agent.load_tasks()
    target = None
    for t in tasks:
        if t.get("id") == task_id:
            target = t
            t["done"] = not t.get("done", False)
            if t["done"]:
                t["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                t.pop("completed_at", None)
            break
    if not target:
        raise HTTPException(status_code=404, detail="Aufgabe nicht gefunden")
    ams_agent.save_tasks(tasks)
    return {"success": True, "task": target}

@app.post("/api/scan")
def trigger_scan(limit: int = 10):
    ams_agent.scan_emails(limit=limit)
    return {"success": True, "tasks": ams_agent.load_tasks()}

class BrowserLaunchRequest(BaseModel):
    url: Optional[str] = None

@app.post("/api/browser/open")
def trigger_browser(req: BrowserLaunchRequest):
    ams_agent.launch_browser(url=req.url)
    return {"success": True, "running": True}

@app.get("/api/actions")
def get_actions():
    return ams_agent.load_actions()

class ActionCreateRequest(BaseModel):
    channel: str
    recipient: str
    subject: str
    summary: str
    status: str = "Durchgeführt"

@app.post("/api/actions")
def create_action(req: ActionCreateRequest):
    action = ams_agent.record_action(
        channel=req.channel,
        recipient=req.recipient,
        subject=req.subject,
        summary=req.summary,
        status=req.status
    )
    return {"success": True, "action": action}

class ApplyRequest(BaseModel):
    job_text: str
    company: Optional[str] = None
    position: Optional[str] = None
    to_email: Optional[str] = None
    create_draft: bool = False

@app.post("/api/apply")
def trigger_apply(req: ApplyRequest):
    if not req.job_text or not req.job_text.strip():
        raise HTTPException(status_code=400, detail="Kein Stellentext übergeben")

    # In-memory inference call
    prompt = f"Stellenausschreibung / Vermittlungsvorschlag:\n\"\"\"\n{req.job_text}\n\"\"\"\n\n"
    if req.company:
        prompt += f"Unternehmen: {req.company}\n"
    if req.position:
        prompt += f"Position: {req.position}\n"
    prompt += "Erstelle nun das vollständige, maßgeschneiderte Bewerbungsschreiben nach österreichischem Standard."

    payload = {
        "model": ams_agent.DEFAULT_MODEL,
        "system": ams_agent.SYSTEM_PROMPT_BEWERBUNG,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }

    try:
        ollama_req = urllib.request.Request(
            ams_agent.OLLAMA_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(ollama_req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("response", "").strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama Inferenz fehlgeschlagen: {str(e)}")

    # Clean filename
    clean_co = re.sub(r'[^a-zA-Z0-9_-]', '_', (req.company or "Bewerbung").lower())
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(ams_agent.BEWERBUNGEN_DIR, f"Bewerbung_{clean_co}_{ts}.md")

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    action_status = "Bewerbungsschreiben erstellt"
    draft_status = False

    if req.create_draft:
        recipient_mail = req.to_email
        if not recipient_mail:
            emails_found = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', req.job_text)
            recipient_mail = emails_found[0] if emails_found else None

        if recipient_mail:
            subj = f"Bewerbung als {req.position or 'Software Entwickler / IT-Spezialist'} – Roland Sauer"
            cmd = ["gmail-cli", "draft", "--to", recipient_mail, "--subject", subj, "--body", content]
            try:
                subprocess.run(cmd, check=True)
                draft_status = True
                action_status = "Bewerbung als Gmail-Entwurf angelegt"
            except Exception as ex:
                action_status = f"Bewerbung erstellt (Draft fehlgeschlagen: {ex})"

    action = ams_agent.record_action(
        channel="E-Mail / Bewerbung",
        recipient=req.company or "Arbeitgeber",
        subject=f"Bewerbung {req.position or ''}",
        summary=f"Bewerbungsschreiben erstellt (Datei: {os.path.basename(out_file)}).\nStatus: {action_status}",
        status=action_status
    )

    return {
        "success": True,
        "filename": os.path.basename(out_file),
        "filepath": out_file,
        "content": content,
        "draft_created": draft_status,
        "action": action
    }

@app.get("/api/protocols")
def get_protocols():
    prot_path = os.path.join(PROJECT_ROOT, "PROTOKOLLE.md")
    act_path = os.path.join(PROJECT_ROOT, "ACTIONS.md")
    tasks_path = os.path.join(PROJECT_ROOT, "TASKS.md")

    def read_safe(path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    return {
        "protokolle_md": read_safe(prot_path),
        "actions_md": read_safe(act_path),
        "tasks_md": read_safe(tasks_path),
        "matrix_version": "241.0",
        "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

@app.get("/api/export-nachweis", response_class=HTMLResponse)
def export_bewerbungsnachweis():
    actions = ams_agent.load_actions()
    tasks = ams_agent.load_tasks()

    app_actions = [a for a in actions if "Bewerbung" in a.get("channel", "") or "Bewerbung" in a.get("subject", "") or a.get("channel") in ["E-Mail", "Post", "Portal"]]

    rows = ""
    for idx, a in enumerate(app_actions, 1):
        rows += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{idx}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{a.get('timestamp', '')[:10]}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;"><strong>{a.get('recipient', '')}</strong></td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{a.get('subject', '')}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{a.get('channel', '')}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;"><span style="background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{a.get('status', '')}</span></td>
        </tr>
        """

    if not rows:
        rows = "<tr><td colspan='6' style='padding: 20px; text-align: center; color: #888;'>Noch keine Bewerbungen im Berichtszeitraum protokolliert.</td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>AMS Bewerbungsnachweis – Roland Sauer (PSTNR: {ams_agent.PSTNR})</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #111; line-height: 1.5; }}
        .header {{ border-bottom: 3px solid #0284c7; padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
        h1 {{ margin: 0; font-size: 24px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px; }}
        .meta {{ font-size: 14px; color: #475569; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }}
        th {{ background: #f1f5f9; padding: 12px 10px; text-align: left; border-bottom: 2px solid #cbd5e1; font-weight: 600; }}
        .footer {{ margin-top: 50px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 20px; display: flex; justify-content: space-between; }}
        @media print {{
            body {{ margin: 15mm; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="no-print" style="margin-bottom: 20px; background: #f8fafc; padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
        <span><strong>NEXUS Druck- & Export-Modul</strong> — Offizieller Nachweis nach AlVG §§ 9, 10</span>
        <button onclick="window.print()" style="background: #0284c7; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold;">Drucken / Als PDF speichern</button>
    </div>

    <div class="header">
        <div>
            <h1>Nachweis der Eigenbewerbungen & Aktivitäten</h1>
            <div class="meta" style="margin-top: 5px;">Arbeitsmarktservice Österreich • Regionalgeschäftsstelle Hietzinger Kai</div>
        </div>
        <div style="text-align: right;">
            <strong>Roland Sauer</strong><br>
            PSTNR: <strong>{ams_agent.PSTNR}</strong><br>
            Stand: {datetime.now().strftime("%d.%m.%Y")}
        </div>
    </div>

    <p style="font-size: 13px; color: #334155;">
        Hiermit wird gemäß den Betreuungsvereinbarungen des AMS und den gesetzlichen Vorschriften des Arbeitslosenversicherungsgesetzes (AlVG) die lückenlose Dokumentation der unternommenen Bewerbungs- und Qualifikationsaktivitäten vorgelegt.
    </p>

    <table>
        <thead>
            <tr>
                <th style="width: 40px;">Nr.</th>
                <th style="width: 100px;">Datum</th>
                <th>Unternehmen / Organisation</th>
                <th>Angestrebte Position / Kontext</th>
                <th style="width: 120px;">Bewerbungsweg</th>
                <th style="width: 160px;">Status / Nachweis</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <div class="footer">
        <div>Erstellt durch die NEXUS // AMS-Suite • Lückenlose System-Versiegelung nach DECORUM-RO</div>
        <div>Unterschrift Bewerber: _________________________________</div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html)

# ---------------------------------------------------------------------------
# Frontend Root View
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index_view():
    template_path = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>NEXUS // AMS Application</h1><p>Template wird geladen...</p>")

if __name__ == "__main__":
    import uvicorn
    port = 8765
    print(f"🚀 Starte NEXUS // AMS Web-Server auf http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
