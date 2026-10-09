"""Prépare le partage ; l’utilisateur confirme l’envoi dans WhatsApp/SMS."""
from urllib.parse import quote
from whatsapp_contract import normalize_whatsapp_number

def message(url,number):return f'Bonjour, voici votre contrat {number}. Consultez-le puis signez ; vous pourrez télécharger votre copie signée : {url}'
def whatsapp_link(phone,url,number):return 'https://wa.me/'+normalize_whatsapp_number(phone)+'?text='+quote(message(url,number))
def sms_link(phone,url,number):return 'sms:+'+normalize_whatsapp_number(phone)+'?body='+quote(message(url,number))
