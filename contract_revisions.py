"""Historique transactionnel des modifications, sans toucher aux archives signées."""
import json

def install(conn):
    columns=[row[1] for row in conn.execute('PRAGMA table_info(contracts)')]
    def quote(s):return '"'+s.replace('"','""')+'"'
    def snapshot(prefix):
        return 'json_object('+','.join("'"+c.replace("'","''")+"',"+prefix+'.'+quote(c) for c in columns)+')'
    changed=' OR '.join('OLD.'+quote(c)+' IS NOT NEW.'+quote(c) for c in columns)
    conn.execute("CREATE TABLE IF NOT EXISTS contract_revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_no TEXT NOT NULL, changed_at TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL)")
    conn.execute('DROP TRIGGER IF EXISTS hbz_contract_revision')
    conn.execute("CREATE TRIGGER hbz_contract_revision AFTER UPDATE ON contracts WHEN "+changed+" BEGIN INSERT INTO contract_revisions(contract_no,changed_at,before_json,after_json) VALUES(OLD.numero,strftime('%Y-%m-%dT%H:%M:%f','now'),"+snapshot('OLD')+','+snapshot('NEW')+"); END")
    conn.commit()

def current_document(content,number,conn=None,client_code=None):
    """Conserve la signature reçue sur la copie imprimée du contrat courant."""
    from phone_signature import saved_signature
    from remote_contract_common import insert_signature
    from client_contract_signature import contract_signature
    payload=contract_signature(conn,number,client_code) if conn is not None else saved_signature(number)
    if payload:
        content=insert_signature(content,payload)
    return content
