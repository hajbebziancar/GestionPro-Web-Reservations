"""Modèle 1 HBZ : contrat A4 élégant, alimenté par les données de GestionPro."""

import html
import json
import re
from pathlib import Path
from .contract_support import image_data


def render_contract_model1(app):
    APP_DIR = Path(__file__).resolve().parent

    values = {key: str(variable.get() or "") for key, variable in app.vars.items()}

    def safe(key):
        return html.escape(values.get(key, ""), quote=True)

    def amount(key):
        raw = re.sub(r"\s*(?:MAD|DH)\s*$", "", values.get(key, "").strip(), flags=re.IGNORECASE)
        return f"{html.escape(raw, quote=True)} DH" if raw else "—"

    def setting(key, fallback=""):
        return html.escape(str(app._get_setting(key, fallback) or ""), quote=True)

    def image_uri(path):
        if isinstance(path,str) and path.startswith('data:image/'):return html.escape(path,quote=True)
        return image_data(path) if path and path.is_file() else ""

    code = values.get("vehicle_code", "").split("|")[0].strip()
    vehicle = None
    try:
        vehicle = app.conn.execute("SELECT * FROM vehicles WHERE code=?", (code,)).fetchone()
    except Exception:
        pass
    def vehicle_value(field):
        try:
            return vehicle[field] if vehicle else ""
        except (KeyError, IndexError, TypeError):
            return ""

    stored_photo = vehicle_value("photo")
    vehicle_photo = app._resolve_vehicle_photo_path(stored_photo, code)
    photo_uri = image_uri(vehicle_photo if str(vehicle_photo).startswith('data:image/') else Path(vehicle_photo)) if vehicle_photo else ""
    state_uri = image_uri(APP_DIR / "assets" / "ETAT_VEHICULE_REFERENCE.png")
    stamp_uri = image_uri(APP_DIR / "assets" / "CACHET_SIGNATURE.png")
    try:
        client_signature_uri=app.signature
    except Exception:
        client_signature_uri = ""
    client_signature = ((f'<img src="{client_signature_uri}" alt="Signature client">' if client_signature_uri else '') +
                        f'<span class="signature-label">CIN / Passeport</span><strong class="signature-cin">{safe("cin") or "—"}</strong>')
    deny_uri = image_uri(APP_DIR / "assets" / "HBZ_DEUXIEME_CONDUCTEUR_NON_AUTORISE_TERRACOTTA.png")

    logo_uri = app._document_logo_uri()
    logo_box = f'<img src="{logo_uri}" alt="Logo société">' if logo_uri else '<span>LOGO SOCIÉTÉ</span>'

    def row(label, value, bold=False):
        return f'<div class="detail"><span>{html.escape(label)}</span><b class="{"strong" if bold else ""}">{value or "—"}</b></div>'

    first = "".join((
        row("CIN / Passeport", safe("cin"), True),
        row("Nom", safe("last_name"), True),
        row("Prénom", safe("first_name"), True),
        row("Date de naissance", safe("birth_date")),
        row("Âge", safe("age")),
        row("Adresse", safe("address")),
        row("Ville", safe("city")),
        row("Téléphone", safe("phone")),
        row("N° de permis", safe("license_no")),
        row("Permis délivré le", safe("license_date")),
        row("Ancienneté permis", safe("license_age")),
    ))
    second_present = any(values.get(k, "").strip() for k in ("second_code", "second_last", "second_cin"))
    if second_present:
        second = "".join((
            row("Code client", f'<span class="client-code">{safe("second_code")}</span>', True),
            row("CIN / Passeport", safe("second_cin"), True),
            row("Nom", safe("second_last"), True),
            row("Prénom", safe("second_first"), True),
            row("Date de naissance", safe("second_birth_date")),
            row("Âge", safe("second_age")),
            row("Téléphone", safe("second_phone")),
            row("N° de permis", safe("second_license")),
            row("Permis délivré le", safe("second_license_date")),
            row("Ancienneté permis", safe("second_license_age")),
        ))
    else:
        mark = f'<img src="{deny_uri}" alt="Non autorisé">' if deny_uri else "⊘"
        second = f'<div class="no-driver">{mark}<strong>DEUXIÈME CONDUCTEUR<br>NON AUTORISÉ</strong></div>'
    second_signature = (f'<span class="signature-label">CIN / Passeport</span><strong class="signature-cin">{safe("second_cin") or "—"}</strong>' if second_present
                        else '<strong class="signature-denied">DEUXIÈME CONDUCTEUR<br>NON AUTORISÉ</strong>')

    def icon(kind):
        paths = {
            "id": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M6 16c.5-2 5.5-2 6 0M15 9h4M15 13h4"/>',
            "driver": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/><path d="M4 10h16M12 14v7"/>',
            "car": '<path d="M4 15 6 8h12l2 7M3 15h18v4H3zM7 19v2m10-2v2M8 11h8"/>',
            "tool": '<path d="M15 4a5 5 0 0 0-6 6L4 15a3 3 0 0 0 5 5l5-5a5 5 0 0 0 6-6l-4 3-3-3z"/>',
            "box": '<path d="m3 7 9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10"/>',
            "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18m-13 4h3m3 0h3m-9 4h3"/>',
            "money": '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18m-13 6h4"/>',
            "file": '<path d="M6 3h9l4 4v14H6zM15 3v5h4M9 12h7m-7 4h7"/>',
            "pen": '<path d="m4 20 4-1 12-12-3-3L5 16zM14 7l3 3"/>',
        }
        return f'<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[kind]}</svg>'

    def heading(title, kind, color="mist"):
        return f'<div class="section-head {color}"><span class="icon-tile">{icon(kind)}</span><strong>{title}</strong></div>'

    fuel = values.get("fuel_level", "½") or "½"
    levels = {"E": 0, "⅛": 1, "¼": 2, "⅜": 3, "½": 4, "⅝": 5, "¾": 6, "⅞": 7, "F": 8, "Plein": 8}
    segments = "".join(f'<i class="{"on" if n < levels.get(fuel, 4) else ""}"></i>' for n in range(8))
    vehicle_state = {}
    try:
        record = app.conn.execute("SELECT payload FROM contract_vehicle_states WHERE contract_no=?", (values.get("contract_no", ""),)).fetchone()
        if record:
            vehicle_state = json.loads(record[0])
    except (ValueError, TypeError, AttributeError):
        pass
    except Exception:  # anciennes bases utilisées avant la création de la table
        pass
    from .contract_support import contract_state,EQUIPMENT
    recorded=contract_state(app.conn,values.get('contract_no',''))
    if 'equipment' in recorded:vehicle_state['equipment']=recorded['equipment']
    equipment=tuple(recorded.get("equipment",{})) or EQUIPMENT
    checked_equipment = vehicle_state.get("equipment", {})
    equipment_default = "equipment" not in vehicle_state
    checks = "".join(
        f'<div class="equipment-item"><span class="{"checked" if checked_equipment.get(item, equipment_default) else ""}">{"✓" if checked_equipment.get(item, equipment_default) else ""}</span>{html.escape(item)}</div>'
        for item in equipment
    )
    damage = vehicle_state.get("damage", {})
    damage_checks = "".join(
        f'<span class="view-check"><i>{"✓" if damage.get(name, False) else ""}</i>{html.escape(name)}</span>'
        for name in ("Vue avant", "Vue arrière", "Côté gauche", "Côté droit")
    )
    observations = html.escape(str(vehicle_state.get("observations", "") or "")).strip()
    cleaning = html.escape(str(vehicle_state.get("cleaning", "") or ""))
    def due_km(field):
        value = vehicle_value(field)
        try:
            return f"{int(value):,} km".replace(",", " ") if int(value) > 0 else "—"
        except (ValueError, TypeError):
            return "—"

    adblue_due = due_km("prochaine_adblue")
    chain_due = due_km("prochaine_chaine")
    def remaining_km(next_field, remaining_field):
        remaining = vehicle_value(remaining_field)
        if remaining is not None and str(remaining).strip() not in ("", "0"):
            return due_km(remaining_field)
        try:
            next_km, current_km = int(vehicle_value(next_field)), int(vehicle_value("compteur"))
            return f"{max(0, next_km-current_km):,} km".replace(",", " ") if next_km > 0 else "—"
        except (ValueError, TypeError):
            return "—"

    administrative = "".join(
        f'<div><span>{html.escape(label)}</span><b>{html.escape(str(value or "—"))}</b></div>'
        for label, value in (
            ("Assurance jusqu’au", vehicle_value("assurance_fin")),
            ("Visite technique jusqu’au", vehicle_value("controle_technique")),
            ("Prochaine vidange", due_km("prochaine_vidange")),
            ("Vidange restante", remaining_km("prochaine_vidange", "vidange_restant")),
            ("Prochain AdBlue", adblue_due),
            ("AdBlue restant", due_km("adblue_restant")),
            ("Chaîne prochaine", chain_due),
            ("Chaîne restante", remaining_km("prochaine_chaine", "chaine_restant")),
        )
    )

    conditions = app._contract_conditions_html()
    try:
        status_row = app.conn.execute("SELECT return_status FROM contracts WHERE numero=?", (values.get("contract_no", ""),)).fetchone()
        status = str(status_row[0] or "En cours") if status_row else "En cours"
    except Exception:
        status = "En cours"

    photo = (f'<img src="{photo_uri}" alt="Photo du véhicule {html.escape(code)}">' if photo_uri else
             f'<div class="photo-empty">Aucune photo enregistrée pour le véhicule {html.escape(code)}<br><small>Ajouter la photo dans la fiche Véhicule</small></div>')
    state = f'<img src="{state_uri}" alt="État du véhicule : quatre vues">' if state_uri else '<span>Schéma du véhicule indisponible</span>'
    stamp = f'<img src="{stamp_uri}" alt="Cachet de l’agence">' if stamp_uri else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Contrat {safe('contract_no')}</title>
