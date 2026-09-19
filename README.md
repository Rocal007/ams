# eAMS Automatisierungs- & Bewerbungs-Suite (AMS Österreich)

Zentrale Automatisierungs-, Dokumenten- und Kommunikations-Suite für das persönliche **eAMS-Konto** von Roland Sauer (PSTNR: 4368522, Regionalgeschäftsstelle AMS Hietzinger Kai).

---

## Funktionsumfang

1. **Persistenter Browser-Workflow (`ams-agent browser`)**
   * Startet eine isolierte Google-Chrome-Instanz mit eigenem Benutzerprofil (`.browser-profile`).
   * Ermöglicht einmaligen Login mit **ID Austria / Digitales Amt**; Session-Cookies bleiben lokal gespeichert.
   * Direkter Absprung zu Nachrichten, Vermittlungsvorschlägen und Terminen.

2. **E-Mail- & Fristen-Scanner (`ams-agent scan`)**
   * Scannt automatisch Roland's Gmail (`r.sauer007@gmail.com`) nach Benachrichtigungen von `ams.hietzingerkai@ams.at` und `@ams.at`.
   * Erkennt neue Nachrichten und trägt diese automatisch mit Fristen in [TASKS.md](TASKS.md) ein.

3. **KI-Bewerbungs-Manager mit lokalem Ollama (`ams-agent apply`)**
   * Analysiert Stellenausschreibungen und AMS-Vermittlungsvorschläge.
   * Generiert passgenaue, hochprofessionelle Bewerbungsschreiben nach österreichischem Standard (Senior Software Architect / CRM & Fullstack Developer) über das lokale Modell `qwen2.5:14b`.
   * Erstellt auf Wunsch direkt einen Gmail-Entwurf (`gmail-cli draft`).
   * Protokolliert jede Bewerbung lückenlos als offiziellen Nachweis in [ACTIONS.md](ACTIONS.md).

4. **Task- & Nachweis-Board**
   * [TASKS.md](TASKS.md): Fristen, Termine und offene eAMS-Nachrichten.
   * [ACTIONS.md](ACTIONS.md): Lückenloses AMS-Bewerbungstagebuch für Kontroll- und Nachweispflichten.

5. **NEXUS Protokoll-Matrix ([PROTOKOLLE.md](PROTOKOLLE.md))**
   * Vollständiges Audit-Register nach dem Operator-Modell $\mathcal{T}_{\text{AMS}} = C \circ P_J \circ D_L \circ F$.
   * AlVG §§ 9, 10 Fristenwächter und Druck-Export für das AMS.

6. **Web-Anwendung (NEXUS Visium Dashboard)**
   * Vollwertige Web-UI mit Live-Telemetrie (RTX 5060 Ti GPU, Ollama, Chrome-Session).
   * Erreichbar unter `http://127.0.0.1:8765`.

---

## Verzeichnisstruktur

```text
ams/
├── .browser-profile/        # Lokales Browser-Profil für ID Austria Login (git-ignoriert)
├── postfach/                # Heruntergeladene Nachrichten & Dokumente aus MeinAMS
├── vermittlungsvorschlaege/ # Stellenangebote & Zuweisungen vom AMS
├── bewerbungen/             # Generierte Bewerbungsschreiben & Lebensläufe
├── bescheide/               # Leistungsbescheide & Vereinbarungen
├── templates/index.html     # NEXUS Visium Web-Dashboard
├── app.py                   # FastAPI Server & REST-API
├── run_app.sh               # Schnellstarter für die Web-Anwendung
├── ams_agent.py             # Zentrales CLI-Tool & Automatisierungsskript
├── TASKS.md                 # Aufgaben- & Fristen-Board
├── ACTIONS.md               # Chronologisches Bewerbungs- & Aktivitätenprotokoll
├── PROTOKOLLE.md            # NEXUS Protokoll- & Audit-Matrix (AlVG-Standard)
└── README.md                # Dokumentation
```

---

## Befehlsübersicht (`ams-agent`)

```bash
# 1. NEXUS Web-Anwendung starten (http://127.0.0.1:8765)
ams-agent app
# oder direkt mit Browser:
ams-agent app --open
# oder via Shell-Starter:
./run_app.sh

# 2. MeinAMS Browser mit ID Austria Session öffnen
ams-agent browser

# 3. Gmail nach neuen AMS-Nachrichten scannen & TASKS.md aktualisieren
ams-agent scan

# 4. Bewerbung auf einen Vermittlungsvorschlag generieren
ams-agent apply "vermittlungsvorschlaege/stelle_123.txt"
# Optional direkt als Gmail-Entwurf speichern:
ams-agent apply "vermittlungsvorschlaege/stelle_123.txt" --draft

# 5. Aufgaben anzeigen / als erledigt markieren
ams-agent tasks
ams-agent done 1

# 6. Bewerbungstagebuch / Nachweise anzeigen
ams-agent actions
```
