from pathlib import Path
s=Path('main.py').read_text(encoding='utf-8')
checks={
'Build V34':'V34.2026-09-15-FOURNISSEUR-CORRIGE' in s,
'Montant facture':'Montant facture / achats' in s,
'Deja regle':'Déjà réglé' in s,
'Nouveau reglement':'Nouveau règlement' in s,
'Reste':'Reste après règlement' in s,
'Confirmation':'✓ Confirmer' in s,
'Annuler':'Annuler' in s,
'Mixte':'MIXTE' in s and 'Caisse et banque diminuées selon la répartition' in s,
'Fournisseur compact':'form_columns = 4 if name == "suppliers"' in s,
}
for k,v in checks.items(): print(('OK  ' if v else 'FAIL'),k)
raise SystemExit(0 if all(checks.values()) else 1)
