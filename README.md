# NAS Assistant

Il cloud di famiglia, a casa tua, dentro Home Assistant.
Un'alternativa locale a iCloud Famiglia: ogni utente di Home Assistant ha il suo spazio privato,
più una cartella condivisa con tutta la famiglia, su un disco dedicato scelto da te.

- 🔒 Spazio privato per ogni utente HA, senza nuovi account
- 👨‍👩‍👧 Cartella Famiglia condivisa
- 💽 Disco dedicato (la capienza la scegli tu): i backup di HA restano sul disco principale
- 📱 App iOS e Android (in arrivo) con backup automatico delle foto
- 🏠 Tutto in locale

## Installazione

1. Impostazioni → Add-on → Store → ⋮ → Repository → aggiungi `https://github.com/ovlas/nas-assistant`
2. Installa **NAS Assistant**, imposta il disco nella configurazione, avvia
3. Apri **NAS** dalla barra laterale

Architettura e roadmap: [docs/ARCHITETTURA.md](docs/ARCHITETTURA.md)

## Sviluppo locale

```bash
cd nas_assistant
pip install -r app/requirements.txt
NAS_ROOT=/tmp/nas NAS_DEV_TRUSTED_IP=127.0.0.1 python -m uvicorn app.main:app --port 8456
curl -H "X-Remote-User-Id: test" http://127.0.0.1:8456/api/me
```

Licenza: MIT
