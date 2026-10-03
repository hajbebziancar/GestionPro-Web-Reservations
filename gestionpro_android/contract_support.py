import json
from pathlib import Path
BASE=Path(__file__).resolve().parent
EQUIPMENT=('Cric','Roue de secours','Clé / Télécommande','Carte grise','Assurance','Visite technique','Feuille circulation','Vignette','Triangle de signalisation','Gilet de sécurité','Extincteur','Trousse de secours')
def contract_state(conn,number):
    row=conn.execute("SELECT payload FROM module_records WHERE module='contract_vehicle_condition' AND record_id=?",(number,)).fetchone()
    return json.loads(row[0]) if row else {}

from functools import lru_cache
@lru_cache(maxsize=16)
def image_data(path):
    import io,base64
    from PIL import Image
    path=Path(path)
    if not path.is_file():return ''
    with Image.open(path) as original:
        rgba=original.convert('RGBA');background=Image.new('RGBA',rgba.size,'white');background.alpha_composite(rgba)
        im=background.convert('RGB');im.thumbnail((1200,1200));out=io.BytesIO();im.save(out,'JPEG',quality=92)
    return 'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()