<style>
@page{{size:A4 portrait;margin:4mm}}
*{{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
html,body{{margin:0;padding:0;background:white}}
body{{width:202mm;height:289mm;margin:auto;color:#24343a;font:8.3px/1.2 'Segoe UI',Arial,sans-serif}}
.page{{height:100%;display:flex;flex-direction:column;gap:1.7mm}}
.masthead{{height:18mm;display:grid;grid-template-columns:43mm 55mm 1fr;gap:3mm;align-items:center}}
.logo-slot{{height:17mm;display:flex;align-items:center;justify-content:flex-start;color:#98928c;font-size:7px;text-align:left}}
.logo-slot img{{max-height:17mm;max-width:43mm;object-fit:contain;object-position:left center;margin:0}}
.company-info{{height:17mm;padding-left:1mm;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;text-align:left;color:#596466;font-size:8.3px;font-weight:600;line-height:1.3;overflow:hidden}}
.company-info b{{font-size:10px;font-weight:800;color:#4e5a5c}}
.company-info span{{max-width:53mm;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.title{{height:15mm;display:flex;flex-direction:column;justify-content:center;align-items:flex-end;text-align:right}}
.title h1{{font-family:Georgia,serif;font-weight:700;font-size:17px;letter-spacing:.2px;margin:0;white-space:nowrap}}
.title small{{color:#a96b57;font-size:8.8px;font-weight:700;margin-top:1mm}}
.title em{{color:#667576;font-size:7.3px;font-style:normal;letter-spacing:.3px;margin-top:.4mm}}
.meta{{height:10mm;display:grid;grid-template-columns:repeat(3,1fr);gap:2mm}}
.meta div{{border:1px solid #dedbd6;border-radius:2mm;background:#faf9f6;padding:0 3mm;display:flex;align-items:center;justify-content:space-between}}
.meta b{{font-size:11px}}.meta .client-code{{color:#a95f49;font-size:14px}}
.two-drivers{{height:49mm;display:grid;grid-template-columns:1fr 1fr;gap:2.5mm}}
.box{{border:1px solid #d2d8d6;border-radius:2mm;overflow:hidden;background:#fff;min-width:0}}
.section-head{{height:8mm;display:flex;align-items:center;gap:2mm;padding:0 2mm;font-family:Georgia,serif;font-size:11px;color:#24343a}}
.section-head strong{{font-weight:700}}
.section-head.terra{{background:#f4e8e2;border-left:1.2mm solid #ba7d69}}
.section-head.teal{{background:#eaf2f0;border-left:1.2mm solid #729b99}}
.section-head.stone{{background:#f1eee8;border-left:1.2mm solid #a69d92}}
.section-head.mist{{background:#eaf2f0}}
.section-head.client{{background:#c8836d;color:white}}
.section-head.second{{background:#698e8d;color:white}}
.icon-tile{{width:6mm;height:6mm;border-radius:1.2mm;background:#ffffffa8;display:grid;place-items:center;flex:none}}
.icon{{width:4.5mm;height:4.5mm}}
.fields{{padding:1mm 3mm}}
.two-drivers .detail{{min-height:3.15mm;font-size:7.5px}}
.detail{{display:grid;grid-template-columns:38% 1fr;align-items:center;border-bottom:1px solid #e6e7e3;min-height:4mm;gap:1mm}}
.detail:last-child{{border-bottom:none}}.detail span{{color:#556365}}.detail b{{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.detail .strong{{font-weight:800;color:#1d3037}}
.detail .client-code{{color:#a95f49;font-weight:800}}
.no-driver{{height:39mm;display:flex;align-items:center;justify-content:center;flex-direction:column;color:#a9664c;text-align:center;gap:1mm;font:700 11px/1.2 Georgia,serif}}
.no-driver img{{display:block;width:30mm;height:30mm;object-fit:contain}}
.vehicle{{height:38mm}}
.vehicle-body{{height:30mm;display:grid;grid-template-columns:43% 1fr;gap:3mm;padding:1mm 3mm 1.5mm;min-height:0}}
.vehicle-photo{{height:27.5mm;max-height:27.5mm;min-width:0;min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden;border-right:1px solid #d7ddda;padding-right:3mm}}
.vehicle-photo img{{display:block;flex:none;width:auto!important;height:auto!important;max-width:100%!important;max-height:27mm!important;object-fit:contain!important}}
.photo-empty{{text-align:center;color:#8a9998;border:1px dashed #cbd7d5;padding:7mm 2mm}}
.vehicle-fields .detail{{min-height:5.4mm}}
.middle{{height:60mm;display:grid;grid-template-columns:2.15fr 1fr;gap:2.5mm}}
.state-image{{height:25mm;max-height:25mm;margin:1mm 2mm 0;text-align:center;line-height:0;overflow:hidden}}
.state-image img{{display:inline-block;width:auto!important;height:auto!important;max-width:100%!important;max-height:25mm!important;object-fit:contain;vertical-align:middle}}
.views{{height:3.5mm;margin:0 2mm;display:grid;grid-template-columns:repeat(4,1fr);align-items:center;color:#657575;font-size:6.5px}}
.view-check{{display:flex;align-items:center;gap:.5mm;white-space:nowrap}}
.view-check i{{width:2.3mm;height:2.3mm;border:1px solid #a7b7b1;border-radius:.3mm;font:700 7px/2mm Arial,sans-serif;color:#a45d49;font-style:normal}}
.admin-details{{height:15mm;margin:1mm 2mm 0;display:grid;grid-template-columns:repeat(2,1fr);grid-template-rows:repeat(4,3.7mm);column-gap:3mm;overflow:hidden}}
.admin-details div{{display:flex;align-items:center;justify-content:space-between;gap:1mm;border-bottom:1px solid #e2e7e3;font-size:7px;white-space:nowrap}}
.admin-details span{{color:#657575}}.admin-details b{{color:#24343a}}
.state-bottom{{height:6mm;margin:1mm 2mm 0}}
.observations{{height:6mm;border-top:1px solid #e2e7e3;color:#5d696a;padding-top:.6mm;overflow:hidden;overflow-wrap:anywhere;font-size:7px}}
.equipment-list{{height:33mm;display:grid;grid-template-columns:1fr 1fr;column-gap:2mm;grid-auto-flow:column;grid-template-rows:repeat(6,1fr);padding:1mm 2mm}}
.equipment-item{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:7px;display:flex;align-items:center;gap:1mm}}
.equipment-item span{{flex:none;width:3mm;height:3mm;line-height:2.5mm;text-align:center;border:1px solid #be8876;color:#ae6b57;border-radius:.6mm}}
.equipment-item span.checked{{background:#b77560;border-color:#b77560;color:white;font-weight:900;font-size:8px}}
.fuel{{height:10mm;margin:0 2mm;border-top:1px solid #d6dedb;padding-top:1mm}}
.fuel .caption{{display:flex;justify-content:space-between;font-weight:700;font-size:7px}}
.fuelrow{{display:flex;align-items:center;gap:1mm;margin-top:1mm}}
.segments{{flex:1;display:grid;grid-template-columns:repeat(8,1fr);gap:.6mm;height:3mm}}
.segments i{{background:#dce6e3;border-radius:.5mm}}.segments i.on{{background:#ba806d}}
.period{{height:19mm}}.period-grid{{height:11mm;display:grid;grid-template-columns:repeat(6,1fr);padding:1mm 2mm}}
.period-grid div{{border-right:1px solid #d4dfdc;text-align:center;font-size:7px;color:#536568}}
.period-grid div:last-child{{border:0}}.period-grid strong{{display:block;font-size:10px;color:#24343a;margin-top:1mm}}
.payment{{height:19mm}}.payment-grid{{height:11mm;display:grid;grid-template-columns:repeat(3,1fr);gap:2mm;padding:1mm 2mm}}
.payment-grid div{{border:1px solid #d8c7c0;border-radius:1.4mm;background:#fcf7f4;padding:1mm 2mm;font-size:7px}}
.payment-grid div:nth-child(2){{background:#f1f7f5;border-color:#c0d6d1}}
.payment-grid strong{{display:block;font-size:12px;color:#a45d49;margin-top:.4mm}}
.payment-grid div:nth-child(2) strong{{color:#3b7775}}
.conditions{{height:26mm}}
.conditions-content{{height:18mm;overflow:hidden;padding:2mm 3mm;column-count:2;column-gap:5mm;white-space:normal;overflow-wrap:anywhere;font-size:7px;line-height:1.25}}
.signatures{{height:27mm;display:grid;grid-template-columns:repeat(3,1fr);gap:2.5mm}}
.signature-body{{height:19mm;margin:1mm 2mm;border:1px solid #d4ddda;border-radius:1.2mm;padding:1mm 2mm;font-size:7px;position:relative}}
.signature-body img{{max-height:17mm;max-width:34mm;object-fit:contain;display:block;margin:auto 0 auto auto}}
.signature-identity img{{max-height:10mm;max-width:40mm;margin:0 auto;flex-shrink:0}}
.signature-identity{{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:.3mm;text-align:center}}
.signature-label{{font:600 7px/1.2 'Segoe UI',Arial,sans-serif;color:#667576}}
.signature-cin{{font:800 10px/1.2 'Segoe UI',Arial,sans-serif;color:#24343a;letter-spacing:.3px;overflow-wrap:anywhere}}
.signature-agency{{display:flex;align-items:center;justify-content:center;padding:.2mm 1mm}}
.signature-agency img{{display:block;max-height:18.4mm;max-width:46mm;width:auto;height:auto;margin:auto;object-fit:contain}}
.signature-denied{{display:block;text-align:center;padding-top:5mm;color:#a9664c;font:700 8px/1.3 Georgia,serif}}
.footer{{margin-top:auto;height:6mm;border-top:1px solid #bbc7c3;display:flex;align-items:center;justify-content:space-between;font-size:7px;color:#466164;white-space:nowrap}}
.footer strong{{font-family:Georgia,serif;color:#a65e49}}
@media print{{body{{margin:0}}}}
</style></head><body><div class="page">
<header class="masthead"><div class="logo-slot">{logo_box}</div>
<div class="company-info"><b>{setting('company_name','HBZ RENT CAR')}</b><span>{setting('company_phone','0661247113')}</span><span>{setting('company_email','hajbenziancar@gmail.com')}</span><span>{setting('company_address','')}</span></div>
<div class="title"><h1>CONTRAT DE LOCATION</h1><small>Votre route, notre engagement</small><em>Confort · confiance · liberté</em></div></header>
<div class="meta"><div>Code client <b class="client-code">{safe('client_code')}</b></div><div>N° de contrat <b>{safe('contract_no')}</b></div><div>Date du contrat <b>{safe('date_start')}</b></div></div>
<div class="two-drivers">
<section class="box">{heading('Client principal','id','client')}<div class="fields">{first}</div></section>
<section class="box">{heading('Deuxième conducteur','driver','second')}<div class="fields">{second}</div></section></div>
<section class="box vehicle">{heading('Véhicule loué','car','terra')}<div class="vehicle-body">
<div class="vehicle-photo">{photo}</div><div class="vehicle-fields">
{row('Marque / Modèle',safe('vehicle_model'),True)}
{row('Immatriculation',safe('plate'),True)}
{row('N° de châssis',safe('chassis'),True)}
{row('Km au départ',safe('km_start')+' km')}
{row('Code véhicule',safe('vehicle_code'))}
</div></div></section>
<div class="middle">
<section class="box">{heading('État du véhicule','tool')}<div class="state-image">{state}</div><div class="views">{damage_checks}</div>
<div class="admin-details">{administrative}</div>
<div class="state-bottom"><div class="observations">Observations : {observations or '__________________________________'} &nbsp;·&nbsp; Nettoyage : {cleaning or '—'}</div></div></section>
<section class="box">{heading('Équipements remis','box')}<div class="equipment-list">{checks}</div>
<div class="fuel"><div class="caption"><span>Niveau de carburant au départ</span><span>{html.escape(fuel)}</span></div><div class="fuelrow"><b>E</b><div class="segments">{segments}</div><b>F</b></div></div></section></div>
<section class="box period">{heading('Période de location','calendar','teal')}<div class="period-grid">
<div>Date départ<strong>{safe('date_start')}</strong></div><div>Heure départ<strong>{safe('time_start')}</strong></div>
<div>Date retour<strong>{safe('date_end')}</strong></div><div>Heure retour<strong>{safe('time_end')}</strong></div>
<div>Durée (jours)<strong>{safe('duration')}</strong></div><div>Prix / jour<strong>{amount('daily_price')}</strong></div>
</div></section>
<section class="box payment">{heading('Paiement et soldes','money','stone')}<div class="payment-grid">
<div>Montant total (DH)<strong>{amount('total')}</strong></div>
<div>Règlement (DH)<strong>{amount('paid')}</strong></div>
<div>Reste à payer (DH)<strong>{amount('balance')}</strong></div></div></section>
<section class="box conditions">{heading('Conditions générales de location','file')}<div class="conditions-content">{conditions}</div></section>
<div class="signatures">
<section class="box">{heading('Signature client','pen')}<div class="signature-body signature-identity">{client_signature}</div></section>
<section class="box">{heading('Signature 2e conducteur','pen')}<div class="signature-body signature-identity">{second_signature}</div></section>
<section class="box">{heading('Cachet et signature agence','file')}<div class="signature-body signature-agency">{("<img src=\""+html.escape(app.agency_signature)+"\" alt=\"Signature agence\" style=\"max-width:100%;max-height:22mm\">") if getattr(app,"agency_signature","") else stamp}</div></section></div>
<footer class="footer"><span>{setting('company_name','HBZ RENT CAR')} · {setting('company_phone','0661247113')} · {setting('company_email','hajbenziancar@gmail.com')}</span>
<span>{setting('company_address','')}</span><strong>{html.escape(status)}</strong></footer>
</div></body></html>"""
