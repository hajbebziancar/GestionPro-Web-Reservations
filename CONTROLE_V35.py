from pathlib import Path
s=Path('main.py').read_text(encoding='utf-8')
checks={
 'snapshot avant refresh':'quick_saved_display = {' in s,
 'restauration montant':'q["total"].set(f"{values[10]:.2f} MAD")' in s,
 'restauration reste':'q["balance"].set(f"{values[12]:.2f} MAD")' in s,
 'restauration duree':'q["duration"].set(f"{values[8]} jour"' in s,
 'bouton enregistrer':'text="▣ Enregistrer"' in s,
}
for k,v in checks.items(): print(('OK' if v else 'ERREUR'),k)
raise SystemExit(0 if all(checks.values()) else 1)
