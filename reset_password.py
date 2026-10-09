import hashlib, secrets, sqlite3, getpass
from pathlib import Path
db=Path(__file__).resolve().parent/"gestionpro_hbz.db"; conn=sqlite3.connect(db)
admin=input("Identifiant administrateur : ").strip(); password=getpass.getpass("Mot de passe administrateur : ")
row=conn.execute("SELECT password_hash FROM users WHERE username=? AND role='ADMINISTRATEUR' AND active=1",(admin,)).fetchone(); valid=False
if row:
    try:
        _,salt,digest=row[0].split("$",2); valid=hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),200000).hex()==digest
    except ValueError: pass
if not valid: print("Accès administrateur refusé."); raise SystemExit(1)
target=input("Compte à réinitialiser : ").strip(); new=getpass.getpass("Nouveau mot de passe (8 caractères minimum) : ")
if len(new)<8: print("Mot de passe trop court."); raise SystemExit(1)
salt=secrets.token_hex(16); digest=hashlib.pbkdf2_hmac("sha256",new.encode(),salt.encode(),200000).hex()
cur=conn.execute("UPDATE users SET password_hash=? WHERE username=?",(f"pbkdf2_sha256${salt}${digest}",target));conn.commit()
print("Mot de passe réinitialisé." if cur.rowcount else "Utilisateur introuvable.")
