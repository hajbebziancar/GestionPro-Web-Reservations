"""Règles financières extraites de la version PC fournie, sans interface ni écritures."""
import json,re,sqlite3
from pathlib import Path
from datetime import datetime,timedelta
class Financial:
    def __init__(self,conn):self.conn=conn
    def _sync_pending_drafts(self):pass
    def _sync_hbz_credit_monthly_bank(self):pass
    def _sync_recurring_charges(self):pass
    def _hbz_credit_db_path(self):return Path("/nonexistent/mobile-finance-credit")

    @staticmethod
    def _parse_french_date(value):
        text = str(value or '').strip()
        for pattern in ('%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%d-%m-%Y'):
            try:
                return datetime.strptime(text[:19], pattern)
            except ValueError:
                continue
        return None
    @staticmethod
    def _number(value):
        match = re.search('-?\\d+(?:[.,]\\d+)?', str(value).replace(' ', ''))
        try:
            return float(match.group(0).replace(',', '.')) if match else 0.0
        except ValueError:
            return 0.0
    def _contract_period_share(self, departure, return_date, duration, start_date=None, end_date=None):
        """Production par mois, hors journée de passage au 1er du mois suivant."""
        first = self._parse_french_date(departure)
        if first is None:
            return 1.0 if start_date is None and end_date is None else 0.0
        last = self._parse_french_date(return_date)
        days = max(1, (last.date() - first.date()).days) if last and last.date() > first.date() else max(1, int(duration or 1))
        first_day = first.date() + timedelta(days=1)
        finish = first_day + timedelta(days=days)
        period_first = start_date.date() if start_date else first_day
        period_finish = end_date.date() + timedelta(days=1) if end_date else finish
        overlap = max(0, (min(finish, period_finish) - max(first_day, period_first)).days)
        first_month = datetime(first_day.year, first_day.month, 1).date()
        boundary = first_month
        while boundary < finish:
            if first.date() < boundary and period_first <= boundary < period_finish and (first_day <= boundary < finish):
                overlap -= 1
            boundary = (boundary.replace(day=28) + timedelta(days=4)).replace(day=1)
        return overlap / days
    def _contract_boundary_share(self, departure, return_date, duration, end_date):
        """Part d'une seule journée entre la clôture du mois et le mois suivant."""
        if end_date is None:
            return 0.0
        first = self._parse_french_date(departure)
        if first is None:
            return 0.0
        last = self._parse_french_date(return_date)
        days = max(1, (last.date() - first.date()).days) if last and last.date() > first.date() else max(1, int(duration or 1))
        boundary = end_date.date() + timedelta(days=1)
        finish = first.date() + timedelta(days=days + 1)
        return 1.0 / days if boundary.day == 1 and first.date() < boundary < finish else 0.0
    def _contract_allocated_parts(self, departure, return_date, duration, amount, cash, bank, start_date=None, end_date=None, savings=False):
        """Affecte l'avance aux jours dans l'ordre, puis crée la créance sur les jours impayés."""
        first = self._parse_french_date(departure)
        last = self._parse_french_date(return_date)
        if first is None:
            share = 0.0 if savings else 1.0 if start_date is None and end_date is None else 0.0
            paid = min(amount, max(0, cash + bank))
            return (amount * share, cash * share, bank * share, (amount - paid) * share)
        days = max(1, (last.date() - first.date()).days) if last and last.date() > first.date() else max(1, int(duration or 1))
        first_day = first.date() + timedelta(days=1)
        paid = min(max(0, amount), max(0, cash + bank))
        cash_ratio = cash / (cash + bank) if cash + bank else 0.0
        portion = amount / days
        selected = settled = 0.0
        for index in range(days):
            day = first_day + timedelta(days=index)
            boundary = day.day == 1 and day > first.date()
            if savings:
                included = bool(end_date and boundary and (day == end_date.date() + timedelta(days=1)))
            else:
                included = not boundary and (start_date is None or day >= start_date.date()) and (end_date is None or day <= end_date.date())
            if included:
                selected += portion
                settled += max(0.0, min(paid, (index + 1) * portion) - min(paid, index * portion))
        return (selected, settled * cash_ratio, settled * (1 - cash_ratio), selected - settled)
    def _contract_payment_parts(self):
        """Ventilation des règlements réels par contrat, sans double compter l'acompte."""
        modes = {}
        for reference, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='contract_payment_mode'"):
            try:
                modes[str(reference)] = str(json.loads(raw).get('mode') or 'ESPÈCES').upper()
            except (ValueError, TypeError):
                continue
        payments = {}
        for raw, in self.conn.execute("SELECT payload FROM module_records WHERE module='payments'"):
            try:
                q = json.loads(raw)
            except (ValueError, TypeError):
                continue
            contract = str(q.get('contract', '')).strip()
            if not contract:
                continue
            cash = self._number(q.get('cash_amount'))
            bank = self._number(q.get('bank_amount'))
            if 'cash_amount' not in q and 'bank_amount' not in q:
                amount = self._number(q.get('amount'))
                mode = str(q.get('mode', '')).upper()
                cash, bank = (amount, 0.0) if 'ESP' in mode else (0.0, amount)
            if any((token in str(q.get('mode', '')).upper() for token in ('CHÈQUE', 'CHEQUE'))):
                bank = 0.0
            old = payments.get(contract, (0.0, 0.0))
            payments[contract] = (old[0] + max(0, cash), old[1] + max(0, bank))
        return (modes, payments)
    def _production_expense_date(self, value):
        """Échéance du 1 au 5 : production du mois précédent ; dès le 6 : mois courant."""
        due = self._parse_french_date(value)
        if due is None:
            return None
        return due.replace(day=1) - timedelta(days=1) if due.day <= 5 else due
    def _is_production_draft(self, payload):
        if str(payload.get('category', '')).upper() in ('TRAITE BANCAIRE', 'CRÉDIT HBZ / ÉCHÉANCE'):
            return True
        reference = payload.get('source_check')
        if reference:
            row = self.conn.execute("SELECT payload FROM module_records WHERE module='checks' AND record_id=?", (reference,)).fetchone()
            if row:
                try:
                    return str(json.loads(row[0]).get('type', '')).upper() == 'TRAITE'
                except (ValueError, TypeError):
                    pass
        return False
    def _expense_is_executed(self, payload):
        if str(payload.get('status', '')).upper() in ('EN ATTENTE', 'ANNULÉ', 'ANNULE', 'REJETÉ', 'REJETE'):
            return False
        if self._is_production_draft(payload):
            due = self._parse_french_date(payload.get('date', ''))
            return due is not None and due.date() <= datetime.now().date()
        return True
    def _expense_charge_date(self, payload):
        return self._production_expense_date(payload.get('date', '')) if self._is_production_draft(payload) else self._parse_french_date(payload.get('date', ''))
    def _expense_charge_in_period(self, payload, start=None, end=None):
        if not self._expense_is_executed(payload):
            return False
        date = self._expense_charge_date(payload)
        if date is None:
            return start is None and end is None
        return (start is None or date >= start) and (end is None or date <= end)
    def _expense_bank_in_period(self, payload, start=None, end=None):
        """Le bilan mensuel rattache le débit exécuté au même cycle que sa charge."""
        if not self._expense_is_executed(payload):
            return False
        received = str(payload.get('direction', '')).upper() in ('REÇU', 'RECU')
        if self._is_production_draft(payload) and (not received):
            return self._expense_charge_in_period(payload, start, end)
        date = self._parse_french_date(payload.get('date', ''))
        if date is None:
            return start is None and end is None
        return (start is None or date >= start) and (end is None or date <= end)
    def _financial_totals(self, start_date=None, end_date=None):
        """Synthèse HBZ : Débit = Banque + Caisse + Créances + Charges ; Crédit = CA ; Résultat = CA - Charges."""
        self._sync_pending_drafts()
        self._sync_hbz_credit_monthly_bank()
        self._sync_recurring_charges()
        totals = {'revenue': 0.0, 'expenses': 0.0, 'cash': 0.0, 'bank': 0.0, 'receivables': 0.0, 'supplier_payable': 0.0, 'savings_future': 0.0, 'savings_cash': 0.0, 'savings_bank': 0.0, 'savings_receivables': 0.0, 'versements': 0.0, 'client_cheques': 0.0, 'charge_cash': 0.0, 'charge_cheques': 0.0}

        def in_period(value):
            d = self._parse_french_date(value)
            if d is None:
                return start_date is None and end_date is None
            return (start_date is None or d >= start_date) and (end_date is None or d <= end_date)
        modes, payments = self._contract_payment_parts()
        for row in self.conn.execute('SELECT numero,date_depart,date_retour,duree,montant,reglement,reste FROM contracts'):
            contract = str(row[0])
            amount = max(0.0, float(row[4] or 0))
            paid = min(amount, max(0.0, float(row[5] or 0)))
            detailed_cash, detailed_bank = payments.get(contract, (0.0, 0.0))
            detailed_total = detailed_cash + detailed_bank
            if detailed_total > paid and detailed_total > 0:
                factor = paid / detailed_total
                detailed_cash *= factor
                detailed_bank *= factor
            initial = max(0.0, paid - detailed_cash - detailed_bank)
            mode = modes.get(contract, 'ESPÈCES')
            is_bank = any((token in mode for token in ('CHÈQUE', 'CHEQUE', 'BANQUE', 'VIREMENT', 'CARTE')))
            cash = detailed_cash + (0.0 if is_bank else initial)
            is_check = any((token in mode for token in ('CHÈQUE', 'CHEQUE')))
            bank = detailed_bank + (initial if is_bank and (not is_check) else 0.0)
            production = self._contract_allocated_parts(row[1], row[2], row[3], amount, cash, bank, start_date, end_date)
            totals['revenue'] += production[0]
            totals['cash'] += production[1]
            totals['client_cheques'] += production[2]
            totals['receivables'] += production[3]
            reserve = self._contract_allocated_parts(row[1], row[2], row[3], amount, cash, bank, start_date, end_date, savings=True)
            for field, value in zip(('savings_future', 'savings_cash', 'savings_bank', 'savings_receivables'), reserve):
                totals[field] += value
        totals['drafts_period_info'] = sum((row[4] for row in self._draft_period_info_rows(start_date, end_date)))
        for raw, in self.conn.execute("SELECT payload FROM module_records WHERE module='expenses'"):
            try:
                q = json.loads(raw)
            except (ValueError, TypeError):
                continue
            status = str(q.get('status', '')).upper()
            if status in ('ANNULÉ', 'ANNULE', 'REJETÉ', 'REJETE'):
                continue
            amount = max(0.0, self._number(q.get('amount')))
            category = str(q.get('category', '')).upper()
            draft = self._is_production_draft(q)
            received = str(q.get('direction', '')).upper() in ('REÇU', 'RECU')
            if not self._expense_is_executed(q):
                continue
            if draft and (not received) and self._expense_charge_in_period(q, start_date, end_date):
                totals['expenses'] += amount
            if not self._expense_bank_in_period(q, start_date, end_date):
                continue
            if q.get('source_check'):
                if not draft and (not received):
                    totals['expenses'] += amount
                totals['client_cheques' if received else 'charge_cheques'] += amount
                continue
            if str(q.get('type', '')).upper() != 'CHARGE':
                continue
            if not draft and category not in ('RÈGLEMENT FOURNISSEUR', 'CRÉDIT HBZ / MENSUALITÉ'):
                totals['expenses'] += amount
            mode = str(q.get('payment_method', '')).upper()
            if 'ESP' in mode:
                totals['charge_cash'] += amount
            elif any((token in mode for token in ('CHÈQUE', 'CHEQUE', 'BANQUE'))):
                totals['charge_cheques'] += amount
        for raw, in self.conn.execute("SELECT payload FROM module_records WHERE module='maintenance'"):
            try:
                q = json.loads(raw)
            except Exception:
                continue
            if not in_period(q.get('date', '')):
                continue
            amount = max(0.0, self._number(q.get('amount')))
            mode = str(q.get('payment_method', '')).upper()
            totals['expenses'] += amount
            if 'ESP' in mode:
                totals['charge_cash'] += amount
            elif 'CHÈQUE' in mode or 'CHEQUE' in mode:
                totals['charge_cheques'] += amount
            elif 'CRÉDIT' in mode or 'CREDIT' in mode:
                totals['supplier_payable'] += amount
        for raw, in self.conn.execute("SELECT payload FROM module_records WHERE module='supplier_payments'"):
            try:
                q = json.loads(raw)
            except Exception:
                continue
            if in_period(q.get('date', '')):
                totals['supplier_payable'] -= max(0.0, self._number(q.get('amount')))
        totals['supplier_payable'] = max(0.0, totals['supplier_payable'])
        transfer_to_bank = 0.0
        transfer_to_cash = 0.0
        for raw, in self.conn.execute("SELECT payload FROM module_records WHERE module='transfers'"):
            try:
                q = json.loads(raw)
            except Exception:
                continue
            if not in_period(q.get('date', '')):
                continue
            amount = self._number(q.get('amount'))
            mode = str(q.get('mode', 'VERSEMENT BANQUE')).upper()
            if 'RETRAIT' in mode:
                transfer_to_cash += amount
            else:
                transfer_to_bank += amount
        totals['versements'] = transfer_to_bank - transfer_to_cash
        totals['cash'] += transfer_to_cash - transfer_to_bank - totals['charge_cash']
        totals['bank'] = transfer_to_bank - transfer_to_cash + totals['client_cheques'] - totals['charge_cheques']
        totals['debit'] = totals['bank'] + totals['cash'] + totals['receivables'] + totals['expenses']
        totals['credit'] = totals['revenue']
        totals['assets'] = totals['debit']
        totals['turnover'] = totals['credit']
        totals['result'] = totals['credit'] - totals['expenses']
        totals['balance_gap'] = totals['debit'] - totals['credit']
        totals['gap'] = totals['balance_gap']
        return totals
    def _draft_period_info_rows(self, start_date=None, end_date=None):
        """Échéances informatives du 6 au 5, indépendantes des charges comptabilisées."""
        rows = []

        def add(value, ref, party, label, amount):
            due = self._parse_french_date(value)
            production = self._production_expense_date(value)
            if due is None or production is None:
                return
            today = datetime.now().date()
            if not today < due.date() <= today + timedelta(days=3):
                return
            if start_date is not None and production < start_date:
                return
            if end_date is not None and production > end_date:
                return
            amount = max(0.0, self._number(amount))
            if amount > 0:
                rows.append((due.strftime('%d/%m/%Y'), str(ref or ''), str(party or ''), label, amount, 'INFORMATIF'))
        for ref, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks'"):
            try:
                q = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if str(q.get('type', '')).upper() != 'TRAITE':
                continue
            if str(q.get('status', '')).upper() in ('ANNULÉ', 'ANNULE', 'REJETÉ', 'REJETE'):
                continue
            if str(q.get('direction', 'ÉMIS')).upper() in ('REÇU', 'RECU'):
                continue
            add(q.get('due_date', ''), q.get('number') or ref, q.get('client'), 'Traite — date réelle d’échéance', q.get('amount'))
        path = self._hbz_credit_db_path()
        if path.exists():
            con = sqlite3.connect(str(path))
            try:
                for ref, org, due, amount in con.execute("SELECT ref,COALESCE(organisme,''),date_ech,COALESCE(echeance,0) FROM echeances"):
                    add(due, ref, org, 'Échéance HBZ Crédit — date réelle d’échéance', amount)
            finally:
                con.close()
        else:
            for ref, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses'"):
                try:
                    q = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if str(q.get('category', '')).upper() != 'CRÉDIT HBZ / ÉCHÉANCE':
                    continue
                if str(q.get('status', '')).upper() in ('ANNULÉ', 'ANNULE', 'REJETÉ', 'REJETE'):
                    continue
                add(q.get('date', ''), q.get('document') or ref, q.get('party'), 'Échéance HBZ Crédit — date réelle d’échéance', q.get('amount'))
        return sorted(rows, key=lambda row: (self._parse_french_date(row[0]), row[1]))

    def details(self, title, key, total, start_date=None, end_date=None):
        """Affiche le détail qui compose une carte de la synthèse financière."""
        if key == 'expenses' and hasattr(self, 'financial_center_month'):
            center_start, center_end = self._center_period()
            if start_date == center_start and end_date == center_end:
                self._open_center_card_sources('expenses')
                return
        self._sync_pending_drafts()

        def in_period(value):
            d = self._parse_french_date(value)
            if d is None:
                return start_date is None and end_date is None
            return (start_date is None or d >= start_date) and (end_date is None or d <= end_date)
        rows = []

        def add(date, ref, party, label, amount, status=''):
            rows.append((str(date or ''), str(ref or ''), str(party or ''), str(label or ''), float(amount or 0), str(status or '')))
        if key in ('receivables', 'revenue', 'bank', 'cash'):
            modes, payments = self._contract_payment_parts()
            for row in self.conn.execute('SELECT numero,date_depart,date_retour,duree,montant,reglement,client_code FROM contracts ORDER BY date_depart DESC'):
                share = self._contract_period_share(row[1], row[2], row[3], start_date, end_date)
                if not share:
                    continue
                amount = max(0.0, self._number(row[4]))
                paid = min(amount, max(0.0, self._number(row[5])))
                cash, bank = payments.get(str(row[0]), (0.0, 0.0))
                detail = cash + bank
                if detail > paid and detail > 0:
                    cash *= paid / detail
                    bank *= paid / detail
                initial = max(0.0, paid - cash - bank)
                mode = modes.get(str(row[0]), 'ESPÈCES')
                if any((token in mode for token in ('CHÈQUE', 'CHEQUE', 'BANQUE', 'VIREMENT', 'CARTE'))):
                    bank += initial
                else:
                    cash += initial
                allocated = self._contract_allocated_parts(row[1], row[2], row[3], amount, cash, bank, start_date, end_date)
                part = dict(zip(('revenue', 'cash', 'bank', 'receivables'), allocated))[key]
                if part > 0.005:
                    add(row[1], row[0], row[6], 'Part du contrat dans la période', part, 'PRODUCTION')
        if key in ('expenses', 'bank', 'cash'):
            for rid, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses' ORDER BY created_at DESC"):
                try:
                    q = json.loads(raw)
                except Exception:
                    continue
                if str(q.get('type', '')).upper() != 'CHARGE' or not self._expense_is_executed(q):
                    continue
                if key == 'expenses':
                    if not self._expense_charge_in_period(q, start_date, end_date):
                        continue
                elif not self._expense_bank_in_period(q, start_date, end_date):
                    continue
                amt = self._number(q.get('amount'))
                mode = str(q.get('payment_method', '')).upper()
                cat = str(q.get('category', '')).upper()
                if key == 'expenses' and cat not in ('RÈGLEMENT FOURNISSEUR', 'CRÉDIT HBZ / MENSUALITÉ'):
                    add(q.get('date'), rid, q.get('party'), q.get('description') or q.get('category'), amt, q.get('status'))
                elif key == 'bank' and ('BANQUE' in mode or 'CHÈQUE' in mode or 'CHEQUE' in mode):
                    add(q.get('date'), rid, q.get('party'), q.get('description') or q.get('category'), -amt, 'SORTIE')
                elif key == 'cash' and 'ESP' in mode:
                    add(q.get('date'), rid, q.get('party'), q.get('description') or q.get('category'), -amt, 'SORTIE')
            if key in ('bank', 'cash'):
                for rid, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='transfers' ORDER BY created_at DESC"):
                    try:
                        q = json.loads(raw)
                    except Exception:
                        continue
                    if not in_period(q.get('date', '')):
                        continue
                    amt = self._number(q.get('amount'))
                    mode = str(q.get('mode', 'VERSEMENT BANQUE')).upper()
                    signed = (amt if 'RETRAIT' not in mode else -amt) if key == 'bank' else -amt if 'RETRAIT' not in mode else amt
                    add(q.get('date'), rid, '', q.get('mode', 'Transfert'), signed, 'TRANSFERT')
        elif key == 'supplier_payable':
            for rid, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='supplier_purchases' ORDER BY created_at DESC"):
                try:
                    q = json.loads(raw)
                except Exception:
                    continue
                if in_period(q.get('date', '')):
                    add(q.get('date'), rid, q.get('supplier_name') or q.get('supplier'), q.get('description') or 'Dette fournisseur', self._number(q.get('total') or q.get('amount')), q.get('status'))
        elif key == 'drafts_period_info':
            rows.extend(self._draft_period_info_rows(start_date, end_date))
        elif key in ('drafts_pending', 'checks_pending', 'drafts_other'):
            for rid, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks' ORDER BY created_at DESC"):
                try:
                    q = json.loads(raw)
                except Exception:
                    continue
                kind = str(q.get('type', '')).upper()
                due = self._parse_french_date(q.get('due_date', ''))
                if kind not in ('TRAITE', 'CHÈQUE', 'CHEQUE') or not due or (kind != 'TRAITE' and due.date() > datetime.now().date() + timedelta(days=3)) or (str(q.get('status', '')).upper() != 'EN ATTENTE'):
                    continue
                if key == 'checks_pending' and kind == 'TRAITE':
                    continue
                if key == 'drafts_other' and kind != 'TRAITE':
                    continue
                add(q.get('due_date'), q.get('number') or rid, q.get('client'), f"{('Traite' if kind == 'TRAITE' else 'Chèque')} à venir — {q.get('bank', '')}", self._number(q.get('amount')), 'INFORMATIF')
            for rid, raw in () if key == 'checks_pending' else self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses' ORDER BY created_at DESC"):
                try:
                    q = json.loads(raw)
                except Exception:
                    continue
                if str(q.get('category', '')).upper() != 'CRÉDIT HBZ / ÉCHÉANCE' or str(q.get('status', '')).upper() != 'EN ATTENTE':
                    continue
                due = self._parse_french_date(q.get('date', ''))
                if not due:
                    continue
                add(q.get('date'), q.get('document') or rid, q.get('party'), q.get('description') or 'Échéance HBZ Crédit à venir', self._number(q.get('amount')), 'INFORMATIF')
        elif key == 'credit_j10':
            today = datetime.now().date()
            limit = today + timedelta(days=10)
            db_path = self._hbz_credit_db_path()
            if db_path.exists():
                con = sqlite3.connect(str(db_path))
                try:
                    for ref, org, date_text, amount in con.execute("SELECT ref,COALESCE(organisme,''),date_ech,COALESCE(echeance,0) FROM echeances ORDER BY date_ech"):
                        try:
                            due = datetime.strptime(str(date_text)[:10], '%Y-%m-%d').date()
                        except Exception:
                            continue
                        if today <= due <= limit:
                            add(due.strftime('%d/%m/%Y'), ref, org, 'Échéance crédit à prélever', amount, 'À PRÉLEVER')
                finally:
                    con.close()
            for rid, raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks' ORDER BY created_at DESC"):
                try:
                    q = json.loads(raw)
                except Exception:
                    continue
                if str(q.get('type', '')).upper() != 'TRAITE' or str(q.get('status', '')).upper() != 'EN ATTENTE':
                    continue
                due = self._parse_french_date(q.get('due_date', ''))
                if due and today <= due.date() <= limit:
                    add(q.get('due_date'), q.get('number') or rid, q.get('client'), 'Traite à prélever', self._number(q.get('amount')), 'À PRÉLEVER')
        return rows

