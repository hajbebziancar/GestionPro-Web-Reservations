"""Reservation receipt: generated directly as PDF, without a browser."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def create_receipt(reservation):
    r = dict(reservation)
    output = BytesIO()
    navy = colors.HexColor('#082d53')
    gold = colors.HexColor('#e9b821')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('Value', fontName='Helvetica', fontSize=10, leading=15, textColor=navy))
    styles.add(ParagraphStyle('Brand', fontName='Helvetica-Bold', fontSize=24, leading=30, textColor=navy))
    def text(value):
        return Paragraph(escape(str(value or '—')), styles['Value'])
    def money(key):
        return f"{float(r.get(key) or 0):,.2f} MAD".replace(',', ' ')
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=40, bottomMargin=40, title='Reçu de réservation ' + str(r['code_reservation']), author='HBZ RENT CAR')
    story = [Paragraph('HBZ RENT CAR', styles['Brand']), text('HAJ BEN ZIAN CAR'), Spacer(1, 18), Paragraph('REÇU DE RÉSERVATION', styles['Heading1']), text('Référence : ' + str(r['code_reservation'])), text('Créée le : ' + str(r.get('date_creation') or '')), text('Statut : ' + str(r.get('statut') or 'EN ATTENTE')), Spacer(1, 18)]
    rows = [
        ('CLIENT', str(r.get('nom') or '') + ' ' + str(r.get('prenom') or '')),
        ('Téléphone', r.get('telephone')),
        ('VÉHICULE', r.get('marque_vehicule')),
        ('Départ', str(r.get('date_depart') or '') + ' à ' + str(r.get('heure_depart') or '')),
        ('Retour', str(r.get('date_retour') or '') + ' à ' + str(r.get('heure_retour') or '')),
        ('Durée facturée', f"{float(r.get('duree') or 0):g} jour(s)"),
        ('Tarif journalier', money('prix')),
        ('TOTAL INDICATIF', money('montant')),
        ('Acompte enregistré', money('avance')),
        ('Reste à payer', money('reste')),
    ]
    table = Table([[text(k), text(v)] for k,v in rows], colWidths=[175,336])
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#f1f6fc')),('BACKGROUND',(0,7),(-1,7),colors.HexColor('#fff2bb')),('LINEBELOW',(0,0),(-1,-1),0.5,colors.white),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]))
    story += [table, Spacer(1,20), text('Ce document récapitule la réservation. Une demande EN ATTENTE reste soumise à confirmation de l’agence. Une réservation ANNULEE ne garantit aucune disponibilité.'), Spacer(1,8), text('Ce reçu de réservation ne constitue pas une preuve de paiement. Les montants correspondent aux données enregistrées par l’agence.')]
    def footer(canvas, document):
        canvas.setStrokeColor(gold)
        canvas.line(42,36,A4[0]-42,36)
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(navy)
        canvas.drawString(42,24,'HBZ RENT CAR - Reçu de réservation')
        canvas.drawRightString(A4[0]-42,24,str(document.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    output.seek(0)
    return output
