from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "sync_web_config.json"


class SyncError(RuntimeError):
    pass


def _date_gestionpro(value):
    text = str(value or "").strip()
    if not text:
        return ""
    date_part = text[:10] if len(text) >= 10 else text
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_part, fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return text


def load_config():
    if not CONFIG_PATH.exists():
        raise SyncError("Configuration Web absente : sync_web_config.json")
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError("Configuration Web illisible ou invalide.") from exc
    base = str(data.get("base_url", "")).strip().rstrip("/")
    token = str(data.get("api_token", "")).strip()
    if not base or not token:
        raise SyncError("Renseignez base_url et api_token dans sync_web_config.json")
    return base, token


def _request(method, path, payload=None, allow_404=False):
    base, token = load_config()
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base + path, data=body, method=method)
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            raw = response.read().decode("utf-8")
        try:
            return json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise SyncError(f"Réponse Web invalide sur {path}.") from exc
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and allow_404:
            return None
        if exc.code == 401:
            raise SyncError("Accès API refusé (HTTP 401). Vérifiez le jeton de synchronisation.")
        raise SyncError(f"Erreur Web HTTP {exc.code} sur {path}.") from exc
    except SyncError:
        raise
    except Exception as exc:
        raise SyncError("Connexion au site impossible : " + str(exc)) from exc


def _request_compatible(method, paths, payload=None):
    for path in paths:
        result = _request(method, path, payload, allow_404=True)
        if result is not None:
            return result
    raise SyncError("Route de synchronisation introuvable sur le site Web.")


def test_connection():
    base, _token = load_config()
    status = _request("GET", "/health", None, allow_404=True)
    return {
        "ok": bool(status and status.get("status") == "ok"),
        "base_url": base,
        "message": "Connexion au site réussie." if status else "Le site répond sans route de contrôle.",
    }


def _vehicle_payload(conn):
    return [
        {
            "code_vehicule": row["code"],
            "marque": row["modele"] or "",
            "immatriculation": row["immatriculation"] or "",
            "num_chassis": row["chassis"] or "",
            "compteur": row["compteur"] or 0,
            "service": "EN SERVICE" if row["service"] else "HORS SERVICE",
            "prix_jour": row["prix"] or 0,
            "remarque": "",
        }
        for row in conn.execute("SELECT * FROM vehicles WHERE COALESCE(service,1)=1 ORDER BY code")
    ]