def summary(data,start=None,end=None,include_details=False):
    c=sqlite3.connect(':memory:')
    try:
        c.execute('CREATE TABLE contracts(numero,date_depart,date_retour,duree,montant,reglement,reste,client_code)')
        c.execute('CREATE TABLE module_records(module,record_id,payload,created_at)')
        for r in data.get('contracts',[]):
            c.execute('INSERT INTO contracts VALUES(?,?,?,?,?,?,?,?)',[r.get(k) for k in ('numero','date_depart','date_retour','duree','montant','reglement','reste','client_code')])
        for name in ('expenses','maintenance','checks','supplier_payments','transfers','payments','contract_payment_mode'):
            for i,r in enumerate(data.get(name,[])):
                c.execute('INSERT INTO module_records VALUES(?,?,?,?)',(name,r.get('reference') or r.get('_record_id') or str(i),json.dumps(r),r.get('created_at','')))
        f=Financial(c);s=f._parse_french_date(start) if start else None;e=f._parse_french_date(end) if end else None
        if start and not s or end and not e or s and e and e<s:raise ValueError('Période financière invalide.')
        totals=f._financial_totals(s,e)
        if include_details:
            details={key:f.details(key,key,totals[key],s,e) for key in ('revenue','receivables','bank','cash','expenses')}
            return {'totals':totals,'details':{key:rows[:500] for key,rows in details.items()},'detail_counts':{key:len(rows) for key,rows in details.items()}}
        return totals
    finally:c.close()
