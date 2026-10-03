from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from pathlib import Path
from datetime import datetime, date
import sqlite3, secrets, os, re, uuid

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ['GESTIONPRO_DATA_DIR']).expanduser().resolve() if os.environ.get('GESTIONPRO_DATA_DIR') else None
DB_PATH = Path(os.environ.get('GESTIONPRO_WEB_DB', str(DATA_DIR / 'gestion.db') if DATA_DIR else str(ROOT / 'gestion.db'))).expanduser().resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
SITE_DIR = Path(__file__).resolve().parent
SECRET_FILE = (DATA_DIR or SITE_DIR) / '.secret_key'
SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = (DATA_DIR / 'uploads' / 'vehicules') if DATA_DIR else SITE_DIR / 'static' / 'uploads' / 'vehicules'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

if SECRET_FILE.exists():
    SECRET_KEY = SECRET_FILE.read_text(encoding='utf-8').strip()
else:
    SECRET_KEY = secrets.token_hex(32)
    SECRET_FILE.write_text(SECRET_KEY, encoding='utf-8')

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', SECRET_KEY),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE','0') == '1',
    MAX_CONTENT_LENGTH=20 * 1024 * 1024,
)

STATUS_ALLOWED = {'EN ATTENTE','CONFIRMEE','ANNULEE'}
VEHICLE_STATUS_ALLOWED = {'EN SERVICE','HORS SERVICE'}
ALLOWED_IMAGE_EXTENSIONS = {'png','jpg','jpeg','webp'}

from contextlib import contextmanager

@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=15000')
    try:
        with c:
            yield c
    finally:
        c.close()

