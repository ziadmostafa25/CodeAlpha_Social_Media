# NIVO (نيفو) — Engineering Handoff & Production Operational Guide

**Platform:** NIVO  
**Brand Identity:** *Your World, In Sync.* / *عالمك، بتواصل يجمعنا.*  
**Repository Path:** `D:\ZIAD WEB ITI\CodeAlpha_Social_Media`  
**Django Project Package:** `nivo_project`  
**Django Version:** 6.1.1 | **Python Version:** 3.14.7  
**Database Backup Location:** `D:\ZIAD WEB ITI\CodeAlpha_Social_Media\db_backup_pre_rename_20261123.sqlite3`  
**Verified Public URL:** `https://deflected-imply-washroom.ngrok-free.dev`  

---

## 1. Quick Startup Workflow (Windows PowerShell)

To run NIVO with real-time WebSockets and public internet access:

### Terminal 1 — Daphne ASGI Application Server:
```powershell
cd "D:\ZIAD WEB ITI\CodeAlpha_Social_Media"
py -m daphne -b 0.0.0.0 -p 8000 nivo_project.asgi:application
```

### Terminal 2 — ngrok Public Tunnel:
```powershell
ngrok http 8000 --url https://deflected-imply-washroom.ngrok-free.dev
```
*(If the assigned static domain is in use by another session, simply run `ngrok http 8000` to generate an available ephemeral tunnel).*

### Local & Public Access:
- **Local Access:** `http://127.0.0.1:8000/`
- **Public URL:** `https://deflected-imply-washroom.ngrok-free.dev/`

---

## 2. Test Execution & System Health Commands

### Execute Automated Test Suite (53 Tests):
```powershell
py manage.py test --no-input
```
Expected output:
```
Ran 53 tests in ~1.9s
OK (100% Passed)
```

### Validate Migrations & System Integrity:
```powershell
py manage.py check
py manage.py makemigrations --check --dry-run
```

### Recompile Translations (if new strings added):
```powershell
py -c "import polib; po = polib.pofile('locale/ar/LC_MESSAGES/django.po'); po.save_as_mofile('locale/ar/LC_MESSAGES/django.mo')"
```

---

## 3. Demo Creator Accounts

All demo accounts use the official NIVO password: **`NivoDemo2026!`**

| Username | Name | Bio Highlights |
|---|---|---|
| `ziad_dev` | Ziad Mostafa | Full Stack Engineer & UI Craftsman (Lead) |
| `sarah_design` | Sarah Jenkins | Design Systems Lead & Product Designer |
| `omar_tech` | Omar Farouk | AI & Distributed Systems Researcher |
| `layla_art` | Layla Nour | Digital Illustrator & 3D Artist |
| `marcus_travel` | Marcus Vance | Adventure Photographer & Storyteller |

---

## 4. Real-Time WebSockets & WebRTC Calling Architecture

1. **Protocol Routing (`nivo_project/asgi.py`)**:
   - HTTP traffic is dispatched via standard `django.core.asgi.get_asgi_application()`.
   - WebSocket traffic is authenticated via `AuthMiddlewareStack` and routed through `chat.routing.websocket_urlpatterns` to `ChatConsumer`.

2. **WebSocket Signaling Endpoint**:
   - Pattern: `ws/chat/<conversation_id>/`
   - Handles:
     - Real-time text message broadcasts (`chat_message`).
     - Typing indicators (`typing`).
     - WebRTC peer-to-peer signaling (`call_offer`, `call_answer`, `ice_candidate`, `call_reject`, `call_end`).

3. **WebRTC Audio & Video Calling**:
   - Built on browser `RTCPeerConnection` with public Google STUN servers (`stun:stun.l.google.com:19302`, `stun:stun1.l.google.com:19302`).
   - UI provides local PIP video stream, remote video stream, call status indicator, call timer, microphone mute, camera toggle, and call disconnect.
   - Incoming call alert dialog allows recipient to Accept or Decline in real time.
   - For symmetric NAT or restricted corporate networks, configure a TURN server (such as Coturn or Twilio Network Traversal) in `rtcConfiguration.iceServers` inside `templates/chat/conversation.html`.

4. **In-Browser Audio Recording**:
   - Client-side microphone recording via HTML5 `MediaRecorder` API.
   - Validates audio binary headers on upload (WebM, Ogg, WAV, MP4 up to 15MB).

---

## 5. Database Switching (SQLite to PostgreSQL)

NIVO supports instant switching to PostgreSQL via environment variables:

1. Create PostgreSQL database:
   ```sql
   CREATE DATABASE nivo_db;
   ```
2. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Update `.env`:
   ```ini
   USE_POSTGRES=True
   DB_NAME=nivo_db
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_HOST=127.0.0.1
   DB_PORT=5432
   ```
4. Run migrations:
   ```powershell
   py manage.py migrate
   ```
