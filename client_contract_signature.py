"""Resolve a signature only after checking the primary client's identity."""
from pathlib import Path

def contract_signature(conn, number, client_code):
    from signed_contracts import find_signed, ROOT, key
    from phone_signature import saved_signature, normalized_signature
    number=str(number or '').strip(); client_code=str(client_code or '').split('|',1)[0].strip()
    if not number or not client_code:return None
    row=conn.execute('SELECT client_code FROM contracts WHERE numero=?',(number,)).fetchone()
    if not row or str(row[0]).strip()!=client_code:return None
    record=find_signed(number)
    if record:
        owners=record.get('client_codes') or []
        if not owners or str(owners[0]).strip()!=client_code:return None
        try:return normalized_signature((ROOT/key(number)/record['signature']).read_bytes())
        except (OSError,ValueError,KeyError):return None
    # Legacy signatures have no archive metadata; their persisted contract owns them.
    return saved_signature(number)

def client_preview_signature(conn, number, client_code):
    """Preview the selected client's signature; this never signs a new contract."""
    payload=contract_signature(conn,number,client_code)
    if payload:return payload
    client_code=str(client_code or '').split('|',1)[0].strip()
    if not client_code:return None
    from signed_contracts import find_signed, ROOT, key
    from phone_signature import normalized_signature
    candidates=[]
    for row in conn.execute('SELECT numero FROM contracts WHERE client_code=?',(client_code,)):
        record=find_signed(row[0])
        if record and record.get('client_codes') and str(record['client_codes'][0]).strip()==client_code:
            candidates.append(record)
    for record in sorted(candidates,key=lambda r:r.get('signed_at',''),reverse=True):
        try:return normalized_signature((ROOT/key(record['contract_no'])/record['signature']).read_bytes())
        except (OSError,ValueError,KeyError):continue
    return None
