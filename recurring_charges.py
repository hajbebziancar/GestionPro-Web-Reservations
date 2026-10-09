"""Échéances mensuelles de charges, comptabilisées une seule fois à leur date."""
from __future__ import annotations

import calendar
import json
import sqlite3
from datetime import date, datetime


class RecurringCharges:
    def __init__(self, connection: sqlite3.Connection):
        self.conn=connection
        self.conn.execute('''CREATE TABLE IF NOT EXISTS recurring_charges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount>0),
            due_day INTEGER NOT NULL CHECK(due_day BETWEEN 1 AND 31),
            payment_method TEXT NOT NULL CHECK(payment_method IN ('BANQUE','ESPÈCES')),
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT ''
        )''')
        self.conn.commit()

    def list(self):
        return self.conn.execute('SELECT * FROM recurring_charges ORDER BY active DESC,due_day,title,id').fetchall()

    def save(self, *, title, category, amount, due_day, payment_method, start_date, end_date='', notes='', record_id=None):
        title=title.strip();category=category.strip() or 'DIVERS'
        method=payment_method.strip().upper()
        amount=float(str(amount).strip().replace(' ','').replace(',','.'))
        due_day=int(due_day)
        start=date.fromisoformat(start_date)
        if not title or amount<=0 or not 1<=due_day<=31 or method not in ('BANQUE','ESPÈCES'):
            raise ValueError('Indiquez un libellé, un montant positif, un jour de 1 à 31 et Banque ou Espèces.')
        if end_date and date.fromisoformat(end_date)<start:
            raise ValueError('La date de fin doit suivre la date de début.')
        if record_id is None:
            cur=self.conn.execute('''INSERT INTO recurring_charges(title,category,amount,due_day,payment_method,start_date,end_date,notes)
                VALUES(?,?,?,?,?,?,?,?)''',(title,category,amount,due_day,method,start_date,end_date,notes.strip()))
            record_id=cur.lastrowid
        else:
            cur=self.conn.execute('''UPDATE recurring_charges SET title=?,category=?,amount=?,due_day=?,payment_method=?,start_date=?,end_date=?,notes=?
                WHERE id=?''',(title,category,amount,due_day,method,start_date,end_date,notes.strip(),int(record_id)))
            if not cur.rowcount:raise ValueError('Échéance introuvable.')
        self.conn.commit()
        return record_id

    def set_active(self, record_id, active):
        self.conn.execute('UPDATE recurring_charges SET active=? WHERE id=?',(int(bool(active)),int(record_id)))
        self.conn.commit()

    @staticmethod
    def due_date(year,month,day):
        return date(year,month,min(day,calendar.monthrange(year,month)[1]))

    def synchronize(self, today=None):
        """Rattrape les échéances dues ; la clé (source, mois) garantit l'unicité."""
        today=today or date.today()
        new=[]
        for row in self.conn.execute('SELECT * FROM recurring_charges WHERE active=1'):
            start=date.fromisoformat(row['start_date'])
            end=date.fromisoformat(row['end_date']) if row['end_date'] else today
            cutoff=min(today,end)
            if cutoff<start:continue
            index=start.year*12+start.month-1
            last=cutoff.year*12+cutoff.month-1
            while index<=last:
                year,month=divmod(index,12);month+=1
                due=self.due_date(year,month,row['due_day'])
                if start<=due<=cutoff:
                    reference=f"CHG-FIXE-{row['id']}-{year}{month:02d}"
                    payload={
                        'reference':reference,'type':'CHARGE',
                        'category':f"CHARGE MENSUELLE / {row['category']}",
                        'date':due.strftime('%d/%m/%Y'),'vehicle':'','party':row['title'],
                        'description':row['title'],'payment_method':row['payment_method'],
                        'amount':f"{row['amount']:.2f}",'document':'',
                        'status':'PAYÉ','notes':row['notes'],
                        'source_recurring_charge':row['id']}
                    cur=self.conn.execute('''INSERT OR IGNORE INTO module_records(module,record_id,payload,created_at)
                        VALUES('expenses',?,?,?)''',(reference,json.dumps(payload,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
                    if cur.rowcount:new.append(reference)
                index+=1
        if new:self.conn.commit()
        return new

    def next_due(self, row, today=None):
        today=today or date.today()
        start=max(today,date.fromisoformat(row['start_date']))
        end=date.fromisoformat(row['end_date']) if row['end_date'] else None
        for offset in (0,1):
            idx=start.year*12+start.month-1+offset
            year,month=divmod(idx,12);month+=1
            due=self.due_date(year,month,row['due_day'])
            if due>=start and (end is None or due<=end):return due
        return None