def init_web_schema():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS web_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'ADMIN',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS web_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS web_vehicle_media(
            code_vehicule TEXT PRIMARY KEY,
            image_filename TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')

init_web_schema()


def ensure_core_schema():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS vehicules(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code_vehicule TEXT NOT NULL UNIQUE,
            marque TEXT, immatriculation TEXT, num_chassis TEXT, compteur REAL DEFAULT 0,
            service TEXT DEFAULT 'EN SERVICE', prix_jour REAL DEFAULT 0, remarque TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS reservations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code_reservation TEXT NOT NULL UNIQUE,
            code_client TEXT NOT NULL, cin TEXT, nom TEXT, prenom TEXT, telephone TEXT,
            code_vehicule TEXT NOT NULL, marque_vehicule TEXT, immatriculation TEXT,
            date_depart TEXT NOT NULL, heure_depart TEXT NOT NULL, date_retour TEXT NOT NULL,
            heure_retour TEXT NOT NULL, duree REAL DEFAULT 0, prix REAL DEFAULT 0,
            montant REAL DEFAULT 0, avance REAL DEFAULT 0, reste REAL DEFAULT 0,
            statut TEXT DEFAULT 'EN ATTENTE', observation TEXT, date_creation TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS locations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code_location TEXT, code_vehicule TEXT,
            date_depart TEXT, date_retour TEXT
        )""")

ensure_core_schema()

def csrf_token():
    token = session.get('_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf'] = token
    return token
app.jinja_env.globals['csrf_token'] = csrf_token
app.jinja_env.globals['current_year'] = datetime.now().year

@app.before_request
def csrf_protect():
    # Les routes API GestionPro utilisent leur propre authentification Bearer.
    # Elles ne doivent pas être bloquées par le CSRF des formulaires Web.
    if request.path.startswith('/api/') or request.endpoint == 'remote_signatures.save':
        return

    if request.method in {'POST','PUT','PATCH','DELETE'}:
        expected = session.get('_csrf','')
        supplied = request.form.get('_csrf','') or request.headers.get('X-CSRF-Token','')
        if not expected or not secrets.compare_digest(expected, supplied):
            abort(400, 'Jeton de sécurité invalide. Rechargez la page.')

def admin_count():
    with db() as c:
        return c.execute('SELECT COUNT(*) FROM web_users WHERE active=1').fetchone()[0]

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('web_user'):
            return redirect(url_for('admin_login', next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def audit(action, details=''):
    try:
        with db() as c:
            c.execute('INSERT INTO web_audit(username,action,details,ip) VALUES(?,?,?,?)',
                      (session.get('web_user'), action, details[:1000], request.headers.get('X-Forwarded-For', request.remote_addr)))
    except Exception:
        pass

def normalize_status(s):
    s = (s or '').strip().upper().replace('É','E')
    if s in ('CONFIRMEE','CONFIRME','CONFIRMÉE'): return 'CONFIRMEE'
    if s in ('ANNULEE','ANNULE','ANNULÉE'): return 'ANNULEE'
    return 'EN ATTENTE'

def to_date(s):
    value = (s or '').strip()
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError('date invalide')

def reservation_overlap(c, vehicle_code, start_date, end_date, ignore_reservation_id=None):
    sql = '''SELECT id,code_reservation,date_depart,date_retour,statut FROM reservations
             WHERE code_vehicule=? AND COALESCE(statut,'EN ATTENTE') NOT IN ('ANNULEE','ANNULÉE')'''
    params = [vehicle_code]
    if ignore_reservation_id:
        sql += ' AND id<>?'; params.append(ignore_reservation_id)
    rows = c.execute(sql, params).fetchall()
    for r in rows:
        try:
            a,b = to_date(r['date_depart']), to_date(r['date_retour'])
            if start_date <= b and end_date >= a:
                return True
        except Exception:
            continue
    rows = c.execute('''SELECT date_depart,date_retour FROM locations WHERE code_vehicule=?''', (vehicle_code,)).fetchall()
    for r in rows:
        try:
            a,b = to_date(r['date_depart']), to_date(r['date_retour'])
            if start_date <= b and end_date >= a:
                return True
        except Exception:
            continue
    return False

def generate_reservation_code(c):
    prefix = datetime.now().strftime('WEB%y%m%d')
    for _ in range(20):
        code = f"{prefix}-{secrets.randbelow(9000)+1000}"
        if not c.execute('SELECT 1 FROM reservations WHERE code_reservation=?', (code,)).fetchone():
            return code
    return prefix + '-' + secrets.token_hex(3).upper()

def generate_vehicle_code(c):
    rows = c.execute("SELECT code_vehicule FROM vehicules").fetchall()
    nums=[]
    for r in rows:
        try: nums.append(int(str(r['code_vehicule']).strip()))
        except Exception: pass
    return f"{(max(nums) + 1 if nums else 1):06d}"

def media_map(c):
    return {r['code_vehicule']: r['image_filename'] for r in c.execute('SELECT code_vehicule,image_filename FROM web_vehicle_media').fetchall()}

def save_vehicle_image(file_storage, old_filename=None):
    if not file_storage or not file_storage.filename:
        return old_filename
    filename = secure_filename(file_storage.filename)
    if '.' not in filename or filename.rsplit('.',1)[1].lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Photo invalide. Formats acceptés : JPG, PNG, WEBP.')
    ext = filename.rsplit('.',1)[1].lower()
    new_name = f"vehicule_{uuid.uuid4().hex[:16]}.{ext}"
    file_storage.save(UPLOAD_DIR / new_name)
    if old_filename:
        try: (UPLOAD_DIR / old_filename).unlink(missing_ok=True)
        except Exception: pass
    return new_name

def vehicle_link_count(c, code):
    total = 0
    for table in ('locations','reservations'):
        try:
            total += c.execute(f'SELECT COUNT(*) FROM {table} WHERE code_vehicule=?', (code,)).fetchone()[0]
        except sqlite3.Error:
            pass
    return total

@app.route('/')
def home():
    with db() as c:
        vehicles = c.execute('''SELECT code_vehicule, marque, immatriculation, prix_jour, service, compteur
                                FROM vehicules
                                WHERE UPPER(COALESCE(service,''))='EN SERVICE'
                                ORDER BY marque, immatriculation''').fetchall()
        media = media_map(c)
    return render_template('home.html', vehicles=vehicles, media=media)

@app.route('/reserver', methods=['POST'])
def reserve():
    nom = request.form.get('nom','').strip()
    prenom = request.form.get('prenom','').strip()
    tel = request.form.get('telephone','').strip()
    cin = request.form.get('cin','').strip()
    vehicle = request.form.get('code_vehicule','').strip()
    dep = request.form.get('date_depart','').strip()
    ret = request.form.get('date_retour','').strip()
    hdep = request.form.get('heure_depart','09:00').strip()
    hret = request.form.get('heure_retour','09:00').strip()
    observation = request.form.get('observation','').strip()
    if not all([nom, prenom, tel, vehicle, dep, ret]):
        flash('Veuillez remplir tous les champs obligatoires.', 'error'); return redirect(url_for('home'))
    if len(nom) > 80 or len(prenom) > 80 or len(tel) > 30 or len(cin) > 40 or len(observation) > 500:
        flash('Une valeur saisie est trop longue.', 'error'); return redirect(url_for('home'))
    if not re.fullmatch(r'[0-9+() .-]{6,30}', tel):
        flash('Numéro de téléphone invalide.', 'error'); return redirect(url_for('home'))
    try:
        d1,d2 = to_date(dep), to_date(ret)
    except ValueError:
        flash('Dates invalides.', 'error'); return redirect(url_for('home'))
    if d1 < date.today() or d2 < d1:
        flash('La période de réservation est invalide.', 'error'); return redirect(url_for('home'))
    duree = (d2-d1).days + 1
    with db() as c:
        v = c.execute('''SELECT code_vehicule,marque,immatriculation,prix_jour FROM vehicules
                         WHERE code_vehicule=? AND UPPER(COALESCE(service,''))='EN SERVICE' ''',(vehicle,)).fetchone()
        if not v:
            flash('Ce véhicule n’est plus disponible.', 'error'); return redirect(url_for('home'))
        if reservation_overlap(c, vehicle, d1, d2):
            flash('Ce véhicule est déjà réservé ou loué pour cette période.', 'error'); return redirect(url_for('home'))
        code = generate_reservation_code(c)
        digits = re.sub(r'\D','',tel)
        code_client = 'WEB-' + digits[-8:] if digits else 'WEB-' + secrets.token_hex(4).upper()
        prix = float(v['prix_jour'] or 0)
        montant = prix * duree
        c.execute('''INSERT INTO reservations(
            code_reservation,code_client,cin,nom,prenom,telephone,code_vehicule,marque_vehicule,immatriculation,
            date_depart,heure_depart,date_retour,heure_retour,duree,prix,montant,avance,reste,statut,observation,date_creation)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)''',
            (code,code_client,cin,nom,prenom,tel,v['code_vehicule'],v['marque'],v['immatriculation'],dep,hdep,ret,hret,duree,prix,montant,0,montant,'EN ATTENTE', '[WEB] '+observation))
    return render_template('success.html', code=code, nom=nom, montant=montant)

@app.route('/admin/setup', methods=['GET','POST'])
def admin_setup():
    if admin_count() > 0:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        confirm = request.form.get('confirm','')
        if len(username) < 3:
            flash('Nom utilisateur trop court.', 'error')
        elif len(password) < 10:
            flash('Le mot de passe doit contenir au moins 10 caractères.', 'error')
        elif password != confirm:
            flash('Les mots de passe ne correspondent pas.', 'error')
        else:
            with db() as c:
                c.execute('INSERT INTO web_users(username,password_hash,role) VALUES(?,?,?)', (username,generate_password_hash(password),'ADMIN'))
            flash('Compte administrateur créé. Connectez-vous.', 'success')
            return redirect(url_for('admin_login'))
    return render_template('setup.html')

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if admin_count() == 0:
        return redirect(url_for('admin_setup'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        with db() as c:
            u = c.execute('SELECT * FROM web_users WHERE username=? AND active=1',(username,)).fetchone()
        if u and check_password_hash(u['password_hash'], password):
            session.clear(); session['web_user']=u['username']; session['_csrf']=secrets.token_urlsafe(32)
            audit('LOGIN')
            return redirect(url_for('admin_dashboard'))
        flash('Identifiants incorrects.', 'error')
    return render_template('login.html')

@app.route('/admin/logout', methods=['POST'])
@login_required
def admin_logout():
    audit('LOGOUT'); session.clear(); return redirect(url_for('admin_login'))

@app.route('/admin')
@login_required
def admin_dashboard():
    status = request.args.get('statut','').strip()
    q = request.args.get('q','').strip()
    sql = 'SELECT * FROM reservations WHERE 1=1'
    params=[]
    if status in STATUS_ALLOWED:
        sql += ' AND UPPER(REPLACE(COALESCE(statut,\'EN ATTENTE\'),\'É\',\'E\'))=?'; params.append(status)
    if q:
        sql += ' AND (code_reservation LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ? OR marque_vehicule LIKE ? OR immatriculation LIKE ?)'
        like=f'%{q}%'; params += [like]*6
    sql += ' ORDER BY datetime(date_creation) DESC, id DESC LIMIT 500'
    with db() as c:
        rows = c.execute(sql,params).fetchall()
        counts = {
            'attente': c.execute("SELECT COUNT(*) FROM reservations WHERE UPPER(REPLACE(COALESCE(statut,'EN ATTENTE'),'É','E'))='EN ATTENTE'").fetchone()[0],
            'confirmee': c.execute("SELECT COUNT(*) FROM reservations WHERE UPPER(REPLACE(COALESCE(statut,''),'É','E')) IN ('CONFIRMEE','CONFIRME')").fetchone()[0],
            'annulee': c.execute("SELECT COUNT(*) FROM reservations WHERE UPPER(REPLACE(COALESCE(statut,''),'É','E')) IN ('ANNULEE','ANNULE')").fetchone()[0],
            'parc': c.execute("SELECT COUNT(*) FROM vehicules WHERE UPPER(COALESCE(service,''))='EN SERVICE'").fetchone()[0],
        }
    return render_template('admin.html', rows=rows, counts=counts, q=q, statut=status)

@app.route('/admin/reservation/<int:rid>/status', methods=['POST'])
@login_required
def change_status(rid):
    new = request.form.get('status','').strip().upper()
    if new not in STATUS_ALLOWED:
        abort(400)
    with db() as c:
        r = c.execute('SELECT code_reservation FROM reservations WHERE id=?',(rid,)).fetchone()
        if not r: abort(404)
        c.execute('UPDATE reservations SET statut=? WHERE id=?',(new,rid))
    audit('RESERVATION_STATUS', f"{r['code_reservation']} -> {new}")
    flash('Statut mis à jour.', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/admin/parc')
@login_required
def admin_fleet():
    q = request.args.get('q','').strip()
    service = request.args.get('service','').strip().upper()
    sql = '''SELECT code_vehicule,marque,immatriculation,num_chassis,compteur,service,prix_jour,remarque
             FROM vehicules WHERE 1=1'''
    params=[]
    if q:
        like=f'%{q}%'
        sql += ' AND (code_vehicule LIKE ? OR marque LIKE ? OR immatriculation LIKE ? OR num_chassis LIKE ?)'
        params += [like]*4
    if service in VEHICLE_STATUS_ALLOWED:
        sql += ' AND UPPER(COALESCE(service,\'EN SERVICE\'))=?'; params.append(service)
    sql += ' ORDER BY CASE WHEN UPPER(COALESCE(service,\'\'))=\'EN SERVICE\' THEN 0 ELSE 1 END, marque, immatriculation'
    with db() as c:
        vehicles = c.execute(sql, params).fetchall()
        media = media_map(c)
        stats = {
            'total': c.execute('SELECT COUNT(*) FROM vehicules').fetchone()[0],
            'service': c.execute("SELECT COUNT(*) FROM vehicules WHERE UPPER(COALESCE(service,''))='EN SERVICE'").fetchone()[0],
            'hors': c.execute("SELECT COUNT(*) FROM vehicules WHERE UPPER(COALESCE(service,''))<>'EN SERVICE'").fetchone()[0],
        }
    return render_template('fleet.html', vehicles=vehicles, media=media, stats=stats, q=q, service=service)

@app.route('/admin/parc/ajouter', methods=['GET','POST'])
@login_required
def admin_fleet_add():
    with db() as c:
        suggested_code = generate_vehicle_code(c)
    if request.method == 'POST':
        code = request.form.get('code_vehicule','').strip()
        marque = request.form.get('marque','').strip()
        immat = request.form.get('immatriculation','').strip()
        chassis = request.form.get('num_chassis','').strip()
        service = request.form.get('service','EN SERVICE').strip().upper()
        remarque = request.form.get('remarque','').strip()
        try: prix = float((request.form.get('prix_jour','0') or '0').replace(',','.'))
        except ValueError: prix = -1
        try: compteur = float((request.form.get('compteur','0') or '0').replace(',','.'))
        except ValueError: compteur = -1
        if not code or not marque or not immat:
            flash('Code véhicule, marque et immatriculation sont obligatoires.', 'error')
        elif service not in VEHICLE_STATUS_ALLOWED:
            flash('État du véhicule invalide.', 'error')
        elif prix < 0 or compteur < 0:
            flash('Prix/jour et compteur doivent être des nombres positifs.', 'error')
        elif len(code)>30 or len(marque)>100 or len(immat)>40 or len(chassis)>100 or len(remarque)>500:
            flash('Une valeur saisie est trop longue.', 'error')
        else:
            try:
                with db() as c:
                    if c.execute('SELECT 1 FROM vehicules WHERE code_vehicule=?',(code,)).fetchone():
                        flash('Ce code véhicule existe déjà.', 'error')
                        return render_template('fleet_form.html', mode='add', vehicle=request.form, suggested_code=suggested_code, image=None)
                    image = save_vehicle_image(request.files.get('photo'))
                    c.execute('''INSERT INTO vehicules(code_vehicule,marque,immatriculation,num_chassis,compteur,service,prix_jour,remarque)
                                 VALUES(?,?,?,?,?,?,?,?)''', (code,marque,immat,chassis,compteur,service,prix,remarque))
                    if image:
                        c.execute('INSERT OR REPLACE INTO web_vehicle_media(code_vehicule,image_filename,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)', (code,image))
                audit('VEHICLE_ADD', f'{code} {marque} {immat}')
                flash('Véhicule ajouté au parc avec succès.', 'success')
                return redirect(url_for('admin_fleet'))
            except ValueError as e:
                flash(str(e), 'error')
            except sqlite3.IntegrityError:
                flash('Impossible d’ajouter ce véhicule : code ou donnée déjà utilisée.', 'error')
    return render_template('fleet_form.html', mode='add', vehicle=None, suggested_code=suggested_code, image=None)

@app.route('/admin/parc/<code>/modifier', methods=['GET','POST'])
@login_required
def admin_fleet_edit(code):
    with db() as c:
        vehicle = c.execute('SELECT * FROM vehicules WHERE code_vehicule=?',(code,)).fetchone()
        image_row = c.execute('SELECT image_filename FROM web_vehicle_media WHERE code_vehicule=?',(code,)).fetchone()
    if not vehicle: abort(404)
    current_image = image_row['image_filename'] if image_row else None
    if request.method == 'POST':
        marque = request.form.get('marque','').strip()
        immat = request.form.get('immatriculation','').strip()
        chassis = request.form.get('num_chassis','').strip()
        service = request.form.get('service','EN SERVICE').strip().upper()
        remarque = request.form.get('remarque','').strip()
        try: prix = float((request.form.get('prix_jour','0') or '0').replace(',','.'))
        except ValueError: prix = -1
        try: compteur = float((request.form.get('compteur','0') or '0').replace(',','.'))
        except ValueError: compteur = -1
        if not marque or not immat:
            flash('Marque et immatriculation sont obligatoires.', 'error')
        elif service not in VEHICLE_STATUS_ALLOWED or prix < 0 or compteur < 0:
            flash('Veuillez vérifier l’état, le prix/jour et le compteur.', 'error')
        else:
            try:
                image = save_vehicle_image(request.files.get('photo'), current_image)
                with db() as c:
                    c.execute('''UPDATE vehicules SET marque=?,immatriculation=?,num_chassis=?,compteur=?,service=?,prix_jour=?,remarque=?
                                 WHERE code_vehicule=?''', (marque,immat,chassis,compteur,service,prix,remarque,code))
                    if image:
                        c.execute('INSERT OR REPLACE INTO web_vehicle_media(code_vehicule,image_filename,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)', (code,image))
                audit('VEHICLE_EDIT', f'{code} {marque} {immat}')
                flash('Fiche véhicule mise à jour.', 'success')
                return redirect(url_for('admin_fleet'))
            except ValueError as e:
                flash(str(e), 'error')
    return render_template('fleet_form.html', mode='edit', vehicle=vehicle, suggested_code=code, image=current_image)

@app.route('/admin/parc/<code>/supprimer', methods=['POST'])
@login_required
def admin_fleet_delete(code):
    confirmation = request.form.get('confirmation','').strip()
    if confirmation != code:
        flash('Suppression annulée : la confirmation du code véhicule est incorrecte.', 'error')
        return redirect(url_for('admin_fleet'))
    with db() as c:
        v = c.execute('SELECT code_vehicule,marque,immatriculation FROM vehicules WHERE code_vehicule=?',(code,)).fetchone()
        if not v: abort(404)
        links = vehicle_link_count(c, code)
        if links:
            c.execute("UPDATE vehicules SET service='HORS SERVICE' WHERE code_vehicule=?", (code,))
            audit('VEHICLE_RETIRE', f'{code} - {links} historique(s) lié(s)')
            flash(f'Le véhicule possède {links} location/réservation(s). Pour protéger l’historique, il a été retiré du parc et placé HORS SERVICE.', 'success')
            return redirect(url_for('admin_fleet'))
        media = c.execute('SELECT image_filename FROM web_vehicle_media WHERE code_vehicule=?',(code,)).fetchone()
        c.execute('DELETE FROM web_vehicle_media WHERE code_vehicule=?',(code,))
        c.execute('DELETE FROM vehicules WHERE code_vehicule=?',(code,))
    if media and media['image_filename']:
        try: (UPLOAD_DIR / media['image_filename']).unlink(missing_ok=True)
        except Exception: pass
    audit('VEHICLE_DELETE', f'{code} {v["marque"]} {v["immatriculation"]}')
    flash('Véhicule supprimé définitivement du parc.', 'success')
    return redirect(url_for('admin_fleet'))



def api_authorized():
    expected = os.environ.get('GESTIONPRO_API_TOKEN','').strip()
    if not expected:
        return False
    supplied = request.headers.get('Authorization','')
    if supplied.lower().startswith('bearer '):
        supplied = supplied[7:].strip()
    return bool(supplied) and secrets.compare_digest(expected, supplied)

@app.route('/api/sync/vehicles', methods=['POST'])
@app.route('/api/vehicles/sync', methods=['POST'])
@app.route('/api/vehicles', methods=['POST'])
def api_sync_vehicles():
    if not api_authorized(): abort(401)
    payload = request.get_json(silent=True) or {}
    items = payload.get('vehicles') or []
    if not isinstance(items, list) or len(items) > 5000: abort(400)
    updated = 0
    with db() as c:
        for v in items:
            code = str(v.get('code_vehicule','')).strip()
            if not code: continue
            vals = (str(v.get('marque',''))[:100], str(v.get('immatriculation',''))[:40], str(v.get('num_chassis',''))[:100],
                    float(v.get('compteur') or 0), str(v.get('service') or 'EN SERVICE')[:30], float(v.get('prix_jour') or 0), str(v.get('remarque',''))[:500])
            if c.execute('SELECT 1 FROM vehicules WHERE code_vehicule=?',(code,)).fetchone():
                c.execute('''UPDATE vehicules SET marque=?,immatriculation=?,num_chassis=?,compteur=?,service=?,prix_jour=?,remarque=? WHERE code_vehicule=?''', vals+(code,))
            else:
                c.execute('''INSERT INTO vehicules(code_vehicule,marque,immatriculation,num_chassis,compteur,service,prix_jour,remarque) VALUES(?,?,?,?,?,?,?,?)''', (code,)+vals)
            updated += 1
    return {'status':'ok','updated':updated}

@app.route('/api/sync/locations', methods=['POST'])
@app.route('/api/locations/sync', methods=['POST'])
@app.route('/api/locations', methods=['POST'])
def api_sync_locations():
    if not api_authorized(): abort(401)
    payload = request.get_json(silent=True) or {}
    items = payload.get('locations') or []
    if not isinstance(items, list) or len(items) > 20000: abort(400)
    cleaned = []
    for item in items:
        code = str(item.get('code_location','')).strip()[:80]
        vehicle = str(item.get('code_vehicule','')).strip()[:80]
        dep = str(item.get('date_depart','')).strip()[:30]
        ret = str(item.get('date_retour','')).strip()[:30]
        if vehicle and dep and ret:
            cleaned.append((code, vehicle, dep, ret))
    # GestionPro est la source de vérité pour les contrats de location.
    # On remplace uniquement la table miroir 'locations'; les réservations,
    # comptes admin, médias et réglages Web restent intacts.
    with db() as c:
        c.execute('DELETE FROM locations')
        c.executemany('INSERT INTO locations(code_location,code_vehicule,date_depart,date_retour) VALUES(?,?,?,?)', cleaned)
    return {'status':'ok','updated':len(cleaned)}

@app.route('/api/sync/reservations', methods=['GET'])
@app.route('/api/reservations/sync', methods=['GET'])
@app.route('/api/reservations', methods=['GET'])
def api_sync_reservations():
    if not api_authorized(): abort(401)
    with db() as c:
        rows = c.execute('SELECT * FROM reservations ORDER BY id').fetchall()
    return {'status':'ok','reservations':[dict(r) for r in rows]}

@app.route('/api/sync/status', methods=['GET'])
def api_sync_status():
    if not api_authorized(): abort(401)
    return {'status':'ok','service':'GestionPro Web','api':'sync','version':'2026-09-10'}

@app.route('/health')
def health():
    try:
        with db() as c: c.execute('SELECT 1').fetchone()
        return {'status':'ok','database':str(DB_PATH.name)}, 200
    except Exception:
        return {'status':'error'}, 500



@app.get('/static/uploads/vehicules/<path:filename>')
def persistent_vehicle_photo(filename):
    return send_from_directory(UPLOAD_DIR, filename)

from remote_signatures import bp as signature_blueprint
app.register_blueprint(signature_blueprint)

if __name__ == '__main__':
    print('\nGestionPro Web - HBZ Rent Car')
    print('Site public : http://127.0.0.1:5000')
    print('Administration : http://127.0.0.1:5000/admin')
    print('Gestion du parc : http://127.0.0.1:5000/admin/parc')
    print('Premier lancement : créez le compte administrateur dans /admin/setup\n')
    app.run(host='127.0.0.1', port=5000, debug=False)
