# NAS Assistant — Architettura

> Il cloud di famiglia, a casa tua, dentro Home Assistant.

## Principi

1. **Plug & play**: si installa come add-on, si sceglie il disco, fine. Nessun account nuovo.
2. **Gli utenti sono quelli di Home Assistant**: ogni utente HA ha il suo spazio privato.
3. **Disco dedicato**: i dati del NAS vivono su un disco secondario scelto dall'utente
   (USB/SATA, la capienza la decide lui). Il disco principale resta di Home Assistant.
4. **Backup separati**: i backup di HA non includono mai i file del NAS e restano sul disco principale.
5. **Tutto in locale**: nessun servizio cloud obbligatorio.

## Componenti

```
┌──────────────────────────── Home Assistant OS ────────────────────────────┐
│                                                                           │
│  Disco principale (SD/eMMC/SSD)        Disco NAS dedicato (USB/SATA)      │
│  ├─ Home Assistant Core                └─ montato in /nas dall'add-on     │
│  ├─ backup di HA  ◄── restano qui         ├─ users/<id utente HA>/        │
│  └─ add-on NAS Assistant (/data =         ├─ family/                     │
│       solo configurazione, piccola)       ├─ .trash/                     │
│                                           └─ .nas_assistant/ (db, thumbs)│
│                                                                           │
│  Add-on NAS Assistant                                                     │
│  ├─ API (FastAPI)  ── porta 8456 (app mobili, LAN/VPN)                     │
│  ├─ Web UI         ── via Ingress (sidebar di HA)                         │
│  └─ integrazione   ── sensori: spazio usato, utenti, stato disco           │
└───────────────────────────────────────────────────────────────────────────┘
        ▲                       ▲                          ▲
   Browser (Ingress)     App iOS / Android          Automazioni HA
```

- **Add-on** (questo repository): backend + interfaccia web.
- **App mobile** (repository separato): **Flutter**, un solo codice per iOS e Play Store.
  È la stessa scelta di Immich, che ha dimostrato che il backup foto in background funziona bene così.
- **Integrazione HA** (in seguito): sensori ed eventi (`nas_assistant_file_uploaded`, ecc.).

## Identità e permessi

| Da dove arriva la richiesta | Come riconosciamo l'utente |
|---|---|
| Web UI dentro HA (Ingress) | Header `X-Remote-User-Id` inserito dal Supervisor. Ci fidiamo **solo** se la richiesta arriva dall'IP di Ingress `172.30.32.2`. |
| App mobile | Login OAuth di Home Assistant (lo stesso flusso dell'app Companion). L'app manda `Authorization: Bearer <token HA>`, l'add-on chiede a HA chi è l'utente (`auth/current_user`) e mette in cache la risposta. |

Risultato: **un solo login, quello di Home Assistant**. Se un utente viene disattivato in HA, perde accesso anche al NAS.

Spazi:
- `personal` → `/nas/users/<user_id>/` visibile solo al proprietario
- `family` → `/nas/family/` condiviso con tutti gli utenti
- Gli admin HA **non** vedono i file privati dall'interfaccia. (Privacy contro chi ha accesso fisico al disco: crittografia per utente, fase 3.)

## Accesso da remoto (la parte importante)

L'app sceglie da sola il percorso migliore, nell'ordine:

1. **LAN diretta** — `http://<ip-ha>:8456`. Massima velocità, usata in casa (rilevata via mDNS).
2. **Tailscale** (consigliato fuori casa) — l'add-on Tailscale ufficiale della community, nessuna porta da aprire,
   cifrato, velocità piena. NAS Assistant lo rileva e guida l'utente nella configurazione.
3. **Dominio personale / Cloudflare Tunnel** — per chi ha già un reverse proxy.
4. **Fallback via Home Assistant (Nabu Casa / URL esterno di HA)** — l'app apre una sessione Ingress con il token HA.
   Funziona ovunque senza configurare nulla, ma è più lenta: va bene per sfogliare e scaricare,
   per i backup grossi l'app aspetta Wi-Fi di casa o Tailscale.

Caricamenti **ripristinabili** (protocollo *tus*, a blocchi): se la connessione cade o si cambia da Wi-Fi a 4G,
l'upload riparte da dove si era fermato. Opzioni nell'app: "solo Wi-Fi", "solo in carica", "solo in casa".

## Disco

- L'add-on monta il disco scelto (per UUID) dentro il proprio container in `/nas`.
- Filesystem supportati: ext4 (consigliato), exFAT, NTFS.
- Procedura guidata nella Web UI: rileva i dischi, mostra capienza, permette di formattare (con doppia conferma).
- Se il disco non c'è, l'add-on **non** scrive niente sul disco principale: mostra un avviso e attende.
- `/data` dell'add-on contiene solo la configurazione → backup di HA leggeri.

## Roadmap

**Fase 1 — MVP (add-on)**
- [x] Riconoscimento utente HA via Ingress
- [x] Spazio personale e cartella Famiglia
- [x] Elenco file, cartelle, caricamento, download, cestino
- [x] Montaggio disco dedicato + procedura guidata (usa così com'è o formatta in ext4)
- [ ] Miniature foto/video (libvips, ffmpeg)
- [ ] Quote per utente
- [ ] Sensori in HA

**Fase 2 — App mobile**
- [ ] Login con HA, scelta automatica del percorso (LAN/Tailscale/HA)
- [ ] Backup automatico rullino in background (iOS e Android)
- [ ] Upload tus ripristinabili
- [ ] Album condivisi famiglia, link di condivisione

**Fase 3 — Meglio di iCloud**
- [ ] Ricerca, deduplica, timeline
- [ ] Riconoscimento volti e oggetti in locale
- [ ] Crittografia per utente
- [ ] Accesso SMB/WebDAV per Mac/PC
- [ ] Backup del disco NAS su un secondo disco o sito remoto
