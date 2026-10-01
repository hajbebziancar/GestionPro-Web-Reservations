"""Restore private backups into an EMPTY persistent data directory."""
import argparse, pathlib, sqlite3, shutil, tarfile, os
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--photos',required=True);p.add_argument('--destination',default='/data');p.add_argument('--secret');args=p.parse_args()
dest=pathlib.Path(args.destination).resolve();dest.mkdir(parents=True,exist_ok=True)
if (dest/'gestion.db').exists():raise SystemExit('Destination déjà utilisée : aucune base écrasée.')
source=pathlib.Path(args.db).resolve()
if not source.is_file():raise SystemExit('Sauvegarde de base introuvable.')
with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as c:
    if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise SystemExit('Base invalide.')
    c.execute('SELECT username FROM web_users').fetchall()
    with sqlite3.connect(dest/'gestion.db.restoring') as target:c.backup(target)
photo_dest=dest/'uploads'/'vehicules';photo_dest.mkdir(parents=True,exist_ok=True)
with tarfile.open(args.photos,'r:gz') as archive:
    # Only regular vehicle files from the tar created with `-C uploads vehicules`.
    members=archive.getmembers()
    for member in members:
        path=pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!='vehicules' or not (member.isdir() or member.isfile()):raise SystemExit('Archive de photos invalide.')
    for member in members:
        if not member.isfile():continue
        rel=pathlib.PurePosixPath(member.name).parts[1:];out=photo_dest.joinpath(*rel);out.parent.mkdir(parents=True,exist_ok=True)
        with archive.extractfile(member) as src,out.open('wb') as target:shutil.copyfileobj(src,target)
if args.secret:
    secret=pathlib.Path(args.secret).read_text().strip()
    if not secret:raise SystemExit('Clé vide.')
    (dest/'.secret_key').write_text(secret);os.chmod(dest/'.secret_key',0o600)
os.replace(dest/'gestion.db.restoring',dest/'gestion.db')
print('Restauration terminée. Aucune ancienne base écrasée.')