def _location_payload(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(contracts)")}
    return_filter = (
        "AND UPPER(COALESCE(return_status,'')) NOT LIKE 'RETOUR CONFIRM%'"
        if "return_status" in columns else ""
    )
    return [
        {
            "code_location": row["numero"],
            "code_vehicule": row["vehicle_code"],
            "date_depart": row["date_depart"],
            "date_retour": row["date_retour"],
        }
        for row in conn.execute(
            "SELECT c.numero,c.vehicle_code,c.date_depart,c.date_retour FROM contracts c "
            "JOIN vehicles v ON v.code=c.vehicle_code "
            "WHERE TRIM(COALESCE(c.vehicle_code,''))<>'' AND COALESCE(v.service,1)=1 " + return_filter
        )
    ]


def _reservation_payload(remote):
    code = str(remote.get("code_reservation", "")).strip()
    return code, {
        "reference": code,
        "client": str(remote.get("code_client") or "WEB"),
        "vehicle": str(remote.get("code_vehicule") or ""),
        "start_date": _date_gestionpro(remote.get("date_depart")),
        "start_time": str(remote.get("heure_depart") or "09:00"),
        "end_date": _date_gestionpro(remote.get("date_retour")),
        "end_time": str(remote.get("heure_retour") or "09:00"),
        "deposit": str(remote.get("avance") or 0),
        "status": str(remote.get("statut") or "EN ATTENTE"),
        "cin": str(remote.get("cin") or ""),
        "last_name": str(remote.get("nom") or ""),
        "first_name": str(remote.get("prenom") or ""),
        "phone": str(remote.get("telephone") or ""),
        "vehicle_model": str(remote.get("marque_vehicule") or ""),
        "plate": str(remote.get("immatriculation") or ""),
        "duration": remote.get("duree") or 0,
        "daily_price": remote.get("prix") or 0,
        "total": remote.get("montant") or 0,
        "balance": remote.get("reste") or 0,
        "notes": str(remote.get("observation") or ""),
        "source": "SITE WEB",
        "web_created_at": str(remote.get("date_creation") or ""),
    }


def resolve_web_reservation_client(conn,payload):
    """Match only an existing CIN; never create or overwrite a client."""
    cin=''.join(str(payload.get('cin') or '').split()).upper()
    matches=conn.execute("SELECT code,cin,nom,prenom,telephone FROM clients WHERE UPPER(REPLACE(TRIM(cin),' ',''))=? LIMIT 2",(cin,)).fetchall() if cin else []
    if len(matches)==1:
        row=matches[0]
        for key,column in (('client','code'),('cin','cin'),('last_name','nom'),('first_name','prenom'),('phone','telephone')):payload[key]=str(row[column] or '')
    else:
        payload['client']='WEB'
    return payload

WEB_CLIENT_FIELDS=('client','cin','last_name','first_name','phone')

def preserve_web_client(incoming,local):
    """A client assigned on the PC stays assigned on subsequent downloads."""
    override=local.get('_web_client_override')
    if isinstance(override,dict) and override.get('client'):
        incoming.update({k:override.get(k,'') for k in WEB_CLIENT_FIELDS})
        incoming['_web_client_override']=dict(override)
    for key in ('second_client','agency','discount','payment_method','departure_place','return_place'):
        if key in local:incoming[key]=local[key]
    return incoming

def sync_database(db_path):
    """Synchronisation bidirectionnelle compatible avec l'API historique HBZ."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS module_records(
            module TEXT NOT NULL, record_id TEXT NOT NULL, payload TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY(module, record_id)
        );
        CREATE TABLE IF NOT EXISTS audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
            module TEXT NOT NULL, reference TEXT, details TEXT, created_at TEXT NOT NULL
        );
        """)
        vehicles = _vehicle_payload(conn)
        locations = _location_payload(conn)
        pushed = _request_compatible(
            "POST", ["/api/sync/vehicles", "/api/vehicles/sync", "/api/vehicles"],
            {"vehicles": vehicles},
        )
        pushed_locations = _request_compatible(
            "POST", ["/api/sync/locations", "/api/locations/sync", "/api/locations"],
            {"locations": locations},
        )
        remote = _request_compatible(
            "GET", ["/api/sync/reservations", "/api/reservations/sync", "/api/reservations"]
        )
        inserted = updated = ignored = deleted = 0
        remote_active_ids=set()
        for item in remote.get("reservations", []):
            code, payload = _reservation_payload(item)
            if not code:
                ignored += 1
                continue
            status=str(item.get("status") or item.get("statut") or payload.get("status") or "").strip().casefold()
            cancelled=status in {"annulee","annulée","annule","annulé","cancelled","canceled","deleted","supprimee","supprimée","supprime","supprimé"}
            if cancelled:
                cur=conn.execute("DELETE FROM module_records WHERE module='reservations' AND record_id=?",(code,))
                deleted += cur.rowcount
                continue
            remote_active_ids.add(code)
            from reservation_actions import local_action
            if local_action(conn,code) in ('cancel','delete'):
                ignored += 1
                continue
            vehicle_code = str(payload.get("vehicle", "")).strip()
            active_vehicle = conn.execute(
                "SELECT 1 FROM vehicles WHERE code=? AND COALESCE(service,1)=1", (vehicle_code,)
            ).fetchone()
            if not active_vehicle:
                ignored += 1
                continue
            payload=resolve_web_reservation_client(conn,payload)
            exists = conn.execute(
                "SELECT payload FROM module_records WHERE module='reservations' AND record_id=?", (code,)
            ).fetchone()
            if exists:
                try:payload=preserve_web_client(payload,json.loads(exists['payload']))
                except (ValueError,TypeError):pass
            raw=json.dumps(payload,ensure_ascii=False)
            conn.execute(
                "INSERT INTO module_records(module,record_id,payload,created_at) VALUES('reservations',?,?,?) "
                "ON CONFLICT(module,record_id) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at",
                (code, raw, datetime.now().isoformat(timespec="seconds")),
            )
            updated += int(bool(exists))
            inserted += int(not exists)
        # La liste Web est la référence pour les réservations SITE WEB : celles qui ont disparu
        # (annulées/supprimées côté site) ne doivent plus bloquer le parc dans GestionPro.
        local_web=conn.execute("SELECT record_id,payload FROM module_records WHERE module='reservations'").fetchall()
        for lr in local_web:
            try: lp=json.loads(lr['payload'])
            except Exception: continue
            if str(lp.get('source','')).upper()=='SITE WEB' and lr['record_id'] not in remote_active_ids:
                conn.execute("DELETE FROM module_records WHERE module='reservations' AND record_id=?",(lr['record_id'],)); deleted += 1
        conn.execute(
            "INSERT INTO audit_log(action,module,reference,details,created_at) VALUES(?,?,?,?,?)",
            ("SYNCHRONISATION", "SITE WEB", "RÉSERVATIONS",
             f"{inserted} nouvelle(s), {updated} mise(s) à jour, {deleted} supprimée(s)/annulée(s)",
             datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return {
            "vehicules_envoyes": pushed.get("updated", len(vehicles)),
            "locations_envoyees": pushed_locations.get("updated", len(locations)),
            "reservations_nouvelles": inserted,
            "reservations_mises_a_jour": updated,
            "reservations_ignorees": ignored,
            "reservations_supprimees": deleted,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
