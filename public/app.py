from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, Response, session, abort
from html import escape as html_escape
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import secrets
import base64
import io
from PIL import Image, ImageOps, ImageFilter
import json
import hashlib
import csv
import socket
import smtplib
import mimetypes
import subprocess
import shutil
import gzip
import ssl
import re
import unicodedata
import time
import threading
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet, InvalidToken

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build as google_build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_OK = True
except Exception:
    GOOGLE_LIBS_OK = False


import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = Path(__file__).resolve().parent
WOPR_ROOT = BASE.parent
PRIVATE_ROOT = WOPR_ROOT / "private"
PUBLIC_ASSETS = BASE / "assets"
PRIVATE_ASSETS = PRIVATE_ROOT / "assets"
PRIVATE_SEEDS = PRIVATE_ROOT / "seeds"

# V2.3.161 - WOPR est autonome : tous les documents gérés par l'application
# voyagent avec le dossier WOPR. FOULFIX_ROOT est conservé comme nom interne
# pour compatibilité avec les chemins relatifs déjà stockés en base (Factures/..., Devis/...).
FOULFIX_ROOT = PRIVATE_ROOT / "documents"
DEVIS_ROOT = FOULFIX_ROOT / "Devis"
FACTURES_ROOT = FOULFIX_ROOT / "Factures"
FOURNISSEURS_ROOT = FOULFIX_ROOT / "Fournisseurs"
SUIVI_REPARATIONS_ROOT = FOULFIX_ROOT / "Suivi de réparation"

MONTH_FOLDER_NAMES = {
    1: "01 - Janvier",
    2: "02 - Février",
    3: "03 - Mars",
    4: "04 - Avril",
    5: "05 - Mai",
    6: "06 - Juin",
    7: "07 - Juillet",
    8: "08 - Août",
    9: "09 - Septembre",
    10: "10 - Octobre",
    11: "11 - Novembre",
    12: "12 - Décembre",
}
DB = PRIVATE_ROOT / "data" / "foulfix.db"
SIGNATURES = PRIVATE_ROOT / "signatures"
CONFIG_PATH = PRIVATE_ROOT / "config.json"

# Personnalisation privée : logo facture choisi par l'utilisateur et signature technicien.
# Aucun logo d'entreprise n'est livré dans public/ : chaque installation garde le sien dans private/.
_PRIVATE_LOGO_INVOICE = PRIVATE_ASSETS / "logo_invoice_user.png"
TECH_SIGNATURE = PRIVATE_ASSETS / "tech_signature.png"

def invoice_logo_path():
    """Retourne le logo facture privé courant, ou None si aucun logo n'est configuré."""
    return _PRIVATE_LOGO_INVOICE if _PRIVATE_LOGO_INVOICE.is_file() else None

GOOGLE_CLIENT_SECRET = PRIVATE_ROOT / "data" / "google_client_secret.json"
GOOGLE_TOKEN = PRIVATE_ROOT / "data" / "google_token.json"
SMTP_SETTINGS_FILE = PRIVATE_ROOT / "data" / "smtp_settings.json"
ABBY_SETTINGS_FILE = PRIVATE_ROOT / "data" / "abby_settings.json"
ABBY_API_BASE = "https://api.app-abby.com"
APP_VERSION = "2.3.285"
GOOGLE_SCOPE = ["https://www.googleapis.com/auth/contacts"]

# Sécurité locale WOPR
ADMIN_PIN_FILE = PRIVATE_ROOT / "data" / "admin_pin.json"
APP_SECRET_FILE = PRIVATE_ROOT / "data" / "app_secret.key"

# Clé maîtresse des secrets : volontairement hors du dossier WOPR.
# Pour une installation existante, l'ancien emplacement Foul-Fix reste reconnu
# afin de ne pas casser le déchiffrement des secrets déjà enregistrés.
def _secret_key_path():
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    current = root / "WOPR" / "master.key"
    legacy = root / "Foul-Fix" / "master.key"
    if current.exists():
        return current
    if legacy.exists():
        return legacy
    return current

MASTER_SECRET_FILE = _secret_key_path()
BACKUP_DIR = PRIVATE_ROOT / "data" / "backups"
IMPORT_DIR = PRIVATE_ROOT / "data" / "imports"
ADMIN_SESSION_HOURS = 8
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 8
PIN_MAX_ATTEMPTS = 5
PIN_BLOCK_SECONDS = 60
LOGIN_FAILURES = {}


# Données historiques privées.
# En version publique, ces fichiers peuvent être absents : l'application démarre alors
# avec des jeux historiques vides, sans révéler les anciens clients/comptes.
LEGACY_LEDGER_ENTRIES = []
LEGACY_ANTIVIRUS_ENTRIES = []
LEGACY_QUOTE = {}
LEGACY_QUOTES_37 = []
LEGACY_QUOTE_DOCUMENTS_37 = []
LEGACY_FOLLOWUPS = []

if PRIVATE_SEEDS.exists():
    sys.path.insert(0, str(PRIVATE_SEEDS))
    try:
        from legacy_ledger_seed import LEGACY_LEDGER_ENTRIES
    except Exception:
        pass
    try:
        from legacy_management_seed import LEGACY_ANTIVIRUS_ENTRIES, LEGACY_QUOTE
    except Exception:
        pass
    try:
        from legacy_quotes37_seed import LEGACY_QUOTES_37, LEGACY_QUOTE_DOCUMENTS_37
    except Exception:
        pass
    try:
        from legacy_followups_seed import LEGACY_FOLLOWUPS
    except Exception:
        pass


# V2.3.108 - PDF multilingues. L'interface et les donnees restent en francais.
PDF_LANGUAGES = {
    "fr": ("FR", "Français"),
    "en": ("EN", "English"),
    "uk": ("UA", "Українська"),
    "es": ("ES", "Español"),
    "de": ("DE", "Deutsch"),
    "it": ("IT", "Italiano"),
}

PDF_FRENCH = {
    "invoice": "FACTURE", "invoice_no": "Facture n°", "date": "Date", "client": "Client", "phone": "Tél.",
    "quantity": "Quantité", "description": "Désignation", "unit_price": "P.U.", "total": "Total",
    "vat_notice": "TVA non applicable, art. 293 B du CGI", "invoice_euros": "Facture en euros", "net_payable": "Net à payer",
    "abandon_1": "Tout matériel confié et non récupéré dans un délai de 3 mois après information de mise à disposition sera considéré comme abandonné.",
    "abandon_2": "Passé ce délai, le matériel pourra être détruit ou recyclé en déchetterie, sans possibilité de réclamation ni indemnisation.",
    "payment_1": "Conditions de paiement : paiement à réception de facture", "payment_2": "Aucun escompte consenti pour règlement anticipé",
    "payment_3": "Tout incident de paiement est passible d'intérêt de retard au taux légal en vigueur au moment de l'incident.",
    "payment_4": "Indemnité forfaitaire pour frais de recouvrement due en cas de retard de paiement : 40 EUR",
    "intake_title": "Prise en charge / Suivi de réparation", "client_info": "Informations Client", "first_name": "Prénom", "last_name": "Nom",
    "address": "Adresse", "postal_city": "Code postal / Ville", "email": "Courriel", "device_details": "Détails de l'Appareil",
    "device_type": "Type d'Appareil", "brand_model": "Marque et Modèle", "serial": "Numéro de Série", "system": "Système",
    "password": "Mot de passe", "accessories": "Accessoires", "condition": "État", "problem_desc": "Description du Problème",
    "problem": "Panne", "diagnosis": "Diagnostic", "repair_authorization": "Autorisation de Réparation", "client_signature": "Signature du Client",
    "signed_on": "Signé le", "validation_return": "Validation et Retour", "tests_validation": "Tests et Validation",
    "technician_signature": "Signature du Technicien", "warranty": "Garantie", "warranty_duration": "Durée de la Garantie",
    "six_months": "Six mois", "warranty_text": "Conformément à l'article L211-4 du Code de la consommation, vous bénéficiez d'une garantie légale de six mois à compter de la date de réparation pour les travaux effectués. Cette garantie couvre les mêmes défauts ou problèmes que ceux réparés initialement.",
    "warranty_conditions": "Conditions de Garantie", "warranty_only": "La garantie couvre uniquement les défauts mentionnés ci-dessus.",
    "remarks": "Remarques", "thanks": "Merci de votre confiance.",
    "siret_no": "N° Siret", "ape_code": "Code APE",
    "legal_registration_exemption": "Dispensé d’immatriculation au registre du commerce et des sociétés, en application de l’article L. 123-1-1 du Code de commerce",
}

PDF_TRANSLATIONS = {
    "en": {
        "invoice":"INVOICE","invoice_no":"Invoice no.","date":"Date","client":"Customer","phone":"Phone","quantity":"Quantity","description":"Description","unit_price":"Unit price","total":"Total",
        "vat_notice":"VAT not applicable - Art. 293 B of the French Tax Code","invoice_euros":"Invoice in euros","net_payable":"Amount due",
        "abandon_1":"Any equipment entrusted to us and not collected within 3 months after notification that it is available will be considered abandoned.",
        "abandon_2":"After this period, the equipment may be destroyed or recycled, with no possibility of claim or compensation.",
        "payment_1":"Payment terms: payment due upon receipt of invoice","payment_2":"No discount granted for early payment","payment_3":"Any late payment may incur interest at the legal rate in force.","payment_4":"Fixed recovery fee in case of late payment: EUR 40",
        "intake_title":"Repair intake / Service report","client_info":"Customer Information","first_name":"First name","last_name":"Last name","address":"Address","postal_city":"Postcode / City","email":"Email",
        "device_details":"Device Details","device_type":"Device type","brand_model":"Brand and model","serial":"Serial number","system":"System","password":"Password","accessories":"Accessories","condition":"Condition",
        "problem_desc":"Problem Description","problem":"Problem","diagnosis":"Diagnosis","repair_authorization":"Repair Authorization","client_signature":"Customer signature","signed_on":"Signed on",
        "validation_return":"Validation and Return","tests_validation":"Tests and validation","technician_signature":"Technician signature","warranty":"Warranty","warranty_duration":"Warranty period","six_months":"Six months",
        "warranty_text":"In accordance with Article L211-4 of the French Consumer Code, the work carried out is covered by a six-month legal warranty from the repair date. This warranty covers the same defects or problems as those initially repaired.",
        "warranty_conditions":"Warranty conditions","warranty_only":"The warranty covers only the defects mentioned above.","remarks":"Notes","thanks":"Thank you for your trust.","siret_no":"SIRET No.","ape_code":"APE code","legal_registration_exemption":"Exempt from registration with the Trade and Companies Register, pursuant to Article L. 123-1-1 of the French Commercial Code",
    },
    "uk": {
        "invoice":"РАХУНОК-ФАКТУРА","invoice_no":"Рахунок №","date":"Дата","client":"Клієнт","phone":"Тел.","quantity":"Кількість","description":"Найменування","unit_price":"Ціна за од.","total":"Сума",
        "vat_notice":"ПДВ не застосовується - ст. 293 B Податкового кодексу Франції","invoice_euros":"Рахунок у євро","net_payable":"До сплати",
        "abandon_1":"Обладнання, передане нам і не забране протягом 3 місяців після повідомлення про готовність, вважатиметься залишеним.",
        "abandon_2":"Після цього строку обладнання може бути утилізоване або перероблене без можливості претензій чи компенсації.",
        "payment_1":"Умови оплати: оплата після отримання рахунку","payment_2":"Знижка за дострокову оплату не надається","payment_3":"У разі прострочення оплати можуть нараховуватися відсотки за чинною законною ставкою.","payment_4":"Фіксована компенсація витрат на стягнення у разі прострочення: 40 EUR",
        "intake_title":"Приймання / Звіт про ремонт","client_info":"Інформація про клієнта","first_name":"Ім'я","last_name":"Прізвище","address":"Адреса","postal_city":"Поштовий індекс / Місто","email":"Ел. пошта",
        "device_details":"Відомості про пристрій","device_type":"Тип пристрою","brand_model":"Марка та модель","serial":"Серійний номер","system":"Система","password":"Пароль","accessories":"Комплектація","condition":"Стан",
        "problem_desc":"Опис несправності","problem":"Несправність","diagnosis":"Діагностика","repair_authorization":"Дозвіл на ремонт","client_signature":"Підпис клієнта","signed_on":"Підписано",
        "validation_return":"Перевірка та повернення","tests_validation":"Тести та перевірка","technician_signature":"Підпис техніка","warranty":"Гарантія","warranty_duration":"Термін гарантії","six_months":"Шість місяців",
        "warranty_text":"Відповідно до статті L211-4 Кодексу споживання Франції, на виконані роботи надається законна гарантія строком шість місяців від дати ремонту. Гарантія поширюється на ті самі несправності, які були усунені під час початкового ремонту.",
        "warranty_conditions":"Умови гарантії","warranty_only":"Гарантія поширюється лише на зазначені вище несправності.","remarks":"Примітки","thanks":"Дякуємо за довіру.","siret_no":"№ SIRET","ape_code":"Код APE","legal_registration_exemption":"Звільнено від реєстрації в Реєстрі торгівлі та компаній відповідно до статті L. 123-1-1 Торгового кодексу Франції",
    },
    "es": {
        "invoice":"FACTURA","invoice_no":"Factura n.º","date":"Fecha","client":"Cliente","phone":"Tel.","quantity":"Cantidad","description":"Descripción","unit_price":"P. unit.","total":"Total",
        "vat_notice":"IVA no aplicable - art. 293 B del Código Fiscal francés","invoice_euros":"Factura en euros","net_payable":"Total a pagar",
        "abandon_1":"Todo material confiado y no recogido en un plazo de 3 meses tras avisar de su disponibilidad se considerará abandonado.","abandon_2":"Pasado este plazo, el material podrá destruirse o reciclarse sin posibilidad de reclamación ni indemnización.",
        "payment_1":"Condiciones de pago: pago a la recepción de la factura","payment_2":"No se concede descuento por pago anticipado","payment_3":"Todo retraso de pago puede generar intereses al tipo legal vigente.","payment_4":"Indemnización fija por gastos de cobro en caso de retraso: 40 EUR",
        "intake_title":"Recepción / Seguimiento de reparación","client_info":"Información del cliente","first_name":"Nombre","last_name":"Apellidos","address":"Dirección","postal_city":"Código postal / Ciudad","email":"Correo electrónico",
        "device_details":"Datos del dispositivo","device_type":"Tipo de dispositivo","brand_model":"Marca y modelo","serial":"Número de serie","system":"Sistema","password":"Contraseña","accessories":"Accesorios","condition":"Estado",
        "problem_desc":"Descripción del problema","problem":"Avería","diagnosis":"Diagnóstico","repair_authorization":"Autorización de reparación","client_signature":"Firma del cliente","signed_on":"Firmado el",
        "validation_return":"Validación y devolución","tests_validation":"Pruebas y validación","technician_signature":"Firma del técnico","warranty":"Garantía","warranty_duration":"Duración de la garantía","six_months":"Seis meses",
        "warranty_text":"De conformidad con el artículo L211-4 del Código de Consumo francés, los trabajos realizados disponen de una garantía legal de seis meses desde la fecha de reparación. Esta garantía cubre los mismos defectos o problemas reparados inicialmente.",
        "warranty_conditions":"Condiciones de garantía","warranty_only":"La garantía cubre únicamente los defectos indicados anteriormente.","remarks":"Observaciones","thanks":"Gracias por su confianza.","siret_no":"N.º SIRET","ape_code":"Código APE","legal_registration_exemption":"Exento de inscripción en el Registro Mercantil y de Sociedades, de conformidad con el artículo L. 123-1-1 del Código de Comercio francés",
    },
    "de": {
        "invoice":"RECHNUNG","invoice_no":"Rechnung Nr.","date":"Datum","client":"Kunde","phone":"Tel.","quantity":"Menge","description":"Bezeichnung","unit_price":"Einzelpreis","total":"Gesamt",
        "vat_notice":"MwSt. nicht anwendbar - Art. 293 B des französischen Steuergesetzbuchs","invoice_euros":"Rechnung in Euro","net_payable":"Zu zahlen",
        "abandon_1":"Überlassenes und trotz Bereitstellungsmitteilung innerhalb von 3 Monaten nicht abgeholtes Gerät gilt als aufgegeben.","abandon_2":"Nach Ablauf dieser Frist kann das Gerät ohne Anspruch auf Reklamation oder Entschädigung entsorgt oder recycelt werden.",
        "payment_1":"Zahlungsbedingungen: Zahlung bei Rechnungserhalt","payment_2":"Kein Skonto bei vorzeitiger Zahlung","payment_3":"Bei Zahlungsverzug können Verzugszinsen zum geltenden gesetzlichen Zinssatz berechnet werden.","payment_4":"Pauschale Beitreibungskosten bei Zahlungsverzug: 40 EUR",
        "intake_title":"Annahme / Reparaturbericht","client_info":"Kundeninformationen","first_name":"Vorname","last_name":"Nachname","address":"Adresse","postal_city":"PLZ / Ort","email":"E-Mail",
        "device_details":"Gerätedaten","device_type":"Gerätetyp","brand_model":"Marke und Modell","serial":"Seriennummer","system":"System","password":"Passwort","accessories":"Zubehör","condition":"Zustand",
        "problem_desc":"Problembeschreibung","problem":"Fehler","diagnosis":"Diagnose","repair_authorization":"Reparaturfreigabe","client_signature":"Unterschrift des Kunden","signed_on":"Unterschrieben am",
        "validation_return":"Prüfung und Rückgabe","tests_validation":"Tests und Prüfung","technician_signature":"Unterschrift des Technikers","warranty":"Garantie","warranty_duration":"Garantiedauer","six_months":"Sechs Monate",
        "warranty_text":"Gemäß Artikel L211-4 des französischen Verbrauchergesetzbuchs gilt für die ausgeführten Arbeiten eine gesetzliche Garantie von sechs Monaten ab Reparaturdatum. Sie deckt dieselben Mängel oder Probleme ab, die ursprünglich repariert wurden.",
        "warranty_conditions":"Garantiebedingungen","warranty_only":"Die Garantie deckt ausschließlich die oben genannten Mängel ab.","remarks":"Bemerkungen","thanks":"Vielen Dank für Ihr Vertrauen.","siret_no":"SIRET-Nr.","ape_code":"APE-Code","legal_registration_exemption":"Von der Eintragung in das französische Handels- und Gesellschaftsregister gemäß Artikel L. 123-1-1 des französischen Handelsgesetzbuchs befreit",
    },
    "it": {
        "invoice":"FATTURA","invoice_no":"Fattura n.","date":"Data","client":"Cliente","phone":"Tel.","quantity":"Quantità","description":"Descrizione","unit_price":"Prezzo unit.","total":"Totale",
        "vat_notice":"IVA non applicabile - art. 293 B del Codice tributario francese","invoice_euros":"Fattura in euro","net_payable":"Da pagare",
        "abandon_1":"Il materiale affidato e non ritirato entro 3 mesi dalla comunicazione di disponibilità sarà considerato abbandonato.","abandon_2":"Trascorso tale termine, il materiale potrà essere distrutto o riciclato senza possibilità di reclamo o indennizzo.",
        "payment_1":"Condizioni di pagamento: pagamento al ricevimento della fattura","payment_2":"Nessuno sconto per pagamento anticipato","payment_3":"In caso di ritardo possono essere applicati interessi al tasso legale vigente.","payment_4":"Indennità forfettaria per spese di recupero in caso di ritardo: 40 EUR",
        "intake_title":"Accettazione / Scheda di riparazione","client_info":"Informazioni cliente","first_name":"Nome","last_name":"Cognome","address":"Indirizzo","postal_city":"CAP / Città","email":"E-mail",
        "device_details":"Dettagli dispositivo","device_type":"Tipo di dispositivo","brand_model":"Marca e modello","serial":"Numero di serie","system":"Sistema","password":"Password","accessories":"Accessori","condition":"Stato",
        "problem_desc":"Descrizione del problema","problem":"Guasto","diagnosis":"Diagnosi","repair_authorization":"Autorizzazione alla riparazione","client_signature":"Firma del cliente","signed_on":"Firmato il",
        "validation_return":"Verifica e restituzione","tests_validation":"Test e verifica","technician_signature":"Firma del tecnico","warranty":"Garanzia","warranty_duration":"Durata della garanzia","six_months":"Sei mesi",
        "warranty_text":"Ai sensi dell'articolo L211-4 del Codice del consumo francese, i lavori eseguiti sono coperti da una garanzia legale di sei mesi dalla data della riparazione. La garanzia copre gli stessi difetti o problemi riparati inizialmente.",
        "warranty_conditions":"Condizioni di garanzia","warranty_only":"La garanzia copre esclusivamente i difetti indicati sopra.","remarks":"Note","thanks":"Grazie per la fiducia.","siret_no":"N. SIRET","ape_code":"Codice APE","legal_registration_exemption":"Esente dall’iscrizione al Registro del Commercio e delle Società ai sensi dell’articolo L. 123-1-1 del Codice di commercio francese",
    },
}

PDF_FREE_TEXT = {
    "uk": {"Forfait réparation Informatique":"Пакет послуг з ремонту комп'ютера","Préparation Ordinateur + Mise à jour":"Підготовка комп'ютера + оновлення","Sauvegarde/Restauration des données utilisateurs":"Резервне копіювання / відновлення даних користувача","Installation/Configuration chez cliente + vérification":"Встановлення / налаштування у клієнта + перевірка","Installation/Configuration chez client + vérification":"Встановлення / налаштування у клієнта + перевірка","Prestation de service":"Послуга","Vente de marchandises / pièces":"Продаж товарів / запчастин","Remplacement":"Заміна","Mise à jour":"Оновлення","Nettoyage":"Очищення","Diagnostic":"Діагностика","Réparation":"Ремонт","Passage du Mode S au mode \"Full\" sur Windows 11":"Перехід Windows 11 з режиму S у повний режим","Cleaning Spywares":"Видалення шпигунського ПЗ","Suppressions Logiciels inutiles et installation logiciels\n\"indispensables\"":"Видалення непотрібних програм і встановлення необхідного ПЗ","Suppressions Logiciels inutiles et installation logiciels \"indispensables\"":"Видалення непотрібних програм і встановлення необхідного ПЗ","Update Windows":"Оновлення Windows"},
    "en": {"Forfait réparation Informatique":"Computer repair package","Préparation Ordinateur + Mise à jour":"Computer setup + update","Sauvegarde/Restauration des données utilisateurs":"User data backup / restore","Installation/Configuration chez cliente + vérification":"On-site installation / configuration + check","Installation/Configuration chez client + vérification":"On-site installation / configuration + check","Prestation de service":"Service","Vente de marchandises / pièces":"Sale of goods / parts","Remplacement":"Replacement","Mise à jour":"Update","Nettoyage":"Cleaning","Diagnostic":"Diagnosis","Réparation":"Repair","Passage du Mode S au mode \"Full\" sur Windows 11":"Switching Windows 11 from S mode to full mode","Cleaning Spywares":"Spyware removal","Suppressions Logiciels inutiles et installation logiciels\n\"indispensables\"":"Removal of unnecessary software and installation of essential software","Suppressions Logiciels inutiles et installation logiciels \"indispensables\"":"Removal of unnecessary software and installation of essential software","Update Windows":"Windows update"},
    "es": {"Forfait réparation Informatique":"Paquete de reparación informática","Préparation Ordinateur + Mise à jour":"Preparación del ordenador + actualización","Sauvegarde/Restauration des données utilisateurs":"Copia de seguridad / restauración de datos del usuario","Installation/Configuration chez cliente + vérification":"Instalación / configuración in situ + verificación","Installation/Configuration chez client + vérification":"Instalación / configuración in situ + verificación","Prestation de service":"Servicio","Vente de marchandises / pièces":"Venta de productos / piezas","Remplacement":"Sustitución","Mise à jour":"Actualización","Nettoyage":"Limpieza","Diagnostic":"Diagnóstico","Réparation":"Reparación","Passage du Mode S au mode \"Full\" sur Windows 11":"Cambio de Windows 11 del modo S al modo completo","Cleaning Spywares":"Eliminación de software espía","Suppressions Logiciels inutiles et installation logiciels\n\"indispensables\"":"Eliminación de software innecesario e instalación del software esencial","Suppressions Logiciels inutiles et installation logiciels \"indispensables\"":"Eliminación de software innecesario e instalación del software esencial","Update Windows":"Actualización de Windows"},
    "de": {"Forfait réparation Informatique":"Pauschale Computerreparatur","Préparation Ordinateur + Mise à jour":"Computer-Einrichtung + Update","Sauvegarde/Restauration des données utilisateurs":"Sicherung / Wiederherstellung von Benutzerdaten","Installation/Configuration chez cliente + vérification":"Installation / Konfiguration vor Ort + Prüfung","Installation/Configuration chez client + vérification":"Installation / Konfiguration vor Ort + Prüfung","Prestation de service":"Dienstleistung","Vente de marchandises / pièces":"Verkauf von Waren / Teilen","Remplacement":"Austausch","Mise à jour":"Aktualisierung","Nettoyage":"Reinigung","Diagnostic":"Diagnose","Réparation":"Reparatur","Passage du Mode S au mode \"Full\" sur Windows 11":"Windows 11 vom S-Modus in den vollständigen Modus wechseln","Cleaning Spywares":"Entfernung von Spyware","Suppressions Logiciels inutiles et installation logiciels\n\"indispensables\"":"Entfernung unnötiger Software und Installation erforderlicher Software","Suppressions Logiciels inutiles et installation logiciels \"indispensables\"":"Entfernung unnötiger Software und Installation erforderlicher Software","Update Windows":"Windows-Aktualisierung"},
    "it": {"Forfait réparation Informatique":"Pacchetto riparazione informatica","Préparation Ordinateur + Mise à jour":"Preparazione computer + aggiornamento","Sauvegarde/Restauration des données utilisateurs":"Backup / ripristino dati utente","Installation/Configuration chez cliente + vérification":"Installazione / configurazione presso il cliente + verifica","Installation/Configuration chez client + vérification":"Installazione / configurazione presso il cliente + verifica","Prestation de service":"Prestazione di servizio","Vente de marchandises / pièces":"Vendita di prodotti / ricambi","Remplacement":"Sostituzione","Mise à jour":"Aggiornamento","Nettoyage":"Pulizia","Diagnostic":"Diagnosi","Réparation":"Riparazione","Passage du Mode S au mode \"Full\" sur Windows 11":"Passaggio di Windows 11 dalla modalità S alla modalità completa","Cleaning Spywares":"Rimozione di spyware","Suppressions Logiciels inutiles et installation logiciels\n\"indispensables\"":"Rimozione del software non necessario e installazione del software essenziale","Suppressions Logiciels inutiles et installation logiciels \"indispensables\"":"Rimozione del software non necessario e installazione del software essenziale","Update Windows":"Aggiornamento di Windows"},
}


# V2.3.156 — vocabulaire atelier commun, traduit dans TOUTES les langues PDF.
# Les champs libres restent saisis en français dans l'interface ; seule la copie PDF est traduite.
PDF_FREE_TEXT_EXTRA = {
    "en": {
        "Forfait Repair électronique": "Electronics repair package",
        "Forfait réparation électronique": "Electronics repair package",
        "Forfait réparation Informatique & électronique": "Computer & electronics repair package",
        "Forfait réparation informatique et électronique": "Computer & electronics repair package",
        "Réparation électronique": "Electronics repair",
        "Réparation informatique": "Computer repair",
        "Diagnostic électronique": "Electronics diagnosis",
        "Diagnostic informatique": "Computer diagnosis",
        "Réparation carte électronique": "Electronic board repair",
        "Réparation carte mère": "Motherboard repair",
        "(soudure/micro-soudure)": "(soldering/microsoldering)",
        "soudure / micro-soudure": "soldering/microsoldering",
        "soudure/micro-soudure": "soldering/microsoldering",
        "micro-soudure": "microsoldering",
        "microsoudure": "microsoldering",
        "soudure": "soldering",
        "Carte électronique": "Electronic board",
        "Carte mère": "Motherboard",
        "Remplacement connecteur HDMI": "HDMI connector replacement",
        "Remplacement connecteur USB-C": "USB-C connector replacement",
        "Remplacement connecteur de charge": "Charging connector replacement",
        "Remplacement écran": "Screen replacement",
        "Remplacement batterie": "Battery replacement",
        "Remplacement ventilateur": "Fan replacement",
        "Remplacement pâte thermique": "Thermal paste replacement",
        "Remplacement métal liquide": "Liquid metal replacement",
        "Nettoyage complet": "Full cleaning",
        "Nettoyage console": "Console cleaning",
        "Installation SSD": "SSD installation",
        "Installation Windows": "Windows installation",
        "Réinstallation Windows": "Windows reinstallation",
        "Récupération de données": "Data recovery",
        "Sauvegarde de données": "Data backup",
        "Suppression virus": "Virus removal",
        "Suppression malware": "Malware removal",
        "Main d'œuvre": "Labour",
        "Main d’oeuvre": "Labour",
        "Pièce détachée": "Spare part",
        "Connecteur de charge": "Charging connector",
        "Connecteur HDMI": "HDMI connector",
        "Port USB-C": "USB-C port",
        "Ventilateur": "Fan",
        "Écran": "Screen",
        "Batterie": "Battery",
        "Alimentation": "Power supply",
    },
    "uk": {
        "Forfait Repair électronique": "Пакет послуг з ремонту електроніки",
        "Forfait réparation électronique": "Пакет послуг з ремонту електроніки",
        "Forfait réparation Informatique & électronique": "Пакет послуг з ремонту комп'ютерів та електроніки",
        "Forfait réparation informatique et électronique": "Пакет послуг з ремонту комп'ютерів та електроніки",
        "Réparation électronique": "Ремонт електроніки",
        "Réparation informatique": "Ремонт комп'ютера",
        "Diagnostic électronique": "Діагностика електроніки",
        "Diagnostic informatique": "Діагностика комп'ютера",
        "Réparation carte électronique": "Ремонт електронної плати",
        "Réparation carte mère": "Ремонт материнської плати",
        "(soudure/micro-soudure)": "(пайка/мікропайка)",
        "soudure / micro-soudure": "пайка/мікропайка",
        "soudure/micro-soudure": "пайка/мікропайка",
        "micro-soudure": "мікропайка",
        "microsoudure": "мікропайка",
        "soudure": "пайка",
        "Carte électronique": "Електронна плата",
        "Carte mère": "Материнська плата",
        "Remplacement connecteur HDMI": "Заміна роз'єму HDMI",
        "Remplacement connecteur USB-C": "Заміна роз'єму USB-C",
        "Remplacement connecteur de charge": "Заміна роз'єму заряджання",
        "Remplacement écran": "Заміна екрана",
        "Remplacement batterie": "Заміна акумулятора",
        "Remplacement ventilateur": "Заміна вентилятора",
        "Remplacement pâte thermique": "Заміна термопасти",
        "Remplacement métal liquide": "Заміна рідкого металу",
        "Nettoyage complet": "Повне очищення",
        "Nettoyage console": "Очищення консолі",
        "Installation SSD": "Встановлення SSD",
        "Installation Windows": "Встановлення Windows",
        "Réinstallation Windows": "Перевстановлення Windows",
        "Récupération de données": "Відновлення даних",
        "Sauvegarde de données": "Резервне копіювання даних",
        "Suppression virus": "Видалення вірусів",
        "Suppression malware": "Видалення шкідливого ПЗ",
        "Main d'œuvre": "Робота",
        "Main d’oeuvre": "Робота",
        "Pièce détachée": "Запасна частина",
        "Connecteur de charge": "Роз'єм заряджання",
        "Connecteur HDMI": "Роз'єм HDMI",
        "Port USB-C": "Порт USB-C",
        "Ventilateur": "Вентилятор",
        "Écran": "Екран",
        "Batterie": "Акумулятор",
        "Alimentation": "Блок живлення",
    },
    "es": {
        "Forfait Repair électronique": "Paquete de reparación electrónica",
        "Forfait réparation électronique": "Paquete de reparación electrónica",
        "Forfait réparation Informatique & électronique": "Paquete de reparación informática y electrónica",
        "Forfait réparation informatique et électronique": "Paquete de reparación informática y electrónica",
        "Réparation électronique": "Reparación electrónica",
        "Réparation informatique": "Reparación informática",
        "Diagnostic électronique": "Diagnóstico electrónico",
        "Diagnostic informatique": "Diagnóstico informático",
        "Réparation carte électronique": "Reparación de placa electrónica",
        "Réparation carte mère": "Reparación de placa base",
        "(soudure/micro-soudure)": "(soldadura/microsoldadura)",
        "soudure / micro-soudure": "soldadura/microsoldadura",
        "soudure/micro-soudure": "soldadura/microsoldadura",
        "micro-soudure": "microsoldadura",
        "microsoudure": "microsoldadura",
        "soudure": "soldadura",
        "Carte électronique": "Placa electrónica",
        "Carte mère": "Placa base",
        "Remplacement connecteur HDMI": "Sustitución del conector HDMI",
        "Remplacement connecteur USB-C": "Sustitución del conector USB-C",
        "Remplacement connecteur de charge": "Sustitución del conector de carga",
        "Remplacement écran": "Sustitución de pantalla",
        "Remplacement batterie": "Sustitución de batería",
        "Remplacement ventilateur": "Sustitución de ventilador",
        "Remplacement pâte thermique": "Sustitución de pasta térmica",
        "Remplacement métal liquide": "Sustitución de metal líquido",
        "Nettoyage complet": "Limpieza completa",
        "Nettoyage console": "Limpieza de consola",
        "Installation SSD": "Instalación de SSD",
        "Installation Windows": "Instalación de Windows",
        "Réinstallation Windows": "Reinstalación de Windows",
        "Récupération de données": "Recuperación de datos",
        "Sauvegarde de données": "Copia de seguridad de datos",
        "Suppression virus": "Eliminación de virus",
        "Suppression malware": "Eliminación de malware",
        "Main d'œuvre": "Mano de obra",
        "Main d’oeuvre": "Mano de obra",
        "Pièce détachée": "Pieza de repuesto",
        "Connecteur de charge": "Conector de carga",
        "Connecteur HDMI": "Conector HDMI",
        "Port USB-C": "Puerto USB-C",
        "Ventilateur": "Ventilador",
        "Écran": "Pantalla",
        "Batterie": "Batería",
        "Alimentation": "Fuente de alimentación",
    },
    "de": {
        "Forfait Repair électronique": "Pauschale Elektronikreparatur",
        "Forfait réparation électronique": "Pauschale Elektronikreparatur",
        "Forfait réparation Informatique & électronique": "Pauschale Computer- und Elektronikreparatur",
        "Forfait réparation informatique et électronique": "Pauschale Computer- und Elektronikreparatur",
        "Réparation électronique": "Elektronikreparatur",
        "Réparation informatique": "Computerreparatur",
        "Diagnostic électronique": "Elektronikdiagnose",
        "Diagnostic informatique": "Computerdiagnose",
        "Réparation carte électronique": "Reparatur der Elektronikplatine",
        "Réparation carte mère": "Mainboard-Reparatur",
        "(soudure/micro-soudure)": "(Löten/Mikrolöten)",
        "soudure / micro-soudure": "Löten/Mikrolöten",
        "soudure/micro-soudure": "Löten/Mikrolöten",
        "micro-soudure": "Mikrolöten",
        "microsoudure": "Mikrolöten",
        "soudure": "Löten",
        "Carte électronique": "Elektronikplatine",
        "Carte mère": "Mainboard",
        "Remplacement connecteur HDMI": "Austausch des HDMI-Anschlusses",
        "Remplacement connecteur USB-C": "Austausch des USB-C-Anschlusses",
        "Remplacement connecteur de charge": "Austausch des Ladeanschlusses",
        "Remplacement écran": "Bildschirmtausch",
        "Remplacement batterie": "Akkutausch",
        "Remplacement ventilateur": "Lüftertausch",
        "Remplacement pâte thermique": "Austausch der Wärmeleitpaste",
        "Remplacement métal liquide": "Austausch des Flüssigmetalls",
        "Nettoyage complet": "Komplettreinigung",
        "Nettoyage console": "Konsolenreinigung",
        "Installation SSD": "SSD-Installation",
        "Installation Windows": "Windows-Installation",
        "Réinstallation Windows": "Windows-Neuinstallation",
        "Récupération de données": "Datenwiederherstellung",
        "Sauvegarde de données": "Datensicherung",
        "Suppression virus": "Virenentfernung",
        "Suppression malware": "Malware-Entfernung",
        "Main d'œuvre": "Arbeitsleistung",
        "Main d’oeuvre": "Arbeitsleistung",
        "Pièce détachée": "Ersatzteil",
        "Connecteur de charge": "Ladeanschluss",
        "Connecteur HDMI": "HDMI-Anschluss",
        "Port USB-C": "USB-C-Anschluss",
        "Ventilateur": "Lüfter",
        "Écran": "Bildschirm",
        "Batterie": "Akku",
        "Alimentation": "Netzteil",
    },
    "it": {
        "Forfait Repair électronique": "Pacchetto riparazione elettronica",
        "Forfait réparation électronique": "Pacchetto riparazione elettronica",
        "Forfait réparation Informatique & électronique": "Pacchetto riparazione informatica ed elettronica",
        "Forfait réparation informatique et électronique": "Pacchetto riparazione informatica ed elettronica",
        "Réparation électronique": "Riparazione elettronica",
        "Réparation informatique": "Riparazione informatica",
        "Diagnostic électronique": "Diagnosi elettronica",
        "Diagnostic informatique": "Diagnosi informatica",
        "Réparation carte électronique": "Riparazione scheda elettronica",
        "Réparation carte mère": "Riparazione scheda madre",
        "(soudure/micro-soudure)": "(saldatura/microsaldatura)",
        "soudure / micro-soudure": "saldatura/microsaldatura",
        "soudure/micro-soudure": "saldatura/microsaldatura",
        "micro-soudure": "microsaldatura",
        "microsoudure": "microsaldatura",
        "soudure": "saldatura",
        "Carte électronique": "Scheda elettronica",
        "Carte mère": "Scheda madre",
        "Remplacement connecteur HDMI": "Sostituzione connettore HDMI",
        "Remplacement connecteur USB-C": "Sostituzione connettore USB-C",
        "Remplacement connecteur de charge": "Sostituzione connettore di ricarica",
        "Remplacement écran": "Sostituzione schermo",
        "Remplacement batterie": "Sostituzione batteria",
        "Remplacement ventilateur": "Sostituzione ventola",
        "Remplacement pâte thermique": "Sostituzione pasta termica",
        "Remplacement métal liquide": "Sostituzione metallo liquido",
        "Nettoyage complet": "Pulizia completa",
        "Nettoyage console": "Pulizia console",
        "Installation SSD": "Installazione SSD",
        "Installation Windows": "Installazione Windows",
        "Réinstallation Windows": "Reinstallazione Windows",
        "Récupération de données": "Recupero dati",
        "Sauvegarde de données": "Backup dei dati",
        "Suppression virus": "Rimozione virus",
        "Suppression malware": "Rimozione malware",
        "Main d'œuvre": "Manodopera",
        "Main d’oeuvre": "Manodopera",
        "Pièce détachée": "Ricambio",
        "Connecteur de charge": "Connettore di ricarica",
        "Connecteur HDMI": "Connettore HDMI",
        "Port USB-C": "Porta USB-C",
        "Ventilateur": "Ventola",
        "Écran": "Schermo",
        "Batterie": "Batteria",
        "Alimentation": "Alimentatore",
    },
}

for _lang, _entries in PDF_FREE_TEXT_EXTRA.items():
    PDF_FREE_TEXT.setdefault(_lang, {}).update(_entries)


# V2.3.195 - Complément de traduction des textes techniques réellement saisis
# dans les factures et feuilles de suivi. Les libellés structurés étaient déjà
# complets dans les 5 langues ; ce bloc couvre les phrases libres fréquentes.
PDF_FREE_TEXT_REPAIR_EXTRA = {
    "en": {
        "Diagnostic et tentative de Réparation": "Diagnosis and attempted repair",
        "Détail sur feuille de suivi": "Details on the service report",
        "Composant HS": "Faulty component",
        "Condensateur coté affichage HS et remplacé": "Faulty display-side capacitor replaced",
        "Condensateur côté affichage HS et remplacé": "Faulty display-side capacitor replaced",
        "Carte mère nettoyé au niveau du composant brulé.": "Motherboard cleaned around the burnt component.",
        "Carte mère nettoyée au niveau du composant brûlé.": "Motherboard cleaned around the burnt component.",
        "Composant brulé remplacé et ressoudé.": "Burnt component replaced and resoldered.",
        "Composant brûlé remplacé et ressoudé.": "Burnt component replaced and resoldered.",
        "Toujours pas de démarrage": "Still does not start",
        "ne consomme rien": "draws no current",
        "Court circuit": "Short circuit",
        "Court-circuit": "Short circuit",
        "PCB abimée": "Damaged PCB",
        "PCB abîmée": "Damaged PCB",
        "Non réparable sans changer la Carte mère.": "Not repairable without replacing the motherboard.",
        "Non réparable sans changer la carte mère.": "Not repairable without replacing the motherboard.",
        "Rendu avec les composants remplacés mais pas d'allumage PC.": "Returned with the components replaced, but the PC still does not power on.",
        "composant brulé": "burnt component",
        "composant brûlé": "burnt component",
        "remplacé": "replaced",
        "ressoudé": "resoldered",
        "démarrage": "startup",
        "allumage": "power-on",
        "nettoyé": "cleaned",
        "nettoyée": "cleaned",
        "abimée": "damaged",
        "abîmée": "damaged",
        "sans changer": "without replacing",
        "tentative de": "attempted",
        "Détail sur": "Details on",
        "feuille de suivi": "service report",
    },
    "uk": {
        "Diagnostic et tentative de Réparation": "Діагностика та спроба ремонту",
        "Détail sur feuille de suivi": "Деталі у звіті про ремонт",
        "Composant HS": "Несправний компонент",
        "Condensateur coté affichage HS et remplacé": "Несправний конденсатор з боку дисплея замінено",
        "Condensateur côté affichage HS et remplacé": "Несправний конденсатор з боку дисплея замінено",
        "Carte mère nettoyé au niveau du composant brulé.": "Материнську плату очищено в зоні згорілого компонента.",
        "Carte mère nettoyée au niveau du composant brûlé.": "Материнську плату очищено в зоні згорілого компонента.",
        "Composant brulé remplacé et ressoudé.": "Згорілий компонент замінено та перепаяно.",
        "Composant brûlé remplacé et ressoudé.": "Згорілий компонент замінено та перепаяно.",
        "Toujours pas de démarrage": "Пристрій усе ще не запускається",
        "ne consomme rien": "не споживає струм",
        "Court circuit": "Коротке замикання",
        "Court-circuit": "Коротке замикання",
        "PCB abimée": "Пошкоджена друкована плата",
        "PCB abîmée": "Пошкоджена друкована плата",
        "Non réparable sans changer la Carte mère.": "Ремонт неможливий без заміни материнської плати.",
        "Non réparable sans changer la carte mère.": "Ремонт неможливий без заміни материнської плати.",
        "Rendu avec les composants remplacés mais pas d'allumage PC.": "Повернено із заміненими компонентами, але ПК усе ще не вмикається.",
        "composant brulé": "згорілий компонент",
        "composant brûlé": "згорілий компонент",
        "remplacé": "замінено",
        "ressoudé": "перепаяно",
        "démarrage": "запуск",
        "allumage": "увімкнення",
        "nettoyé": "очищено",
        "nettoyée": "очищено",
        "abimée": "пошкоджена",
        "abîmée": "пошкоджена",
        "sans changer": "без заміни",
        "tentative de": "спроба",
        "Détail sur": "Деталі у",
        "feuille de suivi": "звіті про ремонт",
    },
    "es": {
        "Diagnostic et tentative de Réparation": "Diagnóstico e intento de reparación",
        "Détail sur feuille de suivi": "Detalles en la hoja de seguimiento",
        "Composant HS": "Componente defectuoso",
        "Condensateur coté affichage HS et remplacé": "Condensador del lado de la pantalla defectuoso y sustituido",
        "Condensateur côté affichage HS et remplacé": "Condensador del lado de la pantalla defectuoso y sustituido",
        "Carte mère nettoyé au niveau du composant brulé.": "Placa base limpiada alrededor del componente quemado.",
        "Carte mère nettoyée au niveau du composant brûlé.": "Placa base limpiada alrededor del componente quemado.",
        "Composant brulé remplacé et ressoudé.": "Componente quemado sustituido y resoldado.",
        "Composant brûlé remplacé et ressoudé.": "Componente quemado sustituido y resoldado.",
        "Toujours pas de démarrage": "Sigue sin arrancar",
        "ne consomme rien": "no consume corriente",
        "Court circuit": "Cortocircuito",
        "Court-circuit": "Cortocircuito",
        "PCB abimée": "PCB dañada",
        "PCB abîmée": "PCB dañada",
        "Non réparable sans changer la Carte mère.": "No se puede reparar sin sustituir la placa base.",
        "Non réparable sans changer la carte mère.": "No se puede reparar sin sustituir la placa base.",
        "Rendu avec les composants remplacés mais pas d'allumage PC.": "Devuelto con los componentes sustituidos, pero el PC sigue sin encender.",
        "composant brulé": "componente quemado",
        "composant brûlé": "componente quemado",
        "remplacé": "sustituido",
        "ressoudé": "resoldado",
        "démarrage": "arranque",
        "allumage": "encendido",
        "nettoyé": "limpiado",
        "nettoyée": "limpiada",
        "abimée": "dañada",
        "abîmée": "dañada",
        "sans changer": "sin sustituir",
        "tentative de": "intento de",
        "Détail sur": "Detalles en",
        "feuille de suivi": "hoja de seguimiento",
    },
    "de": {
        "Diagnostic et tentative de Réparation": "Diagnose und Reparaturversuch",
        "Détail sur feuille de suivi": "Details im Servicebericht",
        "Composant HS": "Defektes Bauteil",
        "Condensateur coté affichage HS et remplacé": "Defekter Kondensator auf der Displayseite ersetzt",
        "Condensateur côté affichage HS et remplacé": "Defekter Kondensator auf der Displayseite ersetzt",
        "Carte mère nettoyé au niveau du composant brulé.": "Mainboard im Bereich des verbrannten Bauteils gereinigt.",
        "Carte mère nettoyée au niveau du composant brûlé.": "Mainboard im Bereich des verbrannten Bauteils gereinigt.",
        "Composant brulé remplacé et ressoudé.": "Verbranntes Bauteil ersetzt und neu verlötet.",
        "Composant brûlé remplacé et ressoudé.": "Verbranntes Bauteil ersetzt und neu verlötet.",
        "Toujours pas de démarrage": "Startet weiterhin nicht",
        "ne consomme rien": "nimmt keinen Strom auf",
        "Court circuit": "Kurzschluss",
        "Court-circuit": "Kurzschluss",
        "PCB abimée": "Beschädigte Leiterplatte",
        "PCB abîmée": "Beschädigte Leiterplatte",
        "Non réparable sans changer la Carte mère.": "Ohne Austausch des Mainboards nicht reparierbar.",
        "Non réparable sans changer la carte mère.": "Ohne Austausch des Mainboards nicht reparierbar.",
        "Rendu avec les composants remplacés mais pas d'allumage PC.": "Mit ersetzten Bauteilen zurückgegeben, der PC lässt sich jedoch weiterhin nicht einschalten.",
        "composant brulé": "verbranntes Bauteil",
        "composant brûlé": "verbranntes Bauteil",
        "remplacé": "ersetzt",
        "ressoudé": "neu verlötet",
        "démarrage": "Start",
        "allumage": "Einschalten",
        "nettoyé": "gereinigt",
        "nettoyée": "gereinigt",
        "abimée": "beschädigt",
        "abîmée": "beschädigt",
        "sans changer": "ohne Austausch",
        "tentative de": "Versuch einer",
        "Détail sur": "Details im",
        "feuille de suivi": "Servicebericht",
    },
    "it": {
        "Diagnostic et tentative de Réparation": "Diagnosi e tentativo di riparazione",
        "Détail sur feuille de suivi": "Dettagli nel rapporto di assistenza",
        "Composant HS": "Componente guasto",
        "Condensateur coté affichage HS et remplacé": "Condensatore lato display guasto e sostituito",
        "Condensateur côté affichage HS et remplacé": "Condensatore lato display guasto e sostituito",
        "Carte mère nettoyé au niveau du composant brulé.": "Scheda madre pulita nella zona del componente bruciato.",
        "Carte mère nettoyée au niveau du composant brûlé.": "Scheda madre pulita nella zona del componente bruciato.",
        "Composant brulé remplacé et ressoudé.": "Componente bruciato sostituito e risaldato.",
        "Composant brûlé remplacé et ressoudé.": "Componente bruciato sostituito e risaldato.",
        "Toujours pas de démarrage": "Continua a non avviarsi",
        "ne consomme rien": "non assorbe corrente",
        "Court circuit": "Cortocircuito",
        "Court-circuit": "Cortocircuito",
        "PCB abimée": "PCB danneggiata",
        "PCB abîmée": "PCB danneggiata",
        "Non réparable sans changer la Carte mère.": "Non riparabile senza sostituire la scheda madre.",
        "Non réparable sans changer la carte mère.": "Non riparabile senza sostituire la scheda madre.",
        "Rendu avec les composants remplacés mais pas d'allumage PC.": "Restituito con i componenti sostituiti, ma il PC continua a non accendersi.",
        "composant brulé": "componente bruciato",
        "composant brûlé": "componente bruciato",
        "remplacé": "sostituito",
        "ressoudé": "risaldato",
        "démarrage": "avvio",
        "allumage": "accensione",
        "nettoyé": "pulito",
        "nettoyée": "pulita",
        "abimée": "danneggiata",
        "abîmée": "danneggiata",
        "sans changer": "senza sostituire",
        "tentative de": "tentativo di",
        "Détail sur": "Dettagli nel",
        "feuille de suivi": "rapporto di assistenza",
    },
}

for _lang, _entries in PDF_FREE_TEXT_REPAIR_EXTRA.items():
    PDF_FREE_TEXT.setdefault(_lang, {}).update(_entries)

def pdf_lang(value=None):
    lang = str(value if value is not None else request.args.get("lang", "fr")).strip().lower()
    return lang if lang in PDF_LANGUAGES else "fr"

def pdf_t(key, lang="fr"):
    if lang == "fr":
        return PDF_FRENCH.get(key, key)
    return PDF_TRANSLATIONS.get(lang, {}).get(key, PDF_FRENCH.get(key, key))

def translate_pdf_text(text, lang="fr"):
    """Traduction uniquement au rendu PDF; aucune donnee n'est modifiee."""
    raw = str(text or "")
    if lang == "fr" or not raw:
        return raw
    out = raw
    glossary = PDF_FREE_TEXT.get(lang, {})
    for src in sorted(glossary, key=len, reverse=True):
        out = re.sub(re.escape(src), glossary[src], out, flags=re.IGNORECASE)
    return out

def pdf_language_suffix(lang="fr"):
    return PDF_LANGUAGES.get(lang, PDF_LANGUAGES["fr"])[0]

PDF_FONTS = {
    "regular": "Helvetica",
    "bold": "Helvetica-Bold",
    "italic": "Helvetica-Oblique",
}

def register_roboto():
    """Utilise Roboto si elle est installée sur Linux, sinon Helvetica."""
    global PDF_FONTS
    candidates = {
        # Roboto reste prioritaire pour conserver le rendu historique WOPR.
        # DejaVu Sans sert de repli Unicode/Cyrillique si Roboto n'est pas installee.
        "Roboto": [
            "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
            "/usr/share/fonts/TTF/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ],
        "Roboto-Bold": [
            "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf",
            "/usr/share/fonts/TTF/Roboto-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ],
        "Roboto-Italic": [
            "/usr/share/fonts/truetype/roboto/unhinted/RobotoTTF/Roboto-Italic.ttf",
            "/usr/share/fonts/truetype/roboto/Roboto-Italic.ttf",
            "/usr/share/fonts/TTF/Roboto-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ],
    }
    mapping = {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
    }
    for font_name, paths in candidates.items():
        for p in paths:
            if Path(p).exists():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, p))
                    if font_name == "Roboto":
                        mapping["regular"] = "Roboto"
                    elif font_name == "Roboto-Bold":
                        mapping["bold"] = "Roboto-Bold"
                    elif font_name == "Roboto-Italic":
                        mapping["italic"] = "Roboto-Italic"
                    break
                except Exception:
                    pass
    PDF_FONTS = mapping

register_roboto()

QUOTE_FONTS = {
    "regular": "Helvetica",
    "bold": "Helvetica-Bold",
    "italic": "Helvetica-Oblique",
}

def register_quote_fonts():
    """Police des devis historiques : priorité à Liberation Sans (très proche du Calc d'origine)."""
    global QUOTE_FONTS
    candidates = {
        "FFQuoteRegular": [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ],
        "FFQuoteBold": [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ],
        "FFQuoteItalic": [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Italic.ttf",
        ],
    }
    mapping = dict(QUOTE_FONTS)
    for font_name, paths in candidates.items():
        for p in paths:
            if Path(p).exists():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, p))
                    if font_name == "FFQuoteRegular":
                        mapping["regular"] = font_name
                    elif font_name == "FFQuoteBold":
                        mapping["bold"] = font_name
                    elif font_name == "FFQuoteItalic":
                        mapping["italic"] = font_name
                    break
                except Exception:
                    pass
    QUOTE_FONTS = mapping

register_quote_fonts()

app = Flask(__name__)
# V2.3.165 — WOPR doit rester autonome même si app.py est lancé directement,
# sans passer par un lanceur Linux/Windows.
for _directory in (
    PRIVATE_ROOT, DB.parent, SIGNATURES, BACKUP_DIR, IMPORT_DIR,
    PRIVATE_ASSETS, PRIVATE_SEEDS, FOULFIX_ROOT, DEVIS_ROOT, FACTURES_ROOT,
    SUIVI_REPARATIONS_ROOT,
):
    _directory.mkdir(parents=True, exist_ok=True)

def load_or_create_app_secret():
    if APP_SECRET_FILE.exists():
        value = APP_SECRET_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    APP_SECRET_FILE.write_text(value, encoding="utf-8")
    try:
        os.chmod(APP_SECRET_FILE, 0o600)
    except OSError:
        pass
    return value

app.secret_key = load_or_create_app_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,  # appli locale HTTP ; passera à True si HTTPS un jour
    PERMANENT_SESSION_LIFETIME=timedelta(hours=ADMIN_SESSION_HOURS),
    SESSION_REFRESH_EACH_REQUEST=True,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
)



def _wopr_remove_topbar_simple_invoice(html):
    """Supprime UNIQUEMENT le premier bouton Facture simple de la navigation haute."""
    # Dans base.html, la navigation principale est rendue avant le menu/pages.
    # On retire donc seulement le premier lien /invoice/simple dont le texte est Facture simple.
    pattern = re.compile(
        r'<a\b(?=[^>]*\bhref=["\']/invoice/simple(?:[?#][^"\']*)?["\'])[^>]*>'
        r'(?:(?!</a>).)*?Facture\s+simple(?:(?!</a>).)*?</a>',
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub("", html, count=1)


def _wopr_folder_button(folder_url):
    safe = html_escape(folder_url, quote=True)
    return (
        f'<button type="button" class="wopr-folder-direct" '
        f'title="Ouvrir le dossier du PDF" aria-label="Ouvrir le dossier du PDF" '
        f'onclick="fetch(\'{safe}\',{{cache:\'no-store\'}});return false;">📁</button>'
    )


def _wopr_add_pdf_folder_buttons(html):
    """Ajoute 📁 directement après les liens PDF réellement présents dans le HTML."""
    if 'wopr-folder-direct' in html:
        return html

    # Factures liées à un suivi : /repair/<id>/invoice.pdf
    invoice_link = re.compile(
        r'(<a\b[^>]*\bhref=["\'](?:https?://[^"\']+)?/repair/(\d+)/invoice\.pdf(?:[?#][^"\']*)?["\'][^>]*>.*?</a>)',
        re.IGNORECASE | re.DOTALL,
    )
    html = invoice_link.sub(
        lambda m: m.group(1) + _wopr_folder_button(f"/repair/{m.group(2)}/invoice-folder"),
        html,
    )

    # PDF de suivi / prise en charge : /repair/<id>/intake.pdf
    intake_link = re.compile(
        r'(<a\b[^>]*\bhref=["\'](?:https?://[^"\']+)?/repair/(\d+)/intake\.pdf(?:[?#][^"\']*)?["\'][^>]*>.*?</a>)',
        re.IGNORECASE | re.DOTALL,
    )
    html = intake_link.sub(
        lambda m: m.group(1) + _wopr_folder_button(f"/repair/{m.group(2)}/intake-folder"),
        html,
    )

    # Factures ouvertes depuis Achats/Ventes.
    ledger_link = re.compile(
        r'(<a\b[^>]*\bhref=["\'](?:https?://[^"\']+)?/achats-ventes/vente/(\d+)/facture(?:[?#][^"\']*)?["\'][^>]*>.*?</a>)',
        re.IGNORECASE | re.DOTALL,
    )
    html = ledger_link.sub(
        lambda m: m.group(1) + _wopr_folder_button(f"/achats-ventes/vente/{m.group(2)}/folder"),
        html,
    )

    # Certains boutons PDF utilisent formaction au lieu de href.
    invoice_formaction = re.compile(
        r'(<(?:button|input)\b[^>]*\bformaction=["\'](?:https?://[^"\']+)?/repair/(\d+)/invoice\.pdf(?:[?#][^"\']*)?["\'][^>]*>)',
        re.IGNORECASE | re.DOTALL,
    )
    html = invoice_formaction.sub(
        lambda m: m.group(1) + _wopr_folder_button(f"/repair/{m.group(2)}/invoice-folder"),
        html,
    )

    intake_formaction = re.compile(
        r'(<(?:button|input)\b[^>]*\bformaction=["\'](?:https?://[^"\']+)?/repair/(\d+)/intake\.pdf(?:[?#][^"\']*)?["\'][^>]*>)',
        re.IGNORECASE | re.DOTALL,
    )
    html = intake_formaction.sub(
        lambda m: m.group(1) + _wopr_folder_button(f"/repair/{m.group(2)}/intake-folder"),
        html,
    )

    # Style compact : n'élargit pas les boutons existants.
    style = """<style id="wopr-folder-direct-style">
.wopr-folder-direct{
 display:inline-flex;align-items:center;justify-content:center;
 width:20px;height:20px;min-width:20px;padding:0;margin-left:4px;
 border:1px solid #aeb8c4;border-radius:4px;background:#fff;
 cursor:pointer;font-size:11px;line-height:1;vertical-align:middle;
}
.wopr-folder-direct:hover{background:#eef6ff;border-color:#4b98df}
</style>"""
    if "</head>" in html:
        html = html.replace("</head>", style + "\n</head>", 1)
    return html


# Force explicitement UTF-8 pour toutes les pages HTML.
# Certains navigateurs Windows peuvent sinon interpréter les accents en Windows-1252
# lorsque l'en-tête HTTP ne précise pas le charset.
@app.after_request
def force_utf8_html(response):
    content_type = response.headers.get("Content-Type", "")
    if content_type.lower().startswith("text/html"):
        response.headers["Content-Type"] = "text/html; charset=utf-8"

        # V2.3.222 — correctifs responsive globaux.
        # Injectés ici pour s'appliquer à toutes les pages sans dupliquer
        # les inclusions dans chaque template.
        try:
            html = response.get_data(as_text=True)
            html = _wopr_remove_topbar_simple_invoice(html)
            css_tag = f'<link rel="stylesheet" href="/static/wopr-responsive.css?v={APP_VERSION}">'
            js_tag = f'<script src="/static/wopr-responsive.js?v={APP_VERSION}" defer></script>'
            print_js_tag = f'<script src="/static/wopr-print.js?v={APP_VERSION}" defer></script>'
            google_sync_js_tag = f'<script src="/static/wopr-google-sync.js?v={APP_VERSION}" defer></script>'
            folders_v248_js_tag = f'<script src="/static/wopr-folders-v248.js?v={APP_VERSION}" defer></script>'
            actions_8bit_runtime_js_tag = f'<script src="/static/wopr-8bit-actions-runtime.js?v={APP_VERSION}" defer></script>'
            uniform_css_tag = f'<link rel="stylesheet" href="/static/wopr-uniform-lists.css?v={APP_VERSION}">'
            action_colors_css_tag = f'<link rel="stylesheet" href="/static/wopr-action-colors.css?v={APP_VERSION}">'
            release_8bit_css_tag = f'<link rel="stylesheet" href="/static/wopr-8bit-release.css?v={APP_VERSION}">'
            hotfix_8bit_css_tag = f'<link rel="stylesheet" href="/static/wopr-8bit-hotfix.css?v={APP_VERSION}">'

            if "wopr-responsive.css" not in html and "</head>" in html:
                html = html.replace("</head>", css_tag + "\n</head>", 1)
            if "wopr-uniform-lists.css" not in html and "</head>" in html:
                html = html.replace("</head>", uniform_css_tag + "\n</head>", 1)
            if "wopr-action-colors.css" not in html and "</head>" in html:
                html = html.replace("</head>", action_colors_css_tag + "\n</head>", 1)
            if "wopr-8bit-release.css" not in html and "</head>" in html:
                html = html.replace("</head>", release_8bit_css_tag + "\n</head>", 1)
            if "wopr-8bit-hotfix.css" not in html and "</head>" in html:
                html = html.replace("</head>", hotfix_8bit_css_tag + "\n</head>", 1)


            if "wopr-responsive.js" not in html and "</body>" in html:
                html = html.replace("</body>", js_tag + "\n</body>", 1)

            if "wopr-print.js" not in html and "</body>" in html:
                html = html.replace("</body>", print_js_tag + "\n</body>", 1)

            if "wopr-google-sync.js" not in html and "</body>" in html:
                html = html.replace("</body>", google_sync_js_tag + "\n</body>", 1)

            if "wopr-folders-v248.js" not in html and "</body>" in html:
                html = html.replace("</body>", folders_v248_js_tag + "\n</body>", 1)
            if "wopr-8bit-actions-runtime.js" not in html and "</body>" in html:
                html = html.replace("</body>", actions_8bit_runtime_js_tag + "\n</body>", 1)

            response.set_data(html)
        except Exception:
            # Un problème cosmétique ne doit jamais empêcher WOPR de répondre.
            pass

    return response

def cfg():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def business_identity():
    """Identité de l'entreprise configurée localement, sans valeur personnelle codée en dur."""
    conf = cfg()
    name = str(conf.get("business_name") or "WOPR").strip() or "WOPR"
    owner = str(conf.get("owner_name") or "").strip()
    website = str(conf.get("website") or "").strip()
    email = str(conf.get("email") or "").strip()
    signature = f"{owner} – {name}" if owner and owner.casefold() != name.casefold() else (owner or name)
    return {"name": name, "owner": owner, "website": website, "email": email, "signature": signature}


def business_signature():
    ident = business_identity()
    lines = [ident["signature"]]
    if ident["website"]:
        lines.append(ident["website"])
    return "\n".join(lines)


def message_signature():
    """Signature courte réservée aux messages clients."""
    ident = business_identity()
    first_name = ident["owner"].split()[0] if ident["owner"] else ""
    if first_name and ident["name"]:
        return f"{first_name} / {ident['name']}"
    return first_name or ident["name"]


SECRET_PREFIX = "enc:v1:"


def validate_master_secret(raw):
    """Valide et normalise une clé Fernet WOPR."""
    raw = bytes(raw or b"").strip()
    if not raw:
        raise ValueError("Le fichier de clé est vide.")
    try:
        Fernet(raw)
    except Exception as exc:
        raise ValueError("Ce fichier n'est pas une clé maître WOPR valide.") from exc
    return raw


def install_master_secret(raw):
    """Installe une clé maître locale avec des permissions restrictives."""
    raw = validate_master_secret(raw)
    MASTER_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = MASTER_SECRET_FILE.with_suffix(".tmp")
    tmp.write_bytes(raw + b"\n")
    try:
        os.chmod(MASTER_SECRET_FILE.parent, 0o700)
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, MASTER_SECRET_FILE)
    try:
        os.chmod(MASTER_SECRET_FILE, 0o600)
    except OSError:
        pass
    return MASTER_SECRET_FILE


def create_master_secret():
    """Crée une nouvelle clé maître locale."""
    return install_master_secret(Fernet.generate_key())


def load_or_create_master_secret():
    """Retourne la clé Fernet locale. La création passe par l'écran dédié."""
    if not MASTER_SECRET_FILE.exists():
        raise RuntimeError(
            "Clé maître WOPR absente. Importez votre master.key au démarrage."
        )
    try:
        return validate_master_secret(MASTER_SECRET_FILE.read_bytes())
    except ValueError as exc:
        raise RuntimeError(f"Clé maître WOPR invalide : {MASTER_SECRET_FILE}") from exc


def encrypt_local_secret(value):
    value = str(value or "")
    if not value:
        return ""
    if value.startswith(SECRET_PREFIX):
        return value
    token = Fernet(load_or_create_master_secret()).encrypt(value.encode("utf-8")).decode("ascii")
    return SECRET_PREFIX + token


def decrypt_local_secret(value):
    value = str(value or "")
    if not value:
        return ""
    if not value.startswith(SECRET_PREFIX):
        # Compatibilité/migration avec les anciennes versions où le secret était en clair.
        return value
    token = value[len(SECRET_PREFIX):]
    try:
        return Fernet(load_or_create_master_secret()).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Impossible de déchiffrer un secret WOPR. La clé maître locale est absente ou différente."
        ) from exc


def decrypt_repair_password(value):
    """Déchiffre un mot de passe appareil stocké en base, avec compatibilité ancien clair."""
    return decrypt_local_secret(value)


def encrypt_repair_password(value):
    """Chiffre un mot de passe appareil avant stockage en base."""
    return encrypt_local_secret(value)


def _migrate_secret_in_json(path, field, loaded):
    """Chiffre silencieusement un ancien secret stocké en clair."""
    raw = str(loaded.get(field) or "")
    if not raw or raw.startswith(SECRET_PREFIX):
        return
    migrated = dict(loaded)
    migrated[field] = encrypt_local_secret(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def read_smtp_settings():
    """Paramètres SMTP locaux. Le jeton est chiffré sur disque."""
    business = cfg()
    business_email = str(business.get("email") or "").strip()
    business_name = str(business.get("business_name") or "WOPR").strip() or "WOPR"
    defaults = {
        "enabled": False,
        "host": "smtp.protonmail.ch",
        "port": 587,
        "security": "starttls",
        "username": business_email,
        "sender_email": business_email,
        "sender_name": business_name,
        "token": "",
    }
    try:
        if SMTP_SETTINGS_FILE.exists():
            loaded = json.loads(SMTP_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _migrate_secret_in_json(SMTP_SETTINGS_FILE, "token", loaded)
                loaded = dict(loaded)
                loaded["token"] = decrypt_local_secret(loaded.get("token", ""))
                defaults.update(loaded)
    except RuntimeError:
        raise
    except Exception:
        pass
    return defaults


def write_smtp_settings(settings):
    SMTP_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    stored = dict(settings)
    stored["token"] = encrypt_local_secret(stored.get("token", ""))
    SMTP_SETTINGS_FILE.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    try:
        os.chmod(SMTP_SETTINGS_FILE, 0o600)
    except OSError:
        pass


def smtp_send_message(msg):
    settings = read_smtp_settings()
    if not settings.get("enabled"):
        raise RuntimeError("SMTP Proton non activé.")
    if not settings.get("token"):
        raise RuntimeError("Jeton SMTP Proton absent.")

    host = str(settings.get("host") or "smtp.protonmail.ch").strip()
    port = int(settings.get("port") or 587)
    security = str(settings.get("security") or "starttls").lower()
    username = str(settings.get("username") or settings.get("sender_email") or "").strip()
    token = str(settings.get("token") or "")

    context = ssl.create_default_context()
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=20, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        if security == "starttls":
            server.starttls(context=context)
            server.ehlo()

    try:
        if username:
            server.login(username, token)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def read_abby_settings():
    """Configuration Abby locale. La clé API est chiffrée sur disque."""
    defaults = {
        "enabled": False,
        "api_key": "",
        "base_url": ABBY_API_BASE,
        "last_test_at": "",
        "last_test_ok": False,
        "last_test_message": "",
        "last_sync_at": "",
        "last_sync_summary": "",
    }
    try:
        if ABBY_SETTINGS_FILE.exists():
            loaded = json.loads(ABBY_SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                _migrate_secret_in_json(ABBY_SETTINGS_FILE, "api_key", loaded)
                loaded = dict(loaded)
                loaded["api_key"] = decrypt_local_secret(loaded.get("api_key", ""))
                defaults.update(loaded)
    except RuntimeError:
        raise
    except Exception:
        pass
    return defaults


def write_abby_settings(settings):
    ABBY_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    stored = dict(settings)
    stored["api_key"] = encrypt_local_secret(stored.get("api_key", ""))
    ABBY_SETTINGS_FILE.write_text(
        json.dumps(stored, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    try:
        os.chmod(ABBY_SETTINGS_FILE, 0o600)
    except OSError:
        pass


def abby_request(method, path, *, query=None, body=None, timeout=25):
    """Appel serveur -> Abby. La clé n'est jamais envoyée au navigateur."""
    settings = read_abby_settings()
    api_key = str(settings.get("api_key") or "").strip()
    if not settings.get("enabled"):
        raise RuntimeError("Intégration Abby non activée.")
    if not api_key:
        raise RuntimeError("Clé API Abby absente.")

    base_url = str(settings.get("base_url") or ABBY_API_BASE).strip().rstrip("/")
    url = base_url + "/" + str(path or "").lstrip("/")
    if query:
        clean_query = {k: v for k, v in query.items() if v is not None}
        url += "?" + urllib.parse.urlencode(clean_query)

    payload = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": f"WOPR/{APP_VERSION}",
    }
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=payload,
        headers=headers,
        method=str(method or "GET").upper()
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return {}
            text = raw.decode("utf-8", errors="replace")
            return json.loads(text)
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        if len(detail) > 500:
            detail = detail[:500] + "…"
        message = f"Abby HTTP {exc.code}"
        if detail:
            message += f" — {detail}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connexion Abby impossible — {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("Connexion Abby expirée (timeout).") from exc


def abby_paginated(path, *, limit=100):
    """Récupère toutes les pages Abby d'un endpoint docs/docs paginé."""
    docs = []
    page = 1
    while page <= 100:
        data = abby_request(
            "GET",
            path,
            query={"page": page, "limit": limit, "archived": "false"}
        )
        page_docs = data.get("docs") if isinstance(data, dict) else None
        if not isinstance(page_docs, list):
            break
        docs.extend(page_docs)
        if not data.get("hasNextPage"):
            break
        next_page = data.get("nextPage")
        try:
            page = int(next_page) if next_page else page + 1
        except Exception:
            page += 1
    return docs


def abby_address_payload(client_row):
    street = " ".join(str(client_row["address_street"] or "").split()).strip()
    postal = str(client_row["postal_code"] or "").strip()
    city = " ".join(str(client_row["city"] or "").split()).strip()
    if not (street and postal and city):
        return None
    return {
        "address": street,
        "complement": None,
        "city": city,
        "zipCode": postal,
        "state": "",
        "country": "FR",
    }


def abby_contact_payload(client_row):
    first = " ".join(str(client_row["first_name"] or "").split()).strip()
    last = " ".join(str(client_row["last_name"] or "").split()).strip()
    legacy = " ".join(str(client_row["name"] or "").split()).strip()

    if not first or not last:
        legacy_last, legacy_first = split_legacy_client_name(legacy)
        first = first or legacy_first
        last = last or legacy_last

    # Abby demande firstname + lastname. On évite de bloquer un ancien client
    # dont une seule partie du nom est connue.
    if not first:
        first = "Client"
    if not last:
        last = legacy or "Client"

    payload = {
        "firstname": first,
        "lastname": last,
    }
    phone = str(client_row["phone"] or "").strip()
    email = str(client_row["email"] or "").strip()
    if phone:
        payload["phone"] = phone
    if email:
        payload["emails"] = [email]
    address = abby_address_payload(client_row)
    if address:
        payload["billingAddress"] = address
    return payload


def abby_organization_payload(client_row):
    company = " ".join(str(client_row["company"] or "").split()).strip()
    legacy = " ".join(str(client_row["name"] or "").split()).strip()
    official_name = company or legacy or "Client"

    payload = {"name": official_name}
    if company:
        payload["commercialName"] = company

    email = str(client_row["email"] or "").strip()
    if email:
        payload["emails"] = [email]
    address = abby_address_payload(client_row)
    if address:
        payload["billingAddress"] = address
    return payload


def abby_remote_indexes():
    contacts = abby_paginated("/contacts")
    organizations = abby_paginated("/organizations")

    contact_email = {}
    contact_name = {}
    for item in contacts:
        iid = str(item.get("id") or "")
        for email in item.get("emails") or []:
            key = str(email or "").strip().casefold()
            if key:
                contact_email.setdefault(key, []).append(iid)
        fullname = _contact_name_normalize(item.get("fullname") or "")
        if fullname:
            contact_name.setdefault(fullname, []).append(iid)

    org_email = {}
    org_name = {}
    for item in organizations:
        iid = str(item.get("id") or "")
        for email in item.get("emails") or []:
            key = str(email or "").strip().casefold()
            if key:
                org_email.setdefault(key, []).append(iid)
        for value in (item.get("name"), item.get("commercialName")):
            key = _contact_name_normalize(value or "")
            if key:
                org_name.setdefault(key, []).append(iid)

    return {
        "contacts": contacts,
        "organizations": organizations,
        "contact_email": contact_email,
        "contact_name": contact_name,
        "org_email": org_email,
        "org_name": org_name,
    }


def abby_unique(index, key):
    values = [x for x in index.get(key, []) if x]
    values = list(dict.fromkeys(values))
    return values[0] if len(values) == 1 else ""


def sync_clients_to_abby():
    """
    Première synchronisation volontairement prudente :
    - WOPR reste la source.
    - si le client existe déjà chez Abby, on le rattache sans l'écraser ;
    - sinon on le crée.
    """
    remote = abby_remote_indexes()
    con = db()
    clients = con.execute("""
        SELECT *
        FROM clients
        WHERE COALESCE(archived,0)=0
        ORDER BY id
    """).fetchall()

    summary = {
        "total": len(clients),
        "linked": 0,
        "created": 0,
        "already": 0,
        "skipped": 0,
        "errors": 0,
        "contacts_remote": len(remote["contacts"]),
        "organizations_remote": len(remote["organizations"]),
    }

    for row in clients:
        cid = int(row["id"])
        company = " ".join(str(row["company"] or "").split()).strip()
        local_type = "organization" if company else "contact"
        existing_id = str(row["abby_id"] or "").strip()
        existing_type = str(row["abby_type"] or "").strip()

        if existing_id and existing_type in {"contact", "organization"}:
            summary["already"] += 1
            continue

        email_key = str(row["email"] or "").strip().casefold()
        name_candidates = _contact_name_variants(
            row["first_name"], row["last_name"], row["name"], company
        )

        remote_id = ""
        try:
            if local_type == "organization":
                if email_key:
                    remote_id = abby_unique(remote["org_email"], email_key)
                if not remote_id:
                    matches = []
                    for key in name_candidates:
                        matches.extend(remote["org_name"].get(key, []))
                    matches = list(dict.fromkeys(x for x in matches if x))
                    remote_id = matches[0] if len(matches) == 1 else ""
            else:
                if email_key:
                    remote_id = abby_unique(remote["contact_email"], email_key)
                if not remote_id:
                    matches = []
                    for key in name_candidates:
                        matches.extend(remote["contact_name"].get(key, []))
                    matches = list(dict.fromkeys(x for x in matches if x))
                    remote_id = matches[0] if len(matches) == 1 else ""

            if remote_id:
                con.execute("""
                    UPDATE clients SET
                        abby_id=?, abby_type=?,
                        abby_sync_status='lié',
                        abby_sync_error='',
                        abby_synced_at=?
                    WHERE id=?
                """, (
                    remote_id, local_type,
                    now().isoformat(timespec="seconds"), cid
                ))
                con.commit()
                summary["linked"] += 1
                continue

            # Ne crée pas les fiches totalement anonymes.
            meaningful = any([
                str(row["email"] or "").strip(),
                str(row["phone"] or "").strip(),
                company,
                str(row["first_name"] or "").strip(),
                str(row["last_name"] or "").strip(),
            ])
            if not meaningful or str(row["name"] or "").strip().casefold() == "client de passage":
                summary["skipped"] += 1
                continue

            if local_type == "organization":
                created = abby_request(
                    "POST", "/organization",
                    body=abby_organization_payload(row)
                )
            else:
                created = abby_request(
                    "POST", "/contact",
                    body=abby_contact_payload(row)
                )

            new_id = str(created.get("id") or "").strip() if isinstance(created, dict) else ""
            if not new_id:
                raise RuntimeError("Abby n'a pas renvoyé d'identifiant client.")

            con.execute("""
                UPDATE clients SET
                    abby_id=?, abby_type=?,
                    abby_sync_status='créé',
                    abby_sync_error='',
                    abby_synced_at=?
                WHERE id=?
            """, (
                new_id, local_type,
                now().isoformat(timespec="seconds"), cid
            ))
            con.commit()
            summary["created"] += 1

            # Enrichit les index pour éviter les doublons pendant le même run.
            if email_key:
                target = remote["org_email"] if local_type == "organization" else remote["contact_email"]
                target.setdefault(email_key, []).append(new_id)
            target_name = remote["org_name"] if local_type == "organization" else remote["contact_name"]
            for key in name_candidates:
                target_name.setdefault(key, []).append(new_id)

        except Exception as exc:
            con.execute("""
                UPDATE clients SET
                    abby_sync_status='erreur',
                    abby_sync_error=?,
                    abby_synced_at=?
                WHERE id=?
            """, (
                str(exc)[:500],
                now().isoformat(timespec="seconds"), cid
            ))
            con.commit()
            summary["errors"] += 1

    con.close()
    return summary


def normalize_global_search(value):
    """Texte canonique pour la recherche globale : accents, casse et ponctuation ignorés."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    # Fonction SQLite locale utilisée uniquement dans les recherches.
    con.create_function("WOPR_NORM", 1, normalize_global_search, deterministic=True)
    return con

def pin_is_configured():
    if not ADMIN_PIN_FILE.exists():
        return False
    try:
        data = json.loads(ADMIN_PIN_FILE.read_text(encoding="utf-8"))
        return bool(data.get("pin_hash"))
    except Exception:
        return False


def read_pin_hash():
    try:
        return json.loads(ADMIN_PIN_FILE.read_text(encoding="utf-8")).get("pin_hash", "")
    except Exception:
        return ""


def write_pin(pin):
    payload = {
        "pin_hash": generate_password_hash(pin, method="scrypt"),
        "updated_at": now().isoformat(timespec="seconds"),
    }
    ADMIN_PIN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(ADMIN_PIN_FILE, 0o600)
    except OSError:
        pass


def valid_pin_format(pin):
    return pin.isdigit() and PIN_MIN_LENGTH <= len(pin) <= PIN_MAX_LENGTH


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def safe_next_url(value):
    value = (value or "").strip()
    if value.startswith("/") and not value.startswith("//"):
        return value
    return url_for("index")


def audit_event(action, details="", ip=None):
    try:
        con = db()
        con.execute(
            "INSERT INTO audit_log(created_at,action,details,ip) VALUES(?,?,?,?)",
            (now().isoformat(timespec="seconds"), action, details[:1000], ip or "")
        )
        con.commit(); con.close()
    except Exception:
        pass


def _backup_stamp():
    return now().strftime("%Y-%m-%d_%Hh%Mm%Ss")


def _backup_marker_write(path, tag="backup"):
    """Ajoute un marqueur interne à la COPIE de sauvegarde, jamais à la base active."""
    con = sqlite3.connect(str(path))
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS wopr_backup_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        values = {
            "signature": "WOPR_BACKUP_V1",
            "app_version": APP_VERSION,
            "created_at": now().isoformat(timespec="seconds"),
            "tag": str(tag or "backup"),
        }
        con.executemany(
            "INSERT OR REPLACE INTO wopr_backup_meta(key,value) VALUES(?,?)",
            values.items()
        )
        con.commit()
    finally:
        con.close()


def _validate_wopr_database(path):
    """Valide le SQLite et vérifie qu'il ressemble bien à une base WOPR.

    Les sauvegardes récentes portent WOPR_BACKUP_V1. Les anciennes restent
    acceptées si leur structure WOPR essentielle est présente.
    """
    ok, detail = database_integrity_check(path)
    if not ok:
        return False, f"Contrôle SQLite = {detail}", {}
    con = None
    try:
        con = sqlite3.connect(str(path))
        tables = {str(r[0]) for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if not {"clients", "repairs"}.issubset(tables):
            return False, "Le fichier est un SQLite valide mais pas une base WOPR reconnue.", {}
        meta = {}
        if "wopr_backup_meta" in tables:
            try:
                meta = {str(k): str(v) for k, v in con.execute(
                    "SELECT key,value FROM wopr_backup_meta"
                ).fetchall()}
            except Exception:
                meta = {}
            signature = meta.get("signature", "")
            if signature and signature != "WOPR_BACKUP_V1":
                return False, "Marqueur de sauvegarde WOPR inconnu.", meta
        return True, "OK", meta
    except Exception as exc:
        return False, str(exc), {}
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def _extract_backup_to_sqlite(source, destination):
    """Matérialise une sauvegarde en SQLite brut d'après son CONTENU, pas son nom."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    with source.open("rb") as f:
        magic = f.read(16)
    if magic.startswith(b"SQLite format 3\x00"):
        shutil.copyfile(source, destination)
    elif magic.startswith(b"\x1f\x8b"):
        try:
            with gzip.open(source, "rb") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise ValueError(f"Archive GZIP invalide : {exc}") from exc
    else:
        raise ValueError("Format non reconnu : attendu SQLite ou GZIP contenant une base WOPR.")

    ok, detail, meta = _validate_wopr_database(destination)
    if not ok:
        destination.unlink(missing_ok=True)
        raise ValueError(detail)
    return meta


def backup_database(force=False, tag="auto", only_if_changed=False):
    if not DB.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # V2.3.243 — deux stratégies :
    # - démarrage : au maximum une sauvegarde automatique par jour ;
    # - fermeture : sauvegarder seulement si la base a réellement été modifiée
    #   depuis la dernière sauvegarde WOPR.
    if not force and only_if_changed:
        latest_backup_mtime_ns = 0
        for candidate in BACKUP_DIR.glob("foulfix_*"):
            try:
                if candidate.is_file():
                    latest_backup_mtime_ns = max(
                        latest_backup_mtime_ns,
                        candidate.stat().st_mtime_ns
                    )
            except OSError:
                pass

        try:
            db_mtime_ns = DB.stat().st_mtime_ns
        except OSError:
            db_mtime_ns = 0

        if latest_backup_mtime_ns and db_mtime_ns <= latest_backup_mtime_ns:
            return None

    elif not force:
        # La sauvegarde quotidienne ne dépend plus du nom : on regarde la date réelle
        # des sauvegardes WOPR déjà générées.
        today = now().date()
        for candidate in BACKUP_DIR.glob("foulfix_*"):
            try:
                if candidate.is_file() and datetime.fromtimestamp(candidate.stat().st_mtime).date() == today:
                    return None
            except OSError:
                pass

    safe_tag = re.sub(r"[^A-Za-z0-9_-]+", "_", tag)[:30] or "backup"
    dest = BACKUP_DIR / f"foulfix_{_backup_stamp()}_{safe_tag}.db.gz"
    temp_db = BACKUP_DIR / f".wopr_backup_{secrets.token_hex(5)}.db"

    try:
        _sqlite_backup_copy(DB, temp_db)
        _backup_marker_write(temp_db, safe_tag)
        ok, detail, _ = _validate_wopr_database(temp_db)
        if not ok:
            raise RuntimeError(f"Sauvegarde SQLite invalide avant compression : {detail}")
        with temp_db.open("rb") as src, dest.open("wb") as raw_dst:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw_dst, compresslevel=6, mtime=0) as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
        # Contrôle du GZIP final, indépendamment de son extension.
        verify_tmp = BACKUP_DIR / f".wopr_verify_{secrets.token_hex(5)}.db"
        try:
            _extract_backup_to_sqlite(dest, verify_tmp)
        finally:
            verify_tmp.unlink(missing_ok=True)
        try:
            os.chmod(dest, 0o600)
        except OSError:
            pass
    finally:
        temp_db.unlink(missing_ok=True)

    # Rétention uniquement sur les sauvegardes générées par WOPR. Un fichier
    # renommé/importé manuellement n'est pas supprimé juste à cause de sa présence.
    managed_pattern = re.compile(
        r"^foulfix_(?:\d{8}_\d{6}|\d{4}-\d{2}-\d{2}_\d{2}h\d{2}m\d{2}s)_[A-Za-z0-9_-]+\.db(?:\.gz)?$"
    )
    backups = []
    for candidate in BACKUP_DIR.iterdir():
        try:
            if candidate.is_file() and managed_pattern.fullmatch(candidate.name):
                backups.append(candidate)
        except OSError:
            pass
    backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[30:]:
        try:
            old.unlink()
        except OSError:
            pass
    return dest


def database_integrity_check(path):
    """Vérifie qu'un fichier SQLite BRUT est lisible et intègre."""
    path = Path(path)
    if not path.is_file():
        return False, "Fichier introuvable."
    con = None
    try:
        con = sqlite3.connect(str(path))
        con.execute("PRAGMA query_only=ON")
        row = con.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0] if row else "").strip()
        return result.casefold() == "ok", result or "Contrôle SQLite sans résultat."
    except Exception as exc:
        return False, str(exc)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


def _sqlite_backup_copy(source, destination):
    """Copie une base via l'API SQLite, sans simple copie de fichier."""
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    src_con = sqlite3.connect(str(source))
    dst_con = sqlite3.connect(str(destination))
    try:
        src_con.backup(dst_con)
    finally:
        dst_con.close()
        src_con.close()


def restore_database_backup(backup_name):
    """Rend une sauvegarde WOPR active après validation de son contenu."""
    backup_name = str(backup_name or "").strip()
    if not backup_name or Path(backup_name).name != backup_name:
        raise ValueError("Nom de sauvegarde invalide.")

    backup_root = BACKUP_DIR.resolve()
    source = (BACKUP_DIR / backup_name).resolve()
    if source.parent != backup_root or not source.is_file():
        raise ValueError("Sauvegarde introuvable.")

    stamp = now().strftime("%Y%m%d_%H%M%S")
    restore_tmp = DB.parent / f".foulfix_restore_{stamp}_{secrets.token_hex(3)}.db"
    rollback_tmp = DB.parent / f".foulfix_rollback_{stamp}_{secrets.token_hex(3)}.db"
    safety_tmp = DB.parent / f".foulfix_safety_{stamp}_{secrets.token_hex(3)}.db"

    # Reconnaissance par signature binaire + contenu SQLite. Le fichier peut donc
    # être renommé librement, avec ou sans extension.
    _extract_backup_to_sqlite(source, restore_tmp)

    # On conserve toujours l'état courant avant de basculer sur l'ancienne base.
    safety = backup_database(force=True, tag="avant_restauration")
    if not safety:
        restore_tmp.unlink(missing_ok=True)
        raise RuntimeError("Impossible de sauvegarder la base actuelle avant restauration.")

    try:
        # Le marqueur appartient à l'archive de sauvegarde, pas à la base active.
        try:
            marker_con = sqlite3.connect(str(restore_tmp))
            marker_con.execute("DROP TABLE IF EXISTS wopr_backup_meta")
            marker_con.commit()
            marker_con.close()
        except Exception:
            pass

        ok, detail, _ = _validate_wopr_database(restore_tmp)
        if not ok:
            raise RuntimeError(f"Copie de restauration invalide : {detail}")

        for suffix in ("-wal", "-shm"):
            try:
                Path(str(DB) + suffix).unlink(missing_ok=True)
            except OSError:
                pass

        os.replace(restore_tmp, DB)
        try:
            init_db()
            ok, detail, _ = _validate_wopr_database(DB)
            if not ok:
                raise RuntimeError(f"Base restaurée invalide après migration : {detail}")
            harden_local_permissions()
        except Exception as exc:
            _extract_backup_to_sqlite(safety, safety_tmp)
            try:
                c = sqlite3.connect(str(safety_tmp))
                c.execute("DROP TABLE IF EXISTS wopr_backup_meta")
                c.commit(); c.close()
            except Exception:
                pass
            _sqlite_backup_copy(safety_tmp, rollback_tmp)
            for suffix in ("-wal", "-shm"):
                try:
                    Path(str(DB) + suffix).unlink(missing_ok=True)
                except OSError:
                    pass
            os.replace(rollback_tmp, DB)
            harden_local_permissions()
            raise RuntimeError(
                f"Restauration annulée ; la base précédente a été remise automatiquement. Détail : {exc}"
            ) from exc
    finally:
        for tmp in (restore_tmp, rollback_tmp, safety_tmp):
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    return source, safety


def harden_local_permissions():
    for directory in (DB.parent, SIGNATURES, BACKUP_DIR, IMPORT_DIR):
        try: os.chmod(directory, 0o700)
        except OSError: pass
    for file_path in (DB, ADMIN_PIN_FILE, APP_SECRET_FILE, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN, SMTP_SETTINGS_FILE, ABBY_SETTINGS_FILE, MASTER_SECRET_FILE):
        if file_path.exists():
            try: os.chmod(file_path, 0o600)
            except OSError: pass


def resolve_signature_path(stored_value):
    """Résout une signature sans dépendre de l'ancien emplacement absolu de WOPR."""
    value = str(stored_value or "").strip()
    if not value:
        return None
    raw = Path(value)
    # Nouveau format portable : le nom du fichier uniquement.
    if not raw.is_absolute():
        candidate = SIGNATURES / raw.name
        return candidate if candidate.exists() else None
    # Compatibilité : ancienne base contenant /home/.../WOPR/private/signatures/x.png.
    if raw.exists():
        return raw
    moved = SIGNATURES / raw.name
    return moved if moved.exists() else None


def _portability_diagnostics_impl():
    """Diagnostic local volontairement non sensible : aucun chemin secret n'est exposé."""
    checks = []

    def add(label, ok, detail_ok, detail_bad, required=True):
        checks.append({
            "label": label,
            "ok": bool(ok),
            "detail": detail_ok if ok else detail_bad,
            "required": bool(required),
        })

    # Tous les emplacements persistants, sauf la clé maître volontairement locale à la machine,
    # doivent être contenus dans WOPR/private.
    managed = (
        DB, CONFIG_PATH, GOOGLE_CLIENT_SECRET, GOOGLE_TOKEN, SMTP_SETTINGS_FILE,
        ABBY_SETTINGS_FILE, ADMIN_PIN_FILE, APP_SECRET_FILE, BACKUP_DIR, IMPORT_DIR,
        SIGNATURES, PRIVATE_ASSETS, PRIVATE_SEEDS, DEVIS_ROOT, FACTURES_ROOT,
        SUIVI_REPARATIONS_ROOT,
    )
    private_resolved = PRIVATE_ROOT.resolve()
    inside_private = True
    for item in managed:
        try:
            item.resolve().relative_to(private_resolved)
        except Exception:
            inside_private = False
            break
    add(
        "Données et documents internes",
        inside_private,
        "Les fichiers persistants gérés par WOPR restent dans private/.",
        "Au moins un fichier persistant pointe encore hors de private/.",
    )

    required_dirs = (DB.parent, SIGNATURES, BACKUP_DIR, IMPORT_DIR, FACTURES_ROOT, DEVIS_ROOT, SUIVI_REPARATIONS_ROOT)
    dirs_ok = all(p.is_dir() for p in required_dirs)
    add(
        "Structure privée",
        dirs_ok,
        "Base, sauvegardes, imports, signatures, Factures, Devis et Suivi sont prêts.",
        "Un ou plusieurs dossiers privés nécessaires sont absents.",
    )

    # Test réel d'écriture, puis suppression immédiate.
    write_ok = False
    probe = DB.parent / f".portability_{secrets.token_hex(4)}.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        write_ok = probe.read_text(encoding="utf-8") == "ok"
    except Exception:
        write_ok = False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except Exception:
            pass
    add(
        "Écriture sur le support",
        write_ok,
        "WOPR peut écrire dans son espace privé.",
        "Le support ou le dossier WOPR n'est pas inscriptible.",
    )

    add(
        "Base de données",
        DB.exists() and DB.is_file(),
        "La base locale est présente.",
        "Aucune base locale n'est présente (normal uniquement pour une installation neuve).",
    )

    public_required = (
        BASE / "app.py", BASE / "requirements.txt", BASE / "templates", BASE / "static",
    )
    add(
        "Cœur public",
        all(p.exists() for p in public_required),
        "Code, dépendances, modèles et ressources publiques sont présents.",
        "Un élément du cœur public de WOPR manque.",
    )

    # Traque ciblée des chemins personnels codés en dur. Les chemins système génériques
    # (/usr/share/fonts, APPDATA, XDG_CONFIG_HOME...) ne sont pas des dépendances à ce PC.
    forbidden = (
        "/home/" + "foul/",
        "GDrive" + "/Web/",
        "/mnt/" + "data/",
        "C:\\Users\\" + "foul\\",
    )
    scan_files = [BASE / "app.py"] + sorted((BASE / "scripts").glob("*"))
    hardcoded = []
    for source in scan_files:
        if not source.is_file():
            continue
        try:
            body = source.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        if any(token.casefold() in body.casefold() for token in forbidden):
            hardcoded.append(source.name)
    add(
        "Chemins propres à ce PC",
        not hardcoded,
        "Aucun chemin personnel propre à cette machine n'est codé en dur dans le cœur ou les lanceurs.",
        "Des chemins personnels codés en dur subsistent : " + ", ".join(hardcoded),
    )

    # V2.3.221 : anciens .desktop/.vbs supprimés.
    # Le launcher unifié est public/launcher/wopr_launcher.py et les binaires
    # officiels sont WOPR (Linux) et WOPR.exe (Windows) à la racine.
    launcher_source = WOPR_ROOT / "public" / "launcher" / "wopr_launcher.py"
    linux_launcher = WOPR_ROOT / "WOPR"
    windows_launcher = WOPR_ROOT / "WOPR.exe"

    missing_launchers = []
    if not launcher_source.is_file():
        missing_launchers.append("public/launcher/wopr_launcher.py")
    if not linux_launcher.is_file():
        missing_launchers.append("WOPR")
    if not windows_launcher.is_file():
        missing_launchers.append("WOPR.exe")

    if missing_launchers:
        launcher_error = "Élément(s) du launcher absent(s) : " + ", ".join(missing_launchers)
    else:
        launcher_error = ""

    add(
        "Lanceurs portables",
        not missing_launchers,
        "Source du launcher présente ; binaires Linux WOPR et Windows WOPR.exe présents.",
        launcher_error,
    )

    # Les bibliothèques principales sont déjà importées si cette page s'affiche.
    deps_ok = bool(qrcode and canvas and Flask)
    add(
        "Dépendances Python actives",
        deps_ok,
        "Les dépendances principales chargées par WOPR sont disponibles.",
        "Une dépendance Python principale est indisponible.",
    )

    # Fonction utile mais non requise pour que WOPR soit portable.
    kde_ok = shutil.which("kdeconnect-cli") is not None
    add(
        "SMS KDE Connect",
        kde_ok,
        "kdeconnect-cli est disponible sur cette machine.",
        "Optionnel : kdeconnect-cli n'est pas disponible sur cette machine.",
        required=False,
    )

    ready = all(c["ok"] for c in checks if c["required"])
    return {"ready": ready, "checks": checks}



def portability_diagnostics():
    """
    Diagnostic de portabilité non bloquant.
    La page Sécurité doit rester accessible même si une vérification locale
    échoue sur une machine, un support USB ou un OS particulier.
    """
    try:
        result = _portability_diagnostics_impl()
        if not isinstance(result, dict):
            raise TypeError("résultat de diagnostic invalide")
        result.setdefault("ready", False)
        result.setdefault("checks", [])
        return result
    except Exception as exc:
        # On n'expose ni chemin local ni secret dans l'interface.
        try:
            audit_event(
                "PORTABILITY_DIAGNOSTIC_ERROR",
                f"{type(exc).__name__}: diagnostic indisponible",
                request.remote_addr if request else "",
            )
        except Exception:
            pass
        return {
            "ready": False,
            "checks": [
                {
                    "label": "Diagnostic de portabilité",
                    "ok": False,
                    "required": True,
                    "detail": "Le diagnostic n'a pas pu s'exécuter sur cette machine. WOPR reste utilisable.",
                }
            ],
        }


def compose_client_name(last_name, first_name):
    """Champ historique `name` conservé pour compatibilité : Prénom Nom."""
    last_name = " ".join(str(last_name or "").split())
    first_name = " ".join(str(first_name or "").split())
    return " ".join(x for x in [first_name, last_name] if x).strip()


def split_legacy_client_name(name):
    """
    Répartition initiale prudente des anciennes fiches.
    L'ancien fichier est le plus souvent NOM Prénom : on garde donc cette convention.
    Les sociétés restent entièrement dans Nom.
    Rien n'est jamais écrasé après correction manuelle.
    """
    value = " ".join(str(name or "").split()).strip()
    if not value:
        return "", ""

    company_markers = (
        "sarl", "sci ", "sas ", "eurl", "suez", "repair lab", "pc-media",
        "pc media", "parvenir formations", "lydelec", "association",
        "cliente de passage", "client de passage", "entreprise "
    )
    low = value.casefold()
    if any(marker in low for marker in company_markers):
        return value, ""

    if "," in value:
        left, right = value.split(",", 1)
        return left.strip(), right.strip()

    parts = value.split()
    if len(parts) == 1:
        return value, ""

    # Convention majoritaire de l'historique WOPR : NOM puis prénom(s).
    return parts[0], " ".join(parts[1:])


def ensure_column(con, table_name, column_name, sql_type):
    cols = [row["name"] for row in con.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in cols:
        con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}")

def record_repair_status_change(con, repair_id, old_status, new_status, note=""):
    """Journalise uniquement les vrais changements d'état d'un dossier."""
    old_status = str(old_status or "").strip()
    new_status = str(new_status or "").strip() or "Reçu"
    if old_status == new_status:
        return False
    con.execute("""
        INSERT INTO repair_status_history(repair_id,status,changed_at,note)
        VALUES(?,?,?,?)
    """, (repair_id, new_status, now().isoformat(timespec="seconds"), str(note or "").strip()))
    return True

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        phone TEXT,
        email TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS app_meta (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ledger_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operation TEXT NOT NULL,
        party TEXT,
        entry_date TEXT NOT NULL,
        description TEXT,
        amount_ttc REAL NOT NULL DEFAULT 0,
        payment_type TEXT,
        invoice_no TEXT,
        remarks TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS antivirus_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT NOT NULL,
        setup_date TEXT,
        antivirus_name TEXT,
        expiration_date TEXT,
        invoice_no TEXT,
        info TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_no TEXT NOT NULL UNIQUE,
        quote_date TEXT NOT NULL,
        client_id INTEGER,
        client_name TEXT NOT NULL,
        client_company TEXT,
        client_address_street TEXT,
        client_postal_code TEXT,
        client_city TEXT,
        contact_name TEXT,
        status TEXT NOT NULL DEFAULT 'Brouillon',
        notes TEXT,
        edited_in_app INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    );

    CREATE TABLE IF NOT EXISTS quote_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        line_type TEXT NOT NULL DEFAULT 'service',
        quantity REAL NOT NULL DEFAULT 1,
        description TEXT NOT NULL,
        unit_price REAL NOT NULL DEFAULT 0,
        FOREIGN KEY(quote_id) REFERENCES quotes(id)
    );

    CREATE TABLE IF NOT EXISTS ca_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(year, month, category)
    );

    CREATE TABLE IF NOT EXISTS quote_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        label TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(quote_id, filename),
        FOREIGN KEY(quote_id) REFERENCES quotes(id)
    );

    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        ip TEXT
    );

    CREATE TABLE IF NOT EXISTS repairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dossier_no TEXT NOT NULL UNIQUE,
        client_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        received_date TEXT NOT NULL,
        device_type TEXT,
        brand_model TEXT,
        serial_no TEXT,
        system_password TEXT,
        accessories TEXT,
        device_state TEXT,
        problem TEXT,
        diagnosis TEXT,
        work_done TEXT,
        tests_validation TEXT,
        remarks TEXT,
        status TEXT NOT NULL DEFAULT 'Reçu',
        signature_token TEXT UNIQUE,
        signature_path TEXT,
        signature_at TEXT,
        finished_at TEXT,
        invoice_no TEXT,
        service_amount REAL DEFAULT 0,
        goods_amount REAL DEFAULT 0,
        payment_method TEXT,
        paid INTEGER DEFAULT 0,
        sent_via TEXT,
        service_description TEXT,
        goods_description TEXT,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    );
    """)
    # migration douce pour les anciennes bases
    ensure_column(con, "quotes", "client_company", "TEXT")
    ensure_column(con, "quotes", "edited_in_app", "INTEGER DEFAULT 0")
    ensure_column(con, "repairs", "service_description", "TEXT")
    ensure_column(con, "repairs", "goods_description", "TEXT")
    ensure_column(con, "repairs", "payment_mode", "TEXT")
    ensure_column(con, "repairs", "payment_detail", "TEXT")
    ensure_column(con, "repairs", "system_name", "TEXT")
    ensure_column(con, "repairs", "legacy_call_note", "TEXT")
    ensure_column(con, "repairs", "legacy_invoice_text", "TEXT")
    ensure_column(con, "repairs", "legacy_source_year", "INTEGER")
    ensure_column(con, "repairs", "legacy_source_row", "INTEGER")
    ensure_column(con, "repairs", "legacy_imported", "INTEGER DEFAULT 0")
    ensure_column(con, "repairs", "followup_year", "INTEGER")
    ensure_column(con, "repairs", "followup_month", "INTEGER")
    ensure_column(con, "repairs", "accounting_year", "INTEGER")
    ensure_column(con, "repairs", "accounting_month", "INTEGER")
    ensure_column(con, "repairs", "accounting_date", "TEXT")
    ensure_column(con, "repairs", "accounting_status", "TEXT DEFAULT 'normal'")
    ensure_column(con, "repairs", "accounting_service_amount", "REAL DEFAULT 0")
    ensure_column(con, "repairs", "accounting_goods_amount", "REAL DEFAULT 0")
    ensure_column(con, "repairs", "simple_invoice", "INTEGER DEFAULT 0")
    ensure_column(con, "repairs", "returned_at", "TEXT")

    # V2.3.165 — les anciennes versions stockaient le chemin ABSOLU des signatures.
    # Dès que le fichier est retrouvé dans private/signatures, on ne conserve plus que
    # son nom afin que la base survive à un déplacement complet du dossier WOPR.
    try:
        for _sig_row in con.execute("SELECT id, signature_path FROM repairs WHERE signature_path IS NOT NULL AND signature_path <> ''").fetchall():
            _stored = str(_sig_row["signature_path"] or "").strip()
            if not _stored:
                continue
            _name = Path(_stored).name
            if _name and (SIGNATURES / _name).exists() and _stored != _name:
                con.execute("UPDATE repairs SET signature_path=? WHERE id=?", (_name, _sig_row["id"]))
    except Exception:
        pass
    ensure_column(con, "clients", "first_name", "TEXT")
    ensure_column(con, "clients", "last_name", "TEXT")
    ensure_column(con, "clients", "company", "TEXT")
    ensure_column(con, "clients", "archived", "INTEGER DEFAULT 0")
    ensure_column(con, "clients", "archived_at", "TEXT")
    ensure_column(con, "clients", "address_street", "TEXT")
    ensure_column(con, "clients", "postal_code", "TEXT")
    ensure_column(con, "clients", "city", "TEXT")
    ensure_column(con, "clients", "google_resource_name", "TEXT")
    ensure_column(con, "clients", "google_sync_status", "TEXT")
    ensure_column(con, "clients", "google_sync_error", "TEXT")
    ensure_column(con, "clients", "google_synced_at", "TEXT")
    ensure_column(con, "clients", "google_sync_hash", "TEXT")
    ensure_column(con, "clients", "notes", "TEXT")
    ensure_column(con, "clients", "proton_uid", "TEXT")
    ensure_column(con, "clients", "proton_imported_at", "TEXT")
    ensure_column(con, "clients", "abby_id", "TEXT")
    ensure_column(con, "clients", "abby_type", "TEXT")
    ensure_column(con, "clients", "abby_sync_status", "TEXT")
    ensure_column(con, "clients", "abby_sync_error", "TEXT")
    ensure_column(con, "clients", "abby_synced_at", "TEXT")
    con.execute("CREATE INDEX IF NOT EXISTS idx_clients_proton_uid ON clients(proton_uid)")
    # V2.3.91 : pièce justificative liée aux achats / ventes.
    # Le fichier reste physiquement dans Fournisseurs/AAAA/MM - Mois,
    # seule sa référence relative est conservée en base.
    ensure_column(con, "ledger_entries", "document_path", "TEXT")
    ensure_column(con, "ledger_entries", "document_original_name", "TEXT")

    con.execute("CREATE INDEX IF NOT EXISTS idx_ledger_entry_date ON ledger_entries(entry_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ledger_operation ON ledger_entries(operation)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_antivirus_expiration ON antivirus_entries(expiration_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_quotes_date ON quotes(quote_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_quote_lines_quote ON quote_lines(quote_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_quote_documents_quote ON quote_documents(quote_id)")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_repairs_legacy_source ON repairs(legacy_source_year, legacy_source_row) WHERE legacy_source_year IS NOT NULL")
    con.execute("CREATE INDEX IF NOT EXISTS idx_repairs_followup_period ON repairs(followup_year, followup_month)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_repairs_accounting_period ON repairs(accounting_year, accounting_month)")

    con.execute("""
        CREATE TABLE IF NOT EXISTS repair_status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY(repair_id) REFERENCES repairs(id)
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_repair_status_history_repair ON repair_status_history(repair_id, changed_at)")

    # V2.3.83 : point de départ de l'historique pour les dossiers existants.
    # On ne fabrique pas de fausses anciennes dates : on note simplement l'état
    # trouvé au moment où l'historique est activé.
    history_seed_rows = con.execute("""
        SELECT r.id, r.status
        FROM repairs r
        WHERE NOT EXISTS (
            SELECT 1 FROM repair_status_history h WHERE h.repair_id=r.id
        )
    """).fetchall()
    history_seed_stamp = now().isoformat(timespec="seconds")
    for history_seed in history_seed_rows:
        con.execute("""
            INSERT INTO repair_status_history(repair_id,status,changed_at,note)
            VALUES(?,?,?,?)
        """, (history_seed["id"], history_seed["status"] or "Reçu", history_seed_stamp,
              "État initial lors de l’activation de l’historique"))

    con.execute("""
        CREATE TABLE IF NOT EXISTS invoice_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repair_id INTEGER NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            line_type TEXT NOT NULL DEFAULT 'service',
            quantity REAL NOT NULL DEFAULT 1,
            description TEXT NOT NULL,
            unit_price REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(repair_id) REFERENCES repairs(id)
        )
    """)
    # V2.3.223 — Nom / prénom séparés : migration UNIQUEMENT des anciennes
    # fiches personnelles encore vierges.
    #
    # Une entreprise pure peut légitimement avoir :
    #   first_name = ''
    #   last_name  = ''
    #   company    = 'Microrecup'
    #   name       = 'Microrecup'
    #
    # Les anciennes versions remettaient alors "Microrecup" dans last_name
    # à chaque redémarrage. On exclut donc explicitement les fiches ayant une
    # raison sociale : une correction manuelle reste enfin corrigée.
    rows_to_split = con.execute("""
        SELECT id,name FROM clients
        WHERE COALESCE(trim(last_name),'')='' AND COALESCE(trim(first_name),'')=''
          AND COALESCE(trim(company),'')=''
          AND COALESCE(trim(name),'')<>''
    """).fetchall()
    for old_client in rows_to_split:
        last_name, first_name = split_legacy_client_name(old_client["name"])
        con.execute("""
            UPDATE clients SET last_name=?, first_name=? WHERE id=?
        """, (last_name, first_name, old_client["id"]))

    # V2.3.29 : ne plus recopier `address` dans `address_street`.
    # Une rue volontairement vide doit rester vide après redémarrage.

    # Ancien champ unique "Système / Mot de passe" :
    # on déplace uniquement les valeurs qui ressemblent clairement à un système
    # et on laisse les autres intactes pour ne jamais perdre un vrai mot de passe.
    old_system_rows = con.execute("""
        SELECT id,system_password
        FROM repairs
        WHERE COALESCE(trim(system_name),'')=''
          AND COALESCE(trim(system_password),'')<>''
    """).fetchall()
    system_prefixes = (
        "windows", "macos", "mac os", "linux", "ubuntu", "debian",
        "fedora", "mint", "chromeos", "chrome os", "android", "ios"
    )
    for old_system_row in old_system_rows:
        old_value = str(old_system_row["system_password"] or "").strip()
        low_value = old_value.casefold()
        if any(low_value.startswith(prefix) for prefix in system_prefixes):
            con.execute("""
                UPDATE repairs
                SET system_name=?, system_password=''
                WHERE id=?
            """, (old_value, old_system_row["id"]))

    # V2.3.80 : chiffrement des mots de passe appareils déjà présents en base.
    # La migration est idempotente : les valeurs enc:v1: ne sont jamais rechiffrées.
    password_rows = con.execute("""
        SELECT id,system_password FROM repairs
        WHERE COALESCE(trim(system_password),'')<>''
    """).fetchall()
    migrated_passwords = 0
    for pw_row in password_rows:
        raw_pw = str(pw_row["system_password"] or "")
        if raw_pw and not raw_pw.startswith(SECRET_PREFIX):
            con.execute(
                "UPDATE repairs SET system_password=? WHERE id=?",
                (encrypt_repair_password(raw_pw), pw_row["id"])
            )
            migrated_passwords += 1
    if migrated_passwords:
        try:
            audit_event("MIGRATION_PASSWORDS", f"{migrated_passwords} mot(s) de passe appareil chiffré(s)")
        except Exception:
            pass

    # V2.3.15 : reconstruction des dates d'encaissement historiques.
    # On remplit la date sans modifier accounting_year/accounting_month ni les montants CA.
    accounting_date_rows = con.execute("""
        SELECT
            id,client_id,payment_method,invoice_no,received_date,paid,
            accounting_year,accounting_month,legacy_source_year
        FROM repairs
        WHERE COALESCE(trim(accounting_date),'')=''
          AND COALESCE(trim(invoice_no),'')<>''
    """).fetchall()

    for accounting_row in accounting_date_rows:
        parsed_date = resolve_accounting_date(
            accounting_row["payment_method"],
            accounting_row["invoice_no"],
            accounting_row["received_date"],
            accounting_row["accounting_year"],
            accounting_row["accounting_month"],
            bool(accounting_row["paid"])
        )
        if parsed_date:
            con.execute(
                "UPDATE repairs SET accounting_date=? WHERE id=?",
                (parsed_date, accounting_row["id"])
            )

    # Une facture ancienne peut avoir une ligne de facture en juillet et une ligne
    # de paiement en août. Propager uniquement la DATE à la ligne d'origine rend
    # le Suivi lisible sans doubler le CA (année/mois/montants restent inchangés).
    invoice_date_groups = con.execute("""
        SELECT
            client_id, invoice_no,
            MAX(CASE
                WHEN accounting_year IS NOT NULL AND accounting_month IS NOT NULL
                     AND COALESCE(trim(accounting_date),'')<>''
                THEN accounting_date
                ELSE NULL
            END) authoritative_date
        FROM repairs
        WHERE COALESCE(trim(invoice_no),'')<>''
        GROUP BY client_id,invoice_no
        HAVING authoritative_date IS NOT NULL
    """).fetchall()

    for date_group in invoice_date_groups:
        # Si une vraie ligne comptable existe (ex. paiement reporté au mois suivant),
        # sa date gagne sur la date estimée de la ligne de facture d'origine.
        con.execute("""
            UPDATE repairs
            SET accounting_date=?
            WHERE client_id=? AND invoice_no=?
        """, (
            date_group["authoritative_date"],
            date_group["client_id"],
            date_group["invoice_no"]
        ))

    # V2.3.19 : correction ciblée de la répartition CA d'août 2026.
    # Source : dernier jeu historique importé avant la migration WOPR.
    ca_aug_fix_key = "v2319_ca_august_2026_repartition_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (ca_aug_fix_key,)).fetchone():
        fixed_notes = []

        # Bellebna Mustapha - 310820261000
        # ODS : 69 € Presta + 40 € March. = 109 €.
        bellebna = con.execute("""
            SELECT id,service_amount,goods_amount,
                   accounting_service_amount,accounting_goods_amount,
                   accounting_year,accounting_month
            FROM repairs
            WHERE invoice_no='310820261000'
              AND received_date='2026-08-27'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if bellebna:
            svc = float(bellebna["service_amount"] or 0)
            goods = float(bellebna["goods_amount"] or 0)

            if abs(svc - 69.0) < 0.01 and abs(goods - 40.0) >= 0.01:
                con.execute(
                    "UPDATE repairs SET goods_amount=40.0 WHERE id=?",
                    (bellebna["id"],)
                )
                fixed_notes.append("Bellebna: marchandises=40")

            if int(bellebna["accounting_year"] or 0) == 2026 and int(bellebna["accounting_month"] or 0) == 8:
                asvc = float(bellebna["accounting_service_amount"] or 0)
                agoods = float(bellebna["accounting_goods_amount"] or 0)
                if abs(asvc - 69.0) < 0.01 and abs(agoods - 40.0) >= 0.01:
                    con.execute(
                        "UPDATE repairs SET accounting_goods_amount=40.0 WHERE id=?",
                        (bellebna["id"],)
                    )
                    fixed_notes.append("Bellebna CA: marchandises=40")

            # Si la facture contient exactement 69 € service + 20 € marchandise,
            # corriger uniquement cette ligne marchandise à 40 €.
            line_rows = con.execute("""
                SELECT id,line_type,quantity,unit_price
                FROM invoice_lines
                WHERE repair_id=?
                ORDER BY position,id
            """, (bellebna["id"],)).fetchall()

            line_total = sum(float(x["quantity"] or 0) * float(x["unit_price"] or 0) for x in line_rows)
            service_line_total = sum(
                float(x["quantity"] or 0) * float(x["unit_price"] or 0)
                for x in line_rows if x["line_type"] == "service"
            )
            goods_20 = [
                x for x in line_rows
                if x["line_type"] == "goods"
                and abs(float(x["quantity"] or 0) * float(x["unit_price"] or 0) - 20.0) < 0.01
                and abs(float(x["quantity"] or 0) - 1.0) < 0.01
            ]
            if (
                line_rows
                and abs(line_total - 89.0) < 0.01
                and abs(service_line_total - 69.0) < 0.01
                and len(goods_20) == 1
            ):
                con.execute(
                    "UPDATE invoice_lines SET unit_price=40.0 WHERE id=?",
                    (goods_20[0]["id"],)
                )
                fixed_notes.append("Bellebna facture: 20→40 marchandise")

        # Favard Michel - 310820261400
        # ODS : 69 € Presta + 50 € March. = 119 €.
        favard = con.execute("""
            SELECT id,service_amount,goods_amount,
                   accounting_service_amount,accounting_goods_amount,
                   accounting_year,accounting_month
            FROM repairs
            WHERE invoice_no='310820261400'
              AND received_date='2026-08-31'
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()

        if favard:
            svc = float(favard["service_amount"] or 0)
            goods = float(favard["goods_amount"] or 0)

            if abs((svc + goods) - 119.0) < 0.01 and (
                abs(svc - 69.0) >= 0.01 or abs(goods - 50.0) >= 0.01
            ):
                con.execute("""
                    UPDATE repairs
                    SET service_amount=69.0, goods_amount=50.0
                    WHERE id=?
                """, (favard["id"],))
                fixed_notes.append("Favard: 69 presta + 50 march.")

            if int(favard["accounting_year"] or 0) == 2026 and int(favard["accounting_month"] or 0) == 8:
                asvc = float(favard["accounting_service_amount"] or 0)
                agoods = float(favard["accounting_goods_amount"] or 0)
                if abs((asvc + agoods) - 119.0) < 0.01 and (
                    abs(asvc - 69.0) >= 0.01 or abs(agoods - 50.0) >= 0.01
                ):
                    con.execute("""
                        UPDATE repairs
                        SET accounting_service_amount=69.0,
                            accounting_goods_amount=50.0
                        WHERE id=?
                    """, (favard["id"],))
                    fixed_notes.append("Favard CA: 69 presta + 50 march.")

            # Si la facture possède déjà deux lignes 69 + 50 toutes deux en service,
            # reclasser uniquement celle à 50 € en marchandise.
            line_rows = con.execute("""
                SELECT id,line_type,quantity,unit_price
                FROM invoice_lines
                WHERE repair_id=?
                ORDER BY position,id
            """, (favard["id"],)).fetchall()

            line_total = sum(float(x["quantity"] or 0) * float(x["unit_price"] or 0) for x in line_rows)
            service_50 = [
                x for x in line_rows
                if x["line_type"] == "service"
                and abs(float(x["quantity"] or 0) * float(x["unit_price"] or 0) - 50.0) < 0.01
            ]
            service_69 = [
                x for x in line_rows
                if x["line_type"] == "service"
                and abs(float(x["quantity"] or 0) * float(x["unit_price"] or 0) - 69.0) < 0.01
            ]
            if (
                line_rows
                and abs(line_total - 119.0) < 0.01
                and len(service_50) == 1
                and len(service_69) >= 1
            ):
                con.execute(
                    "UPDATE invoice_lines SET line_type='goods' WHERE id=?",
                    (service_50[0]["id"],)
                )
                fixed_notes.append("Favard facture: ligne 50 reclassée march.")

        # Si 2049 / 1239 avaient été enregistrés comme overrides manuels,
        # supprimer uniquement ces deux valeurs précises pour repasser en auto.
        override_service = con.execute("""
            SELECT amount FROM ca_overrides
            WHERE year=2026 AND month=8 AND category='service'
        """).fetchone()
        if override_service and abs(float(override_service["amount"] or 0) - 2049.0) < 0.01:
            con.execute("""
                DELETE FROM ca_overrides
                WHERE year=2026 AND month=8 AND category='service'
            """)
            fixed_notes.append("override presta août 2049 supprimé")

        override_goods = con.execute("""
            SELECT amount FROM ca_overrides
            WHERE year=2026 AND month=8 AND category='goods'
        """).fetchone()
        if override_goods and abs(float(override_goods["amount"] or 0) - 1239.0) < 0.01:
            con.execute("""
                DELETE FROM ca_overrides
                WHERE year=2026 AND month=8 AND category='goods'
            """)
            fixed_notes.append("override march. août 1239 supprimé")

        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            ca_aug_fix_key,
            "; ".join(fixed_notes) if fixed_notes else "aucune correction nécessaire",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.79 : tous les suivis 2025 encore marqués « Terminé » sont
    # considérés comme déjà restitués. Migration volontairement limitée à 2025
    # et exécutée une seule fois pour ne jamais toucher aux statuts 2026.
    returned_2025_key = "v2379_2025_termine_to_restitue_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (returned_2025_key,)).fetchone():
        cur = con.execute("""
            UPDATE repairs
            SET status='Restitué'
            WHERE status='Terminé'
              AND (
                    followup_year=2025
                 OR legacy_source_year=2025
                 OR received_date LIKE '2025-%'
              )
        """)
        migrated_2025 = int(cur.rowcount or 0)
        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            returned_2025_key,
            f"{migrated_2025} suivi(s) 2025 passé(s) de Terminé à Restitué",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.20 : normalisation légère des anciennes adresses client.
    # Si address_street contient uniquement "24210 Ville" et que CP/Ville sont vides,
    # on place ces valeurs dans les bons champs. Cela permet ensuite de les effacer
    # réellement depuis Clients.
    addr_fix_key = "v2320_split_legacy_postal_city_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (addr_fix_key,)).fetchone():
        addr_rows = con.execute("""
            SELECT id,address_street,postal_code,city
            FROM clients
            WHERE COALESCE(trim(address_street),'')<>''
        """).fetchall()

        addr_fixed = 0
        for ar in addr_rows:
            street = str(ar["address_street"] or "").strip()
            postal = str(ar["postal_code"] or "").strip()
            city = str(ar["city"] or "").strip()

            m = re.fullmatch(r"(\d{5})\s+(.+)", street)
            if m and not postal and not city:
                new_postal = m.group(1).strip()
                new_city = m.group(2).strip()
                new_address = f"{new_postal} {new_city}".strip()
                con.execute("""
                    UPDATE clients
                    SET address_street='',
                        postal_code=?,
                        city=?,
                        address=?
                    WHERE id=?
                """, (new_postal, new_city, new_address, ar["id"]))
                addr_fixed += 1

        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            addr_fix_key,
            f"{addr_fixed} adresse(s) normalisée(s)",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.31 : les dossiers WOPR n'utilisent plus les secondes.
    dossier_key = "v2331_dossier_numbers_without_seconds_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (dossier_key,)).fetchone():
        changed = 0
        rows = con.execute("SELECT id,dossier_no FROM repairs ORDER BY id").fetchall()
        occupied = {str(x["dossier_no"] or "") for x in rows}

        for rr in rows:
            old_no = str(rr["dossier_no"] or "").strip()
            if len(old_no) != 14 or not old_no.isdigit():
                continue

            base_no = old_no[:12]
            new_no = base_no
            suffix = 2
            while new_no in occupied and new_no != old_no:
                new_no = f"{base_no}-{suffix}"
                suffix += 1

            if new_no != old_no:
                con.execute(
                    "UPDATE repairs SET dossier_no=? WHERE id=?",
                    (new_no, rr["id"])
                )
                occupied.discard(old_no)
                occupied.add(new_no)
                changed += 1

        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            dossier_key,
            f"{changed} numéro(s) de dossier raccourci(s)",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.29 : nettoyage adresses + alias "Client de passage (X)".
    fix_key = "v2329_addresses_and_passage_aliases_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (fix_key,)).fetchone():
        cleaned_addresses = 0
        merged_aliases = 0

        # A. Si la rue est exactement "CP Ville", elle provient de l'ancien fallback.
        for ar in con.execute("""
            SELECT id,address_street,postal_code,city,address
            FROM clients
        """).fetchall():
            street = " ".join(str(ar["address_street"] or "").split()).strip()
            postal = " ".join(str(ar["postal_code"] or "").split()).strip()
            city = " ".join(str(ar["city"] or "").split()).strip()
            postal_city = " ".join(x for x in [postal, city] if x).strip()

            if street and postal_city and street.casefold() == postal_city.casefold():
                con.execute("""
                    UPDATE clients
                    SET address_street='',
                        address=?,
                        updated_at=?
                    WHERE id=?
                """, (
                    postal_city,
                    now().isoformat(timespec="seconds"),
                    ar["id"]
                ))
                cleaned_addresses += 1
                continue

            raw_address = str(ar["address"] or "").replace("\r", "")
            lines = [" ".join(x.split()).strip() for x in raw_address.split("\n") if x.strip()]
            if len(lines) >= 2 and len({x.casefold() for x in lines}) == 1:
                con.execute("""
                    UPDATE clients
                    SET address=?, updated_at=?
                    WHERE id=?
                """, (
                    lines[0],
                    now().isoformat(timespec="seconds"),
                    ar["id"]
                ))
                cleaned_addresses += 1

        # B. Fusionner "Client de passage (X)" vers la vraie fiche X.
        client_rows = [dict(x) for x in con.execute(
            "SELECT * FROM clients ORDER BY id"
        ).fetchall()]

        def norm_alias(value):
            text = unicodedata.normalize("NFKD", str(value or ""))
            text = "".join(ch for ch in text if not unicodedata.combining(ch))
            text = text.casefold()
            text = re.sub(r"[^a-z0-9]+", " ", text)
            return re.sub(r"\s+", " ", text).strip()

        for alias in client_rows:
            alias_text = str(alias.get("last_name") or alias.get("name") or "").strip()
            m = re.fullmatch(
                r"\s*client(?:e)?\s+de\s+passage\s*\(([^)]+)\)\s*",
                alias_text,
                flags=re.I
            )
            if not m:
                continue

            wanted = norm_alias(m.group(1))
            candidates = []
            for candidate in client_rows:
                if candidate["id"] == alias["id"]:
                    continue

                candidate_values = [
                    candidate.get("last_name"),
                    candidate.get("name"),
                    " ".join(x for x in [
                        str(candidate.get("first_name") or "").strip(),
                        str(candidate.get("last_name") or "").strip()
                    ] if x),
                ]
                if any(
                    norm_alias(v) == wanted
                    for v in candidate_values
                    if str(v or "").strip()
                ):
                    candidates.append(candidate)

            if len(candidates) != 1:
                continue

            master = candidates[0]
            alias_email = str(alias.get("email") or "").strip().casefold()
            master_email = str(master.get("email") or "").strip().casefold()
            alias_phone = re.sub(r"\D+", "", str(alias.get("phone") or ""))
            master_phone = re.sub(r"\D+", "", str(master.get("phone") or ""))

            if alias_email and master_email and alias_email != master_email:
                continue
            if alias_phone and master_phone and alias_phone != master_phone:
                continue

            master_id = master["id"]
            alias_id = alias["id"]

            fields = (
                "first_name", "last_name", "company", "phone", "email",
                "address_street", "postal_code", "city", "notes"
            )
            updates = {}
            for field in fields:
                if (
                    not str(master.get(field) or "").strip()
                    and str(alias.get(field) or "").strip()
                ):
                    updates[field] = alias[field]
                    master[field] = alias[field]

            if updates:
                first = str(master.get("first_name") or "").strip()
                last = str(master.get("last_name") or "").strip()
                name_after = compose_client_name(last, first) or str(master.get("name") or "").strip()

                street_after = str(master.get("address_street") or "").strip()
                postal_after = str(master.get("postal_code") or "").strip()
                city_after = str(master.get("city") or "").strip()
                address_after = "\n".join(
                    x for x in [
                        street_after,
                        " ".join(x for x in [postal_after, city_after] if x).strip()
                    ] if x
                )

                updates["name"] = name_after
                updates["address"] = address_after
                updates["google_sync_status"] = "À synchroniser"
                updates["google_sync_error"] = ""
                updates["updated_at"] = now().isoformat(timespec="seconds")

                sets = ", ".join(f"{k}=?" for k in updates)
                con.execute(
                    f"UPDATE clients SET {sets} WHERE id=?",
                    list(updates.values()) + [master_id]
                )

            con.execute(
                "UPDATE repairs SET client_id=? WHERE client_id=?",
                (master_id, alias_id)
            )
            con.execute(
                "UPDATE quotes SET client_id=? WHERE client_id=?",
                (master_id, alias_id)
            )
            con.execute("DELETE FROM clients WHERE id=?", (alias_id,))
            merged_aliases += 1

        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            fix_key,
            f"{cleaned_addresses} adresse(s) nettoyée(s); {merged_aliases} alias fusionné(s)",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.9 : fusion de l'ancien champ "Travaux effectués"
    # dans "Intervention / Tests / Validation".
    merge_key = "merge_work_done_into_tests_validation_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (merge_key,)).fetchone():
        merge_rows = con.execute("""
            SELECT id,work_done,tests_validation
            FROM repairs
            WHERE COALESCE(trim(work_done),'')<>''
        """).fetchall()

        for merge_row in merge_rows:
            work = str(merge_row["work_done"] or "").strip()
            validation = str(merge_row["tests_validation"] or "").strip()

            if work and validation:
                # Intervention d'abord, puis tests/validation existants.
                if work not in validation:
                    merged = work + "\n" + validation
                else:
                    merged = validation
            elif work:
                merged = work
            else:
                merged = validation

            con.execute("""
                UPDATE repairs
                SET tests_validation=?, work_done=''
                WHERE id=?
            """, (merged, merge_row["id"]))

        con.execute("""
            INSERT OR REPLACE INTO app_meta(key,value,updated_at)
            VALUES(?,?,?)
        """, (
            merge_key,
            f"{len(merge_rows)} dossier(s) fusionné(s)",
            now().isoformat(timespec="seconds")
        ))

    # V2.3.10 : mode de paiement structuré.
    # Le texte historique payment_method reste intact.
    payment_mode_rows = con.execute("""
        SELECT id,payment_method
        FROM repairs
        WHERE COALESCE(trim(payment_mode),'')=''
          AND COALESCE(trim(payment_method),'')<>''
    """).fetchall()

    for payment_mode_row in payment_mode_rows:
        detected_mode = infer_payment_mode(payment_mode_row["payment_method"])
        if detected_mode:
            con.execute(
                "UPDATE repairs SET payment_mode=? WHERE id=?",
                (detected_mode, payment_mode_row["id"])
            )

    # Les dossiers déjà créés dans WOPR doivent aussi apparaître dans le Suivi mensuel.
    con.execute("""
        UPDATE repairs
        SET followup_year = CAST(substr(received_date,1,4) AS INTEGER),
            followup_month = CAST(substr(received_date,6,2) AS INTEGER)
        WHERE followup_year IS NULL
          AND received_date GLOB '????-??-??'
    """)

    # Si un ancien dossier WOPR est déjà payé, il alimente automatiquement le CA.
    con.execute("""
        UPDATE repairs
        SET accounting_year = CAST(substr(COALESCE(finished_at,received_date),1,4) AS INTEGER),
            accounting_month = CAST(substr(COALESCE(finished_at,received_date),6,2) AS INTEGER),
            accounting_service_amount = COALESCE(service_amount,0),
            accounting_goods_amount = COALESCE(goods_amount,0),
            accounting_status = CASE
                WHEN substr(COALESCE(finished_at,received_date),1,7) <> substr(received_date,1,7)
                    THEN 'yellow'
                ELSE 'normal'
            END
        WHERE COALESCE(legacy_imported,0)=0
          AND COALESCE(paid,0)=1
          AND (COALESCE(service_amount,0)<>0 OR COALESCE(goods_amount,0)<>0)
          AND accounting_year IS NULL
    """)

    # Facture créée mais non réglée : rouge et exclue du CA.
    con.execute("""
        UPDATE repairs
        SET accounting_status='red',
            accounting_year=NULL,
            accounting_month=NULL,
            accounting_service_amount=0,
            accounting_goods_amount=0
        WHERE COALESCE(legacy_imported,0)=0
          AND COALESCE(paid,0)=0
          AND COALESCE(invoice_no,'')<>''
          AND COALESCE(accounting_status,'normal')='normal'
    """)

    # Import historique Achats/Ventes 2025 + 2026 (une seule fois, anti-doublons).
    seed_legacy_ledger_entries(con)
    con.commit()
    con.close()

PAYMENT_MODES = ("ESP", "CB", "VIR", "PAY", "BTC", "CHQ", "MIXTE")


def normalize_payment_mode(value):
    raw = str(value or "").strip().upper()
    aliases = {
        "ESP": "ESP",
        "ESPÈCES": "ESP",
        "ESPECES": "ESP",
        "CASH": "ESP",
        "CB": "CB",
        "CARTE": "CB",
        "CARTE BANCAIRE": "CB",
        "VIR": "VIR",
        "VIREMENT": "VIR",
        "PAY": "PAY",
        "PAYPAL": "PAY",
        "BTC": "BTC",
        "BITCOIN": "BTC",
        "CHQ": "CHQ",
        "CHÈQUE": "CHQ",
        "CHEQUE": "CHQ",
        "MIXTE": "MIXTE",
        "MIXED": "MIXTE",
    }
    return aliases.get(raw, raw if raw in PAYMENT_MODES else "")


PAYMENT_MODE_LABELS = {
    "ESP": "Espèces", "CB": "CB", "VIR": "Virement",
    "PAY": "PayPal", "BTC": "Bitcoin", "CHQ": "Chèque",
}


def payment_split_from_form(total_expected=None):
    """Lit un paiement mixte depuis le formulaire et valide sa ventilation."""
    parts = []
    for mode in ("ESP", "CB", "VIR", "PAY", "BTC", "CHQ"):
        raw = request.form.get(f"payment_{mode}", "").strip()
        if not raw:
            continue
        try:
            amount = parse_money_input(raw)
        except Exception:
            return None, f"Montant {PAYMENT_MODE_LABELS[mode]} invalide."
        if amount < 0:
            return None, "Un montant de règlement ne peut pas être négatif."
        if amount > 0:
            parts.append((mode, round(float(amount), 2)))

    if len(parts) < 2:
        return None, "Un paiement mixte doit contenir au moins deux modes de règlement."

    total_split = round(sum(amount for _, amount in parts), 2)
    if total_expected is not None and abs(total_split - round(float(total_expected), 2)) > 0.009:
        return None, (
            f"La ventilation du paiement fait {total_split:.2f} € alors que la facture fait "
            f"{float(total_expected):.2f} €."
        )
    return parts, None


def payment_split_text(parts):
    return " + ".join(
        f"{amount:.2f} € {mode}".replace(".", ",")
        for mode, amount in (parts or [])
    )


def payment_split_json(parts):
    return json.dumps({mode: amount for mode, amount in (parts or [])}, ensure_ascii=False)


def payment_split_values(detail, method_text=""):
    """Retourne une ventilation exploitable par les formulaires, sans modifier la DB."""
    values = {mode: "" for mode in ("ESP", "CB", "VIR", "PAY", "BTC", "CHQ")}
    raw = str(detail or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                for mode in values:
                    if mode in data and data[mode] not in (None, ""):
                        amount = float(data[mode])
                        if amount > 0:
                            values[mode] = f"{amount:.2f}"
                return values
        except Exception:
            pass

    # Compatibilité : anciennes chaînes lisibles du type "50,00 € ESP + 79,00 € CB".
    legacy = str(method_text or "")
    for mode in values:
        m = re.search(rf"([0-9]+(?:[.,][0-9]{{1,2}})?)\s*€?\s*{mode}\b", legacy, re.I)
        if m:
            try:
                amount = float(m.group(1).replace(",", "."))
                if amount > 0:
                    values[mode] = f"{amount:.2f}"
            except Exception:
                pass
    return values


def payment_data_from_form(total_expected=None, fallback_mode="", fallback_method="", fallback_detail=""):
    """Retourne (mode, texte lisible, détail JSON, erreur)."""
    mode = normalize_payment_mode(request.form.get("payment_mode", ""))
    if mode == "MIXTE":
        parts, error = payment_split_from_form(total_expected)
        if error:
            return "", "", "", error
        return "MIXTE", payment_split_text(parts), payment_split_json(parts), None
    if mode:
        return mode, mode, "", None
    return (
        normalize_payment_mode(fallback_mode),
        str(fallback_method or ""),
        str(fallback_detail or ""),
        None,
    )


def infer_payment_mode(text):
    """
    Détecte un mode unique dans les anciens textes ODS.
    Si plusieurs modes sont présents (paiement mixte), retourne '' pour ne pas inventer.
    """
    value = str(text or "").upper()
    found = []

    patterns = (
        ("ESP", r"\bESP(?:ÈCES|ECES)?\b"),
        ("CB", r"\bCB\b|CARTE BANCAIRE"),
        ("VIR", r"\bVIR\b|VIREMENT"),
        ("PAY", r"\bPAY\b|PAYPAL"),
        ("BTC", r"\bBTC\b|BITCOIN"),
        ("CHQ", r"\bCHQ\b|CHÈQUE|CHEQUE"),
    )

    for mode, pattern in patterns:
        if re.search(pattern, value, flags=re.I):
            found.append(mode)

    unique = list(dict.fromkeys(found))
    return unique[0] if len(unique) == 1 else ""


def extract_payment_date(text, fallback_year=None):
    """
    Extrait une date d'encaissement depuis les anciens textes :
    '69€ CB le 12/08', 'ESP 22/04/25', 'VIR le 20/04/2026', etc.
    Retourne YYYY-MM-DD ou ''.
    """
    value = str(text or "")
    matches = re.findall(r"(?<!\d)(\d{1,2})[\/\-.](\d{1,2})(?:[\/\-.](\d{2,4}))?(?!\d)", value)
    if not matches:
        return ""

    # La dernière date du texte est généralement celle du règlement.
    day, month, year = matches[-1]
    try:
        day = int(day)
        month = int(month)
        if year:
            year = int(year)
            if year < 100:
                year += 2000
        elif fallback_year:
            year = int(fallback_year)
        else:
            year = now().year

        d = datetime(year, month, day)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ""


def invoice_no_date(invoice_no):
    """Extrait la date JJMMYYYY depuis un numéro de facture historique."""
    digits = re.sub(r"\D", "", str(invoice_no or ""))
    if len(digits) < 8:
        return ""
    try:
        return datetime.strptime(digits[:8], "%d%m%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


def resolve_accounting_date(payment_text, invoice_no, received_date,
                            accounting_year=None, accounting_month=None,
                            paid=False):
    """
    Reconstruit la date d'encaissement historique.
    Le mois comptable existant est prioritaire et n'est jamais modifié ici.
    """
    year = int(accounting_year) if accounting_year else None
    month = int(accounting_month) if accounting_month else None

    # 1. Date explicite dans le texte de paiement.
    explicit = extract_payment_date(
        payment_text,
        fallback_year=year or (str(received_date or "")[:4] or now().year)
    )
    if explicit:
        try:
            d = datetime.strptime(explicit, "%Y-%m-%d")
            if not year or not month or (d.year, d.month) == (year, month):
                return explicit
        except Exception:
            pass

    # 2. Si un mois comptable existe, la date du n° de facture est acceptable
    #    uniquement si elle tombe dans ce même mois.
    inv_date = invoice_no_date(invoice_no)
    if inv_date:
        try:
            d = datetime.strptime(inv_date, "%Y-%m-%d")
            if year and month and (d.year, d.month) == (year, month):
                return inv_date
        except Exception:
            pass

    # 3. Date de la ligne de Suivi, si elle est dans le mois comptable.
    try:
        rd = datetime.strptime(str(received_date or "")[:10], "%Y-%m-%d")
        if year and month and (rd.year, rd.month) == (year, month):
            return rd.strftime("%Y-%m-%d")
    except Exception:
        pass

    # 4. Ancienne facture marquée payée mais sans période comptable structurée :
    #    on utilise la date portée par le numéro de facture comme meilleure trace
    #    historique disponible. Cela ne change PAS CA/Déclarations.
    if paid and inv_date:
        return inv_date

    return ""


def payment_modes_from_text(text):
    """Modes reconnus dans les vieux textes, y compris paiement mixte."""
    value = str(text or "").upper()
    found = []
    patterns = (
        ("ESP", r"\bESP(?:ÈCES|ECES)?\b"),
        ("CB", r"\bCB\b|CARTE BANCAIRE"),
        ("VIR", r"\bVIR\b|VIREMENT"),
        ("PAY", r"\bPAY\b|PAYPAL"),
        ("BTC", r"\bBTC\b|BITCOIN"),
        ("CHQ", r"\bCHQ\b|CHÈQUE|CHEQUE"),
    )
    for mode, pattern in patterns:
        if re.search(pattern, value, flags=re.I) and mode not in found:
            found.append(mode)
    return found


def payment_amount_from_text(text):
    """
    Extrait au mieux un total d'un ancien champ paiement.
    Exemples :
      122,00 € -> 122
      110€ ESP 12€ CB -> 122
      88.80€ (29€+59.80€) -> 88.80 (évite le double comptage)
      69+40 -> 109
    """
    value = str(text or "").replace("\u202f", " ").replace("\xa0", " ")
    # Les dates ne doivent jamais devenir des montants.
    clean = re.sub(r"(?<!\d)(?:\d{1,2}[\/-]\d{1,2}(?:[\/-]\d{2,4})?|\d{1,2}\.\d{1,2}\.\d{2,4})(?!\d)", " ", value)

    money_tokens = re.findall(r"(\d[\d ]*(?:[,.]\d{1,2})?)\s*€", clean)
    amounts = []
    for token in money_tokens:
        try:
            amounts.append(float(token.replace(" ", "").replace(",", ".")))
        except Exception:
            pass

    if amounts:
        if len(amounts) == 1:
            return amounts[0]
        first = amounts[0]
        rest = sum(amounts[1:])
        # Premier nombre = total, détails monétaires entre parenthèses ensuite.
        if abs(first - rest) < 0.011:
            return first
        # Sinon il s'agit typiquement d'un paiement mixte 110€ + 12€.
        return sum(amounts)

    # Anciens textes sans symbole € : 69+40, 89 + 3, etc.
    plus_match = re.search(r"(\d+(?:[,.]\d{1,2})?(?:\s*\+\s*\d+(?:[,.]\d{1,2})?)+)", clean)
    if plus_match:
        vals = re.findall(r"\d+(?:[,.]\d{1,2})?", plus_match.group(1))
        try:
            return sum(float(v.replace(",", ".")) for v in vals)
        except Exception:
            pass

    return 0.0


def normalize_history_name(value):
    return normalize_global_search(str(value or "").replace("-", " ").replace("/", " "))




def normalize_client_filename_name(value):
    """Nom client canonique pour retrouver les PDF historiques sans civilité."""
    key = normalize_history_name(value)
    if not key:
        return ""
    titles = {"m", "mr", "mme", "mlle", "monsieur", "madame", "mademoiselle"}
    parts = [part for part in key.split() if part not in titles]
    return " ".join(parts).strip()


def canonical_client_invoice_no(value):
    """Normalise les anciens numéros de facture client.

    Les imports ODS ont parfois perdu le zéro initial d'un numéro JJMMYYYYHHMM :
    040820261400 est ainsi devenu 40820261400 dans ledger_entries.
    """
    raw = str(value or "").strip()
    if raw.isdigit() and len(raw) == 11:
        return raw.zfill(12)
    return raw


def find_client_invoice_pdf(invoice_no, client_name):
    """
    Retrouve le PDF client réellement classé dans Factures.

    V2.3.237 :
    - corrige les numéros historiques ayant perdu leur zéro initial ;
    - exige que le numéro soit en FIN de nom de fichier, donc
      40820261400 ne peut plus matcher Pinson_140820261400.pdf ;
    - si plusieurs clients partagent le même numéro, privilégie le nom/surnom
      présent dans le fichier (ex. Lacombe_240820261100.pdf).
    """
    if not FACTURES_ROOT.exists():
        return None

    needle = canonical_client_invoice_no(invoice_no)
    if not needle:
        return None

    invoice_key = _match_key(needle)
    if not invoice_key:
        return None

    candidates = []
    for p in FACTURES_ROOT.rglob("*.pdf"):
        if "fournisseurs" in {part.casefold() for part in p.parts}:
            continue
        stem_key = _match_key(p.stem)
        # Le numéro de facture doit être le suffixe du nom, pas une simple
        # sous-chaîne. Évite 40820261400 -> 140820261400.
        if stem_key.endswith(invoice_key):
            candidates.append(p)

    if not candidates:
        return None

    client_key = normalize_client_filename_name(client_name)
    client_tokens = [
        t for t in normalize_history_name(client_name).split()
        if len(t) >= 2
    ]

    def score(path):
        stem_key = normalize_history_name(path.stem)
        stem_compact = _match_key(path.stem)
        points = 0

        if stem_compact.endswith(invoice_key):
            points += 100

        # Nom complet quand il est présent.
        if client_key and client_key in stem_key:
            points += 120

        # Les anciens PDF sont souvent nommés uniquement avec le nom de famille.
        # On donne donc un fort bonus à chaque token du client présent avant le n°.
        name_part = stem_key
        needle_norm = normalize_history_name(needle)
        if needle_norm and name_part.endswith(needle_norm):
            name_part = name_part[:-len(needle_norm)].strip()

        matched_tokens = sum(1 for t in client_tokens if t in name_part.split())
        points += matched_tokens * 80

        # Bonus supplémentaire si le premier/dernier token du nom client apparaît.
        if client_tokens:
            if client_tokens[0] in name_part.split():
                points += 30
            if client_tokens[-1] in name_part.split():
                points += 40

        first = stem_key.split()[0] if stem_key.split() else ""
        if first in {"m", "mr", "mme", "mlle", "monsieur", "madame", "mademoiselle"}:
            points -= 35

        return (points, -len(path.name), str(path).casefold())

    return max(candidates, key=score)


def seed_legacy_followups(con):
    """
    Importe les deux onglets Suivi-Rép 2025 et 2026 du WOPR.ods.

    - 296 lignes historiques.
    - Conserve les mois d'affichage du classeur.
    - Conserve la nomenclature jaune / rouge.
    - Conserve séparément les montants affichés et les montants réellement
      comptabilisés par les formules LibreOffice.
    """
    migration_key = "legacy_followups_2025_2026_from_ods_v1"
    if con.execute("SELECT 1 FROM app_meta WHERE key=?", (migration_key,)).fetchone():
        return 0

    stamp = datetime.now().isoformat(timespec="seconds")
    inserted = 0

    # Index clients tolérant accents, tirets et ponctuation.
    clients = con.execute("SELECT id,name FROM clients").fetchall()
    client_index = {}
    for c in clients:
        key = normalize_history_name(c["name"])
        if key and key not in client_index:
            client_index[key] = c["id"]

    for item in LEGACY_FOLLOWUPS:
        exists = con.execute("""
            SELECT id FROM repairs
            WHERE legacy_source_year=? AND legacy_source_row=?
            LIMIT 1
        """, (item["legacy_year"], item["legacy_row_no"])).fetchone()
        if exists:
            continue

        client_name = item.get("client_name", "").strip() or "Client historique"
        key = normalize_history_name(client_name)
        client_id = client_index.get(key)

        if not client_id:
            created = item.get("received_date", "") + "T12:00:00"
            cur = con.execute("""
                INSERT INTO clients(
                    name,address,address_street,postal_code,city,phone,email,
                    created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                client_name, "", "", "", "", "", "",
                created, created
            ))
            client_id = cur.lastrowid
            if key:
                client_index[key] = client_id

        dossier_no = f"HIST-{item['legacy_year']}-{int(item['legacy_row_no']):04d}"
        # Rare collision possible si une ancienne tentative existe : on la réutilise.
        existing_dossier = con.execute(
            "SELECT id FROM repairs WHERE dossier_no=?",
            (dossier_no,)
        ).fetchone()
        if existing_dossier:
            continue

        created = item.get("received_date", "") + "T12:00:00"
        signature_token = "hist-" + secrets.token_urlsafe(15)

        con.execute("""
            INSERT INTO repairs(
                dossier_no, client_id, created_at, received_date,
                device_type, brand_model, serial_no, system_password,
                accessories, device_state, problem, diagnosis, work_done,
                tests_validation, remarks, status, signature_token,
                invoice_no, service_amount, goods_amount,
                payment_method, payment_mode, paid, sent_via,
                service_description, goods_description,
                legacy_call_note, legacy_invoice_text,
                legacy_source_year, legacy_source_row, legacy_imported,
                followup_year, followup_month,
                accounting_year, accounting_month, accounting_date, accounting_status,
                accounting_service_amount, accounting_goods_amount
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dossier_no,
            client_id,
            created,
            item.get("received_date",""),
            "", "", "", "", "", "",
            item.get("problem",""),
            "", "", "",
            item.get("remarks",""),
            "Terminé",
            signature_token,
            item.get("invoice_no",""),
            float(item.get("service_amount",0) or 0),
            float(item.get("goods_amount",0) or 0),
            item.get("payment_method",""),
            infer_payment_mode(item.get("payment_method","")),
            int(item.get("paid",0) or 0),
            item.get("sent_via",""),
            item.get("problem",""),
            "",
            item.get("call_note",""),
            item.get("legacy_invoice_text",""),
            int(item.get("legacy_year")),
            int(item.get("legacy_row_no")),
            1,
            int(item.get("followup_year")),
            int(item.get("followup_month")),
            item.get("accounting_year"),
            item.get("accounting_month"),
            resolve_accounting_date(
                item.get("payment_method",""),
                item.get("invoice_no",""),
                item.get("received_date",""),
                item.get("accounting_year"),
                item.get("accounting_month"),
                bool(item.get("paid",0))
            ),
            item.get("accounting_status","normal"),
            float(item.get("accounting_service_amount",0) or 0),
            float(item.get("accounting_goods_amount",0) or 0),
        ))
        inserted += 1

    con.execute("""
        INSERT OR REPLACE INTO app_meta(key,value,updated_at)
        VALUES(?,?,?)
    """, (
        migration_key,
        f"{inserted}/{len(LEGACY_FOLLOWUPS)} suivis ajoutés",
        stamp
    ))
    return inserted


def seed_legacy_ledger_entries(con):
    """
    Importe une seule fois les lignes historiques Achats/Ventes 2025 + 2026
    extraites du classeur WOPR.ods.

    - N'écrase aucune ligne existante.
    - Évite les doublons exacts si quelques lignes ont déjà été saisies à la main.
    - Une fois la migration faite, une suppression volontaire ne sera pas recréée.
    """
    migration_key = "legacy_ledger_2025_2026_from_ods_v2_seedfix"

    done = con.execute(
        "SELECT value FROM app_meta WHERE key=?",
        (migration_key,)
    ).fetchone()
    if done:
        return 0

    inserted = 0
    imported_at = datetime.now().isoformat(timespec="seconds")

    for item in LEGACY_LEDGER_ENTRIES:
        existing = con.execute("""
            SELECT id
            FROM ledger_entries
            WHERE operation=?
              AND COALESCE(party,'')=?
              AND entry_date=?
              AND COALESCE(description,'')=?
              AND ABS(COALESCE(amount_ttc,0) - ?) < 0.001
              AND COALESCE(invoice_no,'')=?
            LIMIT 1
        """, (
            item["operation"],
            item.get("party", ""),
            item["entry_date"],
            item.get("description", ""),
            float(item.get("amount_ttc", 0)),
            item.get("invoice_no", ""),
        )).fetchone()

        if existing:
            continue

        con.execute("""
            INSERT INTO ledger_entries(
                operation, party, entry_date, description, amount_ttc,
                payment_type, invoice_no, remarks, created_at, updated_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            item["operation"],
            item.get("party", ""),
            item["entry_date"],
            item.get("description", ""),
            float(item.get("amount_ttc", 0)),
            item.get("payment_type", ""),
            item.get("invoice_no", ""),
            item.get("remarks", ""),
            imported_at,
            imported_at,
        ))
        inserted += 1

    con.execute("""
        INSERT OR REPLACE INTO app_meta(key, value, updated_at)
        VALUES(?,?,?)
    """, (
        migration_key,
        f"{inserted}/{len(LEGACY_LEDGER_ENTRIES)} lignes ajoutées",
        imported_at,
    ))
    return inserted


def seed_legacy_management_data(con):
    """Importe une seule fois Antivirus + devis historique du classeur ODS."""
    stamp = datetime.now().isoformat(timespec="seconds")

    av_key = "legacy_antivirus_from_ods_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (av_key,)).fetchone():
        inserted = 0
        for item in LEGACY_ANTIVIRUS_ENTRIES:
            duplicate = con.execute("""
                SELECT id FROM antivirus_entries
                WHERE client_name=?
                  AND COALESCE(setup_date,'')=?
                  AND COALESCE(antivirus_name,'')=?
                  AND COALESCE(expiration_date,'')=?
                  AND COALESCE(invoice_no,'')=?
                LIMIT 1
            """, (
                item.get("client_name",""),
                item.get("setup_date",""),
                item.get("antivirus_name",""),
                item.get("expiration_date",""),
                item.get("invoice_no",""),
            )).fetchone()
            if duplicate:
                continue
            con.execute("""
                INSERT INTO antivirus_entries(
                    client_name, setup_date, antivirus_name, expiration_date,
                    invoice_no, info, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?)
            """, (
                item.get("client_name",""),
                item.get("setup_date",""),
                item.get("antivirus_name",""),
                item.get("expiration_date",""),
                item.get("invoice_no",""),
                item.get("info",""),
                stamp, stamp
            ))
            inserted += 1
        con.execute(
            "INSERT OR REPLACE INTO app_meta(key,value,updated_at) VALUES(?,?,?)",
            (av_key, f"{inserted}/{len(LEGACY_ANTIVIRUS_ENTRIES)} antivirus ajoutés", stamp)
        )

    quote_key = "legacy_quote_300620261500_from_ods_v1"
    if not con.execute("SELECT 1 FROM app_meta WHERE key=?", (quote_key,)).fetchone():
        quote = LEGACY_QUOTE
        existing = con.execute(
            "SELECT id FROM quotes WHERE quote_no=?",
            (quote["quote_no"],)
        ).fetchone()

        if existing:
            quote_id = existing["id"]
        else:
            cur = con.execute("""
                INSERT INTO quotes(
                    quote_no, quote_date, client_name, client_address_street,
                    client_postal_code, client_city, contact_name, status,
                    notes, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                quote["quote_no"], quote["quote_date"], quote["client_name"],
                quote.get("client_address_street",""),
                quote.get("client_postal_code",""),
                quote.get("client_city",""),
                quote.get("contact_name",""),
                quote.get("status","Historique"),
                quote.get("notes",""),
                stamp, stamp
            ))
            quote_id = cur.lastrowid

            for line in quote.get("lines", []):
                con.execute("""
                    INSERT INTO quote_lines(
                        quote_id, position, line_type, quantity, description, unit_price
                    ) VALUES(?,?,?,?,?,?)
                """, (
                    quote_id,
                    line.get("position", 0),
                    line.get("line_type", "service"),
                    float(line.get("quantity", 1)),
                    line.get("description", ""),
                    float(line.get("unit_price", 0)),
                ))

        con.execute(
            "INSERT OR REPLACE INTO app_meta(key,value,updated_at) VALUES(?,?,?)",
            (quote_key, f"devis_id={quote_id}", stamp)
        )


def seed_legacy_quotes37(con):
    """Importe l'archive devis.zip : 33 devis uniques et 37 PDF historiques."""
    migration_key = "legacy_quotes37_zip_v3_recheck_complete"
    done = con.execute("SELECT value FROM app_meta WHERE key=?", (migration_key,)).fetchone()
    if done:
        return {"quotes_added": 0, "documents_added": 0, "already_done": True}

    stamp = datetime.now().isoformat(timespec="seconds")
    quotes_added = 0
    docs_added = 0

    for quote in LEGACY_QUOTES_37:
        existing = con.execute(
            "SELECT id FROM quotes WHERE quote_no=?",
            (quote["quote_no"],)
        ).fetchone()

        if existing:
            quote_id = existing["id"]
        else:
            # Tente d'associer automatiquement au client local par nom exact, sans créer de doublon.
            client_row = con.execute(
                "SELECT id FROM clients WHERE lower(trim(name))=lower(trim(?)) LIMIT 1",
                (quote.get("client_name", ""),)
            ).fetchone()
            client_id = client_row["id"] if client_row else None

            cur = con.execute("""
                INSERT INTO quotes(
                    quote_no, quote_date, client_id, client_name,
                    client_address_street, client_postal_code, client_city,
                    contact_name, status, notes, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                quote["quote_no"],
                quote.get("quote_date", ""),
                client_id,
                quote.get("client_name", "Client"),
                quote.get("client_address_street", ""),
                quote.get("client_postal_code", ""),
                quote.get("client_city", ""),
                quote.get("contact_name", ""),
                quote.get("status", "Historique"),
                quote.get("notes", ""),
                stamp,
                stamp,
            ))
            quote_id = cur.lastrowid

            for line in quote.get("lines", []):
                con.execute("""
                    INSERT INTO quote_lines(
                        quote_id, position, line_type, quantity, description, unit_price
                    ) VALUES(?,?,?,?,?,?)
                """, (
                    quote_id,
                    int(line.get("position", 0)),
                    line.get("line_type", "service"),
                    float(line.get("quantity", 1)),
                    line.get("description", ""),
                    float(line.get("unit_price", 0)),
                ))
            quotes_added += 1

    # Les 37 fichiers sont reliés à leur devis. Plusieurs documents peuvent appartenir au même devis.
    for doc in LEGACY_QUOTE_DOCUMENTS_37:
        q = con.execute(
            "SELECT id FROM quotes WHERE quote_no=?",
            (doc["quote_no"],)
        ).fetchone()
        if not q:
            continue
        exists = con.execute(
            "SELECT id FROM quote_documents WHERE quote_id=? AND filename=?",
            (q["id"], doc["filename"])
        ).fetchone()
        if exists:
            continue
        con.execute("""
            INSERT INTO quote_documents(quote_id, filename, label, created_at)
            VALUES(?,?,?,?)
        """, (
            q["id"],
            doc["filename"],
            doc.get("label", "PDF historique"),
            stamp,
        ))
        docs_added += 1

    con.execute(
        "INSERT OR REPLACE INTO app_meta(key,value,updated_at) VALUES(?,?,?)",
        (
            migration_key,
            f"{quotes_added} devis ajoutés / {docs_added} PDF reliés / 33 devis uniques / 37 fichiers",
            stamp,
        )
    )
    return {"quotes_added": quotes_added, "documents_added": docs_added, "already_done": False}


def now():
    return datetime.now()

def make_dossier_no():
    """
    Numéro de dossier lisible : JJMMAAAAHHMM (sans secondes).
    Si deux dossiers sont créés dans la même minute, suffixe -2, -3, ...
    """
    base = now().strftime("%d%m%Y%H%M")
    con = db()
    candidate = base
    idx = 2
    while con.execute("SELECT 1 FROM repairs WHERE dossier_no=?", (candidate,)).fetchone():
        candidate = f"{base}-{idx}"
        idx += 1
    return candidate

def parse_money_input(value):
    text = str(value or "").strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not text:
        return 0.0
    return round(float(text), 2)


def ledger_valid_date(value):
    try:
        datetime.strptime(str(value or ""), "%Y-%m-%d")
        return True
    except Exception:
        return False


def ledger_month_name(month):
    names = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]
    return names[month] if 1 <= month <= 12 else ""


def year_month_folder(root, date_value, supplier=False, create=True):
    """Retourne root/YYYY/MM - Mois[/Fournisseurs]."""
    try:
        d = datetime.strptime(str(date_value or ""), "%Y-%m-%d")
    except Exception:
        d = now()

    folder = root / f"{d.year:04d}" / MONTH_FOLDER_NAMES[d.month]
    if supplier:
        folder = folder / "Fournisseurs"
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_document_name(name):
    value = str(name or "").strip()
    value = value.replace("/", "-").replace("\\\\", "-")
    value = re.sub(r'[<>:"|?*]+', "-", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value or "Document.pdf"


def _match_key(value):
    """Normalise un texte pour comparer noms de fournisseurs / numéros de facture."""
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", value.casefold())




def is_supplier_invoice_reference(invoice_no, party="", remarks=""):
    """True uniquement pour une vraie référence de facture fournisseur.

    Les anciens imports ODS contiennent parfois dans invoice_no un bon de commande
    ou un numéro interne/date-heure. Ces valeurs ne doivent jamais servir à nommer
    ou rapprocher une facture fournisseur.
    """
    raw = str(invoice_no or "").strip()
    if not raw:
        return False
    folded = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode().casefold()
    if any(x in folded for x in ("bon de commande", "n° de commande", "no de commande", "numero de commande", "commande n°", "commande no")):
        return False

    digits = re.sub(r"\D", "", raw)
    remarks_folded = unicodedata.normalize("NFKD", str(remarks or "")).encode("ascii", "ignore").decode().casefold()
    party_folded = str(party or "").casefold()
    # Imports historiques Amazon/eBay : certains numéros ressemblent à une date/heure
    # (ex. 60820261300 = 06/08/2026 13:00) et ne sont pas des factures fournisseur.
    if ("commande" in remarks_folded or party_folded in {"amazon", "ebay"}) and len(digits) in (11, 12):
        padded = digits.zfill(12)
        try:
            datetime.strptime(padded, "%d%m%Y%H%M")
            return False
        except Exception:
            pass
    return True

def supplier_document_filename(entry_date, party, invoice_no, original_name):
    """Nom maison : FOURNISSEUR_NumeroFacture.ext, comme le classement manuel de Foul."""
    original = Path(str(original_name or "facture.pdf"))
    suffix = original.suffix.lower() or ".pdf"
    supplier = safe_document_name(party or "Fournisseur")
    invoice_raw = str(invoice_no or "").strip()

    # Si le N° est déjà connu en compta, il devient la partie droite du nom.
    if is_supplier_invoice_reference(invoice_raw, party=party):
        invoice = safe_document_name(invoice_raw)
        return safe_document_name(f"{supplier}_{invoice}{suffix}")

    # Sinon on conserve l'information utile du nom reçu (ex: Facture_20260903-0006.pdf)
    # en retirant seulement les préfixes génériques, puis on ajoute le fournisseur réel.
    stem = original.stem.strip()
    stem = re.sub(r"^(facture|invoice)[ _-]*", "", stem, flags=re.IGNORECASE).strip(" _-")
    if not stem:
        stem = str(entry_date or now().strftime("%Y%m%d")).replace("-", "")
    if _match_key(stem).startswith(_match_key(supplier)):
        return safe_document_name(f"{stem}{suffix}")
    return safe_document_name(f"{supplier}_{stem}{suffix}")


def save_ledger_document(entry_id, storage):
    """
    Lie une facture fournisseur à une ligne Achats/Ventes et la range proprement.
    Pas de sous-dossier par fournisseur : un seul dossier Fournisseurs par mois.
    Les nouvelles pièces suivent le nom maison FOURNISSEUR_NumeroFacture.ext.
    """
    filename = str(getattr(storage, "filename", "") or "").strip()
    if not filename:
        return None
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}:
        raise ValueError("Format non accepté : PDF, XML, JPG ou PNG uniquement.")
    raw = storage.read()
    if not raw:
        raise ValueError("Fichier vide.")
    if len(raw) > 20 * 1024 * 1024:
        raise ValueError("Fichier trop volumineux (20 Mo maximum).")

    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    if not row:
        con.close()
        raise ValueError("Ligne Achats/Ventes introuvable.")
    if str(row["document_path"] or "").strip():
        con.close()
        raise ValueError("Une pièce justificative est déjà liée à cette ligne.")

    folder = year_month_folder(FOURNISSEURS_ROOT, row["entry_date"], supplier=False, create=True)

    # V2.3.95 — anti-doublon strict : avant même de fabriquer un nouveau nom,
    # on cherche si CE fichier existe déjà dans Fournisseurs, quel que soit son nom.
    # Exemple : une facture VistaPrint déjà classée manuellement doit être simplement
    # liée à l'achat, jamais recopiée à côté sous un autre nom.
    dest = None
    for existing in folder.iterdir():
        if not existing.is_file() or existing.suffix.lower() not in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}:
            continue
        try:
            if existing.stat().st_size == len(raw) and existing.read_bytes() == raw:
                dest = existing
                break
        except Exception:
            continue

    # V2.3.97 — priorité absolue au classement existant de Foul.
    # Même si le PDF reçu à nouveau n'est pas strictement identique (métadonnées,
    # régénération du fournisseur, etc.), on ne doit pas créer une seconde facture
    # à côté si une pièce déjà classée correspond sans ambiguïté à la même facture.
    if dest is None:
        existing_docs = [
            p for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
        ]
        invoice_key = _match_key(row["invoice_no"]) if is_supplier_invoice_reference(
            row["invoice_no"], party=row["party"], remarks=row["remarks"]
        ) else ""
        supplier_key = _match_key(row["party"])

        original_stem = Path(filename).stem.strip()
        original_stem = re.sub(r"^(facture|invoice)[ _-]*", "", original_stem, flags=re.IGNORECASE).strip(" _-")
        original_key = _match_key(original_stem)
        # Un identifiant trop court/générique ne doit jamais servir à rapprocher.
        if len(original_key) < 5:
            original_key = ""

        strong_matches = []
        for existing in existing_docs:
            stem_key = _match_key(existing.stem)
            by_invoice = bool(invoice_key and len(invoice_key) >= 4 and invoice_key in stem_key)
            by_original = bool(original_key and (original_key in stem_key or stem_key.endswith(original_key)))
            # Quand on matche par nom reçu, on exige aussi le fournisseur si celui-ci
            # est présent dans le nom classé, afin d'éviter les collisions.
            supplier_ok = not supplier_key or supplier_key in stem_key or by_invoice
            if by_invoice or (by_original and supplier_ok):
                strong_matches.append(existing)

        if len(strong_matches) == 1:
            dest = strong_matches[0]
        elif len(strong_matches) > 1:
            con.close()
            raise ValueError(
                "Plusieurs justificatifs déjà classés semblent correspondre à cette facture. "
                "Aucun nouveau fichier n'a été créé : vérifie les fichiers du mois puis rattache le bon."
            )

    if dest is None:
        clean_name = supplier_document_filename(row["entry_date"], row["party"], row["invoice_no"], filename)
        dest = folder / clean_name

        # Le même nom existe déjà mais le contenu diffère : surtout ne pas fabriquer
        # automatiquement un ' - 2'. Cela crée exactement le bazar que l'on veut éviter.
        # On arrête et on laisse l'utilisateur vérifier le document existant.
        if dest.exists():
            con.close()
            raise ValueError(
                f"Un justificatif nommé {dest.name} existe déjà dans Fournisseurs. "
                "Aucun doublon n'a été créé."
            )
        dest.write_bytes(raw)

    rel = str(dest.relative_to(FOULFIX_ROOT))
    con.execute("""
        UPDATE ledger_entries
        SET document_path=?, document_original_name=?, updated_at=?
        WHERE id=?
    """, (rel, filename, now().isoformat(timespec="seconds"), entry_id))
    con.commit()
    con.close()
    return dest


def _supplier_document_candidates(entry_date):
    """Factures déjà classées par l'utilisateur dans le mois concerné, sans les modifier."""
    folder = year_month_folder(FOURNISSEURS_ROOT, entry_date, supplier=False, create=False)
    if not folder.is_dir():
        return []
    allowed = {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in allowed), key=lambda p: p.name.casefold())


def _supplier_auto_match(row, candidates):
    """Retourne un fichier uniquement quand le rapprochement est suffisamment sûr."""
    if not candidates:
        return None, "missing"

    invoice_key = _match_key(row["invoice_no"] or "") if is_supplier_invoice_reference(row["invoice_no"], row["party"], row["remarks"]) else ""
    party_key = _match_key(row["party"] or "")
    date_txt = str(row["entry_date"] or "")[:10]
    date_tokens = set()
    if date_txt:
        date_tokens.add(_match_key(date_txt))
        date_tokens.add(_match_key(date_txt.replace("-", "")))
        try:
            d = datetime.strptime(date_txt, "%Y-%m-%d")
            # Noms de fichiers rencontrés : 2026-09-08, 20260908,
            # 08-09-2026, 08_09_2026, 08092026, etc.
            date_tokens.update({
                _match_key(d.strftime("%Y-%m-%d")),
                _match_key(d.strftime("%Y%m%d")),
                _match_key(d.strftime("%d-%m-%Y")),
                _match_key(d.strftime("%d_%m_%Y")),
                _match_key(d.strftime("%d%m%Y")),
            })
        except Exception:
            pass
    date_tokens.discard("")

    scored = []
    for path in candidates:
        name_key = _match_key(path.stem)
        score = 0
        # Numéro de facture : signal le plus fiable.
        if invoice_key and invoice_key in name_key:
            score += 100
        # Fournisseur réel tel que l'utilisateur l'a ajouté au nom du fichier.
        if party_key and len(party_key) >= 3 and party_key in name_key:
            score += 35
        # Date de facture / achat, utile en complément.
        if any(tok and tok in name_key for tok in date_tokens):
            score += 15
        scored.append((score, path))

    scored.sort(key=lambda x: (-x[0], x[1].name.casefold()))
    best_score = scored[0][0]
    best = [p for score, p in scored if score == best_score and score > 0]

    # Auto uniquement si le numéro de facture correspond, ou fournisseur+date sans ambiguïté.
    if best_score >= 100 and len(best) == 1:
        return best[0], "invoice"
    if best_score >= 50 and len(best) == 1:
        return best[0], "party_date"
    if best_score > 0:
        return None, "ambiguous"
    return None, "missing"


def auto_link_supplier_documents(years=(2025, 2026)):
    """
    Rattache les factures déjà présentes dans private/documents/Fournisseurs aux achats existants.
    Ne déplace, ne copie et ne renomme aucun fichier historique.
    """
    con = db()
    placeholders = ",".join("?" for _ in years)
    rows = con.execute(f"""
        SELECT * FROM ledger_entries
        WHERE operation='Achat'
          AND COALESCE(document_path,'')=''
          AND substr(entry_date,1,4) IN ({placeholders})
        ORDER BY entry_date, id
    """, tuple(str(y) for y in years)).fetchall()

    linked = ambiguous = missing = 0
    used = set()
    for row in rows:
        candidates = [p for p in _supplier_document_candidates(row["entry_date"]) if str(p.resolve()) not in used]
        match, reason = _supplier_auto_match(row, candidates)
        if not match:
            if reason == "ambiguous":
                ambiguous += 1
            else:
                missing += 1
            continue
        try:
            rel = str(match.relative_to(FOULFIX_ROOT))
        except Exception:
            missing += 1
            continue
        con.execute("""
            UPDATE ledger_entries
            SET document_path=?, document_original_name=?, updated_at=?
            WHERE id=? AND COALESCE(document_path,'')=''
        """, (rel, match.name, now().isoformat(timespec="seconds"), row["id"]))
        used.add(str(match.resolve()))
        linked += 1

    con.commit()
    con.close()
    return linked, ambiguous, missing


def ledger_document_file(row):
    """Résout une pièce fournisseur déplacée dans documents/Fournisseurs.

    Ordre volontairement déterministe :
      1. vraie référence de facture si connue ;
      2. nom original enregistré ;
      3. nom du fichier de l'ancien document_path ;
      4. fournisseur + date si résultat unique ;
      5. même logique dans toute l'arborescence Fournisseurs.

    Un ancien chemin faux ne doit jamais empêcher la recherche.
    """
    if not row:
        return None

    rel = str(row["document_path"] or "").strip()
    original_name = str(row["document_original_name"] or "").strip()
    invoice_no = str(row["invoice_no"] or "").strip()
    party = str(row["party"] or "").strip()
    entry_date = str(row["entry_date"] or "").strip()

    def _basename(value):
        return str(value or "").replace("\\", "/").rstrip("/").split("/")[-1]

    def _files(folder):
        try:
            return [
                p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
            ]
        except Exception:
            return []

    def _pick(candidates):
        if not candidates:
            return None

        # 1) La référence de facture est prioritaire sur les anciens noms.
        invoice_key = _match_key(invoice_no)
        if invoice_key and len(invoice_key) >= 4:
            hits = [p for p in candidates if invoice_key in _match_key(p.stem)]
            if len(hits) == 1:
                return hits[0]
            if len(hits) > 1:
                party_key = _match_key(party)
                if party_key and len(party_key) >= 3:
                    narrowed = [p for p in hits if party_key in _match_key(p.stem)]
                    if len(narrowed) == 1:
                        return narrowed[0]

        # 2) Nom original puis ancien basename document_path.
        for wanted in (_basename(original_name), _basename(rel)):
            if not wanted:
                continue
            hits = [p for p in candidates if p.name.casefold() == wanted.casefold()]
            if len(hits) == 1:
                return hits[0]

        # 3) Fournisseur + date, seulement si sans ambiguïté.
        party_key = _match_key(party)
        date_keys = set()
        try:
            d = datetime.strptime(entry_date, "%Y-%m-%d")
            date_keys.update({
                _match_key(d.strftime("%Y%m%d")),
                _match_key(d.strftime("%d%m%Y")),
            })
        except Exception:
            pass
        date_keys.discard("")

        if party_key and len(party_key) >= 3:
            hits = []
            for p in candidates:
                key = _match_key(p.stem)
                if party_key in key and (not date_keys or any(dk in key for dk in date_keys)):
                    hits.append(p)
            if len(hits) == 1:
                return hits[0]

        return None

    # Ancien chemin encore valide ? On l'accepte uniquement si le fichier existe.
    # Mais si invoice_no est renseigné et que le basename ne correspond pas à cette
    # référence, on ne fait PAS confiance à ce vieux lien (cas FR6201Q9ABEI qui
    # pointait encore vers FR61SZP5ABEI).
    if rel:
        try:
            candidate = (FOULFIX_ROOT / rel).resolve()
            allowed = False
            for root in (FOURNISSEURS_ROOT.resolve(), FACTURES_ROOT.resolve()):
                try:
                    candidate.relative_to(root)
                    allowed = True
                    break
                except Exception:
                    continue
        except Exception:
            allowed = False

        if allowed and candidate.is_file():
            invoice_key = _match_key(invoice_no)
            if not invoice_key or invoice_key in _match_key(candidate.stem):
                return candidate

    # D'abord le mois réel de la ligne.
    try:
        d = datetime.strptime(entry_date, "%Y-%m-%d")
        month_folder = FOURNISSEURS_ROOT / f"{d.year:04d}" / MONTH_FOLDER_NAMES[d.month]
        hit = _pick(_files(month_folder))
        if hit:
            return hit
    except Exception:
        pass

    # Puis toute l'arborescence : utile après déplacement manuel ou date historique
    # légèrement différente du mois où le justificatif a été classé.
    try:
        all_files = [
            p for p in FOURNISSEURS_ROOT.rglob("*")
            if p.is_file() and p.suffix.lower() in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}
        ]
        hit = _pick(all_files)
        if hit:
            return hit
    except Exception:
        pass

    return None


def repair_dead_supplier_document_links():
    """Répare uniquement les liens morts vers une pièce déjà présente dans Fournisseurs.

    Aucun fichier n'est créé, copié, renommé ou supprimé ici.
    """
    con = db()
    rows = con.execute("""
        SELECT * FROM ledger_entries
        WHERE operation='Achat' AND COALESCE(document_path,'')<>''
    """).fetchall()
    repaired = 0
    for row in rows:
        rel = str(row["document_path"] or "").strip()
        try:
            direct = (FOULFIX_ROOT / rel).resolve()
            if direct.is_file():
                continue
        except Exception:
            pass
        found = ledger_document_file(row)
        if not found:
            continue
        try:
            new_rel = str(found.relative_to(FOULFIX_ROOT))
        except Exception:
            continue
        if new_rel == rel:
            continue
        con.execute(
            "UPDATE ledger_entries SET document_path=?, updated_at=? WHERE id=?",
            (new_rel, now().isoformat(timespec="seconds"), row["id"]),
        )
        repaired += 1
    if repaired:
        con.commit()
    con.close()
    return repaired


def find_document_recursive(root, filename=None, document_no=None):
    """
    Cherche un document dans les vrais dossiers WOPR/private/documents/Devis ou Factures.
    Priorité au nom de fichier exact, sinon au numéro contenu dans le nom.
    """
    if not root.exists():
        return None

    if filename:
        target = Path(filename).name.casefold()
        for p in root.rglob("*"):
            if p.is_file() and p.name.casefold() == target:
                return p

    if document_no:
        needle = str(document_no).strip().casefold()
        if needle:
            matches = [
                p for p in root.rglob("*.pdf")
                if needle in p.name.casefold()
            ]
            if matches:
                return sorted(matches)[0]

    return None


def quote_document_candidates(quote_no):
    """
    PDF historiques réellement présents avant génération WOPR.
    Les PDF produits par l'application portent le suffixe `.foulfix.pdf`
    et ne sont jamais comptés comme des Originaux.
    """
    if not DEVIS_ROOT.exists():
        return []
    needle = str(quote_no or "").strip().casefold()
    if not needle:
        return []
    return sorted(
        p for p in DEVIS_ROOT.rglob("*.pdf")
        if needle in p.name.casefold()
        and not p.name.casefold().endswith(".foulfix.pdf")
    )


def make_quote_no(con=None):
    """
    Numéro de devis automatique, identique à la logique facture :
    JJMMYYYYHHMM, ex. 310820261516.
    """
    base_dt = now()
    prefix = cfg().get("invoice_prefix", "")
    fmt = "%d%m%Y%H%M"

    if con is None:
        return prefix + base_dt.strftime(fmt)

    # Très rare : deux devis dans la même minute.
    # On conserve strictement le format demandé et prend la minute libre suivante.
    for offset in range(0, 120):
        candidate = prefix + (base_dt + timedelta(minutes=offset)).strftime(fmt)
        if not con.execute("SELECT 1 FROM quotes WHERE quote_no=?", (candidate,)).fetchone():
            return candidate

    return prefix + base_dt.strftime(fmt)


def parse_quote_lines(form):
    quantities = form.getlist("line_qty[]")
    descriptions = form.getlist("line_desc[]")
    prices = form.getlist("line_price[]")
    types = form.getlist("line_type[]")

    lines = []
    count = max(len(quantities), len(descriptions), len(prices), len(types))
    for i in range(count):
        desc = descriptions[i].strip() if i < len(descriptions) else ""
        if not desc:
            continue
        try:
            qty = float((quantities[i] if i < len(quantities) else "1").replace(",", ".") or 1)
        except Exception:
            qty = 1.0
        try:
            price = float((prices[i] if i < len(prices) else "0").replace(",", ".") or 0)
        except Exception:
            price = 0.0
        line_type = types[i] if i < len(types) and types[i] in ("service", "goods") else "service"
        lines.append({
            "position": len(lines),
            "line_type": line_type,
            "quantity": qty,
            "description": desc,
            "unit_price": price,
        })
    return lines


def make_invoice_no():
    """
    Numéro standard JJMMYYYYHHMM.
    Si une facture existe déjà dans la même minute :
    JJMMYYYYHHMM-2, puis -3, etc.
    """
    c = cfg()
    base = c.get("invoice_prefix", "") + now().strftime(
        c.get("invoice_number_format", "%d%m%Y%H%M")
    )

    con = db()
    try:
        if not con.execute(
            "SELECT 1 FROM repairs WHERE invoice_no=? LIMIT 1",
            (base,)
        ).fetchone():
            return base

        suffix = 2
        while con.execute(
            "SELECT 1 FROM repairs WHERE invoice_no=? LIMIT 1",
            (f"{base}-{suffix}",)
        ).fetchone():
            suffix += 1
        return f"{base}-{suffix}"
    finally:
        con.close()

def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def safe_filename(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())
    return text.strip("_") or "client"


def normalize_phone(value):
    digits = re.sub(r"\D", "", value or "")
    # Uniformise les formats français : +33 / 0033 / 0...
    if digits.startswith("0033") and len(digits) > 4:
        digits = "0" + digits[4:]
    elif digits.startswith("33") and len(digits) >= 11:
        digits = "0" + digits[2:]
    return digits


def google_is_configured():
    return GOOGLE_LIBS_OK and GOOGLE_CLIENT_SECRET.exists() and GOOGLE_TOKEN.exists()


def google_credentials():
    if not GOOGLE_LIBS_OK or not GOOGLE_TOKEN.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN), GOOGLE_SCOPE)
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            GOOGLE_TOKEN.write_text(creds.to_json(), encoding="utf-8")
        return creds if creds.valid else None
    except Exception:
        return None


def google_service():
    creds = google_credentials()
    if not creds:
        return None
    return google_build("people", "v1", credentials=creds, cache_discovery=False)


def google_execute_with_retry(request, max_retries=3):
    """Exécute une requête Google et temporise proprement en cas de quota 429."""
    for attempt in range(max_retries + 1):
        try:
            return request.execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 429 or attempt >= max_retries:
                raise
            # Le quota critique est calculé à la minute : attendre un peu plus
            # d'une minute évite de repartir dans la même fenêtre de quota.
            time.sleep(65)


def google_find_group(service, wanted_name=None):
    wanted = (wanted_name or cfg().get("google_contact_group") or cfg().get("business_name") or "WOPR").strip().casefold()
    token = None
    while True:
        res = service.contactGroups().list(pageSize=1000, pageToken=token).execute()
        for group in res.get("contactGroups", []):
            if (group.get("name") or "").strip().casefold() == wanted or (group.get("formattedName") or "").strip().casefold() == wanted:
                return group.get("resourceName")
        token = res.get("nextPageToken")
        if not token:
            break
    return None


def google_find_existing_contact(service, client):
    """Premier rattachement: cherche un contact Google existant pour éviter les doublons."""
    wanted_email = (client["email"] or "").strip().casefold()
    wanted_phone = normalize_phone(client["phone"])
    token = None
    while True:
        res = service.people().connections().list(
            resourceName="people/me",
            pageSize=1000,
            pageToken=token,
            personFields="names,emailAddresses,phoneNumbers,addresses,memberships"
        ).execute()
        for person in res.get("connections", []):
            emails = {(x.get("value") or "").strip().casefold() for x in person.get("emailAddresses", [])}
            phones = {normalize_phone(x.get("value")) for x in person.get("phoneNumbers", [])}
            if wanted_email and wanted_email in emails:
                return person.get("resourceName")
            if wanted_phone and wanted_phone in phones:
                return person.get("resourceName")
        token = res.get("nextPageToken")
        if not token:
            break
    return None


def google_contact_body(client):
    """Construit uniquement les champs WOPR réellement renseignés.

    Aucun tableau vide n'est envoyé à Google : une valeur absente dans WOPR ne
    signifie jamais "effacer la valeur Google".
    """
    body = {}

    first_name = (client["first_name"] or "").strip() if "first_name" in client.keys() else ""
    last_name = (client["last_name"] or "").strip() if "last_name" in client.keys() else ""
    fallback_name = (client["name"] or "").strip() if "name" in client.keys() else ""

    if first_name or last_name:
        google_name = {}
        if first_name:
            google_name["givenName"] = first_name
        if last_name:
            google_name["familyName"] = last_name
        body["names"] = [google_name]
    elif fallback_name:
        body["names"] = [{"givenName": fallback_name}]

    email = (client["email"] or "").strip()
    if email:
        body["emailAddresses"] = [{"value": email, "type": "home"}]

    phone = (client["phone"] or "").strip()
    if phone:
        body["phoneNumbers"] = [{"value": phone, "type": "mobile"}]

    street = (client["address_street"] or "").strip()
    city = (client["city"] or "").strip()
    postal = (client["postal_code"] or "").strip()
    if street or city or postal:
        body["addresses"] = [{
            "streetAddress": street,
            "city": city,
            "postalCode": postal,
            "country": "France",
            "type": "home"
        }]

    company = (client["company"] or "").strip() if "company" in client.keys() else ""
    if company:
        body["organizations"] = [{"name": company, "type": "work"}]

    notes = (client["notes"] or "").strip()
    if notes:
        body["biographies"] = [{"value": notes, "contentType": "TEXT_PLAIN"}]

    return body


def google_safe_merge_contact(latest, wopr_body):
    """Fusion non destructive WOPR -> Google."""
    merged = {}
    fields_changed = []

    existing_names = [dict(x) for x in latest.get("names", [])]
    wanted_names = wopr_body.get("names", [])
    if wanted_names:
        wanted = wanted_names[0]
        if existing_names:
            current = dict(existing_names[0])
            if wanted.get("givenName"):
                current["givenName"] = wanted["givenName"]
            if wanted.get("familyName"):
                current["familyName"] = wanted["familyName"]
            existing_names[0] = current
        else:
            existing_names = [dict(wanted)]
        merged["names"] = existing_names
        fields_changed.append("names")

    def merge_multi(field, keyfunc):
        existing = [dict(x) for x in latest.get(field, [])]
        wanted = [dict(x) for x in wopr_body.get(field, [])]
        if not wanted:
            return
        seen = {keyfunc(x) for x in existing if keyfunc(x)}
        for item in wanted:
            key = keyfunc(item)
            if key and key not in seen:
                existing.append(item)
                seen.add(key)
        merged[field] = existing
        fields_changed.append(field)

    merge_multi("emailAddresses", lambda x: (x.get("value") or "").strip().casefold())
    merge_multi("phoneNumbers", lambda x: normalize_phone(x.get("value")))
    merge_multi(
        "addresses",
        lambda x: "|".join([
            (x.get("streetAddress") or "").strip().casefold(),
            (x.get("postalCode") or "").strip().casefold(),
            (x.get("city") or "").strip().casefold(),
        ])
    )
    merge_multi("organizations", lambda x: (x.get("name") or "").strip().casefold())
    merge_multi("biographies", lambda x: (x.get("value") or "").strip().casefold())

    if latest.get("etag"):
        merged["etag"] = latest["etag"]

    return merged, ",".join(fields_changed)


def google_contact_sync_hash(body):
    """Empreinte stable des données WOPR destinées à Google Contacts."""
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def set_google_sync_state(client_id, status, resource_name=None, error=""):
    con = db()
    if resource_name is None:
        con.execute("UPDATE clients SET google_sync_status=?, google_sync_error=? WHERE id=?",
                    (status, error[:1000], client_id))
    else:
        con.execute("""UPDATE clients SET google_sync_status=?, google_sync_error=?,
                     google_resource_name=?, google_synced_at=? WHERE id=?""",
                    (status, error[:1000], resource_name, now().isoformat(timespec="seconds"), client_id))
    con.commit(); con.close()


def sync_client_to_google(client_id):
    if not cfg().get("google_sync_enabled", True):
        return False, "Synchronisation Google désactivée"

    con = db()
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    con.close()
    if not client:
        return False, "Client introuvable"
    if int(client["archived"] or 0) == 1:
        return False, "Client archivé"

    body = google_contact_body(client)
    current_hash = google_contact_sync_hash(body)
    previous_hash = (client["google_sync_hash"] or "").strip()
    resource_name = (client["google_resource_name"] or "").strip()

    # Rien n'a changé depuis le dernier envoi : zéro appel à Google.
    if resource_name and previous_hash and previous_hash == current_hash:
        set_google_sync_state(client_id, "Synchronisé")
        return True, "Aucune modification à synchroniser"

    service = google_service()
    if not service:
        set_google_sync_state(client_id, "À connecter", error="Google n'est pas encore connecté")
        return False, "Google n'est pas encore connecté"

    try:
        group_resource = google_find_group(service)
        if not group_resource:
            msg = f"Le groupe Google '{cfg().get('google_contact_group') or cfg().get('business_name') or 'WOPR'}' est introuvable."
            set_google_sync_state(client_id, "Erreur", error=msg)
            return False, msg

        if not resource_name:
            resource_name = google_find_existing_contact(service, client)

        if resource_name:
            try:
                latest = google_execute_with_retry(service.people().get(
                    resourceName=resource_name,
                    personFields="names,emailAddresses,phoneNumbers,addresses,organizations,biographies,metadata"
                ))
                safe_body, update_fields = google_safe_merge_contact(latest, body)
                if update_fields:
                    updated = google_execute_with_retry(service.people().updateContact(
                        resourceName=resource_name,
                        updatePersonFields=update_fields,
                        body=safe_body
                    ))
                    resource_name = updated.get("resourceName", resource_name)
            except HttpError as e:
                if getattr(e.resp, "status", None) == 404:
                    resource_name = None
                else:
                    raise

        if not resource_name:
            created = service.people().createContact(body=body).execute()
            resource_name = created.get("resourceName")

        # Ajoute au groupe Google configuré. Cette opération est sans danger si déjà membre.
        try:
            service.contactGroups().members().modify(
                resourceName=group_resource,
                body={"resourceNamesToAdd": [resource_name]}
            ).execute()
        except HttpError as e:
            if getattr(e.resp, "status", None) not in (400, 409):
                raise

        set_google_sync_state(client_id, "Synchronisé", resource_name=resource_name)

        # On mémorise uniquement une synchro réellement réussie.
        con = db()
        con.execute(
            "UPDATE clients SET google_sync_hash=? WHERE id=?",
            (current_hash, client_id),
        )
        con.commit()
        con.close()
        return True, "Synchronisé"
    except Exception as e:
        msg = str(e)
        set_google_sync_state(client_id, "Erreur", error=msg)
        return False, msg


def sync_client_to_google_async(client_id):
    """Lance la synchronisation Google sans bloquer la requête web."""
    try:
        client_id = int(client_id)
    except (TypeError, ValueError):
        return False

    def _worker():
        try:
            sync_client_to_google(client_id)
        except Exception as exc:
            try:
                set_google_sync_state(client_id, "Erreur", error=str(exc))
            except Exception:
                pass

    threading.Thread(
        target=_worker,
        name=f"wopr-google-sync-{client_id}",
        daemon=True,
    ).start()
    return True



def _split_escaped(value, sep=";"):
    out, cur = [], []
    escaped = False
    for ch in value:
        if escaped:
            cur.append("\\")
            cur.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == sep:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if escaped:
        cur.append("\\")
    out.append("".join(cur))
    return out


def _vcard_unescape(value):
    value = str(value or "")
    # Ordre important : les séquences vCard sont traitées avant le backslash final.
    value = value.replace("\\N", "\n").replace("\\n", "\n")
    value = value.replace("\\,", ",").replace("\\;", ";")
    value = value.replace("\\\\", "\\")
    return value.strip()


def _vcard_pref(key):
    m = re.search(r"(?:^|;)PREF=(\\d+)", key, flags=re.I)
    return int(m.group(1)) if m else 999


def parse_proton_vcf(raw_text):
    """Parse les champs utiles d'un export Proton Contacts VCF 3/4 sans dépendance externe."""
    text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    unfolded = []
    for line in text.split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    raw_cards, current = [], None
    for line in unfolded:
        u = line.strip().upper()
        if u == "BEGIN:VCARD":
            current = []
        elif u == "END:VCARD":
            if current is not None:
                raw_cards.append(current)
            current = None
        elif current is not None:
            current.append(line)

    contacts = []
    for pos, lines in enumerate(raw_cards, start=1):
        fn = ""
        n_value = ""
        family_name = ""
        given_name = ""
        uid = ""
        emails = []
        phones = []
        addresses = []
        notes = []

        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            base = key.split(";", 1)[0]
            prop = base.split(".")[-1].upper()
            pref = _vcard_pref(key)

            # PHOTO / KEY peuvent être énormes : on les ignore volontairement.
            if prop in {"PHOTO", "KEY"}:
                continue

            if prop == "FN":
                fn = _vcard_unescape(value)
            elif prop == "N":
                n_value = value
            elif prop == "UID":
                uid = _vcard_unescape(value)
            elif prop == "EMAIL":
                val = _vcard_unescape(value)
                if val:
                    emails.append((pref, val))
            elif prop == "TEL":
                val = _vcard_unescape(value)
                if val:
                    phones.append((pref, val))
            elif prop == "ADR":
                parts = _split_escaped(value, ";")
                parts += [""] * (7 - len(parts))
                parts = [_vcard_unescape(x) for x in parts[:7]]
                addresses.append((pref, {
                    "po_box": parts[0],
                    "extended": parts[1],
                    "street": parts[2],
                    "city": parts[3],
                    "region": parts[4],
                    "postal_code": parts[5],
                    "country": parts[6],
                }))
            elif prop == "NOTE":
                val = _vcard_unescape(value)
                if val:
                    notes.append(val)

        if n_value:
            parts = _split_escaped(n_value, ";")
            parts += [""] * (5 - len(parts))
            family_name = _vcard_unescape(parts[0]).strip()
            given_name = _vcard_unescape(parts[1]).strip()
            if not fn:
                fn = " ".join(x for x in [given_name, family_name] if x).strip()

        emails.sort(key=lambda x: x[0])
        phones.sort(key=lambda x: x[0])
        addresses.sort(key=lambda x: x[0])

        email_values = []
        for _, value in emails:
            if value.casefold() not in {x.casefold() for x in email_values}:
                email_values.append(value)

        phone_values = []
        seen_phone = set()
        for _, value in phones:
            np = normalize_phone(value)
            if np and np not in seen_phone:
                seen_phone.add(np)
                phone_values.append(value)

        address_values = [x[1] for x in addresses]

        if not fn:
            fn = (email_values[0] if email_values else (phone_values[0] if phone_values else f"Contact Proton {pos}"))

        primary_address = address_values[0] if address_values else {}
        extra_notes = list(notes)

        # La base WOPR a un email/téléphone/adresse principal.
        # Les coordonnées Proton supplémentaires sont donc conservées dans Notes.
        if len(email_values) > 1:
            extra_notes.append("Autres e-mails Proton : " + " / ".join(email_values[1:]))
        if len(phone_values) > 1:
            extra_notes.append("Autres téléphones Proton : " + " / ".join(phone_values[1:]))
        if len(address_values) > 1:
            formatted = []
            for adr in address_values[1:]:
                line1 = adr.get("street", "")
                line2 = " ".join(x for x in [adr.get("postal_code", ""), adr.get("city", "")] if x).strip()
                formatted.append(", ".join(x for x in [line1, line2, adr.get("country", "")] if x))
            if formatted:
                extra_notes.append("Autres adresses Proton : " + " / ".join(formatted))

        contacts.append({
            "source_position": pos,
            "uid": uid,
            "name": fn.strip(),
            "first_name": given_name,
            "last_name": family_name,
            "email": email_values[0].strip() if email_values else "",
            "emails": email_values,
            "phone": phone_values[0].strip() if phone_values else "",
            "phones": phone_values,
            "address_street": primary_address.get("street", "").strip(),
            "postal_code": primary_address.get("postal_code", "").strip(),
            "city": primary_address.get("city", "").strip(),
            "country": primary_address.get("country", "").strip(),
            "addresses": address_values,
            "notes": "\n".join(x for x in extra_notes if x).strip(),
        })

    return contacts



def _contact_name_normalize(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(
        r"\b(client|cliente|client[e]? de passage|mme|mr|m|madame|monsieur)\b",
        " ",
        text
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contact_name_variants(first_name="", last_name="", legacy_name="", organization=""):
    variants = set()

    first = str(first_name or "").strip()
    last = str(last_name or "").strip()
    legacy = str(legacy_name or "").strip()
    org = str(organization or "").strip()

    for raw in (
        " ".join(x for x in [first, last] if x),
        " ".join(x for x in [last, first] if x),
        legacy,
        org,
    ):
        key = _contact_name_normalize(raw)
        if key:
            variants.add(key)

    return variants



def clean_google_contact_name(first_name="", last_name="", organization=""):
    """Répare les exports Google où prénom/nom sont mal répartis."""
    first = " ".join(str(first_name or "").split()).strip()
    last = " ".join(str(last_name or "").split()).strip()
    org = " ".join(str(organization or "").split()).strip()

    # Cas : First Name = "Agnès Foricher", Last Name vide.
    if first and not last:
        parts = first.split()
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])

    # Cas : First Name = "Antoine", Last Name = "Lacoste Antoine"
    if first and last:
        fkey = _contact_name_normalize(first)
        last_parts = last.split()
        if last_parts and _contact_name_normalize(last_parts[-1]) == fkey:
            cleaned_last = " ".join(last_parts[:-1]).strip()
            if cleaned_last:
                return first, cleaned_last

        # Variante inverse : Last Name commence par le prénom.
        if last_parts and _contact_name_normalize(last_parts[0]) == fkey:
            cleaned_last = " ".join(last_parts[1:]).strip()
            if cleaned_last:
                return first, cleaned_last

    # Organisation / association : ne pas inventer un prénom.
    if not first and not last and org:
        return "", org

    return first, last



def _contact_name_signature(first_name="", last_name="", legacy_name="", organization=""):
    """Signature indépendante de l'ordre Prénom/Nom pour un rapprochement exact."""
    variants = _contact_name_variants(first_name, last_name, legacy_name, organization)
    signatures = set()
    for value in variants:
        tokens = [x for x in value.split() if x]
        if not tokens:
            continue
        signatures.add(" ".join(sorted(tokens)))
    return signatures



def _merge_manual_local_client(con, master_id, duplicate_id):
    """
    Fusion manuelle explicitement demandée par l'utilisateur.
    La fiche master est conservée. Les champs vides sont complétés depuis le doublon.
    Les coordonnées différentes non copiées sont conservées dans les notes afin de ne rien perdre.
    Les réparations/factures (portées par repairs) et les devis sont rattachés au master.
    Aucun contact Google n'est supprimé.
    """
    if master_id == duplicate_id:
        return {"merged": False, "repairs": 0, "quotes": 0, "reason": "same"}

    master_row = con.execute("SELECT * FROM clients WHERE id=?", (master_id,)).fetchone()
    dup_row = con.execute("SELECT * FROM clients WHERE id=?", (duplicate_id,)).fetchone()
    if not master_row or not dup_row:
        return {"merged": False, "repairs": 0, "quotes": 0, "reason": "missing"}

    master = dict(master_row)
    dup = dict(dup_row)
    updates = {}

    # Complète uniquement les champs vides de la fiche conservée.
    for field in (
        "first_name", "last_name", "company", "phone", "email",
        "address_street", "postal_code", "city"
    ):
        mv = str(master.get(field) or "").strip()
        dv = str(dup.get(field) or "").strip()
        if not mv and dv:
            updates[field] = dup.get(field)
            master[field] = dup.get(field)

    # Conserve les éventuelles valeurs différentes dans les notes.
    extra_notes = []
    for label, field, normalizer in (
        ("Téléphone", "phone", normalize_phone),
        ("E-mail", "email", _email_key),
        ("Adresse", "address_street", lambda x: str(x or "").strip().casefold()),
        ("Code postal", "postal_code", lambda x: str(x or "").strip()),
        ("Ville", "city", lambda x: str(x or "").strip().casefold()),
        ("Entreprise", "company", lambda x: str(x or "").strip().casefold()),
    ):
        mv = str(master.get(field) or "").strip()
        dv = str(dup.get(field) or "").strip()
        if mv and dv and normalizer(mv) != normalizer(dv):
            extra_notes.append(f"{label} (ancienne fiche fusionnée) : {dv}")

    master_notes = str(master.get("notes") or "").strip()
    dup_notes = str(dup.get("notes") or "").strip()
    merged_notes_parts = []
    if master_notes:
        merged_notes_parts.append(master_notes)
    if dup_notes and dup_notes != master_notes:
        merged_notes_parts.append("Notes de la fiche fusionnée :\n" + dup_notes)
    if extra_notes:
        merged_notes_parts.append("\n".join(extra_notes))
    merged_notes = "\n\n".join(x for x in merged_notes_parts if x).strip()
    if merged_notes != master_notes:
        updates["notes"] = merged_notes
        master["notes"] = merged_notes

    # Si le master n'est pas lié à Google mais le doublon l'est, récupère le lien.
    # Si les deux ont des ressources Google différentes, on garde celle du master
    # et on ne supprime rien chez Google.
    if (
        not str(master.get("google_resource_name") or "").strip()
        and str(dup.get("google_resource_name") or "").strip()
    ):
        updates["google_resource_name"] = dup["google_resource_name"]
        master["google_resource_name"] = dup["google_resource_name"]

    first = str(master.get("first_name") or "").strip()
    last = str(master.get("last_name") or "").strip()
    company = str(master.get("company") or "").strip()
    composed = compose_client_name(last, first) or company or str(master.get("name") or "").strip()

    street = str(master.get("address_street") or "").strip()
    postal = str(master.get("postal_code") or "").strip()
    city = str(master.get("city") or "").strip()
    address = "\n".join(
        x for x in [street, " ".join(x for x in [postal, city] if x).strip()] if x
    )

    updates["name"] = composed
    updates["address"] = address
    updates["google_sync_status"] = "À synchroniser"
    updates["google_sync_error"] = ""
    updates["updated_at"] = now().isoformat(timespec="seconds")

    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        con.execute(
            f"UPDATE clients SET {sets} WHERE id=?",
            list(updates.values()) + [master_id]
        )

    repairs_count = con.execute(
        "SELECT COUNT(*) FROM repairs WHERE client_id=?", (duplicate_id,)
    ).fetchone()[0]
    quotes_count = con.execute(
        "SELECT COUNT(*) FROM quotes WHERE client_id=?", (duplicate_id,)
    ).fetchone()[0]

    # Les factures WOPR sont rattachées aux suivis via repairs.invoice_no :
    # déplacer repairs déplace donc aussi l'historique de facturation côté client.
    con.execute("UPDATE repairs SET client_id=? WHERE client_id=?", (master_id, duplicate_id))
    con.execute("UPDATE quotes SET client_id=? WHERE client_id=?", (master_id, duplicate_id))
    con.execute("DELETE FROM clients WHERE id=?", (duplicate_id,))

    return {
        "merged": True,
        "repairs": int(repairs_count or 0),
        "quotes": int(quotes_count or 0),
        "reason": "",
    }


def _merge_one_local_client(con, master_id, duplicate_id):
    """Fusionne un doublon local vers le master, après contrôles de conflit."""
    if master_id == duplicate_id:
        return {"merged": False, "repairs": 0, "quotes": 0}

    master_row = con.execute("SELECT * FROM clients WHERE id=?", (master_id,)).fetchone()
    dup_row = con.execute("SELECT * FROM clients WHERE id=?", (duplicate_id,)).fetchone()
    if not master_row or not dup_row:
        return {"merged": False, "repairs": 0, "quotes": 0}

    master = dict(master_row)
    dup = dict(dup_row)

    if _field_conflict([master.get("email"), dup.get("email")], _email_key):
        return {"merged": False, "repairs": 0, "quotes": 0}
    if _field_conflict([master.get("phone"), dup.get("phone")], normalize_phone):
        return {"merged": False, "repairs": 0, "quotes": 0}

    # Les signatures doivent partager au moins une identité normalisée.
    msig = _contact_name_signature(
        master.get("first_name"), master.get("last_name"), master.get("name"), ""
    )
    dsig = _contact_name_signature(
        dup.get("first_name"), dup.get("last_name"), dup.get("name"), ""
    )
    if not (msig & dsig):
        return {"merged": False, "repairs": 0, "quotes": 0}

    updates = {}
    for field in (
        "first_name", "last_name", "company", "phone", "email",
        "address_street", "postal_code", "city", "notes"
    ):
        if not str(master.get(field) or "").strip() and str(dup.get(field) or "").strip():
            updates[field] = dup[field]
            master[field] = dup[field]

    if (
        not str(master.get("google_resource_name") or "").strip()
        and str(dup.get("google_resource_name") or "").strip()
    ):
        updates["google_resource_name"] = dup["google_resource_name"]
        master["google_resource_name"] = dup["google_resource_name"]

    first = str(master.get("first_name") or "").strip()
    last = str(master.get("last_name") or "").strip()
    composed = compose_client_name(last, first) or str(master.get("name") or "").strip()

    street = str(master.get("address_street") or "").strip()
    postal = str(master.get("postal_code") or "").strip()
    city = str(master.get("city") or "").strip()
    address = "\n".join(
        x for x in [
            street,
            " ".join(x for x in [postal, city] if x).strip()
        ] if x
    )

    updates["name"] = composed
    updates["address"] = address
    updates["google_sync_status"] = "À synchroniser"
    updates["google_sync_error"] = ""
    updates["updated_at"] = now().isoformat(timespec="seconds")

    if updates:
        sets = ", ".join(f"{k}=?" for k in updates)
        con.execute(
            f"UPDATE clients SET {sets} WHERE id=?",
            list(updates.values()) + [master_id]
        )

    repairs_count = con.execute(
        "SELECT COUNT(*) FROM repairs WHERE client_id=?", (duplicate_id,)
    ).fetchone()[0]
    quotes_count = con.execute(
        "SELECT COUNT(*) FROM quotes WHERE client_id=?", (duplicate_id,)
    ).fetchone()[0]

    con.execute("UPDATE repairs SET client_id=? WHERE client_id=?", (master_id, duplicate_id))
    con.execute("UPDATE quotes SET client_id=? WHERE client_id=?", (master_id, duplicate_id))
    con.execute("DELETE FROM clients WHERE id=?", (duplicate_id,))

    return {
        "merged": True,
        "repairs": repairs_count,
        "quotes": quotes_count,
    }


def _local_client_richness(local, repairs_count=0, quotes_count=0):
    filled = sum(
        1 for field in (
            "first_name", "last_name", "company", "phone", "email",
            "address_street", "postal_code", "city", "notes",
            "google_resource_name"
        )
        if str(local.get(field) or "").strip()
    )
    return (repairs_count * 1000) + (quotes_count * 100) + filled


def _identity_key(first_name="", last_name="", legacy_name=""):
    first = _contact_name_normalize(first_name)
    last = _contact_name_normalize(last_name)
    if first or last:
        return f"{first}|{last}"
    return _contact_name_normalize(legacy_name)


def _field_conflict(values, normalizer=lambda x: str(x or "").strip().casefold()):
    nonempty = {normalizer(x) for x in values if str(x or "").strip()}
    nonempty.discard("")
    return len(nonempty) > 1


def find_safe_local_duplicate_groups(con):
    rows = [dict(x) for x in con.execute("SELECT * FROM clients ORDER BY id").fetchall()]

    # One client can have multiple historical spellings; group by exact token signature.
    signature_to_ids = {}
    by_id = {x["id"]: x for x in rows}
    for c in rows:
        for sig in _contact_name_signature(
            c.get("first_name"), c.get("last_name"), c.get("name"), ""
        ):
            if sig:
                signature_to_ids.setdefault(sig, set()).add(c["id"])

    visited = set()
    safe_groups = []

    for sig, ids in signature_to_ids.items():
        ids = set(ids)
        if len(ids) < 2:
            continue

        frozen = tuple(sorted(ids))
        if frozen in visited:
            continue
        visited.add(frozen)

        members = [by_id[x] for x in sorted(ids) if x in by_id]
        if len(members) < 2:
            continue

        if _field_conflict([x.get("email") for x in members], _email_key):
            continue
        if _field_conflict([x.get("phone") for x in members], normalize_phone):
            continue

        stats = {}
        for m in members:
            repairs_count = con.execute(
                "SELECT COUNT(*) FROM repairs WHERE client_id=?", (m["id"],)
            ).fetchone()[0]
            quotes_count = con.execute(
                "SELECT COUNT(*) FROM quotes WHERE client_id=?", (m["id"],)
            ).fetchone()[0]
            stats[m["id"]] = (repairs_count, quotes_count)

        ordered = sorted(
            members,
            key=lambda m: (
                _local_client_richness(
                    m,
                    stats[m["id"]][0],
                    stats[m["id"]][1]
                ),
                -int(m["id"])
            ),
            reverse=True
        )

        safe_groups.append({
            "key": sig,
            "master": ordered[0],
            "duplicates": ordered[1:],
            "repairs_count": stats[ordered[0]["id"]][0],
            "quotes_count": stats[ordered[0]["id"]][1],
        })

    return safe_groups


def merge_safe_local_duplicates():
    backup_database(force=True, tag="avant_fusion_doublons_clients")
    con = db()
    groups = find_safe_local_duplicate_groups(con)

    merged_clients = 0
    moved_repairs = 0
    moved_quotes = 0

    for group in groups:
        master_id = group["master"]["id"]
        for dup in group["duplicates"]:
            result = _merge_one_local_client(con, master_id, dup["id"])
            if result["merged"]:
                merged_clients += 1
                moved_repairs += result["repairs"]
                moved_quotes += result["quotes"]

    con.commit()
    con.close()

    return {
        "groups": len(groups),
        "merged_clients": merged_clients,
        "moved_repairs": moved_repairs,
        "moved_quotes": moved_quotes,
    }


def parse_google_contacts_csv(raw_text):
    """Lit un export CSV Google Contacts et conserve les champs utiles à WOPR."""
    reader = csv.DictReader(io.StringIO(str(raw_text or "")))
    if not reader.fieldnames:
        return []

    required_hint = {"First Name", "Last Name", "Phone 1 - Value", "E-mail 1 - Value"}
    if not any(x in set(reader.fieldnames) for x in required_hint):
        raise ValueError("Ce fichier ne ressemble pas à un export Google Contacts.")

    contacts = []
    for pos, row in enumerate(reader, start=2):
        labels = str(row.get("Labels") or "").strip()
        # Les libellés Google sont conservés pour information ; le groupe cible est configurable.
        # Si Labels est vide partout, on accepte le fichier tel quel.
        raw_first_name = str(row.get("First Name") or "").strip()
        raw_last_name = str(row.get("Last Name") or "").strip()
        organization = str(row.get("Organization Name") or "").strip()

        first_name, last_name = clean_google_contact_name(
            raw_first_name,
            raw_last_name,
            organization
        )

        email = str(row.get("E-mail 1 - Value") or "").strip()
        phone = str(row.get("Phone 1 - Value") or "").strip()

        street = str(row.get("Address 1 - Street") or "").strip()
        postal = str(row.get("Address 1 - Postal Code") or "").strip()
        city = str(row.get("Address 1 - City") or "").strip()
        country = str(row.get("Address 1 - Country") or "").strip()
        notes = str(row.get("Notes") or "").strip()

        display_name = " ".join(x for x in [first_name, last_name] if x).strip() or organization
        if not display_name and not email and not phone:
            continue

        contacts.append({
            "source_position": pos,
            "labels": labels,
            "first_name": first_name,
            "last_name": last_name,
            "organization": organization,
            "display_name": display_name,
            "email": email,
            "phone": phone,
            "address_street": street,
            "postal_code": postal,
            "city": city,
            "country": country,
            "notes": notes,
        })

    return contacts


def analyze_google_csv_contacts(contacts):
    """
    Matching V2.3.25 :
      1) e-mail / téléphone uniques = preuves fortes, prioritaires ;
      2) sinon identité exacte, ordre Prénom/Nom indifférent ;
      3) doublons locaux sûrs sélectionnent la fiche la plus riche.
    """
    con = db()
    local_rows = [dict(x) for x in con.execute("SELECT * FROM clients ORDER BY id").fetchall()]

    local_stats = {}
    for local in local_rows:
        cid = local["id"]
        local_stats[cid] = {
            "repairs": con.execute(
                "SELECT COUNT(*) FROM repairs WHERE client_id=?", (cid,)
            ).fetchone()[0],
            "quotes": con.execute(
                "SELECT COUNT(*) FROM quotes WHERE client_id=?", (cid,)
            ).fetchone()[0],
        }

    con.close()

    email_index = {}
    phone_index = {}
    sig_index = {}

    for local in local_rows:
        cid = local["id"]

        ek = _email_key(local.get("email"))
        if ek:
            email_index.setdefault(ek, []).append(cid)

        pk = normalize_phone(local.get("phone"))
        if pk:
            phone_index.setdefault(pk, []).append(cid)

        for sig in _contact_name_signature(
            local.get("first_name"),
            local.get("last_name"),
            local.get("name"),
            ""
        ):
            sig_index.setdefault(sig, []).append(cid)

    local_by_id = {x["id"]: x for x in local_rows}

    analyzed = []
    summary = {
        "total_source": len(contacts),
        "safe": 0,
        "ambiguous": 0,
        "unmatched": 0,
        "already_complete": 0,
        "will_fill": 0,
        "will_merge": 0,
        "actionable": 0,
    }

    for source in contacts:
        evidence = []
        status = "unmatched"
        local = None
        duplicate_ids = []

        # ---------- Strong evidence first ----------
        strong_sets = []

        ek = _email_key(source.get("email"))
        if ek:
            email_ids = set(email_index.get(ek, []))
            if len(email_ids) == 1:
                strong_sets.append(email_ids)
                evidence.append("e-mail")

        pk = normalize_phone(source.get("phone"))
        if pk:
            phone_ids = set(phone_index.get(pk, []))
            if len(phone_ids) == 1:
                strong_sets.append(phone_ids)
                evidence.append("téléphone")

        strong_ids = set()
        if strong_sets:
            strong_ids = set.union(*strong_sets)

        if len(strong_ids) == 1:
            cid = next(iter(strong_ids))
            local = local_by_id.get(cid)
            status = "safe"

        elif len(strong_ids) > 1:
            # e-mail and phone point to different clients: never guess.
            status = "ambiguous"

        # ---------- Name signature only if no strong conflict ----------
        source_sigs = _contact_name_signature(
            source.get("first_name"),
            source.get("last_name"),
            source.get("display_name"),
            source.get("organization")
        )

        name_ids = set()
        for sig in source_sigs:
            name_ids.update(sig_index.get(sig, []))

        if status == "safe" and local is not None:
            # Other exact-name locals are treated as possible duplicates,
            # but they cannot invalidate a strong e-mail/phone match.
            others = [
                local_by_id[x] for x in name_ids
                if x != local["id"] and x in local_by_id
            ]
            safe_others = []
            for other in others:
                if _field_conflict(
                    [local.get("email"), other.get("email")], _email_key
                ):
                    continue
                if _field_conflict(
                    [local.get("phone"), other.get("phone")], normalize_phone
                ):
                    continue
                safe_others.append(other["id"])

            duplicate_ids = safe_others
            if duplicate_ids:
                evidence.append("doublons locaux")

        elif status == "unmatched" and name_ids:
            candidate_rows = [local_by_id[x] for x in name_ids if x in local_by_id]

            if len(candidate_rows) == 1:
                local = candidate_rows[0]
                status = "safe"
                evidence.append("nom exact")

            elif len(candidate_rows) > 1:
                # Same exact identity and no conflicting phone/email => safe local duplicates.
                conflict_email = _field_conflict(
                    [x.get("email") for x in candidate_rows], _email_key
                )
                conflict_phone = _field_conflict(
                    [x.get("phone") for x in candidate_rows], normalize_phone
                )

                if not conflict_email and not conflict_phone:
                    candidate_rows.sort(
                        key=lambda x: _local_client_richness(
                            x,
                            local_stats[x["id"]]["repairs"],
                            local_stats[x["id"]]["quotes"],
                        ),
                        reverse=True
                    )
                    local = candidate_rows[0]
                    duplicate_ids = [x["id"] for x in candidate_rows[1:]]
                    status = "safe"
                    evidence.extend(["nom exact", "doublons locaux"])
                else:
                    status = "ambiguous"

        # ---------- Fields to complete ----------
        fill = {}
        if local is not None:
            source_first = str(source.get("first_name") or "").strip()
            source_last = str(source.get("last_name") or "").strip()

            if not str(local.get("first_name") or "").strip() and source_first:
                fill["first_name"] = source_first
            if not str(local.get("last_name") or "").strip() and source_last:
                fill["last_name"] = source_last
            if not str(local.get("phone") or "").strip() and source.get("phone"):
                fill["phone"] = str(source.get("phone") or "").strip()
            if not str(local.get("email") or "").strip() and source.get("email"):
                fill["email"] = str(source.get("email") or "").strip()
            if not str(local.get("address_street") or "").strip() and source.get("address_street"):
                fill["address_street"] = str(source.get("address_street") or "").strip()
            if not str(local.get("postal_code") or "").strip() and source.get("postal_code"):
                fill["postal_code"] = str(source.get("postal_code") or "").strip()
            if not str(local.get("city") or "").strip() and source.get("city"):
                fill["city"] = str(source.get("city") or "").strip()
            if not str(local.get("company") or "").strip() and source.get("organization"):
                fill["company"] = str(source.get("organization") or "").strip()

        actionable = bool(fill or duplicate_ids)

        row = dict(source)
        row.update({
            "status": status,
            "local_client_id": local["id"] if local else None,
            "local_name": (
                compose_client_name(local.get("last_name"), local.get("first_name"))
                or local.get("name")
                or ""
            ) if local else "",
            "evidence": list(dict.fromkeys(evidence)),
            "fill": fill,
            "fill_count": len(fill),
            "duplicate_local_ids": duplicate_ids,
            "actionable": actionable,
        })
        analyzed.append(row)

        if status == "safe":
            summary["safe"] += 1
            if fill:
                summary["will_fill"] += 1
            if duplicate_ids:
                summary["will_merge"] += len(duplicate_ids)
            if actionable:
                summary["actionable"] += 1
            else:
                summary["already_complete"] += 1
        elif status == "ambiguous":
            summary["ambiguous"] += 1
        else:
            summary["unmatched"] += 1

    return analyzed, summary


def save_pending_google_csv_import(payload):
    cleanup_pending_imports()
    token = secrets.token_urlsafe(24)
    path = IMPORT_DIR / f"googlecsv_{token}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    session["google_csv_import_token"] = token
    return token


def load_pending_google_csv_import():
    token = session.get("google_csv_import_token", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token or ""):
        return None, None
    path = IMPORT_DIR / f"googlecsv_{token}.json"
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except Exception:
        return None, None


def _email_key(value):
    return (value or "").strip().casefold()


def _name_key(value):
    return re.sub(r"\\s+", " ", (value or "").strip()).casefold()


def build_local_contact_index(rows):
    index = {"email": {}, "phone": {}, "name": {}, "uid": {}}
    for row in rows:
        item = dict(row)
        rid = item.get("id")
        email = _email_key(item.get("email"))
        phone = normalize_phone(item.get("phone"))
        name = _name_key(item.get("name"))
        uid = (item.get("proton_uid") or "").strip()
        if email:
            index["email"].setdefault(email, []).append(rid)
        if phone:
            index["phone"].setdefault(phone, []).append(rid)
        if name:
            index["name"].setdefault(name, []).append(rid)
        if uid:
            index["uid"].setdefault(uid, []).append(rid)
    return index


def google_contacts_bulk_index(service):
    """Indexe une seule fois tous les Google Contacts pour éviter 295 recherches API."""
    index = {"email": {}, "phone": {}, "name": {}, "people": {}}
    token = None
    while True:
        result = service.people().connections().list(
            resourceName="people/me",
            pageSize=1000,
            pageToken=token,
            personFields="names,emailAddresses,phoneNumbers,memberships"
        ).execute()

        for person in result.get("connections", []):
            resource = person.get("resourceName")
            if not resource:
                continue
            names = person.get("names", [])
            display = (names[0].get("displayName") if names else "") or resource
            emails = [(x.get("value") or "").strip() for x in person.get("emailAddresses", [])]
            phones = [(x.get("value") or "").strip() for x in person.get("phoneNumbers", [])]
            groups = set()
            for membership in person.get("memberships", []):
                cg = membership.get("contactGroupMembership", {})
                if cg.get("contactGroupResourceName"):
                    groups.add(cg["contactGroupResourceName"])

            info = {
                "resource_name": resource,
                "display_name": display,
                "emails": emails,
                "phones": phones,
                "groups": list(groups),
            }
            index["people"][resource] = info

            nk = _name_key(display)
            if nk:
                index["name"].setdefault(nk, []).append(resource)
            for email in emails:
                ek = _email_key(email)
                if ek:
                    index["email"].setdefault(ek, []).append(resource)
            for phone in phones:
                pk = normalize_phone(phone)
                if pk:
                    index["phone"].setdefault(pk, []).append(resource)

        token = result.get("nextPageToken")
        if not token:
            break
    return index


def _unique_contact_matches(contact, index, source_phone_counts=None):
    """Retourne les IDs/ressources exacts par UID/email/téléphone sans fusion par simple nom."""
    matches = set()
    reasons = []

    uid = (contact.get("uid") or "").strip()
    if uid and "uid" in index and index["uid"].get(uid):
        matches.update(index["uid"][uid])
        reasons.append("UID Proton")

    for email in contact.get("emails", []):
        ek = _email_key(email)
        vals = index.get("email", {}).get(ek, [])
        if vals:
            matches.update(vals)
            reasons.append("e-mail")

    # Un numéro partagé par plusieurs fiches Proton n'est pas assez sûr pour fusionner automatiquement.
    for phone in contact.get("phones", []):
        pk = normalize_phone(phone)
        if not pk:
            continue
        if source_phone_counts is not None and source_phone_counts.get(pk, 0) > 1:
            continue
        vals = index.get("phone", {}).get(pk, [])
        if vals:
            matches.update(vals)
            reasons.append("téléphone")

    return sorted(matches), sorted(set(reasons))


def analyze_proton_contacts(contacts, google_index=None):
    # Détecte les coordonnées partagées dans le fichier source.
    source_email_counts = {}
    source_phone_counts = {}
    for c in contacts:
        for email in c.get("emails", []):
            ek = _email_key(email)
            if ek:
                source_email_counts[ek] = source_email_counts.get(ek, 0) + 1
        for phone in c.get("phones", []):
            pk = normalize_phone(phone)
            if pk:
                source_phone_counts[pk] = source_phone_counts.get(pk, 0) + 1

    con = db()
    local_rows = con.execute("SELECT * FROM clients ORDER BY id").fetchall()
    con.close()
    local_index = build_local_contact_index(local_rows)

    group_resource = None
    if google_index is not None:
        service = google_service()
        group_resource = google_find_group(service) if service else None

    analyzed = []
    summary = {
        "total": len(contacts),
        "local_existing": 0,
        "local_ambiguous": 0,
        "google_existing": 0,
        "google_ambiguous": 0,
        "google_missing": 0,
        "google_in_group": 0,
        "shared_coordinates": 0,
    }

    for c in contacts:
        local_matches, local_reasons = _unique_contact_matches(c, local_index, source_phone_counts)
        google_matches, google_reasons = ([], [])
        if google_index is not None:
            google_matches, google_reasons = _unique_contact_matches(c, google_index, source_phone_counts)

        shared = []
        for email in c.get("emails", []):
            ek = _email_key(email)
            if ek and source_email_counts.get(ek, 0) > 1:
                shared.append("e-mail partagé")
        for phone in c.get("phones", []):
            pk = normalize_phone(phone)
            if pk and source_phone_counts.get(pk, 0) > 1:
                shared.append("téléphone partagé")

        google_in_group = False
        if len(google_matches) == 1 and group_resource:
            info = google_index["people"].get(google_matches[0], {})
            google_in_group = group_resource in set(info.get("groups", []))

        row = dict(c)
        row.update({
            "local_matches": local_matches,
            "local_reasons": local_reasons,
            "google_matches": google_matches,
            "google_reasons": google_reasons,
            "google_in_group": google_in_group,
            "shared_warnings": sorted(set(shared)),
        })
        analyzed.append(row)

        if len(local_matches) == 1:
            summary["local_existing"] += 1
        elif len(local_matches) > 1:
            summary["local_ambiguous"] += 1

        if google_index is not None:
            if len(google_matches) == 1:
                summary["google_existing"] += 1
                if google_in_group:
                    summary["google_in_group"] += 1
            elif len(google_matches) > 1:
                summary["google_ambiguous"] += 1
            else:
                summary["google_missing"] += 1

        if shared:
            summary["shared_coordinates"] += 1

    return analyzed, summary


def save_pending_proton_import(payload):
    cleanup_pending_imports()
    token = secrets.token_urlsafe(24)
    path = IMPORT_DIR / f"proton_{token}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    session["proton_import_token"] = token
    return token


def load_pending_proton_import():
    token = session.get("proton_import_token", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token or ""):
        return None, None
    path = IMPORT_DIR / f"proton_{token}.json"
    if not path.exists():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), path
    except Exception:
        return None, None


def cleanup_pending_imports():
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 24 * 3600
    for pattern in ("proton_*.json", "googlecsv_*.json"):
        for path in IMPORT_DIR.glob(pattern):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass


def _merge_notes(existing, imported):
    existing = (existing or "").strip()
    imported = (imported or "").strip()
    if not imported:
        return existing
    if not existing:
        return imported
    if imported.casefold() in existing.casefold():
        return existing
    return existing + "\n\n--- Import Proton ---\n" + imported


def google_create_from_proton(service, contact, group_resource):
    if contact.get("first_name") or contact.get("last_name"):
        google_name = {}
        if contact.get("first_name"):
            google_name["givenName"] = contact["first_name"]
        if contact.get("last_name"):
            google_name["familyName"] = contact["last_name"]
        body = {"names": [google_name]}
    else:
        body = {"names": [{"givenName": contact.get("name") or "Client Proton"}]}

    emails = [{"value": x, "type": "home"} for x in contact.get("emails", []) if x]
    phones = [{"value": x, "type": "mobile"} for x in contact.get("phones", []) if x]
    addresses = []
    for adr in contact.get("addresses", []):
        if any(adr.get(k) for k in ("street", "city", "postal_code", "country")):
            addresses.append({
                "streetAddress": adr.get("street", ""),
                "city": adr.get("city", ""),
                "region": adr.get("region", ""),
                "postalCode": adr.get("postal_code", ""),
                "country": adr.get("country", "") or "France",
                "type": "home",
            })

    if emails:
        body["emailAddresses"] = emails
    if phones:
        body["phoneNumbers"] = phones
    if addresses:
        body["addresses"] = addresses
    if contact.get("notes"):
        body["biographies"] = [{"value": contact["notes"], "contentType": "TEXT_PLAIN"}]

    created = service.people().createContact(body=body).execute()
    resource = created.get("resourceName")
    if resource and group_resource:
        try:
            service.contactGroups().members().modify(
                resourceName=group_resource,
                body={"resourceNamesToAdd": [resource]}
            ).execute()
        except HttpError as e:
            if getattr(e.resp, "status", None) not in (400, 409):
                raise
    return resource


def csv_response(filename, rows):
    bio = io.StringIO(newline="")
    writer = csv.writer(bio)
    for row in rows:
        writer.writerow(row)
    data = "\ufeff" + bio.getvalue()
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def vcard_escape(value):
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

@app.route("/master-key/setup", methods=["GET", "POST"])
def master_key_setup():
    """Premier démarrage portable : importer ou créer la clé maître locale."""
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return "Configuration de la clé maître autorisée uniquement depuis le PC local.", 403

    if MASTER_SECRET_FILE.exists():
        try:
            validate_master_secret(MASTER_SECRET_FILE.read_bytes())
            return redirect(url_for("index"))
        except ValueError:
            pass

    if request.method == "POST":
        action = str(request.form.get("action") or "").strip()
        if action == "import":
            uploaded = request.files.get("master_key_file")
            if not uploaded or not uploaded.filename:
                flash("Choisis ton fichier master.key.")
            else:
                try:
                    raw = uploaded.read(4096)
                    install_master_secret(raw)
                    audit_event("MASTER_KEY_IMPORTED", "Clé maître importée sur cette machine", request.remote_addr)
                    flash("Clé maître importée. WOPR peut maintenant déchiffrer tes secrets.")
                    return redirect(url_for("index"))
                except Exception as exc:
                    flash(str(exc))
        elif action == "create":
            try:
                create_master_secret()
                audit_event("MASTER_KEY_CREATED", "Nouvelle clé maître créée sur cette machine", request.remote_addr)
                flash("Nouvelle clé maître créée. Pense à l'exporter et à la sauvegarder séparément.")
                return redirect(url_for("index"))
            except Exception as exc:
                flash(f"Impossible de créer la clé maître : {exc}")

    return render_template(
        "master_key_setup.html",
    )


@app.context_processor
def inject_globals():
    return {
        "config": cfg(),
        "current_year": now().year,
        "app_version": APP_VERSION,
        "pdf_languages": PDF_LANGUAGES,
    }

@app.context_processor
def inject_security_globals():
    return {
        "csrf_token": csrf_token,
        "admin_authenticated": bool(session.get("admin_authenticated")),
        "client_mode": bool(session.get("client_mode")),
    }


@app.before_request
def security_gate():
    endpoint = request.endpoint or ""

    # V2.3.157 — Une installation portable ne fabrique jamais silencieusement
    # une nouvelle clé si master.key manque. Sur le PC local, WOPR demande
    # d'abord d'importer la clé existante (ou d'en créer une pour une vraie
    # nouvelle installation).
    if endpoint == "master_key_setup":
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Configuration de la clé maître autorisée uniquement depuis le PC local.", 403
        return None
    if endpoint != "static" and not MASTER_SECRET_FILE.exists():
        if request.remote_addr not in {"127.0.0.1", "::1"}:
            return "Clé maître WOPR absente sur la machine hôte.", 503
        return redirect(url_for("master_key_setup"))

    # V2.3.52 — vraie sauvegarde quotidienne :
    # si WOPR reste ouvert plusieurs jours, la première requête du nouveau
    # jour crée le backup. backup_database évite automatiquement les doublons.
    if endpoint != "static":
        try:
            backup_database(force=False, tag="quotidien")
        except Exception:
            # Une sauvegarde ne doit jamais bloquer l'utilisation de l'application.
            pass

    # Pages volontairement publiques : ressources statiques et signature client.
    if endpoint in {"static", "sign"}:
        return None

    # La toute première création du PIN ne peut se faire que sur le PC local.
    if not pin_is_configured():
        if endpoint == "admin_setup":
            if request.remote_addr not in {"127.0.0.1", "::1"}:
                return render_template("pin_setup_local_only.html"), 403
        else:
            if request.remote_addr not in {"127.0.0.1", "::1"}:
                return render_template("pin_setup_local_only.html"), 403
            return redirect(url_for("admin_setup"))

    # Protection CSRF de toutes les écritures atelier. La signature publique
    # utilise son token fort dédié et est volontairement exclue ci-dessus.
    if request.method == "POST":
        supplied = request.form.get("_csrf_token", "") or request.headers.get("X-CSRF-Token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not supplied or not secrets.compare_digest(str(supplied), str(expected)):
            abort(400, description="Jeton de sécurité invalide. Recharge la page puis réessaie.")

    if endpoint in {"admin_login", "admin_setup"}:
        return None

    if not session.get("admin_authenticated"):
        return redirect(url_for("admin_login", next=request.full_path if request.query_string else request.path))

    # V2.3.39 — Mode Client :
    # même si l'atelier est authentifié, aucune donnée sensible de l'application
    # n'est accessible pendant une prise en charge devant le client.
    if session.get("client_mode"):
        allowed = {"static", "sign", "admin_lock", "repair_new"}
        current_rid = session.get("client_mode_rid")

        if endpoint in {"repair_detail", "qr_png", "intake_pdf"}:
            try:
                rid = int((request.view_args or {}).get("rid"))
            except Exception:
                rid = None
            if current_rid and rid == int(current_rid):
                allowed.add(endpoint)

        if endpoint not in allowed:
            if request.method == "GET":
                return render_template("client_mode_blocked.html"), 403
            abort(403, description="Action indisponible en Mode Client.")

    session.permanent = True
    return None


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    if pin_is_configured():
        return redirect(url_for("admin_login"))
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        confirm = request.form.get("pin_confirm", "").strip()
        if not valid_pin_format(pin):
            flash(f"Le PIN doit contenir uniquement {PIN_MIN_LENGTH} à {PIN_MAX_LENGTH} chiffres.")
        elif pin != confirm:
            flash("Les deux PIN ne correspondent pas.")
        else:
            write_pin(pin)
            session.clear()
            session["admin_authenticated"] = True
            session.permanent = True
            session["_csrf_token"] = secrets.token_urlsafe(32)
            audit_event("PIN_CREATED", "PIN administrateur initialisé", request.remote_addr)
            flash("PIN administrateur créé. WOPR est maintenant verrouillé.")
            return redirect(url_for("index"))
    return render_template("admin_setup.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_authenticated"):
        return redirect(url_for("index"))
    ip = request.remote_addr or "unknown"
    state = LOGIN_FAILURES.get(ip, {"fails": 0, "blocked_until": 0.0})
    wait = max(0, int(state.get("blocked_until", 0) - time.time()))
    if request.method == "POST":
        if wait > 0:
            flash(f"Trop de tentatives. Réessaie dans {wait} seconde(s).")
            return render_template("admin_login.html", wait=wait), 429
        pin = request.form.get("pin", "").strip()
        if read_pin_hash() and check_password_hash(read_pin_hash(), pin):
            LOGIN_FAILURES.pop(ip, None)
            next_url = safe_next_url(request.form.get("next"))
            session.clear()
            session["admin_authenticated"] = True
            session.permanent = True
            session["_csrf_token"] = secrets.token_urlsafe(32)
            audit_event("LOGIN_OK", "Connexion PIN réussie", ip)
            return redirect(next_url)
        state["fails"] = int(state.get("fails", 0)) + 1
        if state["fails"] >= PIN_MAX_ATTEMPTS:
            state["blocked_until"] = time.time() + PIN_BLOCK_SECONDS
            state["fails"] = 0
        LOGIN_FAILURES[ip] = state
        audit_event("LOGIN_FAIL", "PIN incorrect", ip)
        flash("PIN incorrect.")
    return render_template("admin_login.html", wait=wait, next_url=safe_next_url(request.args.get("next")))


@app.route("/admin/lock", methods=["POST"])
def admin_lock():
    audit_event("LOCK", "Verrouillage manuel", request.remote_addr)
    session.clear()
    return redirect(url_for("admin_login", next=url_for("atelier_dashboard")))


@app.route("/security", methods=["GET", "POST"])
def security_page():
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "change_pin":
            current = request.form.get("current_pin", "").strip()
            new_pin = request.form.get("new_pin", "").strip()
            confirm = request.form.get("new_pin_confirm", "").strip()
            if not check_password_hash(read_pin_hash(), current):
                flash("PIN actuel incorrect.")
            elif not valid_pin_format(new_pin):
                flash(f"Le nouveau PIN doit contenir {PIN_MIN_LENGTH} à {PIN_MAX_LENGTH} chiffres.")
            elif new_pin != confirm:
                flash("Les deux nouveaux PIN ne correspondent pas.")
            else:
                write_pin(new_pin)
                audit_event("PIN_CHANGED", "PIN administrateur modifié", request.remote_addr)
                flash("PIN modifié.")
        elif action == "backup":
            path = backup_database(force=True, tag="manuel")
            audit_event("BACKUP", path.name if path else "", request.remote_addr)
            flash("Sauvegarde locale créée." if path else "Aucune base à sauvegarder.")
        elif action == "restore_backup":
            backup_name = request.form.get("backup_name", "").strip()
            if request.form.get("confirm_restore") != "1":
                flash("Restauration annulée : confirmation absente.")
            else:
                try:
                    source, safety = restore_database_backup(backup_name)
                    audit_event(
                        "BACKUP_RESTORE",
                        f"Sauvegarde restaurée : {source.name}; sécurité : {safety.name}",
                        request.remote_addr
                    )
                    flash(
                        f"Sauvegarde {source.name} ouverte dans WOPR. "
                        f"L'ancienne base a été sauvegardée sous {safety.name}."
                    )
                except Exception as exc:
                    audit_event("BACKUP_RESTORE_ERROR", type(exc).__name__, request.remote_addr)
                    flash(f"Impossible de restaurer cette sauvegarde : {exc}")
        elif action == "master_key_export":
            if not MASTER_SECRET_FILE.exists():
                flash("Aucune clé maître locale à exporter.")
            else:
                try:
                    raw = validate_master_secret(MASTER_SECRET_FILE.read_bytes())
                    audit_event("MASTER_KEY_EXPORTED", "Clé maître exportée manuellement", request.remote_addr)
                    response = Response(raw + b"\n", mimetype="application/octet-stream")
                    response.headers["Content-Disposition"] = 'attachment; filename="master.key"'
                    response.headers["Cache-Control"] = "no-store"
                    return response
                except Exception as exc:
                    flash(f"Impossible d'exporter la clé maître : {exc}")
        elif action == "invoice_logo_upload":
            storage = request.files.get("invoice_logo")
            if not storage or not str(storage.filename or "").strip():
                flash("Choisis une image pour le logo des factures.")
            else:
                suffix = Path(str(storage.filename)).suffix.lower()
                if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                    flash("Format de logo non pris en charge. Utilise PNG, JPG/JPEG ou WebP.")
                else:
                    try:
                        img = Image.open(storage.stream)
                        img = ImageOps.exif_transpose(img)
                        img.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                            img = img.convert("RGBA")
                        else:
                            img = img.convert("RGB")
                        PRIVATE_ASSETS.mkdir(parents=True, exist_ok=True)
                        tmp = _PRIVATE_LOGO_INVOICE.with_suffix(".tmp.png")
                        img.save(tmp, format="PNG", optimize=True)
                        os.replace(tmp, _PRIVATE_LOGO_INVOICE)
                        audit_event("INVOICE_LOGO_UPDATED", f"source={Path(storage.filename).name}", request.remote_addr)
                        flash("Logo des factures enregistré.")
                    except Exception as exc:
                        flash(f"Image de logo invalide : {exc}")
        elif action == "invoice_logo_remove":
            try:
                _PRIVATE_LOGO_INVOICE.unlink(missing_ok=True)
                audit_event("INVOICE_LOGO_REMOVED", "Logo facture supprimé", request.remote_addr)
                flash("Logo des factures supprimé. Les PDF seront générés sans logo.")
            except Exception as exc:
                flash(f"Impossible de supprimer le logo : {exc}")
        elif action == "smtp_save":
            current = read_smtp_settings()
            token = request.form.get("smtp_token", "").strip()
            if token:
                current["token"] = token
            current.update({
                "enabled": request.form.get("smtp_enabled") == "on",
                "host": request.form.get("smtp_host", "smtp.protonmail.ch").strip() or "smtp.protonmail.ch",
                "port": int(request.form.get("smtp_port", "587") or 587),
                "security": request.form.get("smtp_security", "starttls").strip().lower() or "starttls",
                "username": request.form.get("smtp_username", "").strip(),
                "sender_email": request.form.get("smtp_sender_email", "").strip(),
                "sender_name": request.form.get("smtp_sender_name", "").strip() or str(cfg().get("business_name") or "WOPR").strip() or "WOPR",
            })
            write_smtp_settings(current)
            audit_event("SMTP_SETTINGS", "Configuration SMTP Proton mise à jour", request.remote_addr)
            flash("Configuration SMTP Proton enregistrée localement.")
    backups = sorted(
        [p for p in BACKUP_DIR.iterdir() if p.is_file() and not p.name.startswith(".")],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    ) if BACKUP_DIR.exists() else []
    smtp_settings = read_smtp_settings()
    business = cfg()
    return render_template(
        "security.html",
        backups=backups[:10],
        session_hours=ADMIN_SESSION_HOURS,
        smtp_settings=smtp_settings,
        smtp_token_configured=bool(smtp_settings.get("token")),
        master_key_configured=MASTER_SECRET_FILE.exists(),
        portability=portability_diagnostics(),
        business_email=str(business.get("email") or "").strip(),
        business_name=str(business.get("business_name") or "WOPR").strip() or "WOPR",
        invoice_logo_configured=_PRIVATE_LOGO_INVOICE.is_file(),
    )


@app.get("/security/invoice-logo")
def security_invoice_logo_preview():
    logo = invoice_logo_path()
    if not logo:
        abort(404)
    response = send_file(logo, mimetype="image/png", as_attachment=False)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def _xml_local_name(tag):
    return str(tag or "").split("}")[-1].split(":")[-1]


def _xml_first_text(root, names):
    wanted = {str(x).casefold() for x in names}
    for elem in root.iter():
        if _xml_local_name(elem.tag).casefold() in wanted:
            text = " ".join("".join(elem.itertext()).split())
            if text:
                return text
    return ""


def _xml_all_text(root, names):
    wanted = {str(x).casefold() for x in names}
    values = []
    for elem in root.iter():
        if _xml_local_name(elem.tag).casefold() in wanted:
            text = " ".join("".join(elem.itertext()).split())
            if text and text not in values:
                values.append(text)
    return values


def _xml_decimal(text):
    text = str(text or "").strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return round(float(m.group(0)), 2)
    except Exception:
        return None


def _xml_date(text):
    text = str(text or "").strip()
    if not text:
        return ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"\b(\d{4})(\d{2})(\d{2})\b", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""



def cleanup_exact_supplier_document_duplicates():
    """V2.3.95 — supprime uniquement les doublons *strictement identiques* déjà créés.

    Le fichier canonique est le plus ancien (donc en pratique celui que Foul avait déjà
    rangé manuellement). Toutes les lignes Achats/Ventes qui pointaient vers une copie
    sont repointées vers ce fichier avant suppression. Aucun rapprochement approximatif.
    """
    con = db()
    key = "v2395_exact_supplier_duplicates_cleanup_v1"
    if con.execute("SELECT 1 FROM app_meta WHERE key=?", (key,)).fetchone():
        con.close()
        return 0

    removed = 0
    if FACTURES_ROOT.exists():
        for folder in FACTURES_ROOT.rglob("Fournisseurs"):
            if not folder.is_dir():
                continue
            files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".xml", ".jpg", ".jpeg", ".png"}]
            groups = {}
            for path in files:
                try:
                    raw = path.read_bytes()
                except Exception:
                    continue
                signature = (len(raw), raw)
                groups.setdefault(signature, []).append(path)

            for same_files in groups.values():
                if len(same_files) < 2:
                    continue
                # Le document manuel existait normalement avant la copie créée par l'API.
                same_files.sort(key=lambda x: (x.stat().st_mtime, " - " in x.stem, len(x.name), x.name.casefold()))
                canonical = same_files[0]
                canonical_rel = str(canonical.relative_to(FOULFIX_ROOT))
                for duplicate in same_files[1:]:
                    duplicate_rel = str(duplicate.relative_to(FOULFIX_ROOT))
                    con.execute(
                        "UPDATE ledger_entries SET document_path=?, updated_at=? WHERE document_path=?",
                        (canonical_rel, now().isoformat(timespec="seconds"), duplicate_rel),
                    )
                    try:
                        duplicate.unlink()
                        removed += 1
                    except Exception:
                        pass

    con.execute(
        "INSERT OR REPLACE INTO app_meta(key,value,updated_at) VALUES(?,?,?)",
        (key, str(removed), now().isoformat(timespec="seconds")),
    )
    con.commit()
    con.close()
    return removed


def parse_supplier_invoice_xml(file_bytes, filename="facture.xml"):
    """Lecture tolérante des XML Factur-X/CII et UBL."""
    try:
        root = ET.fromstring(file_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML invalide : {exc}") from exc

    invoice_no = ""
    for parent in root.iter():
        lname = _xml_local_name(parent.tag)
        if lname in {"ExchangedDocument", "Invoice"}:
            for child in list(parent):
                if _xml_local_name(child.tag) == "ID":
                    invoice_no = " ".join("".join(child.itertext()).split())
                    if invoice_no:
                        break
        if invoice_no:
            break
    if not invoice_no:
        invoice_no = _xml_first_text(root, ["InvoiceNumber", "DocumentNumber", "ID"])

    invoice_date = ""
    for key in ("IssueDate", "InvoiceDate", "IssueDateTime", "DateTimeString"):
        value = _xml_first_text(root, [key])
        invoice_date = _xml_date(value)
        if invoice_date:
            break

    supplier = ""
    for party_name in ("SellerTradeParty", "AccountingSupplierParty", "SellerSupplierParty"):
        for elem in root.iter():
            if _xml_local_name(elem.tag) != party_name:
                continue
            supplier = _xml_first_text(elem, ["Name", "RegistrationName", "PartyName"])
            if supplier:
                break
        if supplier:
            break
    if not supplier:
        supplier = _xml_first_text(root, ["SellerName", "SupplierName", "RegistrationName"])

    amount_ttc = None
    for key in ("GrandTotalAmount", "TaxInclusiveAmount", "PayableAmount"):
        for value in _xml_all_text(root, [key]):
            parsed = _xml_decimal(value)
            if parsed is not None:
                amount_ttc = parsed
                break
        if amount_ttc is not None:
            break

    currency = ""
    for elem in root.iter():
        code = elem.attrib.get("currencyID") or elem.attrib.get("currencyId")
        if code:
            currency = str(code).strip().upper()
            break
    if not currency:
        currency = _xml_first_text(root, ["InvoiceCurrencyCode"])

    if not invoice_date:
        raise ValueError("Date de facture introuvable dans le XML.")
    if not supplier:
        raise ValueError("Fournisseur introuvable dans le XML.")
    if amount_ttc is None:
        raise ValueError("Montant TTC introuvable dans le XML.")

    return {
        "invoice_no": invoice_no or Path(filename).stem,
        "entry_date": invoice_date,
        "party": supplier,
        "amount_ttc": amount_ttc,
        "currency": currency or "EUR",
    }


def import_supplier_xml_to_ledger(storage):
    filename = str(storage.filename or "").strip()
    if not filename.lower().endswith(".xml"):
        raise ValueError("Seuls les fichiers XML sont acceptés.")

    raw = storage.read()
    if not raw:
        raise ValueError("Fichier vide.")

    info = parse_supplier_invoice_xml(raw, filename)

    con = db()
    duplicate = con.execute("""
        SELECT id FROM ledger_entries
        WHERE operation='Achat'
          AND lower(trim(COALESCE(party,'')))=lower(trim(?))
          AND lower(trim(COALESCE(invoice_no,'')))=lower(trim(?))
          AND entry_date=?
        LIMIT 1
    """, (info["party"], info["invoice_no"], info["entry_date"])).fetchone()

    if duplicate:
        con.close()
        return {"status": "duplicate", **info}

    created = now().isoformat(timespec="seconds")
    remarks = "Import Abby — facture électronique XML"
    if info["currency"] and info["currency"] != "EUR":
        remarks += f" — devise {info['currency']}"

    cur = con.execute("""
        INSERT INTO ledger_entries(
            operation, party, entry_date, description, amount_ttc,
            payment_type, invoice_no, remarks, created_at, updated_at
        )
        VALUES('Achat',?,?,?,?,?,?,?,?,?)
    """, (
        info["party"],
        info["entry_date"],
        "Facture fournisseur",
        info["amount_ttc"],
        "",
        info["invoice_no"],
        remarks,
        created,
        created,
    ))
    entry_id = int(cur.lastrowid)
    con.commit()
    con.close()

    folder = year_month_folder(
        FACTURES_ROOT, info["entry_date"], supplier=True, create=True
    )
    base_name = safe_document_name(f"{info['party']}_{info['invoice_no']}.xml")
    dest = folder / base_name
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        n = 2
        while (folder / f"{stem}_{n}{suffix}").exists():
            n += 1
        dest = folder / f"{stem}_{n}{suffix}"
    dest.write_bytes(raw)
    try:
        con = db()
        con.execute("""
            UPDATE ledger_entries
            SET document_path=?, document_original_name=?, updated_at=?
            WHERE id=?
        """, (str(dest.relative_to(FOULFIX_ROOT)), filename, now().isoformat(timespec="seconds"), entry_id))
        con.commit()
        con.close()
    except Exception:
        pass

    return {"status": "created", "entry_id": entry_id, "saved_path": str(dest), **info}


@app.route("/abby")
def abby_page():
    settings = read_abby_settings()
    con = db()
    stats = con.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN COALESCE(abby_id,'')<>'' THEN 1 ELSE 0 END) AS linked,
            SUM(CASE WHEN abby_sync_status='erreur' THEN 1 ELSE 0 END) AS errors
        FROM clients
    """).fetchone()
    recent_errors = con.execute("""
        SELECT id,name,company,abby_sync_error
        FROM clients
        WHERE abby_sync_status='erreur'
          AND COALESCE(abby_sync_error,'')<>''
        ORDER BY COALESCE(abby_synced_at,'') DESC, id DESC
        LIMIT 10
    """).fetchall()
    con.close()

    safe_settings = dict(settings)
    safe_settings["api_key"] = ""
    return render_template(
        "abby.html",
        abby=safe_settings,
        api_key_configured=bool(settings.get("api_key")),
        stats=stats,
        recent_errors=recent_errors,
        business_name=str(cfg().get("business_name") or "WOPR").strip() or "WOPR",
    )



@app.route("/abby/import-fournisseurs", methods=["POST"])
def abby_import_supplier_invoices():
    files = request.files.getlist("supplier_xml")
    files = [f for f in files if f and str(f.filename or "").strip()]
    if not files:
        flash("Sélectionne au moins une facture XML Abby.")
        return redirect(url_for("abby_page"))

    if len(files) > 100:
        flash("Maximum 100 fichiers par import.")
        return redirect(url_for("abby_page"))

    backup_database(force=True, tag="avant_import_abby_fournisseurs")

    created = 0
    duplicates = 0
    errors = []
    last_year = now().year

    for storage in files:
        try:
            result = import_supplier_xml_to_ledger(storage)
            last_year = int(result["entry_date"][:4])
            if result["status"] == "duplicate":
                duplicates += 1
            else:
                created += 1
        except Exception as exc:
            errors.append(f"{storage.filename}: {exc}")

    details = f"{created} importée(s), {duplicates} doublon(s), {len(errors)} erreur(s)"
    audit_event("ABBY_SUPPLIER_XML_IMPORT", details, request.remote_addr)

    if errors:
        preview = " | ".join(errors[:3])
        if len(errors) > 3:
            preview += f" | +{len(errors)-3} autre(s)"
        flash(f"Import Abby : {details}. {preview}")
    else:
        flash(f"Import Abby : {details}.")

    return redirect(url_for("achats_ventes_page", year=last_year))


@app.route("/abby/api-key/reveal", methods=["POST"])
def abby_api_key_reveal():
    """Révèle la clé uniquement sur demande explicite depuis une session atelier authentifiée."""
    settings = read_abby_settings()
    api_key = str(settings.get("api_key") or "")
    audit_event("ABBY_API_KEY_REVEAL", "Clé API affichée à l'écran", request.remote_addr)
    return jsonify({"api_key": api_key})


@app.route("/abby/settings", methods=["POST"])
def abby_settings_save():
    current = read_abby_settings()
    api_key = request.form.get("abby_api_key", "").strip()
    if api_key:
        current["api_key"] = api_key
    current["enabled"] = request.form.get("abby_enabled") == "on"
    current["base_url"] = ABBY_API_BASE
    write_abby_settings(current)
    audit_event("ABBY_SETTINGS", "Configuration Abby mise à jour", request.remote_addr)
    flash("Configuration Abby enregistrée localement.")
    return redirect(url_for("abby_page"))


@app.route("/abby/test", methods=["POST"])
def abby_test():
    settings = read_abby_settings()
    stamp = now().isoformat(timespec="seconds")
    try:
        contacts = abby_request(
            "GET", "/contacts",
            query={"page": 1, "limit": 1, "archived": "false"}
        )
        organizations = abby_request(
            "GET", "/organizations",
            query={"page": 1, "limit": 1, "archived": "false"}
        )
        c_total = int(contacts.get("totalDocs") or 0) if isinstance(contacts, dict) else 0
        o_total = int(organizations.get("totalDocs") or 0) if isinstance(organizations, dict) else 0
        message = f"Connexion Abby OK — {c_total} contact(s), {o_total} entreprise(s)."
        settings.update({
            "last_test_at": stamp,
            "last_test_ok": True,
            "last_test_message": message,
        })
        write_abby_settings(settings)
        audit_event("ABBY_TEST_OK", message, request.remote_addr)
        flash(message)
    except Exception as exc:
        message = str(exc)
        settings.update({
            "last_test_at": stamp,
            "last_test_ok": False,
            "last_test_message": message,
        })
        write_abby_settings(settings)
        audit_event("ABBY_TEST_ERROR", type(exc).__name__, request.remote_addr)
        flash(f"Échec connexion Abby : {message}")
    return redirect(url_for("abby_page"))


@app.route("/abby/sync-clients", methods=["POST"])
def abby_sync_clients():
    settings = read_abby_settings()
    try:
        summary = sync_clients_to_abby()
        stamp = now().isoformat(timespec="seconds")
        text = (
            f"{summary['created']} créé(s), {summary['linked']} relié(s), "
            f"{summary['already']} déjà synchronisé(s), "
            f"{summary['skipped']} ignoré(s), {summary['errors']} erreur(s)."
        )
        settings["last_sync_at"] = stamp
        settings["last_sync_summary"] = text
        write_abby_settings(settings)
        audit_event("ABBY_SYNC_CLIENTS", text, request.remote_addr)
        flash(f"Synchronisation Abby terminée : {text}")
    except Exception as exc:
        audit_event("ABBY_SYNC_CLIENTS_ERROR", type(exc).__name__, request.remote_addr)
        flash(f"Synchronisation Abby impossible : {exc}")
    return redirect(url_for("abby_page"))


@app.route("/atelier")
def atelier_dashboard():
    """Vue synthétique de l'atelier, sans modifier le Suivi historique."""
    today = now().date()
    current_year = today.year
    current_month = today.month
    month_prefix = f"{current_year:04d}-{current_month:02d}"

    con = db()

    # Dossiers réellement présents dans l'atelier : on exclut les factures simples
    # et les anciennes lignes comptables « Paiement du… » qui ne représentent pas du matériel.
    active_rows = con.execute("""
        SELECT r.id, r.status, r.problem, r.received_date, r.finished_at, r.returned_at,
               r.invoice_no, r.accounting_status, r.accounting_service_amount,
               r.accounting_goods_amount, r.service_amount, r.goods_amount,
               c.first_name AS client_first_name, c.last_name AS client_last_name,
               c.name AS client_name
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE COALESCE(r.simple_invoice,0)=0
          AND lower(trim(COALESCE(r.problem,''))) NOT LIKE 'paiement du%'
        ORDER BY r.received_date DESC, r.id DESC
    """).fetchall()

    en_cours_statuses = {"Reçu", "Diagnostic", "En attente accord", "En attente pièce", "En réparation"}
    en_cours = [r for r in active_rows if str(r["status"] or "") in en_cours_statuses]
    attente_piece = [r for r in active_rows if str(r["status"] or "") == "En attente pièce"]
    a_restituer = [r for r in active_rows if str(r["status"] or "") == "Terminé"]

    # Dossiers actifs anciens : information de pilotage, sans imposer de délai métier.
    # On signale simplement les dossiers encore actifs reçus depuis 14 jours ou plus.
    overdue = []
    for r in en_cours:
        raw_date = str(r["received_date"] or "")[:10]
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
            days = max(0, (today - d).days)
        except Exception:
            days = 0
        if days >= 14:
            item = dict(r)
            item["days_open"] = days
            overdue.append(item)
    overdue.sort(key=lambda x: x["days_open"], reverse=True)

    reparations_mois = [
        r for r in active_rows
        if str(r["received_date"] or "")[:7] == month_prefix
    ]

    # CA encaissé du mois : même source de vérité que CA / Déclarations.
    ca_row = con.execute("""
        SELECT COALESCE(SUM(accounting_service_amount),0) AS service,
               COALESCE(SUM(accounting_goods_amount),0) AS goods
        FROM repairs
        WHERE accounting_year=? AND accounting_month=?
    """, (current_year, current_month)).fetchone()
    ca_month = float(ca_row["service"] or 0) + float(ca_row["goods"] or 0)

    # Impayés : exactement la même logique que la page Factures, une seule fois par facture.
    # Cela évite de compter plusieurs lignes techniques / historiques d'une même facture.
    invoice_rows = con.execute("""
        SELECT r.*,
               c.name AS client_name, c.first_name AS client_first_name,
               c.last_name AS client_last_name,
               (
                   SELECT COALESCE(SUM(COALESCE(il.quantity,0) * COALESCE(il.unit_price,0)), 0)
                   FROM invoice_lines il
                   WHERE il.repair_id=r.id
               ) AS invoice_lines_total
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE COALESCE(trim(r.invoice_no),'')<>''
        ORDER BY r.id
    """).fetchall()

    unpaid_groups = {}
    for raw in invoice_rows:
        x = dict(raw)
        key = (x["client_id"], x["invoice_no"])
        unpaid_groups.setdefault(key, []).append(x)

    unpaid_rows = []
    for members in unpaid_groups.values():
        # La page Factures considère la facture payée dès qu'une des lignes du groupe est payée.
        if any(bool(x.get("paid")) for x in members):
            continue

        representative = next((x for x in members if not x.get("legacy_imported")), None) or max(
            members, key=lambda x: (str(x.get("received_date") or ""), int(x.get("id") or 0))
        )

        total_candidates = []
        edited_line_totals = []
        for x in members:
            line_total = float(x.get("invoice_lines_total") or 0)
            if line_total > 0:
                edited_line_totals.append(line_total)
            total_candidates.extend([
                line_total,
                float(x.get("service_amount") or 0) + float(x.get("goods_amount") or 0),
                float(x.get("accounting_service_amount") or 0) + float(x.get("accounting_goods_amount") or 0),
                payment_amount_from_text(x.get("payment_method")),
            ])

        invoice_total = max(edited_line_totals) if edited_line_totals else max(total_candidates or [0.0])
        item = dict(representative)
        item["invoice_total"] = invoice_total
        unpaid_rows.append(item)

    unpaid_rows.sort(key=lambda r: (str(r.get("received_date") or ""), int(r.get("id") or 0)))
    unpaid_total = sum(float(r.get("invoice_total") or 0) for r in unpaid_rows)

    # À surveiller : terminé depuis >= 7 jours. La date de fin est privilégiée,
    # sinon la date de réception sert de filet pour l'ancien historique importé.
    watch = []
    for r in a_restituer:
        raw_date = str(r["finished_at"] or r["received_date"] or "")[:10]
        try:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()
            days = max(0, (today - d).days)
        except Exception:
            days = 0
        if days >= 7:
            item = dict(r)
            item["days_waiting"] = days
            watch.append(item)
    watch.sort(key=lambda x: x["days_waiting"], reverse=True)

    con.close()

    return render_template(
        "atelier.html",
        current_year=current_year,
        current_month=current_month,
        month_name=ledger_month_name(current_month),
        en_cours_count=len(en_cours),
        attente_piece_count=len(attente_piece),
        overdue_count=len(overdue),
        overdue_rows=overdue[:10],
        a_restituer_count=len(a_restituer),
        unpaid_count=len(unpaid_rows),
        unpaid_total=unpaid_total,
        ca_month=ca_month,
        reparations_mois_count=len(reparations_mois),
        watch=watch[:10],
        unpaid_rows=unpaid_rows[:10],
        recent_rows=active_rows[:8],
        business_name=str(cfg().get("business_name") or "WOPR").strip() or "WOPR",
    )



@app.get("/_w/7f3a9c")
def wopr_end_sequence_audio():
    """Sample audio privé de l'easter egg WOPR."""
    sample = PRIVATE_ASSETS / ".wopr_7f3a9c.bin"
    if not sample.exists():
        abort(404)
    return send_file(
        sample,
        mimetype="audio/mpeg",
        as_attachment=False,
        download_name="sequence.bin",
        conditional=True,
        max_age=3600,
    )

@app.route("/")
def home():
    """Accueil WOPR : le tableau de bord Atelier devient la page principale."""
    return redirect(url_for("atelier_dashboard"))


@app.route("/suivi")
def index():
    to_return_only = request.args.get("a_restituer") == "1"
    client_search = str(request.args.get("q") or "").strip()
    client_search_folded = client_search.casefold()
    try:
        requested_year = int(request.args.get("year") or now().year)
    except Exception:
        requested_year = now().year

    con = db()

    # V2.3.138 — les dossiers "Laissé pour pièces" doivent avoir une date de clôture
    # afin que le PDF de suivi affiche bien la date finale.
    con.execute("""
        UPDATE repairs
        SET finished_at=?
        WHERE status='Laissé pour pièces'
          AND COALESCE(trim(finished_at),'')=''
    """, (now().isoformat(timespec="seconds"),))

    # V2.3.136 — invariant métier :
    # "Laissé pour pièces" = aucune facture, aucun paiement, aucun CA, aucun impayé.
    # Corrige aussi automatiquement les dossiers déjà passés dans cet état avec
    # d'anciens montants / statut comptable restés en base.
    con.execute("""
        UPDATE repairs
        SET service_amount=0,
            goods_amount=0,
            payment_method='',
            payment_mode='',
            payment_detail='',
            paid=0,
            invoice_no=NULL,
            accounting_year=NULL,
            accounting_month=NULL,
            accounting_date='',
            accounting_status='normal',
            accounting_service_amount=0,
            accounting_goods_amount=0,
            service_description='',
            goods_description='',
            legacy_invoice_text=''
        WHERE status='Laissé pour pièces'
          AND (
              COALESCE(service_amount,0)<>0
              OR COALESCE(goods_amount,0)<>0
              OR COALESCE(trim(invoice_no),'')<>''
              OR COALESCE(paid,0)<>0
              OR COALESCE(accounting_status,'normal')<>'normal'
              OR COALESCE(accounting_service_amount,0)<>0
              OR COALESCE(accounting_goods_amount,0)<>0
          )
    """)
    con.execute("""
        DELETE FROM invoice_lines
        WHERE repair_id IN (
            SELECT id FROM repairs WHERE status='Laissé pour pièces'
        )
    """)
    con.commit()

    # Garde-fou : si la migration n'a jamais été exécutée (lancement atypique),
    # la page Suivi la déclenche.
    inserted_now = seed_legacy_followups(con)
    if inserted_now:
        con.commit()
        flash(f"Historique Suivi importé : {inserted_now} ligne(s).")

    year_rows = con.execute("""
        SELECT DISTINCT COALESCE(
            followup_year,
            CAST(substr(received_date,1,4) AS INTEGER)
        ) AS y
        FROM repairs
        WHERE received_date IS NOT NULL
          AND COALESCE(simple_invoice,0)=0
        ORDER BY y DESC
    """).fetchall()
    available_years = [int(x["y"]) for x in year_rows if x["y"]]

    if available_years and requested_year not in available_years:
        requested_year = max(available_years)

    rows = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name,
               c.phone client_phone
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE COALESCE(r.simple_invoice,0)=0
          AND COALESCE(
            r.followup_year,
            CAST(substr(r.received_date,1,4) AS INTEGER)
        )=?
        ORDER BY
            COALESCE(r.followup_month, CAST(substr(r.received_date,6,2) AS INTEGER)) DESC,
            r.received_date DESC,
            CASE WHEN r.legacy_source_row IS NULL THEN 999999 ELSE r.legacy_source_row END DESC,
            r.id DESC
    """, (requested_year,)).fetchall()

    # V2.3.84 : recherche client directement dans le Suivi.
    # On filtre avant la construction mensuelle afin que les compteurs et la vue
    # « À restituer » correspondent exactement aux lignes affichables.
    if client_search_folded:
        filtered_rows = []
        for row in rows:
            haystack = " ".join([
                str(row["client_first_name"] or ""),
                str(row["client_last_name"] or ""),
                str(row["client_name"] or ""),
                str(row["client_phone"] or ""),
            ]).casefold()
            if client_search_folded in haystack:
                filtered_rows.append(row)
        rows = filtered_rows

    # V2.3.82 : un encaissement effectué un autre mois que le suivi doit être
    # visible dans le mois d'encaissement, sans créer une seconde écriture comptable.
    # On fabrique donc uniquement une ligne d'affichage virtuelle.
    cross_month_payments = {}
    for source_row in rows:
        if to_return_only:
            continue
        ay = source_row["accounting_year"]
        am = source_row["accounting_month"]
        fm = source_row["followup_month"]
        fy = source_row["followup_year"]
        if not (ay and am and source_row["paid"]):
            continue
        if int(ay) != requested_year:
            continue
        if int(fy or requested_year) == int(ay) and int(fm or 0) == int(am):
            continue
        virtual = dict(source_row)
        virtual["_virtual_payment"] = True
        virtual["_source_followup_month"] = fm
        virtual["_display_total"] = float(source_row["accounting_service_amount"] or 0) + float(source_row["accounting_goods_amount"] or 0)
        virtual["_display_payment_mode"] = source_row["payment_mode"] or ""
        virtual["_display_accounting_date"] = source_row["accounting_date"] or ""
        virtual["problem"] = f"Paiement du {str(source_row['received_date'] or '')[8:10]}/{str(source_row['received_date'] or '')[5:7]}/{str(source_row['received_date'] or '')[0:4]}"
        cross_month_payments.setdefault(int(am), []).append(virtual)

    # V2.3.19 : les anciennes lignes "Paiement du ..." servent au CA,
    # mais ne doivent pas remplacer le dossier d'origine dans le Suivi.
    history_invoice_groups = {}
    for row in rows:
        item = dict(row)
        invoice_no = str(item.get("invoice_no") or "").strip()
        if not invoice_no:
            continue

        key = (item.get("client_id"), invoice_no)
        group = history_invoice_groups.setdefault(key, {
            "total": 0.0,
            "modes": [],
            "accounting_date": "",
            "has_origin": False,
        })

        problem_text = str(item.get("problem") or "").strip().casefold()
        if not problem_text.startswith("paiement du"):
            group["has_origin"] = True

        group["total"] = max(
            float(group["total"] or 0),
            float(item.get("service_amount") or 0) + float(item.get("goods_amount") or 0),
            float(item.get("accounting_service_amount") or 0) + float(item.get("accounting_goods_amount") or 0),
            payment_amount_from_text(item.get("payment_method")),
        )

        structured_mode = normalize_payment_mode(item.get("payment_mode"))
        if structured_mode and structured_mode not in group["modes"]:
            group["modes"].append(structured_mode)

        for detected_mode in payment_modes_from_text(item.get("payment_method")):
            if detected_mode not in group["modes"]:
                group["modes"].append(detected_mode)

        accounting_date = str(item.get("accounting_date") or "")[:10]
        if accounting_date and accounting_date > str(group["accounting_date"] or ""):
            group["accounting_date"] = accounting_date

    # V2.3.84 : le compteur « À restituer » doit compter exactement les dossiers
    # qui peuvent réellement être affichés. Les anciennes lignes ODS « Paiement du… »
    # sont des écritures comptables, pas du matériel encore présent à l'atelier.
    to_return_count = 0
    for row in rows:
        if row["status"] != "Terminé":
            continue
        invoice_no = str(row["invoice_no"] or "").strip()
        group = history_invoice_groups.get((row["client_id"], invoice_no)) if invoice_no else None
        problem_text = str(row["problem"] or "").strip().casefold()
        is_payment_row = problem_text.startswith("paiement du")
        if row["legacy_imported"] and is_payment_row and group and group.get("has_origin"):
            continue
        # Une ligne comptable de paiement seule n'est jamais un appareil à restituer.
        if is_payment_row:
            continue
        to_return_count += 1

    totals_rows = con.execute("""
        SELECT accounting_month m,
               SUM(COALESCE(accounting_service_amount,0)) service_total,
               SUM(COALESCE(accounting_goods_amount,0)) goods_total
        FROM repairs
        WHERE accounting_year=?
          AND accounting_month BETWEEN 1 AND 12
        GROUP BY accounting_month
    """, (requested_year,)).fetchall()

    totals_map = {
        int(x["m"]): {
            "service": float(x["service_total"] or 0),
            "goods": float(x["goods_total"] or 0),
        }
        for x in totals_rows
    }

    con.close()

    month_names = {
        1:"Janvier",2:"Février",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
        7:"Juillet",8:"Août",9:"Septembre",10:"Octobre",11:"Novembre",12:"Décembre"
    }

    months = []
    red_count = 0
    yellow_count = 0

    for month in range(12,0,-1):
        month_rows = []
        for row in rows:
            row_month = row["followup_month"]
            if not row_month:
                try:
                    row_month = int(str(row["received_date"])[5:7])
                except Exception:
                    row_month = 0
            if int(row_month or 0) != month:
                continue

            item = dict(row)
            if to_return_only and item.get("status") != "Terminé":
                continue

            item["_days_waiting_return"] = None
            if item.get("status") == "Terminé" and item.get("finished_at"):
                try:
                    finished_dt = datetime.fromisoformat(str(item.get("finished_at")))
                    if finished_dt.tzinfo is None and now().tzinfo is not None:
                        finished_dt = finished_dt.replace(tzinfo=now().tzinfo)
                    item["_days_waiting_return"] = max(0, (now().date() - finished_dt.date()).days)
                except Exception:
                    pass

            invoice_no = str(item.get("invoice_no") or "").strip()
            group = history_invoice_groups.get((item.get("client_id"), invoice_no)) if invoice_no else None
            problem_text = str(item.get("problem") or "").strip().casefold()
            is_payment_row = problem_text.startswith("paiement du")

            # Masquer les lignes comptables « Paiement du… » de la vue atelier :
            # ce ne sont pas des appareils encore présents. Dans la vue normale,
            # on conserve l'ancien comportement pour ne pas modifier l'historique.
            if to_return_only and is_payment_row:
                continue
            # Masquer la ligne comptable de paiement lorsqu'une vraie ligne dossier existe.
            # Le CA continue d'utiliser cette ligne via accounting_*.
            if item.get("legacy_imported") and is_payment_row and group and group.get("has_origin"):
                continue

            item["_payment_split"] = payment_split_values(item.get("payment_detail"), item.get("payment_method"))

            if item.get("status") == "Laissé pour pièces":
                item["_display_total"] = 0.0
                item["_display_payment_mode"] = ""
                item["_display_accounting_date"] = ""
                item["accounting_status"] = "normal"
            elif group:
                item["_display_total"] = float(group.get("total") or 0)
                item["_display_payment_mode"] = " + ".join(group.get("modes") or [])
                item["_display_accounting_date"] = group.get("accounting_date") or item.get("accounting_date") or ""
            else:
                item["_display_total"] = float(item.get("service_amount") or 0) + float(item.get("goods_amount") or 0)
                item["_display_payment_mode"] = item.get("payment_mode") or ""
                item["_display_accounting_date"] = item.get("accounting_date") or ""

            if item.get("accounting_status") == "red":
                red_count += 1
            elif item.get("accounting_status") == "yellow":
                yellow_count += 1
            month_rows.append(item)

        # Lignes purement visuelles pour les encaissements inter-mois.
        month_rows.extend(cross_month_payments.get(month, []))

        t = totals_map.get(month, {"service":0.0,"goods":0.0})
        months.append({
            "number": month,
            "name": month_names[month],
            "rows": month_rows,
            "service_total": 0.0 if to_return_only else t["service"],
            "goods_total": 0.0 if to_return_only else t["goods"],
        })

    try:
        edit_id = int(request.args.get("edit") or 0)
    except Exception:
        edit_id = 0

    return render_template(
        "index.html",
        months=months,
        selected_year=requested_year,
        available_years=available_years,
        red_count=red_count,
        yellow_count=yellow_count,
        to_return_count=to_return_count,
        to_return_only=to_return_only,
        client_search=client_search,
        edit_id=edit_id,
        current_period=now().strftime("%Y-%m"),
    )




@app.route("/documents/dossiers")
def document_folders_info():
    return {
        "devis": str(DEVIS_ROOT),
        "factures": str(FACTURES_ROOT),
        "factures_fournisseurs": "Factures/AAAA/MM - Mois/Fournisseurs",
    }


@app.route("/antivirus")
def antivirus_page():
    con = db()
    seed_legacy_management_data(con)
    con.commit()
    entries = con.execute("""
        SELECT * FROM antivirus_entries
        ORDER BY COALESCE(expiration_date,'0000-00-00') DESC, id DESC
    """).fetchall()
    clients = con.execute("SELECT name FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    con.close()

    today = now().date()
    display_entries = []
    for row in entries:
        item = dict(row)
        status = "unknown"
        days = None
        if item.get("expiration_date"):
            try:
                exp = datetime.strptime(item["expiration_date"], "%Y-%m-%d").date()
                days = (exp - today).days
                if days < 0:
                    status = "expired"
                elif days <= 30:
                    status = "soon"
                else:
                    status = "valid"
            except Exception:
                pass
        item["expiration_status"] = status
        item["days_left"] = days
        display_entries.append(item)

    return render_template(
        "antivirus.html",
        entries=display_entries,
        clients=clients,
        today=today.isoformat(),
    )


@app.route("/antivirus/add", methods=["POST"])
def antivirus_add():
    client_name = request.form.get("client_name", "").strip()
    if not client_name:
        flash("Le nom ou le prénom du client est obligatoire.")
        return redirect(url_for("antivirus_page"))

    stamp = now().isoformat(timespec="seconds")
    con = db()
    con.execute("""
        INSERT INTO antivirus_entries(
            client_name, setup_date, antivirus_name, expiration_date,
            invoice_no, info, created_at, updated_at
        ) VALUES(?,?,?,?,?,?,?,?)
    """, (
        client_name,
        request.form.get("setup_date", "").strip(),
        request.form.get("antivirus_name", "").strip(),
        request.form.get("expiration_date", "").strip(),
        request.form.get("invoice_no", "").strip(),
        request.form.get("info", "").strip(),
        stamp, stamp
    ))
    con.commit()
    con.close()
    audit_event("ANTIVIRUS_ADD", client_name, request.remote_addr)
    flash("Antivirus ajouté.")
    return redirect(url_for("antivirus_page"))


@app.route("/antivirus/<int:entry_id>/edit", methods=["POST"])
def antivirus_edit(entry_id):
    client_name = request.form.get("client_name", "").strip()
    if not client_name:
        flash("Le nom du client est obligatoire.")
        return redirect(url_for("antivirus_page"))

    con = db()
    if not con.execute("SELECT id FROM antivirus_entries WHERE id=?", (entry_id,)).fetchone():
        con.close()
        return "Ligne introuvable", 404

    con.execute("""
        UPDATE antivirus_entries SET
            client_name=?, setup_date=?, antivirus_name=?, expiration_date=?,
            invoice_no=?, info=?, updated_at=?
        WHERE id=?
    """, (
        client_name,
        request.form.get("setup_date", "").strip(),
        request.form.get("antivirus_name", "").strip(),
        request.form.get("expiration_date", "").strip(),
        request.form.get("invoice_no", "").strip(),
        request.form.get("info", "").strip(),
        now().isoformat(timespec="seconds"),
        entry_id
    ))
    con.commit()
    con.close()
    audit_event("ANTIVIRUS_EDIT", f"id={entry_id}", request.remote_addr)
    flash("Ligne antivirus modifiée.")
    return redirect(url_for("antivirus_page"))


@app.route("/antivirus/<int:entry_id>/delete", methods=["POST"])
def antivirus_delete(entry_id):
    backup_database(force=True, tag="avant_suppression_antivirus")
    con = db()
    con.execute("DELETE FROM antivirus_entries WHERE id=?", (entry_id,))
    con.commit()
    con.close()
    audit_event("ANTIVIRUS_DELETE", f"id={entry_id}", request.remote_addr)
    flash("Ligne antivirus supprimée.")
    return redirect(url_for("antivirus_page"))



def quote_client_email(con, quote_row):
    """
    Recherche l'e-mail directement dans la table Clients.

    Priorité :
    1. client_id du devis ;
    2. adresse + code postal + ville (très fiable pour les devis historiques) ;
    3. égalité exacte sur Nom ou Entreprise/Société ;
    4. correspondance partielle unique sur Nom / Société.
    """
    try:
        client_id = quote_row["client_id"]
    except Exception:
        client_id = None

    if client_id:
        row = con.execute(
            "SELECT email FROM clients WHERE id=?",
            (client_id,)
        ).fetchone()
        if row and str(row["email"] or "").strip():
            return str(row["email"]).strip()

    quote_name = " ".join(str(quote_row["client_name"] or "").split()).strip()
    wanted = _contact_name_normalize(quote_name)

    quote_street = " ".join(str(quote_row["client_address_street"] or "").split()).strip().casefold()
    quote_cp = str(quote_row["client_postal_code"] or "").strip()
    quote_city = " ".join(str(quote_row["client_city"] or "").split()).strip().casefold()

    rows = con.execute("""
        SELECT id,name,first_name,last_name,company,email,
               address_street,postal_code,city
        FROM clients
        WHERE COALESCE(trim(email),'')<>''
    """).fetchall()

    # 1) Adresse + CP + ville : idéal pour les anciens devis dont le nom
    # a changé ou contient une faute de frappe.
    address_matches = []
    if quote_street and quote_cp and quote_city:
        for r in rows:
            street = " ".join(str(r["address_street"] or "").split()).strip().casefold()
            cp = str(r["postal_code"] or "").strip()
            city = " ".join(str(r["city"] or "").split()).strip().casefold()
            if street == quote_street and cp == quote_cp and city == quote_city:
                address_matches.append(r)

    if len(address_matches) == 1:
        return str(address_matches[0]["email"] or "").strip()

    if not wanted:
        return ""

    # 2) Match exact sur nom complet ou société.
    exact = []
    for r in rows:
        keys = {
            _contact_name_normalize(r["name"]),
            _contact_name_normalize(r["company"]),
            _contact_name_normalize(
                " ".join(x for x in [r["first_name"] or "", r["last_name"] or ""] if x)
            ),
            _contact_name_normalize(
                " ".join(x for x in [r["last_name"] or "", r["first_name"] or ""] if x)
            ),
        }
        keys.discard("")
        if wanted in keys:
            exact.append(r)

    if len(exact) == 1:
        return str(exact[0]["email"] or "").strip()

    # 3) Match partiel UNIQUE sur nom / société.
    partial = []
    if len(wanted) >= 5:
        for r in rows:
            values = [
                _contact_name_normalize(r["name"]),
                _contact_name_normalize(r["company"]),
            ]
            values = [v for v in values if len(v) >= 5]
            if any(wanted in v or v in wanted for v in values):
                partial.append(r)

    unique = {}
    for r in partial:
        unique[int(r["id"])] = r

    if len(unique) == 1:
        r = next(iter(unique.values()))
        return str(r["email"] or "").strip()

    return ""



@app.route("/devis")
def quotes_page():
    con = db()
    seed_legacy_management_data(con)
    seed_result = seed_legacy_quotes37(con)
    con.commit()

    rows = con.execute("""
        SELECT q.*,
               (SELECT COALESCE(SUM(ql.quantity * ql.unit_price),0)
                FROM quote_lines ql WHERE ql.quote_id=q.id) AS total
        FROM quotes q
        ORDER BY q.quote_date DESC, q.id DESC
    """).fetchall()

    quotes = []
    all_real_docs = set()
    for row in rows:
        item = dict(row)
        item["client_email"] = quote_client_email(con, row)
        candidates = quote_document_candidates(item["quote_no"])
        item["real_documents"] = [str(p) for p in candidates]
        item["document_count"] = len(candidates)
        item["first_document_path"] = str(candidates[0]) if candidates else ""
        all_real_docs.update(str(p) for p in candidates)
        quotes.append(item)

    con.close()

    if seed_result.get("quotes_added") or seed_result.get("documents_added"):
        flash(
            f"Archive devis importée : {seed_result.get('quotes_added',0)} devis ajoutés."
        )

    historical_document_count = len(list(DEVIS_ROOT.rglob("*.pdf"))) if DEVIS_ROOT.exists() else 0
    historical_quote_count = sum(1 for q in quotes if q["document_count"] > 0)

    return render_template(
        "quotes.html",
        quotes=quotes,
        historical_document_count=historical_document_count,
        historical_quote_count=historical_quote_count,
        devis_root=str(DEVIS_ROOT),
    )


@app.route("/devis/new", methods=["GET", "POST"])
def quote_new():
    con = db()
    clients = con.execute("""
        SELECT id,name,company,address_street,postal_code,city
        FROM clients ORDER BY name COLLATE NOCASE
    """).fetchall()

    if request.method == "POST":
        lines = parse_quote_lines(request.form)
        if not lines:
            con.close()
            flash("Ajoute au moins une ligne au devis.")
            return redirect(url_for("quote_new"))

        quote_no = request.form.get("quote_no", "").strip()
        if not re.fullmatch(r"\d{12}", quote_no):
            quote_no = make_quote_no(con)
        if con.execute("SELECT id FROM quotes WHERE quote_no=?", (quote_no,)).fetchone():
            quote_no = make_quote_no(con)

        quote_date = request.form.get("quote_date", "").strip() or now().strftime("%Y-%m-%d")
        stamp = now().isoformat(timespec="seconds")

        client_id_raw = request.form.get("client_id", "").strip()
        client_id = int(client_id_raw) if client_id_raw.isdigit() else None

        cur = con.execute("""
            INSERT INTO quotes(
                quote_no, quote_date, client_id, client_name, client_company,
                client_address_street, client_postal_code, client_city,
                contact_name, status, notes, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            quote_no, quote_date, client_id,
            request.form.get("client_name","").strip() or "Client",
            request.form.get("client_company","").strip(),
            request.form.get("client_address_street","").strip(),
            request.form.get("client_postal_code","").strip(),
            request.form.get("client_city","").strip(),
            "",
            request.form.get("status","Brouillon").strip() or "Brouillon",
            request.form.get("notes","").strip(),
            stamp, stamp
        ))
        quote_id = cur.lastrowid

        for line in lines:
            con.execute("""
                INSERT INTO quote_lines(
                    quote_id,position,line_type,quantity,description,unit_price
                ) VALUES(?,?,?,?,?,?)
            """, (
                quote_id, line["position"], line["line_type"], line["quantity"],
                line["description"], line["unit_price"]
            ))

        con.commit()
        con.close()
        audit_event("QUOTE_ADD", f"id={quote_id}; no={quote_no}", request.remote_addr)
        flash("Devis créé.")
        return redirect(url_for("quote_edit", quote_id=quote_id))

    automatic_quote_no = make_quote_no(con)
    con.close()
    empty_quote = {
        "id": None,
        "quote_no": automatic_quote_no,
        "quote_date": now().strftime("%Y-%m-%d"),
        "client_id": None,
        "client_name": "",
        "client_company": "",
        "client_address_street": "",
        "client_postal_code": "",
        "client_city": "",
        "contact_name": "",
        "status": "Brouillon",
        "notes": "",
    }
    return render_template("quote_edit.html", q=empty_quote, quote_lines=[], clients=clients, documents=[], is_new=True)


@app.route("/devis/<int:quote_id>/edit", methods=["GET", "POST"])
def quote_edit(quote_id):
    con = db()
    q = con.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
    if not q:
        con.close()
        return "Devis introuvable", 404

    clients = con.execute("""
        SELECT id,name,company,address_street,postal_code,city
        FROM clients ORDER BY name COLLATE NOCASE
    """).fetchall()

    if request.method == "POST":
        lines = parse_quote_lines(request.form)
        if not lines:
            con.close()
            flash("Ajoute au moins une ligne au devis.")
            return redirect(url_for("quote_edit", quote_id=quote_id))

        # Le numéro est attribué automatiquement à la création et ne change plus.
        quote_no = q["quote_no"]

        client_id_raw = request.form.get("client_id", "").strip()
        client_id = int(client_id_raw) if client_id_raw.isdigit() else None

        con.execute("""
            UPDATE quotes SET
                quote_no=?, quote_date=?, client_id=?, client_name=?, client_company=?,
                client_address_street=?, client_postal_code=?, client_city=?,
                contact_name=?, status=?, notes=?, updated_at=?, edited_in_app=1
            WHERE id=?
        """, (
            quote_no,
            request.form.get("quote_date","").strip() or q["quote_date"],
            client_id,
            request.form.get("client_name","").strip() or "Client",
            request.form.get("client_company","").strip(),
            request.form.get("client_address_street","").strip(),
            request.form.get("client_postal_code","").strip(),
            request.form.get("client_city","").strip(),
            "",
            request.form.get("status","Brouillon").strip() or "Brouillon",
            request.form.get("notes","").strip(),
            now().isoformat(timespec="seconds"),
            quote_id
        ))

        con.execute("DELETE FROM quote_lines WHERE quote_id=?", (quote_id,))
        for line in lines:
            con.execute("""
                INSERT INTO quote_lines(
                    quote_id,position,line_type,quantity,description,unit_price
                ) VALUES(?,?,?,?,?,?)
            """, (
                quote_id, line["position"], line["line_type"], line["quantity"],
                line["description"], line["unit_price"]
            ))

        con.commit()
        con.close()
        audit_event("QUOTE_EDIT", f"id={quote_id}", request.remote_addr)
        flash("Devis modifié.")
        return redirect(url_for("quote_edit", quote_id=quote_id))

    lines = con.execute("""
        SELECT * FROM quote_lines WHERE quote_id=? ORDER BY position,id
    """, (quote_id,)).fetchall()
    con.close()
    documents = [
        {"index": i, "filename": p.name, "path": str(p)}
        for i, p in enumerate(quote_document_candidates(q["quote_no"]))
    ]
    return render_template("quote_edit.html", q=q, quote_lines=lines, clients=clients, documents=documents, is_new=False)



@app.route("/devis/<int:quote_id>/email", methods=["GET", "POST"])
def quote_email(quote_id):
    smtp_settings = read_smtp_settings()

    con = db()
    q = con.execute(
        "SELECT * FROM quotes WHERE id=?",
        (quote_id,)
    ).fetchone()

    if not q:
        con.close()
        return "Devis introuvable", 404

    client_email = quote_client_email(con, q)
    q = dict(q)
    q["client_email"] = client_email
    con.close()

    cancel_url = url_for("quotes_page")

    if request.method == "GET":
        if not smtp_settings.get("enabled") or not smtp_settings.get("token"):
            flash("Configure d'abord le SMTP Proton dans Sécurité.")
            return redirect(url_for("security_page"))

        if not q["client_email"]:
            flash("Impossible d'envoyer : le client n'a pas d'adresse e-mail.")
            return redirect(cancel_url)

        ident = business_identity()
        subject = f"{ident['name']} - Devis {q['quote_no']}"
        body = (
            "Bonjour,\n\n"
            f"Veuillez trouver ci-joint votre devis {ident['name']}.\n\n"
            "Je reste à votre disposition si vous avez des questions.\n\n"
            "Cordialement,\n"
            f"{business_signature()}"
        )

        return render_template(
            "quote_email_preview.html",
            q=q,
            recipient=q["client_email"],
            subject=subject,
            body=body,
            cancel_url=cancel_url,
            sender=smtp_settings.get("sender_email") or smtp_settings.get("username"),
        )

    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    if not recipient or "@" not in recipient:
        flash("Adresse destinataire invalide.")
        return redirect(url_for("quote_email", quote_id=quote_id))

    if not subject:
        flash("L'objet du message est obligatoire.")
        return redirect(url_for("quote_email", quote_id=quote_id))

    # Réutilise le PDF officiel du devis pour garantir la même pièce jointe
    # que celle téléchargée depuis la page Devis.
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess.update(dict(session))
        pdf_response = client.get(url_for("quote_pdf", quote_id=quote_id))
        if pdf_response.status_code != 200:
            flash("Impossible de générer le PDF du devis.")
            return redirect(url_for("quote_email", quote_id=quote_id))
        pdf_data = bytes(pdf_response.data)

    sender_email = str(
        smtp_settings.get("sender_email") or smtp_settings.get("username") or ""
    ).strip()
    sender_name = str(smtp_settings.get("sender_name") or business_identity()["name"]).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    msg["To"] = recipient
    msg.set_content(body)

    attachment_name = (
        f"{safe_filename(q['client_name'])}_"
        f"{safe_filename(q['quote_no'])}.pdf"
    )
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=attachment_name
    )

    try:
        smtp_send_message(msg)
        audit_event(
            "QUOTE_EMAIL",
            f"Devis {q['quote_no']} envoyé à {recipient}",
            request.remote_addr
        )
        flash(f"Devis {q['quote_no']} envoyé par e-mail à {recipient}.")
        return redirect(cancel_url)
    except Exception as e:
        audit_event(
            "QUOTE_EMAIL_ERROR",
            f"Devis {q['quote_no']} : {type(e).__name__}",
            request.remote_addr
        )
        flash(f"Échec envoi e-mail : {e}")
        return redirect(url_for("quote_email", quote_id=quote_id))


@app.route("/devis/<int:quote_id>/delete", methods=["POST"])
def quote_delete(quote_id):
    backup_database(force=True, tag="avant_suppression_devis")
    con = db()
    q = con.execute("SELECT quote_no FROM quotes WHERE id=?", (quote_id,)).fetchone()
    if not q:
        con.close()
        return "Devis introuvable", 404
    con.execute("DELETE FROM quote_documents WHERE quote_id=?", (quote_id,))
    con.execute("DELETE FROM quote_lines WHERE quote_id=?", (quote_id,))
    con.execute("DELETE FROM quotes WHERE id=?", (quote_id,))
    con.commit()
    con.close()
    audit_event("QUOTE_DELETE", f"id={quote_id}; no={q['quote_no']}", request.remote_addr)
    flash("Devis supprimé.")
    return redirect(url_for("quotes_page"))


@app.route("/devis/<int:quote_id>/original/<int:doc_index>")
def quote_original_real(quote_id, doc_index):
    con = db()
    q = con.execute("SELECT quote_no FROM quotes WHERE id=?", (quote_id,)).fetchone()
    con.close()
    if not q:
        return "Devis introuvable", 404

    docs = quote_document_candidates(q["quote_no"])
    if doc_index < 0 or doc_index >= len(docs):
        return "PDF original introuvable dans WOPR/private/documents/Devis", 404

    path = docs[doc_index]
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=path.name,
    )


@app.route("/devis/document/<int:document_id>")
def quote_original_document(document_id):
    con = db()
    row = con.execute("""
        SELECT qd.*, q.quote_no
        FROM quote_documents qd
        JOIN quotes q ON q.id=qd.quote_id
        WHERE qd.id=?
    """, (document_id,)).fetchone()
    con.close()
    if not row:
        return "Document introuvable", 404

    path = find_document_recursive(
        DEVIS_ROOT,
        filename=row["filename"],
        document_no=row["quote_no"],
    )
    if not path:
        return (
            "PDF historique introuvable dans le dossier privé des devis. "
            "Vérifie qu'il est bien rangé dans Devis/AAAA/MM - Mois/.",
            404,
        )

    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=path.name,
    )


@app.route("/devis/<int:quote_id>/pdf")
def quote_pdf(quote_id):
    """
    Devis WOPR au format historique Calc/PDF.
    La mise en page reprend le modèle réel fourni par l'utilisateur.
    """
    con = db()
    q = con.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
    lines = con.execute("""
        SELECT * FROM quote_lines WHERE quote_id=? ORDER BY position,id
    """, (quote_id,)).fetchall()
    con.close()

    if not q:
        return "Devis introuvable", 404

    # V2.3.68 — pour un devis historique encore intact, le PDF téléchargé
    # est le vrai fichier original, octet pour octet.
    original_docs = quote_document_candidates(q["quote_no"])
    if original_docs and not int(q["edited_in_app"] or 0):
        original_path = original_docs[0]
        return send_file(
            original_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=original_path.name,
        )

    conf = cfg()
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    W, H = A4

    BLUE = colors.HexColor("#3399FF")
    LINE_BLUE = colors.HexColor("#3399FF")
    BORDER = colors.HexColor("#222222")
    LIGHT_BORDER = colors.HexColor("#8DC8F0")
    LIGHT_GREY = colors.HexColor("#777777")
    QF = QUOTE_FONTS

    def euro(value):
        return f"{float(value or 0):,.2f} €".replace(",", "X").replace(".", ",").replace("X", " ")

    def qty_text(value):
        v = float(value or 0)
        if abs(v - round(v)) < 0.0001:
            return str(int(round(v)))
        return f"{v:g}".replace(".", ",")

    def split_to_width(text, font, size, max_width):
        words = str(text or "").split()
        if not words:
            return [""]
        out, current = [], ""
        for word in words:
            test = word if not current else current + " " + word
            if pdfmetrics.stringWidth(test, font, size) <= max_width:
                current = test
            else:
                if current:
                    out.append(current)
                current = word
        if current:
            out.append(current)
        return out

    def draw_wrapped(text, x, y, max_width, font, size, leading, max_lines=None):
        lines_out = []
        for raw in str(text or "").splitlines() or [""]:
            wrapped = split_to_width(raw, font, size, max_width)
            lines_out.extend(wrapped or [""])
        if max_lines:
            lines_out = lines_out[:max_lines]
        c.setFont(font, size)
        for item in lines_out:
            c.drawString(x, y, item)
            y -= leading
        return y

    def draw_footer():
        c.setFillColor(colors.black)
        c.setFont(QF["regular"], 7.4)
        footer_parts = [str(conf.get("business_name") or "WOPR").strip()]
        owner = str(conf.get("owner_name") or "").strip()
        if owner:
            footer_parts.append(owner)
        if str(conf.get("siret") or "").strip():
            footer_parts.append(f"N° Siret : {conf.get('siret')}")
        if str(conf.get("ape") or "").strip():
            footer_parts.append(f"Code APE : {conf.get('ape')}")
        footer1 = " - ".join(x for x in footer_parts if x)
        c.drawCentredString(W/2, 17.8*mm, footer1)
        c.setFont(QF["bold"], 7.4)
        c.drawCentredString(W/2, 13.8*mm, f"IBAN : {conf.get('iban','')}")
        c.setFont(QF["regular"], 7.2)
        c.drawCentredString(
            W/2, 10.2*mm,
            f"- {conf.get('website','')} - {conf.get('email','')} -"
        )
        c.setFont(QF["regular"], 7.0)
        c.drawCentredString(
            W/2, 5.8*mm,
            "Dispensé d'immatriculation au registre du commerce et des sociétés, "
            "en application de l'article L. 123-1-1 du Code de commerce"
        )

    # ----------------------------------------------------------------
    # Bandeau supérieur identique au modèle historique
    # ----------------------------------------------------------------
    margin_x = 4.5*mm
    c.setStrokeColor(LINE_BLUE)
    c.setLineWidth(0.9*mm)
    c.line(margin_x, H-4.2*mm, W-margin_x, H-4.2*mm)

    logo_x = 4.5*mm
    logo_top = H-5.8*mm
    logo_w = 121.5*mm
    logo_h = 53.7*mm
    invoice_logo = invoice_logo_path()
    if invoice_logo:
        try:
            c.drawImage(
                str(invoice_logo),
                logo_x, logo_top-logo_h,
                width=logo_w, height=logo_h,
                preserveAspectRatio=False,
                mask="auto"
            )
        except Exception:
            pass

    # Bloc DEVIS bleu à droite
    bx = 136.8*mm
    by = H-36.2*mm
    bw = 68.3*mm
    bh = 28.0*mm
    c.setFillColor(BLUE)
    c.setStrokeColor(BLUE)
    c.rect(bx, by, bw, bh, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont(QF["regular"], 22)
    c.drawCentredString(bx+bw/2, by+18.0*mm, "DEVIS")

    c.setFillColor(colors.black)
    c.setFont(QF["regular"], 9.2)
    c.drawString(bx+1.2*mm, by+8.1*mm, "Devis n°")
    c.drawString(bx+1.2*mm, by+3.4*mm, "Date")
    c.drawString(bx+20.3*mm, by+8.1*mm, ":")
    c.drawString(bx+20.3*mm, by+3.4*mm, ":")
    c.setFont(QF["regular"], 9.0)
    c.drawString(bx+23.2*mm, by+8.1*mm, str(q["quote_no"] or ""))
    c.drawString(bx+23.2*mm, by+3.4*mm, fr_date(q["quote_date"]))

    # Ligne bleue sous le bandeau
    c.setStrokeColor(LINE_BLUE)
    c.setLineWidth(0.9*mm)
    c.line(margin_x, H-58.3*mm, W-margin_x, H-58.3*mm)

    # ----------------------------------------------------------------
    # Cadres entreprise / client
    # ----------------------------------------------------------------
    company_x = 9.6*mm
    box_y = H-111.8*mm
    company_w = 69.0*mm
    box_h = 45.5*mm
    c.setFillColor(colors.white)
    c.setStrokeColor(LIGHT_BORDER)
    c.setLineWidth(0.45*mm)
    c.rect(company_x, box_y, company_w, box_h, fill=1, stroke=1)

    c.setFillColor(colors.black)
    c.setFont(QF["bold"], 13.0)
    c.drawString(company_x+1.0*mm, box_y+box_h-6.0*mm, conf.get("owner_name",""))
    c.setFont(QF["regular"], 12.2)
    c.drawString(company_x+1.0*mm, box_y+box_h-18.5*mm, conf.get("address_line1","25 rue font laurière"))
    c.drawString(company_x+1.0*mm, box_y+box_h-30.7*mm, conf.get("address_line2",""))
    c.drawString(company_x+1.0*mm, box_y+box_h-42.2*mm, f"Tél : {conf.get('phone','06 60 47 29 48')}")

    client_x = 136.5*mm
    client_w = 68.1*mm
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.35*mm)
    c.rect(client_x, box_y, client_w, box_h, fill=0, stroke=1)

    c.setFont(QF["regular"], 13.2)
    c.drawString(client_x+0.6*mm, box_y+box_h-6.0*mm, "Client :")
    # Soulignement du titre comme sur l'original
    client_label_w = pdfmetrics.stringWidth("Client :", QF["regular"], 13.2)
    c.setLineWidth(0.35*mm)
    c.line(
        client_x+0.6*mm, box_y+box_h-6.8*mm,
        client_x+0.6*mm+client_label_w, box_y+box_h-6.8*mm
    )

    c.setFont(QF["regular"], 9.5)
    cy = box_y+box_h-15.2*mm
    cy = draw_wrapped(q["client_name"], client_x+0.7*mm, cy, client_w-2*mm, QF["regular"], 9.5, 4.5*mm, 2)
    if q["client_company"]:
        cy -= 0.5*mm
        cy = draw_wrapped(q["client_company"], client_x+0.7*mm, cy, client_w-2*mm, QF["regular"], 9.2, 4.2*mm, 2)
    if q["client_address_street"]:
        cy -= 1.0*mm
        cy = draw_wrapped(q["client_address_street"], client_x+0.7*mm, cy, client_w-2*mm, QF["regular"], 9.2, 4.2*mm, 3)
    cityline = " ".join(x for x in [q["client_postal_code"], q["client_city"]] if x)
    if cityline:
        cy -= 1.0*mm
        draw_wrapped(cityline, client_x+0.7*mm, cy, client_w-2*mm, QF["regular"], 9.2, 4.2*mm, 2)

    # ----------------------------------------------------------------
    # Tableau historique : Quantité | Désignation | vide | Total
    # ----------------------------------------------------------------
    table_x = 4.2*mm
    table_top = H-116.7*mm
    col_qty = 19.0*mm
    col_desc = 91.0*mm
    col_blank = 29.0*mm
    col_total = 61.0*mm
    table_w = col_qty + col_desc + col_blank + col_total
    header_h = 9.2*mm
    row_h = 5.8*mm

    xs = [
        table_x,
        table_x+col_qty,
        table_x+col_qty+col_desc,
        table_x+col_qty+col_desc+col_blank,
        table_x+table_w
    ]

    c.setStrokeColor(BORDER)
    c.setLineWidth(0.28*mm)
    c.setFillColor(BLUE)
    c.rect(table_x, table_top-header_h, table_w, header_h, fill=1, stroke=1)
    for x in xs[1:-1]:
        c.line(x, table_top, x, table_top-header_h)

    c.setFillColor(colors.white)
    c.setFont(QF["regular"], 9.8)
    c.drawCentredString((xs[0]+xs[1])/2, table_top-header_h+2.8*mm, "Quantité")
    c.setFont(QF["bold"], 9.7)
    c.drawCentredString((xs[1]+xs[2])/2, table_top-header_h+2.8*mm, "Désignation")
    c.drawCentredString((xs[3]+xs[4])/2, table_top-header_h+2.8*mm, "Total")

    # Transforme chaque ligne métier en lignes visuelles du Calc.
    visual_rows = []
    grand_total = 0.0

    for line in lines:
        qty = float(line["quantity"] or 0)
        price = float(line["unit_price"] or 0)
        total = qty * price
        grand_total += total

        desc_raw = str(line["description"] or "")
        desc_parts = []
        for raw in desc_raw.splitlines() or [""]:
            wrapped = split_to_width(raw, QF["regular"], 8.2, col_desc-2.0*mm)
            desc_parts.extend(wrapped or [""])

        if not desc_parts:
            desc_parts = [""]

        visual_rows.append({
            "qty": qty_text(qty),
            "desc": desc_parts[0],
            "total": euro(total),
            "main": True,
        })
        for extra in desc_parts[1:]:
            visual_rows.append({"qty":"", "desc":extra, "total":"", "main":False})

        # Dans le modèle Calc, les articles/prestations sont séparés par une ligne vide.
        visual_rows.append({"qty":"", "desc":"", "total":"", "main":False})

    # Le modèle d'origine conserve un tableau visuel assez haut, même avec peu de lignes.
    min_visual_rows = 12
    while len(visual_rows) < min_visual_rows:
        visual_rows.append({"qty":"", "desc":"", "total":"", "main":False})

    # Pour garder le bas de page identique, limite l'affichage à 16 lignes visuelles.
    # Les descriptions sont compactées plus haut pour éviter le dépassement.
    visual_rows = visual_rows[:16]

    y_top = table_top-header_h
    c.setFillColor(colors.black)

    for row in visual_rows:
        y_bottom = y_top-row_h
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.22*mm)
        c.rect(table_x, y_bottom, table_w, row_h, fill=0, stroke=1)
        for x in xs[1:-1]:
            c.line(x, y_top, x, y_bottom)

        c.setFont(QF["regular"], 8.2)
        if row["qty"]:
            c.drawCentredString((xs[0]+xs[1])/2, y_bottom+1.8*mm, row["qty"])
        if row["desc"]:
            fit_text(c, row["desc"], xs[1]+0.8*mm, y_bottom+1.7*mm, col_desc-1.6*mm, QF["regular"], 8.2, 6.0)
        if row["total"]:
            c.setFont(QF["regular"], 8.7)
            c.drawRightString(xs[4]-0.8*mm, y_bottom+1.7*mm, row["total"])
        y_top = y_bottom

    # Deux lignes TVA / Facture / Total
    vat_h = 7.0*mm
    vat_y1 = y_top-vat_h
    vat_y2 = vat_y1-vat_h

    # Ligne 1
    c.rect(table_x, vat_y1, table_w, vat_h, fill=0, stroke=1)
    c.line(xs[2], y_top, xs[2], vat_y1)
    c.line(xs[3], y_top, xs[3], vat_y1)
    c.setFont(QF["italic"], 9.5)
    c.drawString(xs[1]+1.0*mm, vat_y1+2.0*mm, "TVA non applicable, art. 293 B du CGI")

    # Ligne 2
    c.rect(table_x, vat_y2, table_w, vat_h, fill=0, stroke=1)
    c.line(xs[2], vat_y1, xs[2], vat_y2)
    c.line(xs[3], vat_y1, xs[3], vat_y2)
    c.setFont(QF["italic"], 9.5)
    c.drawString(xs[1]+1.0*mm, vat_y2+2.0*mm, "Facture en euros")
    c.setFont(QF["bold"], 9.5)
    c.drawString(xs[2]+2.2*mm, vat_y2+2.0*mm, "Net à payer :")
    c.setFont(QF["bold"], 10.0)
    c.drawRightString(xs[4]-0.8*mm, vat_y2+2.0*mm, euro(grand_total))

    # ----------------------------------------------------------------
    # Mentions sous tableau
    # ----------------------------------------------------------------
    under_y = vat_y2-3.2*mm
    c.setFillColor(colors.black)
    c.setFont(QF["regular"], 7.2)
    c.drawString(table_x+0.5*mm, under_y, "En cas de non réparation, un ")
    prefix_w = pdfmetrics.stringWidth("En cas de non réparation, un ", QF["regular"], 7.2)
    c.setFont(QF["bold"], 7.2)
    c.drawString(table_x+0.5*mm+prefix_w, under_y, "forfait de 30€")
    bold_w = pdfmetrics.stringWidth("forfait de 30€", QF["bold"], 7.2)
    c.setFont(QF["regular"], 7.2)
    c.drawString(
        table_x+0.5*mm+prefix_w+bold_w, under_y,
        " pour recherche de pannes sera appliqué."
    )
    c.drawString(
        table_x+0.5*mm, under_y-4.2*mm,
        "Le client aura la possibilité de régler le forfait ou de laisser le matériel pour pièces."
    )

    # Paragraphe données - texte identique à l'original
    data_y = under_y-13.0*mm
    data_text = (
        "L'entreprise met en œuvre des mesures de sécurité conformes aux exigences légales pour protéger les données. "
        "Toutefois, elle ne peut être tenue responsable des pertes de données résultant d'événements imprévisibles "
        "tels que les cyberattaques, les défaillances techniques ou les catastrophes naturelles."
    )
    c.setFont(QF["regular"], 5.9)
    wrapped_data = split_to_width(data_text, QF["regular"], 5.9, 185*mm)
    for part in wrapped_data[:3]:
        c.drawString(table_x+0.5*mm, data_y, part)
        data_y -= 3.3*mm

    c.setFont(QF["bold"], 5.9)
    c.drawString(
        table_x+0.5*mm, data_y,
        "Les utilisateurs sont invités à sauvegarder régulièrement leurs données importantes."
    )

    # Conditions paiement à gauche
    conditions_y = data_y-10.0*mm
    c.setFillColor(LIGHT_GREY)
    c.setFont(QF["regular"], 5.8)
    condition_lines = [
        "Conditions de paiement : paiement à réception de facture",
        "Aucun escompte consenti pour règlement anticipé",
        "Tout incident de paiement est passible d'intérêt de retard. Le montant des pénalités résulte de l'application",
        "aux sommes restant dues d'un taux d'intérêt légal en vigueur au moment de l'incident.",
        "Indemnité forfaitaire pour frais de recouvrement due au créancier en cas de retard de paiement: 40€",
    ]
    yy = conditions_y
    for txt in condition_lines:
        c.drawString(table_x+0.5*mm, yy, txt)
        yy -= 4.0*mm

    # Zone Bon pour accord à droite
    sig_x = 151.5*mm
    sig_w = 53.5*mm
    sig_h = 34.0*mm
    sig_y = 27.2*mm
    sig_header_h = 4.3*mm
    c.setFillColor(colors.white)
    c.setStrokeColor(LINE_BLUE)
    c.setLineWidth(0.55*mm)
    c.rect(sig_x, sig_y, sig_w, sig_h, fill=0, stroke=1)
    c.line(sig_x, sig_y+sig_h-sig_header_h, sig_x+sig_w, sig_y+sig_h-sig_header_h)
    c.setFillColor(colors.black)
    c.setFont(QF["bold"], 5.7)
    c.drawCentredString(
        sig_x+sig_w/2, sig_y+sig_h-sig_header_h+1.3*mm,
        "Bon pour accord + Signature"
    )

    draw_footer()

    c.save()
    pdf_bytes = bio.getvalue()

    # Sauvegarde automatique dans WOPR/private/documents/Devis/AAAA/MM - Mois
    quote_folder = year_month_folder(DEVIS_ROOT, q["quote_date"], create=True)
    quote_filename = safe_document_name(f"{q['client_name']}_{q['quote_no']}.foulfix.pdf")
    quote_saved_path = quote_folder / quote_filename
    try:
        quote_saved_path.write_bytes(pdf_bytes)
    except Exception as exc:
        app.logger.warning("Impossible d'enregistrer le devis dans %s: %s", quote_saved_path, exc)

    bio.seek(0)
    return send_file(
        bio,
        mimetype="application/pdf",
        # V2.3.239 : le devis vient d'être archivé dans private/documents/Devis.
        # L'utilisateur le visualise sans créer une seconde copie dans Téléchargements.
        as_attachment=False,
        download_name=quote_filename
    )


def open_local_document_folder(folder):
    """Ouvre un dossier local dans l'explorateur du système."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    try:
        if os.name == "nt":
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(folder)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["xdg-open", str(folder)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _folder_open_response(folder):
    ok, error = open_local_document_folder(folder)
    if ok:
        return Response(status=204)
    return Response(
        error or "Impossible d'ouvrir le dossier",
        status=500,
        mimetype="text/plain"
    )


@app.route("/repair/<int:rid>/intake-folder", methods=["GET", "POST"])
def repair_intake_folder(rid):
    con = db()
    row = con.execute(
        "SELECT received_date, created_at FROM repairs WHERE id=?",
        (rid,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify(ok=False, error="Dossier introuvable"), 404

    document_date = str(row["received_date"] or row["created_at"] or "")[:10]
    folder = year_month_folder(
        SUIVI_REPARATIONS_ROOT,
        document_date,
        create=True
    )
    return _folder_open_response(folder)


@app.route("/repair/<int:rid>/invoice-folder", methods=["GET", "POST"])
def repair_invoice_folder(rid):
    con = db()
    row = con.execute(
        "SELECT invoice_no, finished_at, received_date FROM repairs WHERE id=?",
        (rid,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify(ok=False, error="Facture introuvable"), 404

    document_date = invoice_no_date(row["invoice_no"])
    if not document_date:
        document_date = str(row["finished_at"] or row["received_date"] or "")[:10]

    folder = year_month_folder(
        FACTURES_ROOT,
        document_date,
        create=True
    )
    return _folder_open_response(folder)


@app.route("/devis/<int:quote_id>/folder", methods=["GET", "POST"])
def quote_folder_open(quote_id):
    con = db()
    row = con.execute(
        "SELECT quote_date FROM quotes WHERE id=?",
        (quote_id,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify(ok=False, error="Devis introuvable"), 404

    folder = year_month_folder(
        DEVIS_ROOT,
        row["quote_date"],
        create=True
    )
    return _folder_open_response(folder)



@app.route("/achats-ventes/<int:entry_id>/document/folder", methods=["GET", "POST"])
def achats_ventes_document_folder(entry_id):
    """Ouvre le dossier du justificatif réellement résolu pour une ligne Achat/Vente."""
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    con.close()
    if not row:
        return "Ligne introuvable", 404

    try:
        path = ledger_document_file(row)
    except Exception:
        path = None

    if path and Path(path).is_file():
        return _folder_open_response(Path(path).parent)

    # Sans justificatif joint, ouvre tout de même le dossier Fournisseurs du mois.
    document_date = str(row["entry_date"] or "")[:10]
    folder = year_month_folder(
        FOURNISSEURS_ROOT,
        document_date,
        create=True
    )
    return _folder_open_response(folder)


@app.route("/achats-ventes/vente/<int:entry_id>/folder", methods=["GET", "POST"])
def achats_ventes_sale_invoice_folder(entry_id):
    con = db()
    row = con.execute(
        "SELECT * FROM ledger_entries WHERE id=?",
        (entry_id,)
    ).fetchone()
    con.close()
    if not row:
        return jsonify(ok=False, error="Ligne introuvable"), 404
    if (row["operation"] or "").casefold() != "vente":
        return jsonify(ok=False, error="Cette ligne n'est pas une vente"), 400

    invoice_no = canonical_client_invoice_no(row["invoice_no"])
    pdf = find_client_invoice_pdf(invoice_no, row["party"] or "")
    if pdf and pdf.exists():
        return _folder_open_response(pdf.parent)

    document_date = invoice_no_date(invoice_no)
    if not document_date:
        document_date = str(row["entry_date"] or "")[:10]
    folder = year_month_folder(
        FACTURES_ROOT,
        document_date,
        create=True
    )
    return _folder_open_response(folder)


@app.route("/achats-ventes")
def achats_ventes_page():
    # Garde-fou : si l'application a été lancée d'une manière qui n'exécute pas init_db(),
    # on vérifie ici aussi que l'historique ODS a bien été injecté.
    con_seed = db()
    inserted_now = seed_legacy_ledger_entries(con_seed)
    con_seed.commit()
    con_seed.close()
    if inserted_now:
        flash(f"Historique Achats/Ventes chargé : {inserted_now} ligne(s) ajoutée(s).")

    # 2026 = vue principale. 2025 reste accessible uniquement comme archive.
    try:
        year = int(request.args.get("year", 2026))
    except Exception:
        year = 2026
    if year not in (2025, 2026):
        year = 2026

    # V2.3.98 — recherche manuelle uniquement : aucun rattachement automatique.
    search_q = str(request.args.get("q", "") or "").strip()

    # V2.3.96 — auto-répare les liens morts créés pendant les premières versions
    # des justificatifs fournisseurs, sans toucher aux fichiers eux-mêmes.
    repair_dead_supplier_document_links()

    con = db()
    all_entries = con.execute("""
        SELECT *
        FROM ledger_entries
        WHERE substr(entry_date,1,4)=?
        ORDER BY entry_date DESC, id DESC
    """, (str(year),)).fetchall()
    supplier_docs_count = sum(
        1 for row in all_entries
        if (row["operation"] or "").casefold() == "achat" and str(row["document_path"] or "").strip()
    )
    supplier_docs_missing = sum(
        1 for row in all_entries
        if (row["operation"] or "").casefold() == "achat" and not str(row["document_path"] or "").strip()
    )

    # V2.3.100 — pour une ligne Vente, le justificatif est la facture client.
    # Aucun PDF n'est copié : on pointe vers la facture déjà générée par WOPR.
    invoice_rows = con.execute("""
        SELECT r.id, r.invoice_no, r.legacy_imported, r.accounting_date,
               r.service_amount, r.goods_amount, r.received_date,
               c.name AS client_name
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE COALESCE(trim(r.invoice_no),'')<>''
        ORDER BY r.id
    """).fetchall()
    con.close()

    invoice_groups = {}
    for inv_row in invoice_rows:
        key = str(inv_row["invoice_no"] or "").strip()
        if key:
            invoice_groups.setdefault(key, []).append(inv_row)

    sale_invoice_rids = {}
    for row in all_entries:
        if (row["operation"] or "").casefold() != "vente":
            continue
        inv_no = str(row["invoice_no"] or "").strip()
        members = invoice_groups.get(inv_no, [])
        if not inv_no or not members:
            continue
        # V2.3.101 — un même numéro peut exister dans plusieurs dossiers historiques.
        # La ligne Achats/Ventes connaît le client dans `party` : on privilégie donc
        # impérativement le dossier dont le nom client correspond, avant tout autre critère.
        party_key = normalize_history_name(row["party"] or "")

        def _client_match_score(member):
            client_key = normalize_history_name(member["client_name"] or "")
            if not party_key or not client_key:
                return 0
            if party_key == client_key:
                return 100
            # Gère les civilités / préfixes : "Mme Jacquement" ↔ "Jacquement".
            if party_key.endswith(" " + client_key) or client_key.endswith(" " + party_key):
                return 90
            if client_key in party_key or party_key in client_key:
                return 80
            party_words = set(party_key.split())
            client_words = set(client_key.split())
            common = party_words & client_words
            return 10 * len(common) if common else 0

        best_client_score = max((_client_match_score(x) for x in members), default=0)
        client_members = [x for x in members if _client_match_score(x) == best_client_score] if best_client_score else members

        editable = next((x for x in client_members if not x["legacy_imported"]), None)
        representative = editable or max(
            client_members,
            key=lambda x: (
                bool(x["accounting_date"]),
                float(x["service_amount"] or 0) + float(x["goods_amount"] or 0),
                str(x["received_date"] or ""),
                int(x["id"] or 0),
            )
        )
        sale_invoice_rids[int(row["id"])] = int(representative["id"])

    # v2.3.103 — SOURCE DE VÉRITÉ FINANCIÈRE : LE SUIVI.
    # Les PDF ne servent qu'à ouvrir un justificatif et ne participent JAMAIS
    # au calcul du CA. Les montants de ventes officiels sont lus dans repairs,
    # exactement comme la page CA / Déclarations et le tableau de bord Atelier.
    con = db()
    suivi_sales_rows = con.execute("""
        SELECT accounting_month AS m,
               COALESCE(SUM(accounting_service_amount),0) AS service,
               COALESCE(SUM(accounting_goods_amount),0) AS goods
        FROM repairs
        WHERE accounting_year=?
          AND accounting_month BETWEEN 1 AND 12
        GROUP BY accounting_month
    """, (year,)).fetchall()
    con.close()
    suivi_sales_by_month = {
        int(r["m"]): float(r["service"] or 0) + float(r["goods"] or 0)
        for r in suivi_sales_rows
    }
    sales_total = sum(suivi_sales_by_month.values())

    entries = all_entries
    if search_q:
        needle = search_q.casefold()
        def _ledger_search_text(row):
            values = [
                row["operation"], row["party"], row["entry_date"], row["description"],
                row["payment_type"], row["invoice_no"], row["remarks"],
                row["document_original_name"], row["document_path"],
                f"{float(row['amount_ttc'] or 0):.2f}",
                f"{float(row['amount_ttc'] or 0):.2f}".replace('.', ','),
            ]
            return " ".join(str(v or "") for v in values).casefold()
        entries = [row for row in all_entries if needle in _ledger_search_text(row)]

    months = []
    # Les achats restent issus du registre Achats/Ventes ; ils ne constituent pas le CA.
    purchases_total = sum(
        float(row["amount_ttc"] or 0) for row in all_entries
        if (row["operation"] or "").casefold() == "achat"
    )

    for month in range(12, 0, -1):
        month_entries = []
        month_purchases = 0.0

        for row in entries:
            try:
                row_month = int(str(row["entry_date"])[5:7])
            except Exception:
                row_month = 0
            if row_month != month:
                continue

            month_entries.append(row)

        # Totaux mensuels officiels indépendants de la recherche affichée.
        for row in all_entries:
            try:
                row_month = int(str(row["entry_date"])[5:7])
            except Exception:
                row_month = 0
            if row_month == month and (row["operation"] or "").casefold() == "achat":
                month_purchases += float(row["amount_ttc"] or 0)

        months.append({
            "number": month,
            "name": ledger_month_name(month),
            "entries": month_entries,
            "purchases": month_purchases,
            "sales": suivi_sales_by_month.get(month, 0.0),
        })

    return render_template(
        "achats_ventes.html",
        year=year,
        months=months,
        purchases_total=purchases_total,
        sales_total=sales_total,
        balance_total=sales_total - purchases_total,
        today=datetime.now().strftime("%Y-%m-%d"),
        supplier_docs_count=supplier_docs_count,
        supplier_docs_missing=supplier_docs_missing,
        sale_invoice_rids=sale_invoice_rids,
        search_q=search_q,
        search_count=len(entries),
    )


@app.route("/achats-ventes/add", methods=["POST"])
def achats_ventes_add():
    operation = request.form.get("operation", "").strip().capitalize()
    if operation not in {"Achat", "Vente"}:
        flash("Opération invalide.")
        return redirect(url_for("achats_ventes_page"))

    entry_date = request.form.get("entry_date", "").strip()
    if not ledger_valid_date(entry_date):
        flash("Date invalide.")
        return redirect(url_for("achats_ventes_page"))

    try:
        amount = parse_money_input(request.form.get("amount_ttc"))
    except Exception:
        flash("Montant TTC invalide.")
        return redirect(url_for("achats_ventes_page", year=entry_date[:4]))

    created = now().isoformat(timespec="seconds")
    con = db()
    cur = con.execute("""
        INSERT INTO ledger_entries(
            operation, party, entry_date, description, amount_ttc,
            payment_type, invoice_no, remarks, created_at, updated_at
        )
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (
        operation,
        request.form.get("party", "").strip(),
        entry_date,
        request.form.get("description", "").strip(),
        amount,
        request.form.get("payment_type", "").strip(),
        request.form.get("invoice_no", "").strip(),
        request.form.get("remarks", "").strip(),
        created,
        created,
    ))
    entry_id = int(cur.lastrowid)
    con.commit()
    con.close()

    document = request.files.get("supplier_document")
    document_msg = ""
    if document and str(document.filename or "").strip():
        if operation != "Achat":
            document_msg = " La pièce n'a pas été rangée : elle est réservée aux achats fournisseurs."
        else:
            try:
                saved = save_ledger_document(entry_id, document)
                if saved:
                    document_msg = " Facture fournisseur rangée et liée à l'achat."
            except ValueError as exc:
                document_msg = f" Achat enregistré, mais pièce non jointe : {exc}"

    audit_event("LEDGER_ADD", f"{operation} {entry_date} {amount:.2f}", request.remote_addr)
    flash("Ligne ajoutée." + document_msg)
    return redirect(url_for("achats_ventes_page", year=entry_date[:4]))


@app.route("/achats-ventes/<int:entry_id>/document", methods=["POST"])
def achats_ventes_document_add(entry_id):
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    con.close()
    if not row:
        return "Ligne introuvable", 404
    year = str(row["entry_date"] or now().strftime("%Y-%m-%d"))[:4]
    if str(row["operation"] or "").casefold() != "achat":
        flash("Les factures fournisseurs peuvent être liées uniquement à un achat.")
        return redirect(url_for("achats_ventes_page", year=year))
    storage = request.files.get("supplier_document")
    if not storage or not str(storage.filename or "").strip():
        flash("Choisis une facture à joindre.")
        return redirect(url_for("achats_ventes_page", year=year))
    try:
        dest = save_ledger_document(entry_id, storage)
    except ValueError as exc:
        flash(str(exc))
        return redirect(url_for("achats_ventes_page", year=year))
    audit_event("LEDGER_DOCUMENT_ADD", f"id={entry_id} file={dest.name if dest else ''}", request.remote_addr)
    flash("Facture fournisseur liée et rangée automatiquement.")
    return redirect(url_for("achats_ventes_page", year=year))


@app.route("/achats-ventes/<int:entry_id>/document/view")
def achats_ventes_document_view(entry_id):
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    con.close()
    if not row:
        return "Ligne introuvable", 404
    path = ledger_document_file(row)
    if not path:
        return "Pièce justificative introuvable", 404
    # Si le résolveur a retrouvé l'original sous un autre nom, on corrige le lien pour de bon.
    try:
        resolved_rel = str(path.relative_to(FOULFIX_ROOT))
        if resolved_rel != str(row["document_path"] or ""):
            con_fix = db()
            con_fix.execute(
                "UPDATE ledger_entries SET document_path=?, updated_at=? WHERE id=?",
                (resolved_rel, now().isoformat(timespec="seconds"), entry_id),
            )
            con_fix.commit()
            con_fix.close()
    except Exception:
        pass
    return send_file(path, as_attachment=False, download_name=path.name)


@app.route("/achats-ventes/<int:entry_id>/edit", methods=["POST"])
def achats_ventes_edit(entry_id):
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    if not row:
        con.close()
        return "Ligne introuvable", 404

    operation = request.form.get("operation", "").strip().capitalize()
    if operation not in {"Achat", "Vente"}:
        con.close()
        flash("Opération invalide.")
        return redirect(url_for("achats_ventes_page", year=str(row["entry_date"])[:4]))

    entry_date = request.form.get("entry_date", "").strip()
    if not ledger_valid_date(entry_date):
        con.close()
        flash("Date invalide.")
        return redirect(url_for("achats_ventes_page", year=str(row["entry_date"])[:4]))

    try:
        amount = parse_money_input(request.form.get("amount_ttc"))
    except Exception:
        con.close()
        flash("Montant TTC invalide.")
        return redirect(url_for("achats_ventes_page", year=str(row["entry_date"])[:4]))

    con.execute("""
        UPDATE ledger_entries SET
            operation=?, party=?, entry_date=?, description=?, amount_ttc=?,
            payment_type=?, invoice_no=?, remarks=?, updated_at=?
        WHERE id=?
    """, (
        operation,
        request.form.get("party", "").strip(),
        entry_date,
        request.form.get("description", "").strip(),
        amount,
        request.form.get("payment_type", "").strip(),
        request.form.get("invoice_no", "").strip(),
        request.form.get("remarks", "").strip(),
        now().isoformat(timespec="seconds"),
        entry_id,
    ))
    con.commit()
    con.close()

    audit_event("LEDGER_EDIT", f"id={entry_id}", request.remote_addr)
    flash("Ligne modifiée.")
    return redirect(url_for("achats_ventes_page", year=entry_date[:4]))


@app.route("/achats-ventes/<int:entry_id>/delete", methods=["POST"])
def achats_ventes_delete(entry_id):
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    if not row:
        con.close()
        return "Ligne introuvable", 404

    year = str(row["entry_date"])[:4]
    backup_database(force=True, tag="avant_suppression_achat_vente")
    con.execute("DELETE FROM ledger_entries WHERE id=?", (entry_id,))
    con.commit()
    con.close()

    audit_event("LEDGER_DELETE", f"id={entry_id}", request.remote_addr)
    flash("Ligne supprimée.")
    return redirect(url_for("achats_ventes_page", year=year))


@app.route("/total")
def total_page():
    """
    CA / Déclarations :
    - calcul automatique depuis le Suivi,
    - correction manuelle possible par cellule.
    """
    con = db()

    rows = con.execute("""
        SELECT accounting_year y, accounting_month m,
               SUM(COALESCE(accounting_service_amount,0)) service_total,
               SUM(COALESCE(accounting_goods_amount,0)) goods_total
        FROM repairs
        WHERE accounting_year IS NOT NULL
          AND accounting_month BETWEEN 1 AND 12
        GROUP BY accounting_year, accounting_month
        ORDER BY accounting_year, accounting_month
    """).fetchall()

    override_rows = con.execute("""
        SELECT year, month, category, amount
        FROM ca_overrides
    """).fetchall()
    con.close()

    bnc_auto = {
        2024: {7: 500.0},
        2025: {7: 450.0},
        2026: {},
    }

    bic_auto = {}
    for row in rows:
        y = int(row["y"])
        m = int(row["m"])
        bic_auto.setdefault(y, {})[m] = {
            "service": float(row["service_total"] or 0),
            "goods": float(row["goods_total"] or 0),
        }

    overrides = {
        (int(row["year"]), int(row["month"]), row["category"]): float(row["amount"] or 0)
        for row in override_rows
    }

    years_set = set(bnc_auto) | set(bic_auto) | {key[0] for key in overrides}
    years_set.add(now().year)

    years = []
    for year in sorted(years_set):
        auto_bnc = [0.0] * 12
        auto_service = [0.0] * 12
        auto_goods = [0.0] * 12

        for month, value in bnc_auto.get(year, {}).items():
            auto_bnc[month-1] = float(value)

        for month, values in bic_auto.get(year, {}).items():
            auto_service[month-1] = float(values.get("service", 0))
            auto_goods[month-1] = float(values.get("goods", 0))

        bnc, service, goods = [], [], []
        overridden = {"bnc": [], "service": [], "goods": []}

        for month in range(1, 13):
            for category, auto_values, result_values in (
                ("bnc", auto_bnc, bnc),
                ("service", auto_service, service),
                ("goods", auto_goods, goods),
            ):
                key = (year, month, category)
                if key in overrides:
                    result_values.append(overrides[key])
                    overridden[category].append(True)
                else:
                    result_values.append(auto_values[month-1])
                    overridden[category].append(False)

        total_months = [bnc[i] + service[i] + goods[i] for i in range(12)]

        years.append({
            "year": year,
            "bnc": bnc,
            "service": service,
            "goods": goods,
            "auto_bnc": auto_bnc,
            "auto_service": auto_service,
            "auto_goods": auto_goods,
            "overridden": overridden,
            "total": total_months,
            "bnc_total": sum(bnc),
            "service_total": sum(service),
            "goods_total": sum(goods),
            "grand_total": sum(total_months),
        })

    return render_template("ca_declarations.html", years=years)


@app.route("/total/save", methods=["POST"])
def total_save():
    """
    Ne garde en base que les cellules différentes du calcul automatique.
    Si une valeur est remise sur l'auto, la correction est supprimée.
    """
    con = db()

    reset_year = request.form.get("reset_year", "").strip()
    if reset_year.isdigit():
        year = int(reset_year)
        con.execute("DELETE FROM ca_overrides WHERE year=?", (year,))
        con.commit()
        con.close()
        flash(f"{year} remis entièrement en automatique depuis le Suivi.")
        return redirect(url_for("total_page"))

    auto_rows = con.execute("""
        SELECT accounting_year y, accounting_month m,
               SUM(COALESCE(accounting_service_amount,0)) service_total,
               SUM(COALESCE(accounting_goods_amount,0)) goods_total
        FROM repairs
        WHERE accounting_year IS NOT NULL
          AND accounting_month BETWEEN 1 AND 12
        GROUP BY accounting_year, accounting_month
    """).fetchall()

    auto_map = {}
    for row in auto_rows:
        auto_map[(int(row["y"]), int(row["m"]), "service")] = float(row["service_total"] or 0)
        auto_map[(int(row["y"]), int(row["m"]), "goods")] = float(row["goods_total"] or 0)

    bnc_auto = {
        (2024, 7, "bnc"): 500.0,
        (2025, 7, "bnc"): 450.0,
    }

    changed = 0
    removed = 0
    stamp = now().isoformat(timespec="seconds")

    for key, raw_value in request.form.items():
        match = re.fullmatch(r"ca_(bnc|service|goods)_(\d{4})_(\d{1,2})", key)
        if not match:
            continue

        category = match.group(1)
        year = int(match.group(2))
        month = int(match.group(3))
        if not 1 <= month <= 12:
            continue

        try:
            value = parse_money_input(raw_value)
        except Exception:
            continue

        if category == "bnc":
            auto_value = bnc_auto.get((year, month, category), 0.0)
        else:
            auto_value = auto_map.get((year, month, category), 0.0)

        if abs(value - auto_value) < 0.005:
            cur = con.execute("""
                DELETE FROM ca_overrides
                WHERE year=? AND month=? AND category=?
            """, (year, month, category))
            removed += cur.rowcount
        else:
            con.execute("""
                INSERT INTO ca_overrides(year,month,category,amount,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(year,month,category)
                DO UPDATE SET amount=excluded.amount, updated_at=excluded.updated_at
            """, (year, month, category, value, stamp))
            changed += 1

    con.commit()
    con.close()

    if changed or removed:
        flash(f"CA enregistré : {changed} correction(s), {removed} retour(s) en automatique.")
    else:
        flash("Aucune correction manuelle nécessaire.")

    return redirect(url_for("total_page"))


@app.route("/total/reset/<int:year>", methods=["POST"])
def total_reset_year(year):
    con = db()
    con.execute("DELETE FROM ca_overrides WHERE year=?", (year,))
    con.commit()
    con.close()
    flash(f"{year} remis en synchronisation automatique avec le Suivi.")
    return redirect(url_for("total_page"))


@app.route("/repair/new", methods=["GET", "POST"])
def repair_new():
    # Nouvelle réparation = écran potentiellement visible par le client.
    # On active automatiquement le mode confidentiel.
    if request.method == "GET":
        session["client_mode"] = True
        session.pop("client_mode_rid", None)

    def active_clients_for_form():
        con_clients = db()
        rows = con_clients.execute("""
            SELECT id, name, first_name, last_name, company,
                   address_street, postal_code, city, phone, email
            FROM clients
            WHERE COALESCE(archived,0)=0
            ORDER BY
                COALESCE(first_name,'') COLLATE NOCASE,
                COALESCE(NULLIF(last_name,''), name) COLLATE NOCASE,
                id
        """).fetchall()
        con_clients.close()
        return [dict(row) for row in rows]

    if request.method == "POST":
        selected_client_id_raw = request.form.get("client_id", "").strip()

        first_name = request.form.get("first_name","").strip()
        last_name = request.form.get("last_name","").strip()
        company = request.form.get("company","").strip()
        contact_name = compose_client_name(last_name, first_name).strip()
        name = contact_name or company

        if not name:
            flash("Renseigne au moins un nom/prénom ou le nom de l’entreprise.")
            return render_template(
                "repair_form.html",
                today=now().strftime("%Y-%m-%d"),
                clients=active_clients_for_form()
            )

        address_street = request.form.get("address_street","").strip()
        postal_code = request.form.get("postal_code","").strip()
        city = request.form.get("city","").strip()
        address = "\n".join(
            [x for x in [address_street, (postal_code + " " + city).strip()] if x]
        )
        phone = request.form.get("phone","").strip()
        email = request.form.get("email","").strip()
        created = now().isoformat(timespec="seconds")

        con = db()
        client = None

        # Si un ancien client a été choisi explicitement, on réutilise toujours
        # cette fiche plutôt que de rechercher/créer un doublon.
        if selected_client_id_raw.isdigit():
            client = con.execute("""
                SELECT * FROM clients
                WHERE id=? AND COALESCE(archived,0)=0
            """, (int(selected_client_id_raw),)).fetchone()

        # Sans sélection explicite, conserve la détection historique e-mail/téléphone.
        if not client and not selected_client_id_raw:
            if email:
                client = con.execute("""
                    SELECT * FROM clients
                    WHERE COALESCE(archived,0)=0
                      AND lower(email)=lower(?)
                """, (email,)).fetchone()
            if not client and phone:
                client = con.execute("""
                    SELECT * FROM clients
                    WHERE COALESCE(archived,0)=0
                      AND phone=?
                """, (phone,)).fetchone()

        if selected_client_id_raw and not client:
            con.close()
            flash("Le client sélectionné est introuvable ou archivé.")
            return render_template(
                "repair_form.html",
                today=request.form.get("received_date") or now().strftime("%Y-%m-%d"),
                clients=active_clients_for_form()
            )

        if client:
            con.execute("""
                UPDATE clients
                SET name=?, last_name=?, first_name=?, company=?,
                    address=?, address_street=?, postal_code=?, city=?,
                    phone=?, email=?, updated_at=?
                WHERE id=?
            """, (
                name, last_name, first_name, company,
                address, address_street, postal_code, city,
                phone, email, created, client["id"]
            ))
            client_id = int(client["id"])
        else:
            cur = con.execute("""
                INSERT INTO clients(
                    name,last_name,first_name,company,
                    address,address_street,postal_code,city,phone,email,created_at,updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                name,last_name,first_name,company,
                address,address_street,postal_code,city,phone,email,created,created
            ))
            client_id = int(cur.lastrowid)

        dossier = make_dossier_no()
        token = secrets.token_urlsafe(18)
        received_date = request.form.get("received_date") or now().strftime("%Y-%m-%d")
        try:
            received_dt = datetime.strptime(received_date, "%Y-%m-%d")
            followup_year = received_dt.year
            followup_month = received_dt.month
        except Exception:
            followup_year = now().year
            followup_month = now().month

        con.execute("""
            INSERT INTO repairs(
                dossier_no, client_id, created_at, received_date,
                device_type, brand_model, serial_no, system_name, system_password,
                accessories, device_state, problem, remarks, status, signature_token,
                followup_year, followup_month, accounting_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            dossier, client_id, created,
            received_date,
            request.form.get("device_type",""),
            request.form.get("brand_model",""),
            request.form.get("serial_no",""),
            request.form.get("system_name",""),
            encrypt_repair_password(request.form.get("system_password","")),
            request.form.get("accessories",""),
            request.form.get("device_state",""),
            request.form.get("problem",""),
            request.form.get("remarks",""),
            "Reçu", token,
            followup_year, followup_month, "normal"
        ))
        rid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        record_repair_status_change(con, rid, "", "Reçu", "Dossier créé")
        con.commit()
        con.close()

        session["client_mode"] = True
        session["client_mode_rid"] = int(rid)
        # V2.3.215 : aucune écriture Google automatique.
        return redirect(url_for("repair_detail", rid=rid))

    return render_template(
        "repair_form.html",
        today=now().strftime("%Y-%m-%d"),
        clients=active_clients_for_form()
    )



def kdeconnect_available_devices():
    """Retourne les appareils KDE Connect appairés ET joignables."""
    cli = shutil.which("kdeconnect-cli")
    if not cli:
        return []
    try:
        proc = subprocess.run(
            [cli, "--list-available", "--id-name-only"],
            capture_output=True,
            text=True,
            timeout=6,
            check=False,
        )
    except Exception:
        return []

    if proc.returncode != 0:
        return []

    devices = []
    for raw in (proc.stdout or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        dev_id = parts[0].strip()
        dev_name = parts[1].strip() if len(parts) > 1 else dev_id
        if dev_id:
            devices.append({"id": dev_id, "name": dev_name})
    return devices


def normalize_sms_phone(phone):
    """Normalise les numéros FR courants pour KDE Connect."""
    value = re.sub(r"[^0-9+]", "", str(phone or "").strip())
    if value.startswith("00"):
        value = "+" + value[2:]
    if re.fullmatch(r"0[1-9][0-9]{8}", value):
        value = "+33" + value[1:]
    return value


@app.route("/kdeconnect/sms/send", methods=["POST"])
def kdeconnect_send_sms():
    """Envoie réellement le SMS via le téléphone Android connecté à KDE Connect."""
    phone = normalize_sms_phone(request.form.get("phone", ""))
    message = str(request.form.get("message", "")).strip()
    device_id = str(request.form.get("device_id", "")).strip()
    return_url = str(request.form.get("return_url", "")).strip()

    if not re.fullmatch(r"\+?[0-9]{6,15}", phone):
        flash("Numéro de téléphone invalide pour l'envoi SMS.")
        return redirect(return_url or url_for("contacts_page"))
    if not message:
        flash("Le message est vide.")
        return redirect(return_url or url_for("contacts_page"))

    cli = shutil.which("kdeconnect-cli")
    if not cli:
        flash("KDE Connect CLI introuvable : installe/active kdeconnect-cli.")
        return redirect(return_url or url_for("contacts_page"))

    devices = kdeconnect_available_devices()
    available_ids = {d["id"] for d in devices}
    if not device_id and len(devices) == 1:
        device_id = devices[0]["id"]

    if not device_id or device_id not in available_ids:
        flash("Aucun téléphone KDE Connect joignable, ou téléphone sélectionné indisponible.")
        return redirect(return_url or url_for("contacts_page"))

    try:
        proc = subprocess.run(
            [
                cli,
                "--send-sms", message,
                "--destination", phone,
                "--device", device_id,
            ],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except subprocess.TimeoutExpired:
        flash("KDE Connect n'a pas répondu à temps. Vérifie que le téléphone est joignable.")
        return redirect(return_url or url_for("contacts_page"))
    except Exception as exc:
        flash(f"Erreur KDE Connect : {exc}")
        return redirect(return_url or url_for("contacts_page"))

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "Erreur inconnue").strip()
        flash(f"Échec envoi SMS via KDE Connect : {detail}")
        return redirect(return_url or url_for("contacts_page"))

    audit_event(
        "KDECONNECT_SMS",
        f"SMS envoyé via KDE Connect vers {phone} avec device={device_id}",
        request.remote_addr,
    )
    flash(f"SMS envoyé via KDE Connect à {phone}.")
    return redirect(return_url or url_for("contacts_page"))


@app.route("/client/<int:client_id>/message")
def client_message_from_client(client_id):
    """Prépare un message à partir de la fiche client, sans dossier obligatoire."""
    con = db()
    row = con.execute("""
        SELECT id, name, first_name, last_name, company, phone
        FROM clients
        WHERE id=?
    """, (client_id,)).fetchone()
    con.close()

    if not row:
        return "Client introuvable", 404

    c = dict(row)
    first_name = str(c.get("first_name") or "").strip()
    last_name = str(c.get("last_name") or "").strip()
    company = str(c.get("company") or "").strip()
    raw_name = str(c.get("name") or "").strip()

    # Ne jamais saluer un client avec son adresse e-mail.
    # Priorité : prénom -> prénom+nom -> nom/raison sociale -> formule générique.
    if first_name:
        display_name = first_name
    elif last_name:
        display_name = last_name
    elif company:
        display_name = company
    elif raw_name and "@" not in raw_name:
        display_name = raw_name
    else:
        display_name = ""

    salutation = "Bonjour,"
    ident = business_identity()
    footer = message_signature()

    templates = {
        "libre": f"{salutation}\n\n\n\n{footer}",
        "rappel": (
            f"{salutation}\n\n"
            f"Je vous contacte au sujet de votre matériel chez {ident['name']}. "
            "Vous pouvez simplement me répondre à ce message.\n\n"
            f"{footer}"
        ),
        "dispo": (
            f"{salutation}\n\n"
            "Je suis disponible si vous souhaitez faire le point concernant votre matériel.\n\n"
            f"{footer}"
        ),
    }

    phone_raw = str(c.get("phone") or "").strip()
    phone_sms = re.sub(r"[^0-9+]", "", phone_raw)

    return render_template(
        "client_message.html",
        r=None,
        client=c,
        templates=templates,
        auto_key="libre",
        phone_raw=phone_raw,
        phone_sms=phone_sms,
        from_client=True,
        kde_devices=kdeconnect_available_devices(),
    )


@app.route("/repair/<int:rid>/message-client")
def client_message(rid):
    """Prépare un SMS/message client sans l'envoyer automatiquement."""
    con = db()
    row = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name,
               c.phone client_phone
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()

    if not row:
        return "Dossier introuvable", 404

    r = dict(row)
    first_name = str(r.get("client_first_name") or "").strip()
    display_name = first_name or str(r.get("client_name") or "").strip()
    salutation = "Bonjour,"

    device_bits = [
        str(r.get("device_type") or "").strip(),
        str(r.get("brand_model") or "").strip(),
    ]
    device = " ".join(x for x in device_bits if x).strip() or "votre matériel"

    ident = business_identity()
    footer = message_signature()
    status = str(r.get("status") or "").strip()

    templates = {
        "auto": "",
        "diagnostic": (
            f"{salutation}\n\n"
            f"Le diagnostic de votre {device} est en cours. "
            "Je reviens vers vous dès que j'ai plus d'informations.\n\n"
            f"{footer}"
        ),
        "accord": (
            f"{salutation}\n\n"
            f"Le diagnostic de votre {device} est terminé. "
            "Je vous contacte afin d'avoir votre accord avant intervention. "
            "Vous pouvez simplement me répondre à ce message.\n\n"
            f"{footer}"
        ),
        "piece": (
            f"{salutation}\n\n"
            f"La pièce nécessaire pour votre {device} a été commandée. "
            "Je vous tiens au courant dès sa réception.\n\n"
            f"{footer}"
        ),
        "termine": (
            f"{salutation}\n\n"
            f"Votre {device} est prêt. Vous pouvez venir le récupérer chez {ident['name']}.\n\n"
            f"{footer}"
        ),
        "pieces": (
            f"{salutation}\n\n"
            f"Comme convenu, votre matériel est laissé à {ident['name']} pour pièces "
            "en remplacement du forfait diagnostic de 30 €.\n\n"
            f"{footer}"
        ),
        "libre": (
            f"{salutation}\n\n"
            "\n\n"
            f"{footer}"
        ),
    }

    auto_key = {
        "Diagnostic": "diagnostic",
        "En attente accord": "accord",
        "En attente pièce": "piece",
        "Terminé": "termine",
        "Laissé pour pièces": "pieces",
    }.get(status, "libre")

    templates["auto"] = templates[auto_key]

    phone_raw = str(r.get("client_phone") or "").strip()
    phone_sms = re.sub(r"[^0-9+]", "", phone_raw)

    return render_template(
        "client_message.html",
        r=r,
        templates=templates,
        auto_key=auto_key,
        phone_raw=phone_raw,
        phone_sms=phone_sms,
        kde_devices=kdeconnect_available_devices(),
    )


@app.route("/repair/<int:rid>")
def repair_detail(rid):
    con = db()
    r = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name,
               c.company client_company,
               c.address client_address,
               c.address_street client_address_street,
               c.postal_code client_postal_code,
               c.city client_city,
               c.phone client_phone,
               c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()
    if not r:
        return "Dossier introuvable", 404
    r = dict(r)
    r["has_system_password"] = bool(r.get("system_password"))
    r["system_password"] = ""  # jamais injecté en clair dans le HTML initial
    sign_url = f"http://{local_ip()}:5000/sign/{r['signature_token']}"
    return render_template("repair_detail.html", r=r, sign_url=sign_url)


@app.route("/repair/<int:rid>/reveal-system-password", methods=["POST"])
def reveal_system_password(rid):
    con = db()
    row = con.execute("SELECT system_password FROM repairs WHERE id=?", (rid,)).fetchone()
    con.close()
    if not row:
        return {"error": "Dossier introuvable"}, 404
    try:
        value = decrypt_repair_password(row["system_password"])
    except RuntimeError as exc:
        return {"error": str(exc)}, 500
    audit_event("REVEAL_REPAIR_PASSWORD", f"repair_id={rid}", request.remote_addr)
    return {"system_password": value}


@app.route("/repair/<int:rid>/quick-edit", methods=["POST"])
def repair_quick_edit(rid):
    """
    Edition directe d'une ligne depuis le tableau Suivi.
    Reprend les colonnes principales du ODS sans obliger à ouvrir la fiche complète.
    """
    con = db()
    r = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()

    if not r:
        con.close()
        return "Dossier introuvable", 404

    # V2.3.21 : l'identité client n'est plus modifiable depuis le Suivi.
    # Prénom / Nom restent gérés uniquement dans la fiche Clients pour éviter
    # les inversions et les incohérences de synchronisation.
    received_date = request.form.get("received_date", "").strip() or r["received_date"]

    try:
        rd = datetime.strptime(received_date, "%Y-%m-%d")
        followup_year, followup_month = rd.year, rd.month
    except Exception:
        followup_year = int(r["followup_year"] or now().year)
        followup_month = int(r["followup_month"] or now().month)

    followup_period = request.form.get("followup_period", "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", followup_period):
        fy, fm = followup_period.split("-")
        if 1 <= int(fm) <= 12:
            followup_year, followup_month = int(fy), int(fm)

    try:
        service_amount = parse_money_input(request.form.get("service_amount", "0"))
    except Exception:
        service_amount = float(r["service_amount"] or 0)

    try:
        goods_amount = parse_money_input(request.form.get("goods_amount", "0"))
    except Exception:
        goods_amount = float(r["goods_amount"] or 0)

    invoice_text = request.form.get("legacy_invoice_text", "").strip()
    normalized_invoice = re.sub(r"\s", "", invoice_text)
    invoice_no = normalized_invoice if re.fullmatch(r"\d{10,14}(?:-\d+)?", normalized_invoice) else ""

    accounting_status = request.form.get("accounting_status", "normal").strip()
    if accounting_status not in {"normal", "yellow", "red"}:
        accounting_status = "normal"

    accounting_year = r["accounting_year"]
    accounting_month = r["accounting_month"]
    accounting_date = request.form.get("accounting_date", "").strip()

    if accounting_date:
        try:
            ad = datetime.strptime(accounting_date, "%Y-%m-%d")
            accounting_year, accounting_month = ad.year, ad.month
        except Exception:
            accounting_date = r["accounting_date"] or ""

    non_facture = "non factur" in invoice_text.casefold()

    if non_facture:
        accounting_status = "yellow"
        accounting_year = None
        accounting_month = None
        accounting_date = ""
        accounting_service_amount = 0.0
        accounting_goods_amount = 0.0
        paid = 0
    elif accounting_status == "red":
        accounting_year = None
        accounting_month = None
        accounting_date = ""
        accounting_service_amount = 0.0
        accounting_goods_amount = 0.0
        paid = 0
    else:
        # Si l'utilisateur fait passer une attente en payé et n'a pas choisi
        # de période, on prend le mois courant : encaissement réel.
        if not accounting_date:
            payment_dt = now()
            accounting_date = payment_dt.strftime("%Y-%m-%d")
            accounting_year, accounting_month = payment_dt.year, payment_dt.month

        accounting_service_amount = service_amount
        accounting_goods_amount = goods_amount
        paid = 1

        # Si le mois de déclaration diffère du mois du suivi, la ligne doit être jaune.
        if (accounting_year, accounting_month) != (followup_year, followup_month):
            accounting_status = "yellow"

    # V2.3.85 — logique atelier simplifiée : un règlement enregistré signifie
    # que le client repart avec son matériel. On marque donc automatiquement
    # le dossier Restitué, sans bouton de restitution séparé dans le Suivi.
    quick_status = r["status"]
    quick_returned_at = r["returned_at"] if "returned_at" in r.keys() else None
    if paid:
        quick_status = "Restitué"
        if r["status"] != "Restitué" or not quick_returned_at:
            quick_returned_at = now().date().isoformat()

    quick_payment_mode = normalize_payment_mode(request.form.get("payment_mode", ""))
    if r["legacy_imported"]:
        quick_payment_method = r["payment_method"] or ""
        quick_payment_detail = r["payment_detail"] or ""
    elif paid and quick_payment_mode == "MIXTE":
        quick_payment_mode, quick_payment_method, quick_payment_detail, pay_error = payment_data_from_form(
            service_amount + goods_amount, r["payment_mode"], r["payment_method"], r["payment_detail"]
        )
        if pay_error:
            con.close()
            flash(pay_error)
            return redirect(url_for("index", year=followup_year, edit=rid) + f"#edit-{rid}")
    else:
        quick_payment_method = quick_payment_mode
        quick_payment_detail = ""

    con.execute("""
        UPDATE repairs SET
            received_date=?,
            problem=?,
            legacy_call_note=?,
            legacy_invoice_text=?,
            invoice_no=?,
            service_amount=?,
            goods_amount=?,
            payment_method=?,
            payment_mode=?,
            payment_detail=?,
            sent_via=?,
            remarks=?,
            paid=?,
            followup_year=?,
            followup_month=?,
            accounting_year=?,
            accounting_month=?,
            accounting_date=?,
            accounting_status=?,
            accounting_service_amount=?,
            accounting_goods_amount=?,
            status=?,
            returned_at=?
        WHERE id=?
    """, (
        received_date,
        request.form.get("problem", "").strip(),
        r["legacy_call_note"] or "",
        invoice_text,
        invoice_no,
        service_amount,
        goods_amount,
        quick_payment_method,
        quick_payment_mode,
        quick_payment_detail,
        request.form.get("sent_via", "").strip(),
        request.form.get("remarks", "").strip(),
        paid,
        followup_year,
        followup_month,
        accounting_year,
        accounting_month,
        accounting_date,
        accounting_status,
        accounting_service_amount,
        accounting_goods_amount,
        quick_status,
        quick_returned_at,
        rid,
    ))

    record_repair_status_change(con, rid, r["status"], quick_status, "Règlement enregistré depuis le Suivi" if paid else "")
    con.commit()
    con.close()

    flash("Ligne du suivi enregistrée.")
    return redirect(url_for("index", year=followup_year) + f"#suivi-{rid}")


@app.route("/repair/<int:rid>/edit", methods=["GET", "POST"])
def repair_edit(rid):
    """Édition du suivi/réparation uniquement.

    V2.3.121 : la facturation, les règlements et la comptabilité ne sont plus
    modifiables depuis cet écran. Ils restent gérés par l'écran Facture.
    """
    con = db()
    r = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name,
               c.company client_company,
               c.address client_address,
               c.address_street client_address_street,
               c.postal_code client_postal_code,
               c.city client_city,
               c.phone client_phone,
               c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()

    if not r:
        con.close()
        return "Dossier introuvable", 404

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        company = request.form.get("company", "").strip()

        name = compose_client_name(last_name, first_name).strip()
        if not name:
            name = company or str(r["client_name"] or "").strip()

        address_street = request.form.get("address_street", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        city = request.form.get("city", "").strip()
        address = "\n".join([x for x in [address_street, (postal_code + " " + city).strip()] if x])

        received_date = request.form.get("received_date", "").strip() or r["received_date"]
        try:
            rd = datetime.strptime(received_date, "%Y-%m-%d")
            followup_year, followup_month = rd.year, rd.month
        except Exception:
            followup_year = r["followup_year"] or now().year
            followup_month = r["followup_month"] or now().month

        con.execute("""
            UPDATE clients SET
                first_name=?, last_name=?, name=?, company=?, address=?, address_street=?,
                postal_code=?, city=?, phone=?, email=?,
                google_sync_status=?, google_sync_error=?, updated_at=?
            WHERE id=?
        """, (
            first_name, last_name, name, company, address, address_street,
            postal_code, city,
            request.form.get("phone", "").strip(),
            request.form.get("email", "").strip(),
            "À synchroniser", "", now().isoformat(timespec="seconds"),
            r["client_id"]
        ))

        new_status = request.form.get("status", "Reçu")
        finished_at = r["finished_at"]
        if new_status in {"Terminé", "Restitué"}:
            if not finished_at:
                finished_at = now().isoformat(timespec="seconds")
        else:
            finished_at = None

        # Sur l'écran Suivi, le statut est volontairement manuel.
        # La logique "paiement = Restitué" reste dans les écrans d'encaissement/facture.
        returned_at = r["returned_at"] if "returned_at" in r.keys() else None
        requested_returned_at = request.form.get("returned_at", "").strip()
        if new_status == "Restitué":
            if requested_returned_at:
                try:
                    datetime.strptime(requested_returned_at, "%Y-%m-%d")
                    returned_at = requested_returned_at
                except ValueError:
                    flash("Date de restitution invalide.")
                    con.close()
                    return redirect(url_for("repair_edit", rid=rid))
            elif r["status"] != "Restitué" or not returned_at:
                returned_at = now().date().isoformat()
        else:
            returned_at = None

        # V2.3.212 — chez Foul-Fix, matériel restitué = règlement encaissé.
        # Si la date de restitution change sur un dossier déjà payé, la date
        # d'encaissement suit automatiquement, sauf si elle a été modifiée
        # explicitement dans le formulaire.
        accounting_date = str(r["accounting_date"] or "")[:10]
        accounting_year = r["accounting_year"]
        accounting_month = r["accounting_month"]
        accounting_status = r["accounting_status"] or "normal"
        requested_accounting_date = request.form.get("accounting_date", accounting_date).strip()

        if r["paid"]:
            if requested_accounting_date:
                try:
                    datetime.strptime(requested_accounting_date, "%Y-%m-%d")
                except ValueError:
                    flash("Date d'encaissement invalide.")
                    con.close()
                    return redirect(url_for("repair_edit", rid=rid))

            old_returned_at = str(r["returned_at"] or "")[:10]
            returned_day = str(returned_at or "")[:10]
            returned_changed = returned_day != old_returned_at
            accounting_changed = requested_accounting_date != accounting_date

            if accounting_changed:
                accounting_date = requested_accounting_date
            elif returned_changed and returned_day:
                accounting_date = returned_day
            elif not accounting_date and returned_day:
                accounting_date = returned_day

            if accounting_date:
                ad = datetime.strptime(accounting_date, "%Y-%m-%d")
                accounting_year, accounting_month = ad.year, ad.month
                accounting_status = (
                    "yellow"
                    if (accounting_year, accounting_month) != (int(followup_year), int(followup_month))
                    else "normal"
                )

        con.execute("""
            UPDATE repairs SET
                received_date=?, device_type=?, brand_model=?, serial_no=?,
                system_name=?, system_password=?, accessories=?, device_state=?,
                problem=?, diagnosis=?, work_done=?, tests_validation=?, remarks=?,
                status=?, finished_at=?, returned_at=?, legacy_call_note=?,
                followup_year=?, followup_month=?, accounting_year=?, accounting_month=?,
                accounting_date=?, accounting_status=?
            WHERE id=?
        """, (
            received_date,
            request.form.get("device_type", ""),
            request.form.get("brand_model", ""),
            request.form.get("serial_no", ""),
            request.form.get("system_name", ""),
            (encrypt_repair_password(request.form.get("system_password", ""))
             if request.form.get("system_password", "") else r["system_password"]),
            request.form.get("accessories", ""),
            request.form.get("device_state", ""),
            request.form.get("problem", ""),
            request.form.get("diagnosis", ""),
            "",
            request.form.get("tests_validation", ""),
            request.form.get("remarks", ""),
            new_status,
            finished_at,
            returned_at,
            r["legacy_call_note"] or "",
            followup_year,
            followup_month,
            accounting_year,
            accounting_month,
            accounting_date,
            accounting_status,
            rid
        ))

        record_repair_status_change(con, rid, r["status"], new_status)
        con.commit()
        con.close()
        # V2.3.215 : aucune écriture Google automatique.
        flash("Suivi modifié.")
        return redirect(url_for("repair_detail", rid=rid))

    con.close()
    r = dict(r)
    r["has_system_password"] = bool(r.get("system_password"))
    r["system_password"] = ""
    return render_template("repair_edit.html", r=r)

@app.route("/repair/<int:rid>/restituer", methods=["POST"])
def repair_return_now(rid):
    """V2.3.83 : restitution en un clic depuis le Suivi."""
    con = db()
    r = con.execute("SELECT * FROM repairs WHERE id=?", (rid,)).fetchone()
    if not r:
        con.close()
        return "Dossier introuvable", 404
    if r["status"] != "Terminé":
        con.close()
        flash("Ce dossier n'est pas en attente de restitution.")
        return redirect(url_for("index", year=r["followup_year"] or now().year))

    stamp = now()
    updates = [
        "status='Restitué'",
        "returned_at=?",
        "finished_at=COALESCE(finished_at,?)",
    ]
    params = [stamp.isoformat(timespec="seconds"), stamp.isoformat(timespec="seconds")]

    total = float(r["service_amount"] or 0) + float(r["goods_amount"] or 0)
    if r["accounting_status"] == "red" and str(r["invoice_no"] or "").strip() and total > 0:
        pay_mode = normalize_payment_mode(request.form.get("payment_mode", ""))
        if not pay_mode:
            con.close()
            flash("Choisis le mode de règlement avant de restituer ce dossier.")
            return redirect(url_for("index", year=r["followup_year"] or now().year, a_restituer=1) + f"#suivi-{rid}")
        fy = int(r["followup_year"] or stamp.year)
        fm = int(r["followup_month"] or stamp.month)
        acc_status = "yellow" if (fy, fm) != (stamp.year, stamp.month) else "normal"
        updates.extend([
            "payment_mode=?", "payment_method=?", "paid=1",
            "accounting_year=?", "accounting_month=?", "accounting_date=?",
            "accounting_status=?",
            "accounting_service_amount=COALESCE(service_amount,0)",
            "accounting_goods_amount=COALESCE(goods_amount,0)",
        ])
        params.extend([pay_mode, pay_mode, stamp.year, stamp.month, stamp.strftime("%Y-%m-%d"), acc_status])

    params.append(rid)
    con.execute(f"UPDATE repairs SET {', '.join(updates)} WHERE id=?", params)
    record_repair_status_change(con, rid, r["status"], "Restitué", "Restitution rapide depuis le Suivi")
    con.commit()
    con.close()
    flash("Matériel marqué Restitué." + (" Règlement encaissé aujourd'hui." if r["accounting_status"] == "red" and r["invoice_no"] and total > 0 else ""))
    return redirect(url_for("index", year=r["followup_year"] or now().year, a_restituer=1))


@app.route("/repair/<int:rid>/encaisser", methods=["POST"])
def repair_cash_now(rid):
    """V2.3.82 : encaisse une facture rouge à la date du jour, sans déplacer le suivi d'origine."""
    con = db()
    r = con.execute("SELECT * FROM repairs WHERE id=?", (rid,)).fetchone()
    if not r:
        con.close()
        return "Dossier introuvable", 404

    total = float(r["service_amount"] or 0) + float(r["goods_amount"] or 0)
    if not str(r["invoice_no"] or "").strip() or total <= 0:
        con.close()
        flash("Impossible d'encaisser : facture ou montant manquant.")
        return redirect(url_for("index", year=r["followup_year"] or now().year))

    pay_dt = now()
    fy = r["followup_year"]
    fm = r["followup_month"]
    status = "yellow" if (fy, fm) != (pay_dt.year, pay_dt.month) else "normal"
    pay_mode, pay_method, pay_detail, pay_error = payment_data_from_form(
        total, r["payment_mode"], r["payment_method"], r["payment_detail"]
    )
    if pay_error:
        con.close()
        flash(pay_error)
        return redirect(url_for("repair_detail", rid=rid))
    if not pay_mode:
        con.close()
        flash("Choisis un mode de règlement.")
        return redirect(url_for("repair_detail", rid=rid))

    con.execute("""
        UPDATE repairs SET
            paid=1,
            payment_mode=?,
            payment_method=?,
            payment_detail=?,
            accounting_year=?, accounting_month=?, accounting_date=?,
            accounting_status=?,
            accounting_service_amount=COALESCE(service_amount,0),
            accounting_goods_amount=COALESCE(goods_amount,0)
        WHERE id=?
    """, (
        pay_mode, pay_method, pay_detail,
        pay_dt.year, pay_dt.month, pay_dt.strftime("%Y-%m-%d"), status, rid
    ))
    con.commit()
    con.close()
    flash(f"Règlement enregistré au {pay_dt.strftime('%d/%m/%Y')} — il est comptabilisé sur ce mois.")
    return redirect(url_for("index", year=fy or pay_dt.year) + f"#suivi-{rid}")


@app.route("/repair/<int:rid>/update", methods=["POST"])
def repair_update(rid):
    con = db()
    current = con.execute(
        "SELECT status, finished_at, returned_at, followup_year, followup_month, service_amount, goods_amount, payment_mode, payment_method, payment_detail, paid, accounting_year, accounting_month, accounting_date, accounting_status FROM repairs WHERE id=?",
        (rid,)
    ).fetchone()
    if not current:
        con.close()
        return "Dossier introuvable", 404

    new_status = request.form.get("status","Reçu")
    finished_at = current["finished_at"]

    # V2.3.52 — date de fin cohérente avec l'état réel du dossier.
    if new_status in {"Terminé", "Restitué"}:
        if not finished_at:
            finished_at = now().isoformat(timespec="seconds")
    else:
        finished_at = None

    returned_at = current["returned_at"]
    requested_returned_at = request.form.get("returned_at", "").strip()
    if new_status == "Restitué":
        if requested_returned_at:
            try:
                datetime.strptime(requested_returned_at, "%Y-%m-%d")
                returned_at = requested_returned_at
            except ValueError:
                con.close()
                flash("Date de restitution invalide.")
                return redirect(url_for("repair_detail", rid=rid))
        elif current["status"] != "Restitué" or not returned_at:
            returned_at = now().date().isoformat()
    else:
        returned_at = None

    payment_received_now = request.form.get("payment_received_now") == "1"
    if payment_received_now:
        # V2.3.85 — encaisser signifie que le matériel a été rendu au client.
        new_status = "Restitué"
        if not returned_at:
            returned_at = now().date().isoformat()
        if not finished_at:
            finished_at = now().isoformat(timespec="seconds")
        pay_dt = now()
        if returned_at:
            try:
                pay_day = datetime.strptime(str(returned_at)[:10], "%Y-%m-%d").date()
                pay_dt = datetime.combine(pay_day, pay_dt.time())
            except ValueError:
                pass
        invoice_total = float(current["service_amount"] or 0) + float(current["goods_amount"] or 0)
        pay_mode, pay_method, pay_detail, pay_error = payment_data_from_form(
            invoice_total, current["payment_mode"], current["payment_method"], current["payment_detail"]
        )
        if pay_error:
            con.close()
            flash(pay_error)
            return redirect(url_for("repair_detail", rid=rid))
        if not pay_mode:
            con.close()
            flash("Choisis un mode de règlement.")
            return redirect(url_for("repair_detail", rid=rid))
        followup_year = current["followup_year"] if "followup_year" in current.keys() else None
        followup_month = current["followup_month"] if "followup_month" in current.keys() else None
        accounting_status = "normal"
        if (followup_year, followup_month) != (pay_dt.year, pay_dt.month):
            accounting_status = "yellow"
        con.execute("""
            UPDATE repairs SET
                diagnosis=?, work_done=?, tests_validation=?, remarks=?, status=?, finished_at=?, returned_at=?,
                payment_mode=?, payment_method=?, payment_detail=?, paid=1,
                accounting_year=?, accounting_month=?, accounting_date=?, accounting_status=?,
                accounting_service_amount=COALESCE(service_amount,0),
                accounting_goods_amount=COALESCE(goods_amount,0)
            WHERE id=?
        """, (
            request.form.get("diagnosis",""), "",
            request.form.get("tests_validation",""), request.form.get("remarks",""),
            new_status, finished_at, returned_at,
            pay_mode, pay_method, pay_detail,
            pay_dt.year, pay_dt.month, pay_dt.strftime("%Y-%m-%d"), accounting_status,
            rid
        ))
    else:
        accounting_date = str(current["accounting_date"] or "")[:10]
        accounting_year = current["accounting_year"]
        accounting_month = current["accounting_month"]
        accounting_status = current["accounting_status"] or "normal"

        if current["paid"]:
            requested_accounting_date = request.form.get("accounting_date", accounting_date).strip()
            if requested_accounting_date:
                try:
                    datetime.strptime(requested_accounting_date, "%Y-%m-%d")
                except ValueError:
                    con.close()
                    flash("Date d'encaissement invalide.")
                    return redirect(url_for("repair_detail", rid=rid))

            old_returned_at = str(current["returned_at"] or "")[:10]
            returned_day = str(returned_at or "")[:10]
            returned_changed = returned_day != old_returned_at
            accounting_changed = requested_accounting_date != accounting_date

            if accounting_changed:
                accounting_date = requested_accounting_date
            elif returned_changed and returned_day:
                accounting_date = returned_day
            elif not accounting_date and returned_day:
                accounting_date = returned_day

            if accounting_date:
                ad = datetime.strptime(accounting_date, "%Y-%m-%d")
                accounting_year, accounting_month = ad.year, ad.month
                fy = current["followup_year"]
                fm = current["followup_month"]
                accounting_status = (
                    "yellow"
                    if fy and fm and (accounting_year, accounting_month) != (int(fy), int(fm))
                    else "normal"
                )

        con.execute("""
            UPDATE repairs SET
                diagnosis=?, work_done=?, tests_validation=?, remarks=?, status=?, finished_at=?, returned_at=?,
                accounting_year=?, accounting_month=?, accounting_date=?, accounting_status=?
            WHERE id=?
        """, (
            request.form.get("diagnosis",""),
            "",
            request.form.get("tests_validation",""),
            request.form.get("remarks",""),
            new_status,
            finished_at,
            returned_at,
            accounting_year,
            accounting_month,
            accounting_date,
            accounting_status,
            rid
        ))
    record_repair_status_change(con, rid, current["status"], new_status)
    con.commit()
    con.close()
    flash("Dossier mis à jour.")
    return redirect(url_for("repair_detail", rid=rid))

@app.route("/repair/<int:rid>/facturer", methods=["GET", "POST"])
@app.route("/repair/<int:rid>/close", methods=["GET", "POST"])
def repair_close(rid):
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.email client_email, c.phone client_phone,
               c.address_street client_address_street, c.postal_code client_postal_code,
               c.city client_city
        FROM repairs r JOIN clients c ON c.id=r.client_id WHERE r.id=?
    """, (rid,)).fetchone()
    if not r:
        con.close()
        return "Dossier introuvable", 404

    if request.method == "POST":
        quantities = request.form.getlist("line_qty[]")
        descriptions = request.form.getlist("line_desc[]")
        prices = request.form.getlist("line_price[]")
        types = request.form.getlist("line_type[]")

        lines = []
        for i in range(max(len(descriptions), len(quantities), len(prices), len(types))):
            desc = descriptions[i].strip() if i < len(descriptions) else ""
            if not desc:
                continue
            try:
                qty = float((quantities[i] if i < len(quantities) else "1").replace(",", ".") or 1)
            except Exception:
                qty = 1.0
            try:
                price = float((prices[i] if i < len(prices) else "0").replace(",", ".") or 0)
            except Exception:
                price = 0.0
            line_type = types[i] if i < len(types) and types[i] in ("service", "goods") else "service"
            lines.append({
                "position": len(lines),
                "line_type": line_type,
                "quantity": qty,
                "description": desc,
                "unit_price": price
            })

        no_invoice_parts = request.form.get("no_invoice_parts") == "on"

        # V2.3.135 — Cas métier : le client laisse le matériel pour pièces
        # à la place du forfait diagnostic. Aucun règlement, aucune facture, aucun CA.
        # On autorise donc zéro ligne de facture uniquement dans ce cas explicite.
        if no_invoice_parts:
            if r["invoice_no"]:
                con.close()
                flash("Ce dossier possède déjà une facture. Le mode « laissé pour pièces » n'est disponible que sans facture existante.")
                return redirect(url_for("repair_close", rid=rid))

            finished = r["finished_at"] or now().isoformat(timespec="seconds")
            close_status = "Laissé pour pièces"
            parts_sent_via = (request.form.get("parts_sent_via") or "Suivi + photos par mail").strip()

            con.execute("""
                UPDATE repairs SET
                    service_amount=0, goods_amount=0,
                    payment_method='', payment_mode='', payment_detail='',
                    paid=0, sent_via=?,
                    tests_validation=?, remarks=?,
                    finished_at=?, invoice_no=NULL,
                    status=?, returned_at=NULL,
                    service_description='', goods_description='',
                    legacy_invoice_text='',
                    accounting_year=NULL, accounting_month=NULL, accounting_date='',
                    accounting_status='normal',
                    accounting_service_amount=0, accounting_goods_amount=0,
                    followup_year=COALESCE(followup_year, CAST(substr(received_date,1,4) AS INTEGER)),
                    followup_month=COALESCE(followup_month, CAST(substr(received_date,6,2) AS INTEGER))
                WHERE id=?
            """, (
                parts_sent_via,
                request.form.get("tests_validation",""),
                (r["remarks"] or ""),
                finished, close_status, rid
            ))
            record_repair_status_change(
                con, rid, r["status"], close_status,
                "Matériel laissé pour pièces — aucune facture"
            )
            con.execute("DELETE FROM invoice_lines WHERE repair_id=?", (rid,))
            con.commit()
            con.close()
            flash("Dossier clôturé : matériel laissé pour pièces. Aucune facture, aucun règlement et aucun CA enregistrés.")

            if request.form.get("return_to") == "suivi":
                return redirect(url_for("index", year=(r["followup_year"] or int(r["received_date"][:4]))) + f"#suivi-{rid}")
            if request.form.get("return_to") == "factures":
                return redirect(url_for("invoices_page"))
            return redirect(url_for("repair_detail", rid=rid))

        if not lines:
            con.close()
            flash("Ajoute au moins une ligne de facture, ou coche « Matériel laissé pour pièces — aucune facture ».")
            return redirect(url_for("repair_close", rid=rid))

        service_total = sum(x["quantity"] * x["unit_price"] for x in lines if x["line_type"] == "service")
        goods_total = sum(x["quantity"] * x["unit_price"] for x in lines if x["line_type"] == "goods")
        service_desc = " + ".join(x["description"] for x in lines if x["line_type"] == "service")
        goods_desc = " + ".join(x["description"] for x in lines if x["line_type"] == "goods")

        inv = r["invoice_no"] or make_invoice_no()

        # V2.3.204 — date de facture éditable depuis FACTURE / MODIFIER FACTURE.
        invoice_date_raw = request.form.get("invoice_date", "").strip()
        try:
            invoice_day = datetime.strptime(invoice_date_raw, "%Y-%m-%d").date()
        except ValueError:
            con.close()
            flash("Date de facture invalide.")
            return redirect(url_for("repair_close", rid=rid))

        if r["finished_at"]:
            try:
                invoice_time = datetime.fromisoformat(str(r["finished_at"])).time().replace(microsecond=0)
            except Exception:
                invoice_time = now().time().replace(microsecond=0)
        else:
            invoice_time = now().time().replace(microsecond=0)

        finished = datetime.combine(invoice_day, invoice_time).isoformat(timespec="seconds")

        is_historical_invoice = bool(r["legacy_imported"])

        # V2.3.214 — la date d'encaissement appartient à la facture.
        # Elle reste éditable, y compris sur une facture historique, sans toucher
        # aux montants historiques. Si elle est vide, on privilégie la restitution.
        accounting_date_raw = request.form.get("accounting_date", "").strip()

        def parsed_accounting_day(raw_value, fallback_value=""):
            value = str(raw_value or fallback_value or "").strip()[:10]
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                return None

        if is_historical_invoice:
            paid_flag = int(r["paid"] or 0)
            accounting_service_amount = float(r["accounting_service_amount"] or 0)
            accounting_goods_amount = float(r["accounting_goods_amount"] or 0)
            accounting_status = r["accounting_status"] or "normal"

            if paid_flag:
                fallback = r["accounting_date"] or r["returned_at"] or now().date().isoformat()
                accounting_day = parsed_accounting_day(accounting_date_raw, fallback)
                if accounting_date_raw and not accounting_day:
                    con.close()
                    flash("Date d'encaissement invalide.")
                    return redirect(url_for("repair_close", rid=rid))
                accounting_day = accounting_day or now().date()
                accounting_date = accounting_day.isoformat()
                accounting_year = accounting_day.year
                accounting_month = accounting_day.month
                try:
                    rd = datetime.strptime(r["received_date"], "%Y-%m-%d")
                    accounting_status = (
                        "yellow"
                        if (rd.year, rd.month) != (accounting_year, accounting_month)
                        else "normal"
                    )
                except Exception:
                    accounting_status = "normal"
            else:
                accounting_year = r["accounting_year"]
                accounting_month = r["accounting_month"]
                accounting_date = r["accounting_date"] or ""
        else:
            paid_flag = 1 if request.form.get("paid") == "on" else 0

            if paid_flag:
                fallback = r["accounting_date"] or r["returned_at"] or now().date().isoformat()
                accounting_day = parsed_accounting_day(accounting_date_raw, fallback)
                if accounting_date_raw and not accounting_day:
                    con.close()
                    flash("Date d'encaissement invalide.")
                    return redirect(url_for("repair_close", rid=rid))
                accounting_day = accounting_day or now().date()
                accounting_date = accounting_day.isoformat()
                accounting_year = accounting_day.year
                accounting_month = accounting_day.month
                accounting_service_amount = service_total
                accounting_goods_amount = goods_total

                try:
                    rd = datetime.strptime(r["received_date"], "%Y-%m-%d")
                    accounting_status = (
                        "yellow"
                        if (rd.year, rd.month) != (accounting_year, accounting_month)
                        else "normal"
                    )
                except Exception:
                    accounting_status = "normal"
            else:
                # Facture créée mais pas encore payée : rouge et exclue du CA.
                accounting_year = None
                accounting_month = None
                accounting_date = ""
                accounting_service_amount = 0.0
                accounting_goods_amount = 0.0
                accounting_status = "red"

        # V2.3.119 — paiement mixte : ventilation exacte par mode.
        if is_historical_invoice:
            close_payment_mode = r["payment_mode"] or ""
            close_payment_method = r["payment_method"] or ""
            close_payment_detail = r["payment_detail"] or ""
        elif paid_flag:
            close_payment_mode, close_payment_method, close_payment_detail, pay_error = payment_data_from_form(
                service_total + goods_total, r["payment_mode"], r["payment_method"], r["payment_detail"]
            )
            if pay_error:
                con.close()
                flash(pay_error)
                return redirect(url_for("repair_close", rid=rid))
            if not close_payment_mode:
                con.close()
                flash("Choisis un mode de règlement avant d'enregistrer le paiement.")
                return redirect(url_for("repair_close", rid=rid))
        else:
            close_payment_mode = normalize_payment_mode(request.form.get("payment_mode", ""))
            close_payment_method = close_payment_mode
            close_payment_detail = ""

        # V2.3.85 — facture réglée = matériel restitué.
        # Une facture non réglée reste Terminé (sauf dossier déjà explicitement restitué).
        if paid_flag:
            close_status = "Restitué"
            close_returned_at = r["returned_at"] or accounting_date or now().date().isoformat()
        else:
            close_status = "Restitué" if r["status"] == "Restitué" else "Terminé"
            close_returned_at = r["returned_at"] if close_status == "Restitué" else None

        con.execute("""
            UPDATE repairs SET
                service_amount=?, goods_amount=?, payment_method=?, payment_mode=?, payment_detail=?,
                paid=?, sent_via=?, work_done=?, tests_validation=?,
                remarks=?, finished_at=?, invoice_no=?, status=?, returned_at=?,
                service_description=?, goods_description=?,
                legacy_invoice_text=?,
                accounting_year=?, accounting_month=?, accounting_date=?, accounting_status=?,
                accounting_service_amount=?, accounting_goods_amount=?,
                followup_year=COALESCE(followup_year, CAST(substr(received_date,1,4) AS INTEGER)),
                followup_month=COALESCE(followup_month, CAST(substr(received_date,6,2) AS INTEGER))
            WHERE id=?
        """, (
            service_total, goods_total,
            close_payment_method, close_payment_mode, close_payment_detail,
            paid_flag,
            request.form.get("sent_via",""),
            "",
            request.form.get("tests_validation",""),
            (r["remarks"] or ""),
            finished, inv, close_status, close_returned_at, service_desc, goods_desc,
            inv,
            accounting_year, accounting_month, accounting_date, accounting_status,
            accounting_service_amount, accounting_goods_amount,
            rid
        ))

        record_repair_status_change(con, rid, r["status"], close_status, "Facturation")

        con.execute("DELETE FROM invoice_lines WHERE repair_id=?", (rid,))
        for line in lines:
            con.execute("""
                INSERT INTO invoice_lines(repair_id,position,line_type,quantity,description,unit_price)
                VALUES(?,?,?,?,?,?)
            """, (rid, line["position"], line["line_type"], line["quantity"], line["description"], line["unit_price"]))

        con.commit()
        con.close()
        flash("Facture modifiée." if r["invoice_no"] else "Facture créée.")

        if request.form.get("return_to") == "suivi":
            try:
                followup_year = int(r["followup_year"] or str(r["received_date"] or "")[:4] or now().year)
            except Exception:
                followup_year = now().year
            return redirect(url_for("index", year=followup_year) + f"#suivi-{rid}")

        if request.form.get("return_to") == "factures":
            return redirect(url_for("invoices_page"))

        return redirect(url_for("repair_detail", rid=rid))

    lines = con.execute("""
        SELECT * FROM invoice_lines WHERE repair_id=? ORDER BY position,id
    """, (rid,)).fetchall()

    invoice_was_reconstructed = bool(lines)
    original_invoice_pdf = None
    if r["legacy_imported"] and r["invoice_no"]:
        original_invoice_pdf = find_document_recursive(
            FACTURES_ROOT,
            document_no=r["invoice_no"]
        )

    # Compatibilité avec les factures créées avant la V1.7 et les factures ODS.
    if not lines:
        legacy = []

        source_rows = [r]
        if r["legacy_imported"] and r["invoice_no"]:
            source_rows = con.execute("""
                SELECT *
                FROM repairs
                WHERE client_id=?
                  AND invoice_no=?
                ORDER BY
                    CASE WHEN COALESCE(accounting_date,'')<>'' THEN 1 ELSE 0 END DESC,
                    id DESC
            """, (r["client_id"], r["invoice_no"])).fetchall() or [r]

        # Les lignes "Paiement du..." peuvent dupliquer les montants de la facture.
        # On prend donc la meilleure valeur connue par catégorie au lieu de les sommer.
        service_source = max(
            source_rows,
            key=lambda x: max(
                float(x["service_amount"] or 0),
                float(x["accounting_service_amount"] or 0)
            )
        )
        goods_source = max(
            source_rows,
            key=lambda x: max(
                float(x["goods_amount"] or 0),
                float(x["accounting_goods_amount"] or 0)
            )
        )

        service_value = max(
            float(service_source["service_amount"] or 0),
            float(service_source["accounting_service_amount"] or 0)
        )
        goods_value = max(
            float(goods_source["goods_amount"] or 0),
            float(goods_source["accounting_goods_amount"] or 0)
        )

        if service_value:
            legacy.append({
                "line_type": "service",
                "quantity": 1,
                "description": (
                    service_source["service_description"]
                    or service_source["tests_validation"]
                    or service_source["problem"]
                    or "Prestation de service"
                ),
                "unit_price": service_value
            })

        if goods_value:
            legacy.append({
                "line_type": "goods",
                "quantity": 1,
                "description": (
                    goods_source["goods_description"]
                    or goods_source["problem"]
                    or "Pièce / marchandise"
                ),
                "unit_price": goods_value
            })

        lines = legacy

    con.close()
    return render_template(
        "close.html",
        r=r,
        invoice_lines=lines,
        invoice_was_reconstructed=invoice_was_reconstructed,
        original_invoice_pdf=bool(original_invoice_pdf and original_invoice_pdf.exists()),
        payment_split=payment_split_values(r["payment_detail"], r["payment_method"]),
        invoice_date_value=((r["finished_at"] or now().date().isoformat())[:10]),
        accounting_date_value=((r["accounting_date"] or r["returned_at"] or now().date().isoformat())[:10])
    )

@app.route("/sign/<token>", methods=["GET", "POST"])
def sign(token):
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.signature_token=?
    """, (token,)).fetchone()
    if not r:
        con.close()
        return "Lien de signature invalide.", 404

    if request.method == "POST":
        if r["signature_at"]:
            con.close()
            return jsonify({"ok": False, "error": "Ce dossier a déjà été signé."}), 409
        data = request.get_json(silent=True) or {}
        img = data.get("image","")
        if not img.startswith("data:image/png;base64,"):
            con.close()
            return jsonify({"ok":False, "error":"Format invalide"}), 400
        raw = base64.b64decode(img.split(",",1)[1])
        date_sig = now().strftime("%Y%m%d_%H%M")
        client_name = safe_filename(r["client_name"])
        path = SIGNATURES / f"{r['dossier_no']}_{client_name}_{date_sig}.png"
        path.write_bytes(raw)
        signed_at = now().isoformat(timespec="seconds")
        con.execute(
            "UPDATE repairs SET signature_path=?, signature_at=? WHERE id=?",
            (path.name, signed_at, r["id"])
        )
        con.commit()
        con.close()
        return jsonify({"ok":True})

    con.close()
    return render_template("sign.html", r=r, already_signed=bool(r["signature_at"]))

@app.route("/qr/<int:rid>.png")
def qr_png(rid):
    con = db()
    r = con.execute("SELECT signature_token FROM repairs WHERE id=?", (rid,)).fetchone()
    con.close()
    if not r:
        return "introuvable", 404
    target = f"http://{local_ip()}:5000/sign/{r['signature_token']}"
    img = qrcode.make(target)
    bio = io.BytesIO()
    img.save(bio, "PNG")
    bio.seek(0)
    return send_file(bio, mimetype="image/png")

def pdf_header(c, title, subtitle=None):
    conf = cfg()
    w, h = A4
    c.setFont(PDF_FONTS["bold"], 18)
    c.drawString(18*mm, h-20*mm, conf["business_name"])
    c.setFont(PDF_FONTS["regular"], 9)
    c.drawRightString(w-18*mm, h-17*mm, conf["website"])
    c.drawRightString(w-18*mm, h-22*mm, conf["email"] + " - " + conf["phone"])
    c.line(18*mm, h-26*mm, w-18*mm, h-26*mm)
    c.setFont(PDF_FONTS["bold"], 16)
    c.drawString(18*mm, h-36*mm, title)
    if subtitle:
        c.setFont(PDF_FONTS["regular"], 10)
        c.drawString(18*mm, h-42*mm, subtitle)
    return w,h

def draw_wrapped(c, text, x, y, max_chars=95, line_h=5*mm, font=None, size=9):
    font = font or PDF_FONTS["regular"]
    c.setFont(font, size)
    words = (text or "").split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    for line in lines[:6]:
        c.drawString(x, y, line)
        y -= line_h
    return y

def fr_datetime(value):
    if not value:
        return ""
    try:
        d = datetime.fromisoformat(value)
        return d.strftime("%d/%m/%Y à %H:%M")
    except Exception:
        return str(value)

def fr_date(value):
    if not value:
        return ""
    try:
        if "T" in str(value):
            d = datetime.fromisoformat(value)
        else:
            d = datetime.strptime(str(value)[:10], "%Y-%m-%d")
        return d.strftime("%d/%m/%Y")
    except Exception:
        return str(value)

def fit_text(c, text, x, y, max_width, font=None, size=9, min_size=6):
    text = str(text or "")
    font = font or PDF_FONTS["regular"]
    cur = size
    c.setFont(font, cur)
    while cur > min_size and c.stringWidth(text, font, cur) > max_width:
        cur -= .5
        c.setFont(font, cur)
    c.drawString(x, y, text)
    return cur


def wrap_pdf_text(text, font, size, max_width):
    """Retourne des lignes qui tiennent dans max_width sans jamais réduire la police."""
    text = str(text or "").replace("\r", "")
    result = []
    paragraphs = text.split("\n") or [""]

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            result.append("")
            continue

        words = paragraph.split()
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
                current = candidate
                continue

            if current:
                result.append(current)
                current = ""

            # Mot/URL exceptionnellement trop long : découpe caractère par caractère.
            if pdfmetrics.stringWidth(word, font, size) > max_width:
                chunk = ""
                for ch in word:
                    test = chunk + ch
                    if chunk and pdfmetrics.stringWidth(test, font, size) > max_width:
                        result.append(chunk)
                        chunk = ch
                    else:
                        chunk = test
                current = chunk
            else:
                current = word

        if current:
            result.append(current)

    return result or [""]

@app.route("/repair/<int:rid>/intake.pdf")
def intake_pdf(rid):
    lang = pdf_lang(request.values.get("lang", "fr"))
    con = db()
    r = con.execute("""
        SELECT r.*,
               c.name client_name,
               c.first_name client_first_name,
               c.last_name client_last_name,
               c.company client_company,
               c.address client_address,
               c.address_street client_address_street, c.postal_code client_postal_code,
               c.city client_city, c.phone client_phone, c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()
    if not r:
        return "introuvable", 404

    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    W, H = A4
    BLUE = colors.HexColor("#3399FF")
    BLACK = colors.black
    x0, x1 = 5*mm, W-5*mm

    # Logo à gauche + bandeau haut, comme la feuille d'origine
    logo = invoice_logo_path()
    if logo:
        c.drawImage(str(logo), 6*mm, H-37*mm, width=44*mm, height=26*mm,
                    preserveAspectRatio=True, mask='auto')

    bx = 52*mm
    bw = W - bx - 5*mm
    c.setStrokeColor(BLUE); c.setLineWidth(1.2)
    c.rect(bx, H-21*mm, bw, 7*mm, fill=0, stroke=1)
    c.setFont(PDF_FONTS["bold"], 10)
    c.drawCentredString(bx+bw/2, H-18.7*mm,
        f"{cfg().get('website','')}  -  {cfg().get('email','')}  -  {cfg().get('phone','')}")
    c.rect(bx, H-34*mm, bw, 9*mm, fill=0, stroke=1)
    c.setFont(PDF_FONTS["bold"], 16)
    c.drawCentredString(bx+bw/2, H-31.5*mm, pdf_t("intake_title", lang))

    def section_title(y, title):
        # V2.3.57 : 5,5 mm au lieu de 6 mm.
        # Le texte garde la même taille ; on récupère juste un peu de hauteur
        # pour permettre un vrai bloc multi-lignes Tests et Validation.
        h = 5.5*mm
        c.setStrokeColor(BLUE); c.setLineWidth(1)
        c.rect(x0, y-h, x1-x0, h, fill=0, stroke=1)
        c.setFont(PDF_FONTS["bold"], 10.5)
        c.drawCentredString((x0+x1)/2, y-h+1.7*mm, title)
        return y-h

    def field_row(y, label, value, h=6*mm, label_w=43*mm, size=9.2, label_size=None):
        c.setStrokeColor(BLUE); c.setLineWidth(.7)
        c.rect(x0, y-h, x1-x0, h, fill=0, stroke=1)
        c.line(x0+label_w, y, x0+label_w, y-h)
        c.setFillColor(BLACK)

        lbl_size = label_size or size
        # V2.3.33 : les libellés longs doivent s'adapter à la largeur
        # de la colonne gauche au lieu de déborder.
        fit_text(
            c, str(label or ''), x0+1*mm, y-h+1.7*mm,
            label_w-2*mm, PDF_FONTS["regular"], lbl_size, 6.8
        )

        fit_text(c, str(value or ''), x0+label_w+1*mm, y-h+1.7*mm,
                 x1-(x0+label_w)-2*mm, PDF_FONTS["regular"], size, 6)
        return y-h

    y = H-37*mm
    y = section_title(y, pdf_t("client_info", lang))
    y = field_row(y, pdf_t("first_name", lang) + " :", r['client_first_name'] or "")
    y = field_row(y, pdf_t("last_name", lang) + " :", r['client_last_name'] or r['client_name'] or "")
    client_company = str(r['client_company'] or "").strip()
    if client_company and client_company.casefold() != str(r['client_name'] or "").strip().casefold():
        y = field_row(y, "Entreprise :", client_company)
    y = field_row(y, pdf_t("address", lang) + " :", r['client_address_street'] or "")
    y = field_row(y, pdf_t("postal_city", lang) + " :", " ".join(x for x in [r['client_postal_code'] or "", r['client_city'] or ""] if x))
    y = field_row(y, pdf_t("phone", lang) + " :", r['client_phone'])
    y = field_row(y, pdf_t("email", lang) + " :", r['client_email'])
    y = field_row(y, pdf_t("date", lang) + " :", fr_date(r['received_date']))

    y -= 1*mm
    y = section_title(y, pdf_t("device_details", lang))
    y = field_row(y, pdf_t("device_type", lang) + " :", r['device_type'])
    y = field_row(y, pdf_t("brand_model", lang) + " :", r['brand_model'])
    y = field_row(y, pdf_t("serial", lang) + " :", r['serial_no'])
    y = field_row(y, pdf_t("system", lang) + " :", r['system_name'])
    y = field_row(y, pdf_t("password", lang) + " :", decrypt_repair_password(r['system_password']))
    y = field_row(y, pdf_t("accessories", lang) + " :", r['accessories'])
    y = field_row(y, pdf_t("condition", lang) + " :", r['device_state'])

    y -= 1*mm
    y = section_title(y, pdf_t("problem_desc", lang))

    # V2.3.40 : afficher aussi le Diagnostic dans le PDF Suivi.
    # Deux lignes dans le même bloc afin de conserver la mise en page A4.
    h = 24*mm
    row_h = h / 2

    c.setStrokeColor(BLUE)
    c.setLineWidth(.7)
    c.rect(x0, y-h, x1-x0, h, fill=0, stroke=1)
    c.line(x0+43*mm, y, x0+43*mm, y-h)
    c.line(x0, y-row_h, x1, y-row_h)

    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 9)

    c.drawString(x0+1*mm, y-5*mm, pdf_t("problem", lang) + " :")
    draw_wrapped(
        c, translate_pdf_text(r['problem'], lang),
        x0+44*mm, y-4.5*mm,
        max_chars=88,
        line_h=3.8*mm,
        size=8.0
    )

    c.drawString(x0+1*mm, y-row_h-5*mm, pdf_t("diagnosis", lang) + " :")

    # V2.3.63 — Diagnostic en vrai multi-lignes, selon la largeur réelle
    # du cadre, comme Tests et Validation.
    diag_text = translate_pdf_text(r['diagnosis'], lang).replace("\r", "").strip()
    diag_x = x0 + 44*mm
    diag_width = x1 - diag_x - 1.5*mm
    diag_font = 8.0
    diag_lines = []

    while diag_font >= 6.5:
        candidate = []
        source_lines = diag_text.split("\n") if diag_text else [""]
        for source_line in source_lines:
            wrapped = wrap_pdf_text(
                source_line,
                PDF_FONTS["regular"],
                diag_font,
                diag_width
            )
            candidate.extend(wrapped or [""])
        diag_lines = candidate
        if len(diag_lines) <= 3:
            break
        diag_font -= 0.3

    # Le demi-bloc Diagnostic fait 12 mm : 3 lignes max, alignées en haut.
    diag_y = y - row_h - 3.8*mm
    diag_line_h = 3.4*mm
    c.setFont(PDF_FONTS["regular"], diag_font)
    for line in diag_lines[:3]:
        c.drawString(diag_x, diag_y, line)
        diag_y -= diag_line_h

    y -= h

    y -= 1*mm
    y = section_title(y, pdf_t("repair_authorization", lang))
    h = 22*mm
    c.setStrokeColor(BLUE); c.rect(x0, y-h, x1-x0, h, fill=0, stroke=1)
    c.line(x0+43*mm, y, x0+43*mm, y-h)
    c.setFont(PDF_FONTS["regular"], 9)
    c.drawString(x0+1*mm, y-5*mm, pdf_t("client_signature", lang) + " :")
    signature_file = resolve_signature_path(r['signature_path'])
    if signature_file:
        c.drawImage(str(signature_file), x0+45*mm, y-h+2*mm, width=58*mm, height=20*mm,
                    preserveAspectRatio=True, mask='auto')
        c.setFont(PDF_FONTS["bold"], 8)
        c.drawString(x0+108*mm, y-7*mm, "Client : " + (r['client_name'] or ''))
        c.setFont(PDF_FONTS["regular"], 8)
        c.drawString(x0+108*mm, y-13*mm, pdf_t("signed_on", lang) + " " + fr_datetime(r['signature_at']))
    y -= h

    y -= 1*mm
    y = section_title(y, pdf_t("validation_return", lang))

    # V2.3.57 — vrai bloc multi-lignes.
    # L'ancien field_row plaçait tout sur UNE ligne de base située en bas du cadre,
    # d'où le texte minuscule qui partait à droite et dépassait.
    tests_h = 16*mm
    label_w = 43*mm
    c.setStrokeColor(BLUE)
    c.setLineWidth(.7)
    c.rect(x0, y-tests_h, x1-x0, tests_h, fill=0, stroke=1)
    c.line(x0+label_w, y, x0+label_w, y-tests_h)
    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 9)
    c.drawString(x0+1*mm, y-5*mm, pdf_t("tests_validation", lang) + " :")

    tests_text = translate_pdf_text(r['tests_validation'], lang).replace("\r", "").strip()
    tests_x = x0 + label_w + 1*mm
    tests_width = x1 - tests_x - 1.5*mm

    # On conserve les retours à la ligne saisis par l'atelier et on replie
    # également les lignes trop longues selon la largeur réelle du cadre.
    tests_font = 8.2
    tests_lines = []
    while tests_font >= 6.4:
        candidate = []
        source_lines = tests_text.split("\n") if tests_text else [""]
        for source_line in source_lines:
            wrapped = wrap_pdf_text(
                source_line,
                PDF_FONTS["regular"],
                tests_font,
                tests_width
            )
            candidate.extend(wrapped or [""])
        tests_lines = candidate
        if len(tests_lines) <= 6:
            break
        tests_font -= 0.3

    # Jusqu'à 6 lignes tiennent dans le bloc de 16 mm.
    # 5 lignes (cas courant) restent autour de 8 pt, donc bien lisibles.
    line_h = 2.7*mm if len(tests_lines) <= 5 else 2.15*mm
    tests_y = y - 3.4*mm
    c.setFont(PDF_FONTS["regular"], tests_font)
    for line in tests_lines:
        c.drawString(tests_x, tests_y, line)
        tests_y -= line_h

    y -= tests_h

    # Signature du technicien préremplie
    h = 9*mm
    c.setStrokeColor(BLUE); c.setLineWidth(.7)
    c.rect(x0, y-h, x1-x0, h, fill=0, stroke=1)
    c.line(x0+43*mm, y, x0+43*mm, y-h)
    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 9)
    c.drawString(x0+1*mm, y-h+1.7*mm, pdf_t("technician_signature", lang) + " :")
    if TECH_SIGNATURE.exists():
        # V2.3.177 : signature réellement plus visible sur papier.
        # L'image source contient souvent beaucoup de marge vide : on recadre
        # automatiquement autour des traits, puis on épaissit légèrement l'encre.
        try:
            with Image.open(TECH_SIGNATURE) as _sig_src:
                _sig_rgba = _sig_src.convert("RGBA")
                _alpha = _sig_rgba.getchannel("A")
                _gray = ImageOps.grayscale(_sig_rgba)

                # Masque des vrais traits : pixel suffisamment opaque ET pas blanc.
                _ink = Image.eval(_gray, lambda p: 255 if p < 245 else 0)
                _ink = Image.composite(_ink, Image.new("L", _ink.size, 0), _alpha)
                _bbox = _ink.getbbox()
                if _bbox:
                    _l, _t, _r, _b = _bbox
                    _pad = max(2, int(max(_sig_rgba.size) * 0.01))
                    _bbox = (
                        max(0, _l - _pad), max(0, _t - _pad),
                        min(_sig_rgba.width, _r + _pad),
                        min(_sig_rgba.height, _b + _pad),
                    )
                    _gray = _gray.crop(_bbox)

                # V2.3.178 : contraste + épaississement, MAIS fond transparent.
                # La V2.3.177 recréait un rectangle blanc derrière la signature,
                # ce qui masquait la ligne bleue supérieure du cadre.
                _gray = ImageOps.autocontrast(_gray)
                _gray = _gray.filter(ImageFilter.MinFilter(3))

                # Alpha basé sur l'encre : blanc = transparent, noir = opaque.
                _alpha_sig = Image.eval(_gray, lambda p: max(0, min(255, (245 - p) * 8)))
                _sig_img = Image.new("RGBA", _gray.size, (0, 0, 0, 0))
                _black = Image.new("RGBA", _gray.size, (20, 20, 20, 255))
                _sig_img.paste(_black, (0, 0), _alpha_sig)

                _sig_buf = io.BytesIO()
                _sig_img.save(_sig_buf, format="PNG", optimize=True)
                _sig_buf.seek(0)

                # Signature grande, mais entièrement contenue dans la ligne de 9 mm.
                c.drawImage(
                    ImageReader(_sig_buf),
                    x0 + 44*mm,
                    y - h + 0.25*mm,
                    width=58*mm,
                    height=8.5*mm,
                    preserveAspectRatio=True,
                    mask='auto'
                )
        except Exception:
            # Repli sûr : on garde au minimum une signature agrandie.
            c.drawImage(
                str(TECH_SIGNATURE),
                x0 + 44*mm,
                y - h + 0.25*mm,
                width=58*mm,
                height=8.5*mm,
                preserveAspectRatio=True,
                mask='auto'
            )
    y = y-h

    # V2.3.138 — date finale du suivi.
    # Pour "Laissé pour pièces", le dossier est bien clôturé même sans facture :
    # la date doit donc toujours être présente sur le PDF.
    final_date = r["finished_at"]
    if not final_date and r["status"] == "Laissé pour pièces":
        final_date = now().isoformat(timespec="seconds")
    y = field_row(y, pdf_t("date", lang) + " :", fr_date(final_date) if final_date else "")

    y -= 1*mm
    y = section_title(y, pdf_t("warranty", lang))
    gh = 19*mm
    c.setStrokeColor(BLUE); c.rect(x0, y-gh, x1-x0, gh, fill=0, stroke=1)
    c.line(x0+43*mm, y, x0+43*mm, y-gh)
    c.setFont(PDF_FONTS["bold"], 8.5); c.drawString(x0+6*mm, y-5*mm, pdf_t("warranty_duration", lang))
    c.setFont(PDF_FONTS["bold"], 8.5); c.drawString(x0+44*mm, y-5*mm, pdf_t("six_months", lang))
    c.setFont(PDF_FONTS["regular"], 7.2)
    warranty = pdf_t("warranty_text", lang)
    draw_wrapped(
        c, warranty,
        x0+44*mm, y-9.5*mm,
        max_chars=92,
        line_h=3.2*mm,
        size=7.2
    )
    y -= gh
    y = field_row(y, pdf_t("warranty_conditions", lang), pdf_t("warranty_only", lang), h=6*mm)

    y -= 1*mm
    y = section_title(y, pdf_t("remarks", lang))

    # V2.3.35 : cadre Remarques entièrement visible + vrai espace dessous.
    rh = 13*mm
    c.setStrokeColor(BLUE)
    c.rect(x0, y-rh, x1-x0, rh, fill=0, stroke=1)

    remarks_text = translate_pdf_text(r['remarks'], lang).strip()
    if remarks_text.casefold() == "merci de votre confiance.":
        remarks_text = ""

    draw_wrapped(
        c, remarks_text,
        x0+2*mm, y-4.5*mm,
        max_chars=115,
        line_h=3.8*mm,
        size=8
    )

    # Positionné relativement au bas du cadre pour garantir qu'il soit dessous.
    footer_y = y - rh - 7*mm
    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 12)
    c.drawString(x0+2*mm, footer_y, pdf_t("thanks", lang))

    c.save()
    pdf_bytes = bio.getvalue()

    # V2.3.238 — classement automatique du suivi selon la date réelle
    # de prise en charge, pas selon le jour où l'utilisateur reclique sur PDF.
    suivi_date = str(r["received_date"] or "")[:10]
    try:
        suivi_dt = datetime.strptime(suivi_date, "%Y-%m-%d")
    except Exception:
        suivi_dt = now()
        suivi_date = suivi_dt.strftime("%Y-%m-%d")

    suivi_filename = (
        f"{safe_filename(r['client_name'])}_"
        f"{suivi_dt.strftime('%d%m%Y')}_"
        f"{pdf_language_suffix(lang)}.pdf"
    )

    suivi_folder = year_month_folder(
        SUIVI_REPARATIONS_ROOT,
        suivi_date,
        create=True
    )
    suivi_saved_path = suivi_folder / safe_document_name(suivi_filename)
    try:
        suivi_saved_path.write_bytes(pdf_bytes)
    except Exception as exc:
        app.logger.warning(
            "Impossible d'enregistrer le suivi dans %s: %s",
            suivi_saved_path, exc
        )

    bio.seek(0)
    return send_file(
        bio,
        mimetype="application/pdf",
        # V2.3.239 : le PDF est déjà archivé dans private/documents.
        # On l'affiche dans le navigateur au lieu d'en créer une 2e copie
        # dans Téléchargements.
        as_attachment=False,
        download_name=suivi_filename
    )


@app.route("/invoice/simple", methods=["GET", "POST"])
def simple_invoice_new():
    con = db()

    if request.method == "POST":
        sync_new_client_id = None
        selected_client_id = request.form.get("client_id", "").strip()
        client = None
        if selected_client_id.isdigit():
            client = con.execute(
                "SELECT * FROM clients WHERE id=?",
                (int(selected_client_id),)
            ).fetchone()

        if client:
            client_id = int(client["id"])
        else:
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            company = request.form.get("company", "").strip()

            if not first_name and not last_name and not company:
                last_name = "Client de passage"

            name = compose_client_name(last_name, first_name).strip()
            if not name:
                name = company or "Client de passage"

            address_street = request.form.get("address_street", "").strip()
            postal_code = request.form.get("postal_code", "").strip()
            city = request.form.get("city", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()
            address = "\n".join(
                x for x in [address_street, (postal_code + " " + city).strip()] if x
            )

            existing = None
            if name.casefold() == "client de passage" and not any(
                [address_street, postal_code, city, phone, email, company]
            ):
                existing = con.execute(
                    "SELECT * FROM clients WHERE lower(trim(name))='client de passage' ORDER BY id LIMIT 1"
                ).fetchone()

            if existing:
                client_id = int(existing["id"])
            else:
                stamp_client = now().isoformat(timespec="seconds")
                cur = con.execute("""
                    INSERT INTO clients(
                        name,last_name,first_name,company,
                        address,address_street,postal_code,city,
                        phone,email,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    name,last_name,first_name,company,
                    address,address_street,postal_code,city,
                    phone,email,stamp_client,stamp_client
                ))
                client_id = int(cur.lastrowid)

                # Un vrai nouveau client saisi depuis Facture simple rejoint
                # automatiquement Google Contacts. Le client générique anonyme
                # "Client de passage" reste local pour éviter de polluer les contacts.
                is_generic_passage = (
                    name.casefold() == "client de passage"
                    and not any([address_street, postal_code, city, phone, email, company])
                )
                if not is_generic_passage:
                    sync_new_client_id = client_id

        quantities = request.form.getlist("line_qty[]")
        descriptions = request.form.getlist("line_desc[]")
        prices = request.form.getlist("line_price[]")
        types = request.form.getlist("line_type[]")

        lines = []
        for i in range(max(len(descriptions), len(quantities), len(prices), len(types))):
            desc = descriptions[i].strip() if i < len(descriptions) else ""
            if not desc:
                continue
            try:
                qty = float((quantities[i] if i < len(quantities) else "1").replace(",", ".") or 1)
            except Exception:
                qty = 1.0
            try:
                price = float((prices[i] if i < len(prices) else "0").replace(",", ".") or 0)
            except Exception:
                price = 0.0
            line_type = types[i] if i < len(types) and types[i] in ("service", "goods") else "service"
            lines.append({
                "position": len(lines),
                "line_type": line_type,
                "quantity": qty,
                "description": desc,
                "unit_price": price,
            })

        if not lines:
            con.close()
            flash("Ajoute au moins une ligne de facture.")
            return redirect(url_for("simple_invoice_new"))

        service_total = sum(x["quantity"] * x["unit_price"] for x in lines if x["line_type"] == "service")
        goods_total = sum(x["quantity"] * x["unit_price"] for x in lines if x["line_type"] == "goods")
        service_desc = " + ".join(x["description"] for x in lines if x["line_type"] == "service")
        goods_desc = " + ".join(x["description"] for x in lines if x["line_type"] == "goods")

        stamp = now()
        finished = stamp.isoformat(timespec="seconds")
        invoice_no = make_invoice_no()
        paid_flag = 1 if request.form.get("paid") == "on" else 0
        payment_mode = normalize_payment_mode(request.form.get("payment_mode", ""))
        sent_via = request.form.get("sent_via", "").strip()

        if paid_flag:
            accounting_year = stamp.year
            accounting_month = stamp.month
            accounting_date = stamp.strftime("%Y-%m-%d")
            accounting_status = "normal"
            accounting_service_amount = service_total
            accounting_goods_amount = goods_total
        else:
            accounting_year = None
            accounting_month = None
            accounting_date = ""
            accounting_status = "red"
            accounting_service_amount = 0.0
            accounting_goods_amount = 0.0

        # Identifiant technique distinct du numéro de facture.
        dossier_no = (
            "FS-" + stamp.strftime("%d%m%Y%H%M%S")
            + "-" + secrets.token_hex(2).upper()
        )

        cur = con.execute("""
            INSERT INTO repairs(
                dossier_no,client_id,created_at,received_date,
                problem,status,finished_at,invoice_no,
                service_amount,goods_amount,payment_method,payment_mode,
                paid,sent_via,service_description,goods_description,
                legacy_invoice_text,
                accounting_year,accounting_month,accounting_date,accounting_status,
                accounting_service_amount,accounting_goods_amount,
                simple_invoice
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
        """, (
            dossier_no,client_id,finished,stamp.strftime("%Y-%m-%d"),
            "Facture simple","Terminé",finished,invoice_no,
            service_total,goods_total,payment_mode,payment_mode,
            paid_flag,sent_via,service_desc,goods_desc,
            invoice_no,
            accounting_year,accounting_month,accounting_date,accounting_status,
            accounting_service_amount,accounting_goods_amount
        ))
        rid = int(cur.lastrowid)

        for line in lines:
            con.execute("""
                INSERT INTO invoice_lines(
                    repair_id,position,line_type,quantity,description,unit_price
                ) VALUES(?,?,?,?,?,?)
            """, (
                rid,line["position"],line["line_type"],
                line["quantity"],line["description"],line["unit_price"]
            ))

        con.commit()
        con.close()

        # V2.3.215 : aucune écriture Google automatique.
        audit_event(
            "SIMPLE_INVOICE_CREATE",
            f"Facture {invoice_no} / repair_id={rid}",
            request.remote_addr
        )
        flash(f"Facture simple {invoice_no} créée.")
        return redirect(url_for("simple_invoice_done", rid=rid))

    clients = con.execute("""
        SELECT id,name,company
        FROM clients
        WHERE COALESCE(archived,0)=0
        ORDER BY name COLLATE NOCASE
    """).fetchall()
    con.close()
    return render_template("simple_invoice.html", clients=clients)



@app.route("/invoice/simple/<int:rid>/done")
def simple_invoice_done(rid):
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.email client_email
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE r.id=? AND COALESCE(r.simple_invoice,0)=1
    """, (rid,)).fetchone()
    con.close()

    if not r:
        return "Facture simple introuvable", 404

    total = float(r["service_amount"] or 0) + float(r["goods_amount"] or 0)
    return render_template(
        "simple_invoice_done.html",
        r=r,
        total=total,
    )


@app.route("/factures")
def invoices_page():
    q = " ".join(request.args.get("q", "").split()).strip()
    unpaid_only = str(request.args.get("unpaid") or "").strip().lower() in {"1", "true", "yes", "oui"}
    con = db()

    raw_rows = con.execute("""
        SELECT
            r.*,
            c.name AS client_name,
            c.email AS client_email,
            (
                SELECT COALESCE(SUM(COALESCE(il.quantity,0) * COALESCE(il.unit_price,0)), 0)
                FROM invoice_lines il
                WHERE il.repair_id=r.id
            ) AS invoice_lines_total
        FROM repairs r
        JOIN clients c ON c.id=r.client_id
        WHERE COALESCE(trim(r.invoice_no),'')<>''
        ORDER BY r.id
    """).fetchall()
    con.close()

    grouped = {}
    for raw in raw_rows:
        row = dict(raw)
        key = (row["client_id"], row["invoice_no"])
        grouped.setdefault(key, {
            "rows": [],
            "client_name": row["client_name"],
            "client_email": row.get("client_email") or "",
            "invoice_no": row["invoice_no"],
        })["rows"].append(row)

    invoices = []

    for group in grouped.values():
        members = group["rows"]
        editable = next((x for x in members if not x["legacy_imported"]), None)
        representative = editable or max(
            members,
            key=lambda x: (
                bool(x.get("accounting_date")),
                float(x.get("service_amount") or 0) + float(x.get("goods_amount") or 0),
                str(x.get("received_date") or ""),
                int(x.get("id") or 0),
            )
        )

        # Total : lignes de facture récentes + montants Suivi + montants comptables
        # + ancien texte de paiement. On prend la meilleure valeur connue.
        total_candidates = []
        for x in members:
            total_candidates.extend([
                float(x.get("invoice_lines_total") or 0),
                float(x.get("service_amount") or 0) + float(x.get("goods_amount") or 0),
                float(x.get("accounting_service_amount") or 0) + float(x.get("accounting_goods_amount") or 0),
                payment_amount_from_text(x.get("payment_method")),
            ])
        invoice_total = max(total_candidates or [0.0])

        # Date de facture depuis le numéro JJMMYYYYHHMM, sinon ligne la plus ancienne.
        inv_date = invoice_no_date(group["invoice_no"])
        if not inv_date:
            date_candidates = sorted({
                str(x.get("finished_at") or x.get("received_date") or "")[:10]
                for x in members
                if x.get("finished_at") or x.get("received_date")
            })
            inv_date = date_candidates[0] if date_candidates else ""

        # Date encaissée : une ligne de paiement reportée gagne sur la ligne facture.
        accounting_dates = sorted({
            str(x.get("accounting_date") or "")[:10]
            for x in members if x.get("accounting_date")
        })
        accounting_date = accounting_dates[-1] if accounting_dates else ""

        # Si l'ancien groupe est marqué payé mais n'a encore aucune date, dernier filet :
        # date du numéro de facture. Cela reste purement visuel ; aucun CA n'est déplacé.
        is_paid = any(bool(x.get("paid")) for x in members)
        if not accounting_date and is_paid:
            accounting_date = inv_date

        # Mode : uniquement les codes reconnus. Jamais de montant dans cette colonne.
        modes = []
        for x in members:
            structured = normalize_payment_mode(x.get("payment_mode"))
            if structured and structured != "MIXTE" and structured not in modes:
                modes.append(structured)
            for detected in payment_modes_from_text(x.get("payment_method")):
                if detected not in modes:
                    modes.append(detected)

        # Si une facture a déjà été modifiée dans l'éditeur, ses invoice_lines
        # deviennent la source de vérité visuelle pour le total de la facture.
        edited_line_totals = [
            float(x.get("invoice_lines_total") or 0)
            for x in members
            if float(x.get("invoice_lines_total") or 0) > 0
        ]
        if edited_line_totals:
            invoice_total = max(edited_line_totals)

        invoice = {
            "id": representative["id"],
            "invoice_no": group["invoice_no"],
            "client_name": group["client_name"],
            "client_email": group.get("client_email") or "",
            "invoice_date": inv_date,
            "invoice_total": invoice_total,
            "payment_mode_display": (("Mixte · " + str(representative.get("payment_method") or "")) if normalize_payment_mode(representative.get("payment_mode")) == "MIXTE" else " + ".join(modes)),
            "accounting_date": accounting_date,
            "accounting_status": "red" if not is_paid else representative.get("accounting_status"),
            "legacy_imported": 0 if editable else 1,
            "historical": 0 if editable else 1,
            "simple_invoice": int(representative.get("simple_invoice") or 0),
        }

        if q:
            haystack = " ".join([
                str(invoice["invoice_no"]), str(invoice["client_name"]),
                str(invoice["invoice_date"]), str(invoice["invoice_total"]),
                str(invoice["payment_mode_display"]), str(invoice["accounting_date"]),
            ]).casefold()
            if q.casefold() not in haystack:
                continue

        if unpaid_only and is_paid:
            continue

        invoices.append(invoice)

    invoices.sort(
        key=lambda x: (str(x["invoice_date"] or ""), str(x["invoice_no"] or ""), int(x["id"] or 0)),
        reverse=True
    )
    return render_template("invoices.html", invoices=invoices, q=q, unpaid_only=unpaid_only)


@app.route("/repair/<int:rid>/invoice.pdf")
def invoice_pdf(rid):
    lang = pdf_lang()
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.company client_company, c.address client_address,
               c.address_street client_address_street, c.postal_code client_postal_code,
               c.city client_city, c.phone client_phone, c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id WHERE r.id=?
    """, (rid,)).fetchone()
    invoice_lines = con.execute("""
        SELECT * FROM invoice_lines WHERE repair_id=? ORDER BY position,id
    """, (rid,)).fetchall()
    con.close()

    if not r:
        return "introuvable", 404
    if not r["invoice_no"]:
        return "La réparation n'est pas clôturée.", 400

    # V2.3.20 : une ancienne facture ODS peut avoir beaucoup plus de détails
    # dans son PDF d'origine que dans le Suivi importé. Tant que l'utilisateur
    # n'a pas réellement reconstruit / enregistré cette facture dans l'éditeur,
    # le PDF original reste la référence.
    if lang == "fr" and r["legacy_imported"] and not invoice_lines and request.args.get("rebuild") != "1":
        original_pdf = find_client_invoice_pdf(
            r["invoice_no"],
            r["client_name"]
        ) or find_document_recursive(
            FACTURES_ROOT,
            document_no=r["invoice_no"]
        )
        if original_pdf and original_pdf.exists():
            legacy_filename = (
                f"{safe_filename(r['client_name'])}_"
                f"{safe_filename(r['invoice_no'])}_FR.pdf"
            )
            return send_file(
                original_pdf,
                mimetype="application/pdf",
                as_attachment=False,
                download_name=legacy_filename
            )

    conf = cfg()
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    W, H = A4

    BLUE = colors.HexColor("#3399FF")
    LIGHT_GREY = colors.HexColor("#777777")
    BLACK = colors.black

    left = 6 * mm
    right = W - 6 * mm
    top = H - 10 * mm

    c.setStrokeColor(BLUE)
    c.setLineWidth(1.1)
    c.line(left, top, right, top)

    # Logo fourni par l'utilisateur
    logo_x, logo_y = 6*mm, H - 62*mm
    logo_w, logo_h = 114*mm, 48*mm
    invoice_logo = invoice_logo_path()
    if invoice_logo:
        c.drawImage(str(invoice_logo), logo_x, logo_y, width=logo_w, height=logo_h,
                    preserveAspectRatio=True, anchor='sw', mask='auto')

    bx, by, bw, bh = 134*mm, H - 51*mm, 67*mm, 38*mm
    c.setFillColor(BLUE)
    c.rect(bx, by, bw, bh, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(PDF_FONTS["bold"], 24)
    c.drawCentredString(bx + bw/2, by + 25*mm, pdf_t("invoice", lang))

    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 10.5)
    c.drawString(bx + 1.5*mm, by + 9*mm, pdf_t("invoice_no", lang) + " :")
    fit_text(c, r["invoice_no"], bx + 29*mm, by + 9*mm, bw - 31*mm, PDF_FONTS["regular"], 10.5, 7)
    c.drawString(bx + 1.5*mm, by + 3.5*mm, pdf_t("date", lang) + " :")
    c.drawString(bx + 29*mm, by + 3.5*mm, fr_date(r["finished_at"]))

    line_y = H - 64*mm
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.1)
    c.line(left, line_y, right, line_y)

    box_y = H - 111*mm
    box_h = 43*mm
    c.setStrokeColor(BLUE)
    c.setLineWidth(.8)
    c.rect(11*mm, box_y, 66*mm, box_h, fill=0, stroke=1)

    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["bold"], 13)
    c.drawString(12*mm, box_y + 36.5*mm, conf.get("owner_name", ""))
    c.setFont(PDF_FONTS["regular"], 11.5)
    c.drawString(12*mm, box_y + 24*mm, conf.get("address_line1", ""))
    c.drawString(12*mm, box_y + 12*mm, conf.get("address_line2", ""))
    c.drawString(12*mm, box_y + 1.5*mm, pdf_t("phone", lang) + " : " + conf.get("phone", ""))

    cbx, cby, cbw, cbh = 134*mm, box_y, 67*mm, box_h
    c.setStrokeColor(colors.HexColor("#555555"))
    c.rect(cbx, cby, cbw, cbh, fill=0, stroke=1)
    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["bold"], 12.5)
    c.drawString(cbx + 1*mm, cby + cbh - 6*mm, pdf_t("client", lang) + " :")
    c.setLineWidth(.6)
    c.line(cbx + 1*mm, cby + cbh - 7*mm, cbx + 18*mm, cby + cbh - 7*mm)

    # Présentation postale classique : entreprise (si présente) / contact / rue / code postal + ville
    client_lines = []
    client_company = str(r["client_company"] or "").strip()
    client_name = str(r["client_name"] or "").strip()
    if client_company:
        client_lines.append(client_company)
    if client_name and client_name.casefold() != client_company.casefold():
        client_lines.append(client_name)
    street = (r["client_address_street"] or "").strip()
    cp_city = " ".join(x for x in [(r["client_postal_code"] or "").strip(), (r["client_city"] or "").strip()] if x)
    if street:
        client_lines.append(street)
    elif r["client_address"]:
        legacy_lines = [x.strip() for x in str(r["client_address"]).replace("\r","").split("\n") if x.strip()]
        client_lines.extend(legacy_lines[:1])
    if cp_city:
        client_lines.append(cp_city)

    cy = cby + cbh - 16*mm
    c.setFont(PDF_FONTS["regular"], 10)
    for line in client_lines[:4]:
        fit_text(c, line, cbx + 1.5*mm, cy, cbw - 3*mm, PDF_FONTS["regular"], 10, 7)
        cy -= 6.8*mm

    tx = 6*mm
    ty_top = H - 117*mm
    table_w = W - 12*mm
    header_h = 9*mm
    row_h = 6.1*mm
    col_qty = 19*mm
    col_desc = 92*mm
    col_blank = 28*mm
    col_total = table_w - col_qty - col_desc - col_blank

    xs = [tx, tx+col_qty, tx+col_qty+col_desc,
          tx+col_qty+col_desc+col_blank, tx+table_w]

    c.setFillColor(BLUE)
    c.rect(tx, ty_top-header_h, table_w, header_h, fill=1, stroke=0)
    c.setStrokeColor(BLACK)
    c.setLineWidth(.55)
    for x in xs:
        c.line(x, ty_top, x, ty_top-header_h)
    c.line(tx, ty_top, tx+table_w, ty_top)
    c.line(tx, ty_top-header_h, tx+table_w, ty_top-header_h)

    c.setFillColor(colors.white)
    c.setFont(PDF_FONTS["bold"], 10.5)
    c.drawCentredString(tx + col_qty/2, ty_top-6.1*mm, pdf_t("quantity", lang))
    c.drawCentredString(xs[1] + col_desc/2, ty_top-6.1*mm, pdf_t("description", lang))
    c.drawCentredString(xs[2] + col_blank/2, ty_top-6.1*mm, pdf_t("unit_price", lang))
    c.drawCentredString(xs[3] + col_total/2, ty_top-6.1*mm, pdf_t("total", lang))

    rows = []
    if invoice_lines:
        for line in invoice_lines:
            qty = float(line["quantity"] or 0)
            unit = float(line["unit_price"] or 0)
            rows.append((qty, translate_pdf_text(line["description"], lang), qty * unit, unit))
    else:
        # Ancienne facture sans lignes détaillées.
        if r["service_amount"]:
            rows.append((1, translate_pdf_text(r["service_description"] or r["tests_validation"] or r["problem"] or "Prestation de service", lang),
                         float(r["service_amount"]), float(r["service_amount"])))
        if r["goods_amount"]:
            rows.append((1, translate_pdf_text(r["goods_description"] or "Vente de marchandises / pièces", lang),
                         float(r["goods_amount"]), float(r["goods_amount"])))

    # -----------------------------------------------------------------
    # Typographie facture WOPR :
    #   - 1re ligne de chaque article/prestation : Roboto 12
    #   - 2e ligne et suivantes (détails)       : Roboto 10
    # Les lignes trop longues sont renvoyées à la ligne, jamais réduites.
    # Quantité / P.U. / Total ne figurent que sur la première ligne.
    # Une ligne vide sépare chaque prestation / marchandise.
    # -----------------------------------------------------------------
    visual_rows = []
    desc_width = col_desc - 2*mm

    for item_index, (qty, description, amount, unit) in enumerate(rows):
        raw_lines = str(description or "").replace("\r", "").split("\n")
        if not raw_lines:
            raw_lines = [""]

        physical_lines = []
        for raw_index, raw_line in enumerate(raw_lines):
            font_size = 12 if raw_index == 0 else 10
            wrapped = wrap_pdf_text(raw_line, PDF_FONTS["regular"], font_size, desc_width)
            for wrap_index, wrapped_line in enumerate(wrapped):
                # Seule la toute première ligne reste l'intitulé en 12.
                is_title = (raw_index == 0 and wrap_index == 0)
                physical_lines.append((wrapped_line, is_title))

        if not physical_lines:
            physical_lines = [("", True)]

        for line_index, (desc_line, is_title) in enumerate(physical_lines):
            visual_rows.append({
                "qty": qty if line_index == 0 else None,
                "desc": desc_line,
                "amount": amount if line_index == 0 else None,
                "unit": unit if line_index == 0 else None,
                "font_size": 12 if is_title else 10,
                "spacer": False,
            })

        # Une ligne entièrement vide ENTRE deux prestations / marchandises.
        # Pas après le dernier article et jamais entre l'intitulé et ses détails.
        if item_index < len(rows) - 1:
            visual_rows.append({
                "qty": None,
                "desc": "",
                "amount": None,
                "unit": None,
                "font_size": 10,
                "spacer": True,
            })

    # Le gabarit historique contient au minimum 13 lignes de tableau.
    # On ajoute des lignes vierges si nécessaire, sans modifier les polices.
    content_rows = max(13, len(visual_rows))
    row_h = 6.1*mm
    y = ty_top - header_h
    c.setFillColor(BLACK)

    for i in range(content_rows):
        y2 = y - row_h
        c.setStrokeColor(BLACK)
        c.setLineWidth(.45)
        for x in xs:
            c.line(x, y, x, y2)
        c.line(tx, y2, tx+table_w, y2)

        if i < len(visual_rows):
            vr = visual_rows[i]

            if vr["qty"] is not None:
                qty = float(vr["qty"])
                qty_text = str(int(qty)) if qty.is_integer() else str(qty).replace(".", ",")
                c.setFont(PDF_FONTS["regular"], 10)
                c.drawCentredString(tx + col_qty/2, y2 + 1.65*mm, qty_text)

            # Taille FIXE : 12 pour l'intitulé, 10 pour les détails.
            c.setFont(PDF_FONTS["regular"], vr["font_size"])
            c.drawString(xs[1] + 1*mm, y2 + 1.45*mm, vr["desc"])

            if vr["unit"] is not None:
                c.setFont(PDF_FONTS["regular"], 10)
                c.drawRightString(xs[3] - 1*mm, y2 + 1.65*mm,
                                  f"{vr['unit']:,.2f} €".replace(",", " ").replace(".", ","))
                c.drawRightString(xs[4] - 1*mm, y2 + 1.65*mm,
                                  f"{vr['amount']:,.2f} €".replace(",", " ").replace(".", ","))
        y = y2

    footer_h = 12*mm
    y2 = y - footer_h
    c.setStrokeColor(BLACK)
    c.setLineWidth(.55)
    c.rect(tx, y2, table_w, footer_h, fill=0, stroke=1)
    for x in xs[2:]:
        c.line(x, y, x, y2)

    c.setFont(PDF_FONTS["italic"], 9.5)
    c.drawString(tx + 20*mm, y - 4.2*mm, pdf_t("vat_notice", lang))
    c.drawString(tx + 20*mm, y - 9.4*mm, pdf_t("invoice_euros", lang))

    total = sum(float(x["quantity"] or 0) * float(x["unit_price"] or 0) for x in invoice_lines) if invoice_lines else (float(r["service_amount"] or 0) + float(r["goods_amount"] or 0))
    c.setFont(PDF_FONTS["bold"], 9.5)
    c.drawString(xs[2] + 2*mm, y - 9.4*mm, pdf_t("net_payable", lang) + " :")
    c.drawRightString(xs[4] - 1*mm, y - 9.4*mm,
                      f"{total:,.2f} €".replace(",", " ").replace(".", ","))

    note_y = y2 - 7*mm
    # V2.3.51 : légèrement plus lisible à l'impression, avec réduction
    # automatique seulement si la ligne risque de dépasser la largeur A4.
    fit_text(
        c,
        pdf_t("abandon_1", lang),
        7*mm, note_y, W-14*mm, PDF_FONTS["italic"], 7.3, 6.8
    )
    fit_text(
        c,
        pdf_t("abandon_2", lang),
        7*mm, note_y-4.5*mm, W-14*mm, PDF_FONTS["regular"], 7.3, 6.8
    )

    c.setFillColor(LIGHT_GREY)
    conds = [
        pdf_t("payment_1", lang),
        pdf_t("payment_2", lang),
        pdf_t("payment_3", lang),
        pdf_t("payment_4", lang),
    ]
    yy = note_y - 14*mm
    for line in conds:
        fit_text(
            c, line, 7*mm, yy, W-14*mm,
            PDF_FONTS["regular"], 7.2, 6.7
        )
        yy -= 4.2*mm

    c.setFillColor(BLACK)
    c.setFont(PDF_FONTS["regular"], 7.8)
    footer = [
        f"{conf.get('business_name','WOPR')} - {conf.get('owner_name','')} - {pdf_t('siret_no', lang)} : {conf.get('siret','')} - {pdf_t('ape_code', lang)} : {conf.get('ape','')}",
        f"IBAN : {conf.get('iban','')}",
        f"- {conf.get('website','')} - {conf.get('email','')} -",
    ]
    legal_lines = wrap_pdf_text(
        pdf_t("legal_registration_exemption", lang),
        PDF_FONTS["regular"], 7.8, W-20*mm
    )
    footer.extend(legal_lines)
    fy = 25*mm
    for line in footer:
        c.drawCentredString(W/2, fy, line)
        fy -= 4.2*mm

    c.save()
    pdf_bytes = bio.getvalue()

    # V2.3.238 — classement automatique de la facture selon sa date réelle.
    # Les numéros historiques JJMMYYYYHHMM restent prioritaires pour retrouver
    # la date de facture ; sinon on utilise finished_at puis received_date.
    invoice_date_value = invoice_no_date(r["invoice_no"])
    if not invoice_date_value:
        invoice_date_value = str(r["finished_at"] or r["received_date"] or "")[:10]
    try:
        datetime.strptime(str(invoice_date_value or ""), "%Y-%m-%d")
    except Exception:
        invoice_date_value = now().strftime("%Y-%m-%d")

    invoice_filename = (
        f"{safe_filename(r['client_name'])}_"
        f"{safe_filename(r['invoice_no'])}_"
        f"{pdf_language_suffix(lang)}.pdf"
    )

    invoice_folder = year_month_folder(
        FACTURES_ROOT,
        invoice_date_value,
        create=True
    )
    invoice_saved_path = invoice_folder / safe_document_name(invoice_filename)
    try:
        invoice_saved_path.write_bytes(pdf_bytes)
    except Exception as exc:
        app.logger.warning(
            "Impossible d'enregistrer la facture dans %s: %s",
            invoice_saved_path, exc
        )

    bio.seek(0)
    return send_file(
        bio,
        mimetype="application/pdf",
        # V2.3.239 : la copie officielle est déjà archivée dans
        # private/documents/Factures. Affichage navigateur, sans doublon
        # automatique dans Téléchargements.
        as_attachment=False,
        download_name=invoice_filename
    )



@app.route("/repair/<int:rid>/followup/email", methods=["GET", "POST"])
def followup_email(rid):
    """Envoie uniquement le PDF de suivi + photos sélectionnées, jamais la facture."""
    smtp_settings = read_smtp_settings()
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()

    if not r:
        return "Dossier introuvable", 404

    lang = pdf_lang(request.values.get("lang", "fr"))
    cancel_url = url_for("repair_detail", rid=rid)

    if request.method == "GET":
        if not smtp_settings.get("enabled") or not smtp_settings.get("token"):
            flash("Configure d'abord le SMTP Proton dans Sécurité.")
            return redirect(url_for("security_page"))
        if not r["client_email"]:
            flash("Impossible d'envoyer : le client n'a pas d'adresse e-mail.")
            return redirect(cancel_url)

        ident = business_identity()
        subject = f"{ident['name']} - Suivi de réparation"
        if str(r["status"] or "") == "Laissé pour pièces":
            body = (
                "Bonjour,\n\n"
                f"Comme convenu, vous avez choisi de laisser votre matériel à {ident['name']} pour pièces "
                "en remplacement du forfait diagnostic de 30 €.\n\n"
                "Vous trouverez ci-joint le suivi de votre dossier ainsi que les photos sélectionnées.\n\n"
                "Cordialement,\n"
                f"{business_signature()}"
            )
        else:
            body = (
                "Bonjour,\n\n"
                f"Vous trouverez ci-joint le suivi de votre dossier {ident['name']} ainsi que les photos sélectionnées.\n\n"
                "Cordialement,\n"
                f"{business_signature()}"
            )

        # Génère aussi le PDF dès l'écran de prévisualisation afin d'afficher
        # une vraie pièce jointe (nom + taille), et pas seulement une phrase.
        preview_pdf = intake_pdf(rid)
        preview_pdf_data = b""
        if hasattr(preview_pdf, "get_data"):
            # send_file() utilise le mode direct_passthrough :
            # get_data() plante tant qu'on ne le désactive pas explicitement.
            preview_pdf.direct_passthrough = False
            preview_pdf_data = bytes(preview_pdf.get_data())
        preview_pdf_ok = preview_pdf_data.startswith(b"%PDF")
        preview_pdf_filename = (
            f"{safe_filename(r['client_name'])}_"
            f"{now().strftime('%d%m%Y')}_"
            f"{pdf_language_suffix(lang)}.pdf"
        )
        preview_pdf_size = len(preview_pdf_data) if preview_pdf_ok else 0

        return render_template(
            "followup_email_preview.html",
            r=r,
            recipient=r["client_email"],
            subject=subject,
            body=body,
            cancel_url=cancel_url,
            sender=smtp_settings.get("sender_email") or smtp_settings.get("username"),
            pdf_lang=lang,
            pdf_languages=PDF_LANGUAGES,
            preview_pdf_ok=preview_pdf_ok,
            preview_pdf_filename=preview_pdf_filename,
            preview_pdf_size=preview_pdf_size,
        )

    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()
    lang = pdf_lang(request.form.get("lang", "fr"))

    if not recipient or "@" not in recipient:
        flash("Adresse destinataire invalide.")
        return redirect(url_for("followup_email", rid=rid, lang=lang))
    if not subject:
        flash("L'objet du message est obligatoire.")
        return redirect(url_for("followup_email", rid=rid, lang=lang))

    # Génère directement le PDF de suivi dans la requête courante.
    # On évite le client Flask interne : selon l'auth/session il pouvait renvoyer
    # autre chose que le PDF tout en ayant un code HTTP 200.
    pdf_response = intake_pdf(rid)
    if not hasattr(pdf_response, "get_data"):
        flash("Impossible de générer le PDF de suivi.")
        return redirect(url_for("followup_email", rid=rid, lang=lang))
    pdf_response.direct_passthrough = False
    pdf_data = bytes(pdf_response.get_data())
    if not pdf_data.startswith(b"%PDF"):
        flash("Le PDF de suivi n'a pas pu être généré correctement.")
        return redirect(url_for("followup_email", rid=rid, lang=lang))

    sender_email = str(smtp_settings.get("sender_email") or smtp_settings.get("username") or "").strip()
    sender_name = str(smtp_settings.get("sender_name") or business_identity()["name"]).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    msg["To"] = recipient
    msg.set_content(body)

    followup_filename = (
        f"{safe_filename(r['client_name'])}_"
        f"{now().strftime('%d%m%Y')}_"
        f"{pdf_language_suffix(lang)}.pdf"
    )
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=followup_filename
    )

    # Médias choisis au moment de l'envoi : photos, GIF et vidéos.
    allowed_media_ext = {
        ".jpg", ".jpeg", ".png", ".webp", ".gif",
        ".mp4", ".mov", ".webm", ".m4v", ".avi"
    }
    media_files = request.files.getlist("media")
    attached_media = 0
    attached_media_bytes = 0
    max_media_total = 20 * 1024 * 1024  # 20 Mo de médias, hors PDF

    for media in media_files:
        filename = str(media.filename or "").strip()
        if not filename:
            continue
        ext = Path(filename).suffix.lower()
        if ext not in allowed_media_ext:
            continue

        data = media.read()
        if not data:
            continue

        if attached_media_bytes + len(data) > max_media_total:
            flash("Certains médias n'ont pas été joints : limite de 20 Mo de médias par e-mail.")
            break

        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type and "/" in guessed_type:
            maintype, subtype = guessed_type.split("/", 1)
        elif ext == ".gif":
            maintype, subtype = "image", "gif"
        elif ext in {".mp4", ".m4v"}:
            maintype, subtype = "video", "mp4"
        elif ext == ".mov":
            maintype, subtype = "video", "quicktime"
        elif ext == ".webm":
            maintype, subtype = "video", "webm"
        elif ext == ".avi":
            maintype, subtype = "video", "x-msvideo"
        else:
            maintype, subtype = "application", "octet-stream"

        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=safe_filename(filename)
        )
        attached_media += 1
        attached_media_bytes += len(data)

    # Vérification avant envoi : le PDF de suivi doit réellement être présent
    # dans le MIME du message.
    attachments = list(msg.iter_attachments())
    pdf_attachments = [
        part for part in attachments
        if part.get_content_type() == "application/pdf"
    ]
    if not pdf_attachments:
        flash("Erreur interne : le PDF de suivi n'a pas été joint au message.")
        return redirect(url_for("followup_email", rid=rid, lang=lang))

    try:
        smtp_send_message(msg)
        audit_event(
            "FOLLOWUP_EMAIL",
            f"Suivi repair_id={rid} envoyé à {recipient} avec {attached_media} média(s)",
            request.remote_addr
        )
        flash(
            f"Suivi PDF joint et envoyé par e-mail à {recipient}"
            + (f" avec {attached_media} média(s)." if attached_media else ".")
        )
        return redirect(cancel_url)
    except Exception as e:
        audit_event(
            "FOLLOWUP_EMAIL_ERROR",
            f"Suivi repair_id={rid} : {type(e).__name__}",
            request.remote_addr
        )
        flash(f"Échec envoi e-mail : {e}")
        return redirect(url_for("followup_email", rid=rid, lang=lang))


@app.route("/repair/<int:rid>/invoice/email", methods=["GET", "POST"])
def invoice_email(rid):
    smtp_settings = read_smtp_settings()
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.email client_email
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()

    if not r:
        return "Dossier introuvable", 404
    if not r["invoice_no"]:
        flash("Impossible d'envoyer : aucune facture n'a encore été créée.")
        return redirect(url_for("repair_detail", rid=rid))

    from_page = request.values.get("from_page", "detail")
    lang = pdf_lang(request.values.get("lang", "fr"))
    cancel_url = url_for("invoices_page") if from_page == "factures" else url_for("repair_detail", rid=rid)

    if request.method == "GET":
        if not smtp_settings.get("enabled") or not smtp_settings.get("token"):
            flash("Configure d'abord le SMTP Proton dans Sécurité.")
            return redirect(url_for("security_page"))
        if not r["client_email"]:
            flash("Impossible d'envoyer : le client n'a pas d'adresse e-mail.")
            return redirect(cancel_url)

        ident = business_identity()
        subject = f"{ident['name']} - Facture {r['invoice_no']}"
        body = (
            "Bonjour,\n\n"
            f"Veuillez trouver ci-joint votre facture {ident['name']}.\n\n"
            "Je vous remercie pour votre confiance.\n\n"
            "Cordialement,\n"
            f"{business_signature()}"
        )
        return render_template(
            "invoice_email_preview.html",
            r=r,
            recipient=r["client_email"],
            subject=subject,
            body=body,
            from_page=from_page,
            cancel_url=cancel_url,
            sender=smtp_settings.get("sender_email") or smtp_settings.get("username"),
            pdf_lang=lang,
            pdf_languages=PDF_LANGUAGES,
        )

    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    if not recipient or "@" not in recipient:
        flash("Adresse destinataire invalide.")
        return redirect(url_for("invoice_email", rid=rid, from_page=from_page))
    if not subject:
        flash("L'objet du message est obligatoire.")
        return redirect(url_for("invoice_email", rid=rid, from_page=from_page))

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess.update(dict(session))
        pdf_response = client.get(url_for("invoice_pdf", rid=rid, lang=lang))
        if pdf_response.status_code != 200:
            flash("Impossible de générer le PDF de facture.")
            return redirect(url_for("invoice_email", rid=rid, from_page=from_page))
        pdf_data = bytes(pdf_response.data)

    sender_email = str(smtp_settings.get("sender_email") or smtp_settings.get("username") or "").strip()
    sender_name = str(smtp_settings.get("sender_name") or business_identity()["name"]).strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>" if sender_name else sender_email
    msg["To"] = recipient
    msg.set_content(body)
    msg.add_attachment(
        pdf_data,
        maintype="application",
        subtype="pdf",
        filename=f"{safe_filename(r['client_name'])}_{safe_filename(r['invoice_no'])}_{pdf_language_suffix(lang)}.pdf"
    )

    try:
        smtp_send_message(msg)
        audit_event("INVOICE_EMAIL", f"Facture {r['invoice_no']} envoyée à {recipient}", request.remote_addr)
        flash(f"Facture {r['invoice_no']} envoyée par e-mail à {recipient}.")
        return redirect(cancel_url)
    except Exception as e:
        audit_event("INVOICE_EMAIL_ERROR", f"Facture {r['invoice_no']} : {type(e).__name__}", request.remote_addr)
        flash(f"Échec envoi e-mail : {e}")
        return redirect(url_for("invoice_email", rid=rid, from_page=from_page))


@app.route("/repair/<int:rid>/invoice/sms-link")
def invoice_sms_link(rid):
    con = db()
    r = con.execute("""
        SELECT r.*, c.name client_name, c.phone client_phone
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.id=?
    """, (rid,)).fetchone()
    con.close()
    if not r:
        return "Dossier introuvable", 404
    if not r["client_phone"]:
        flash("Le client n'a pas de numéro de téléphone.")
        return redirect(url_for("repair_detail", rid=rid))

    # Cette page ouvre le composeur SMS sur un téléphone.
    message = f"Bonjour {r['client_name']}, votre facture {business_identity()['name']} n° {r['invoice_no'] or ''} est disponible. Merci."
    from urllib.parse import quote
    phone = re.sub(r"[^0-9+]", "", r["client_phone"])
    return redirect(f"sms:{phone}?body={quote(message)}")




@app.route("/contacts/import-google-csv", methods=["GET", "POST"])
def import_google_csv_contacts():
    if request.method == "POST":
        f = request.files.get("csv")
        if not f or not f.filename:
            flash("Choisis ton export Google Contacts .csv.")
            return redirect(url_for("import_google_csv_contacts"))

        if not f.filename.lower().endswith(".csv"):
            flash("Le fichier doit être un export Google Contacts .csv.")
            return redirect(url_for("import_google_csv_contacts"))

        try:
            raw = f.read().decode("utf-8-sig", errors="replace")
            contacts = parse_google_contacts_csv(raw)

            if request.form.get("only_foulfix") == "on":
                contacts = [
                    c for c in contacts
                    if "foul-fix" in str(c.get("labels") or "").casefold()
                ]
        except Exception as e:
            flash(f"Impossible de lire le CSV Google : {e}")
            return redirect(url_for("import_google_csv_contacts"))

        if not contacts:
            flash("Aucun contact exploitable trouvé dans ce CSV.")
            return redirect(url_for("import_google_csv_contacts"))

        analyzed, summary = analyze_google_csv_contacts(contacts)

        payload = {
            "created_at": now().isoformat(timespec="seconds"),
            "source_filename": safe_filename(Path(f.filename).stem) + ".csv",
            "summary": summary,
            "contacts": analyzed,
        }
        save_pending_google_csv_import(payload)

        audit_event(
            "GOOGLE_CSV_IMPORT_ANALYZE",
            (
                f"{summary['total_source']} source; {summary['safe']} sûrs; "
                f"{summary['will_fill']} à compléter; "
                f"filtre_label={'oui' if request.form.get('only_foulfix') == 'on' else 'non'}"
            ),
            request.remote_addr
        )
        return redirect(url_for("import_google_csv_preview"))

    return render_template("google_csv_import.html")


@app.route("/contacts/import-google-csv/preview")
def import_google_csv_preview():
    payload, _ = load_pending_google_csv_import()
    if not payload:
        flash("Aucun import Google CSV en attente. Recharge le fichier.")
        return redirect(url_for("import_google_csv_contacts"))
    return render_template("google_csv_import_preview.html", payload=payload)


@app.route("/contacts/import-google-csv/confirm", methods=["POST"])
def import_google_csv_confirm():
    payload, pending_path = load_pending_google_csv_import()
    if not payload:
        flash("L'aperçu Google CSV a expiré. Recharge le fichier.")
        return redirect(url_for("import_google_csv_contacts"))

    selected_ids = {
        int(x) for x in request.form.getlist("apply_client_id")
        if str(x).isdigit()
    }

    safe_rows = [
        x for x in payload.get("contacts", [])
        if x.get("status") == "safe"
        and x.get("local_client_id") in selected_ids
        and (x.get("fill") or x.get("duplicate_local_ids"))
    ]

    if not safe_rows:
        flash("Aucun complément ou doublon sûr sélectionné.")
        return redirect(url_for("import_google_csv_preview"))

    backup_database(force=True, tag="avant_import_google_csv")
    con = db()

    updated_clients = 0
    updated_fields = 0
    merged_duplicates = 0
    moved_repairs = 0
    moved_quotes = 0

    for row in safe_rows:
        cid = int(row["local_client_id"])

        # Merge safe local duplicates in the same operation.
        for dup_id in row.get("duplicate_local_ids") or []:
            try:
                dup_id = int(dup_id)
            except Exception:
                continue
            merge_result = _merge_one_local_client(con, cid, dup_id)
            if merge_result["merged"]:
                merged_duplicates += 1
                moved_repairs += merge_result["repairs"]
                moved_quotes += merge_result["quotes"]

        current = con.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        if not current:
            continue

        # Revalider au moment de l'écriture : uniquement les champs encore vides.
        allowed = (
            "first_name", "last_name", "company", "phone", "email",
            "address_street", "postal_code", "city"
        )
        sets = []
        values = []

        for field in allowed:
            wanted = str((row.get("fill") or {}).get(field) or "").strip()
            if wanted and not str(current[field] or "").strip():
                sets.append(f"{field}=?")
                values.append(wanted)

        if not sets:
            # The row may still have merged local duplicates.
            continue

        # Maintenir le nom historique/compatibilité à partir des champs structurés.
        first_after = (
            (row.get("fill") or {}).get("first_name")
            if not str(current["first_name"] or "").strip()
            else current["first_name"]
        ) or ""
        last_after = (
            (row.get("fill") or {}).get("last_name")
            if not str(current["last_name"] or "").strip()
            else current["last_name"]
        ) or ""

        if (first_after or last_after):
            composed = compose_client_name(last_after, first_after)
            if composed and not str(current["name"] or "").strip():
                sets.append("name=?")
                values.append(composed)

        # Reconstruire address uniquement à partir des champs structurés finaux.
        street_after = (
            (row.get("fill") or {}).get("address_street")
            if not str(current["address_street"] or "").strip()
            else current["address_street"]
        ) or ""
        postal_after = (
            (row.get("fill") or {}).get("postal_code")
            if not str(current["postal_code"] or "").strip()
            else current["postal_code"]
        ) or ""
        city_after = (
            (row.get("fill") or {}).get("city")
            if not str(current["city"] or "").strip()
            else current["city"]
        ) or ""

        address_after = "\n".join(
            x for x in [
                str(street_after).strip(),
                " ".join(x for x in [str(postal_after).strip(), str(city_after).strip()] if x).strip()
            ] if x
        )

        if address_after != str(current["address"] or ""):
            sets.append("address=?")
            values.append(address_after)

        sets.extend(["google_sync_status=?", "google_sync_error=?", "updated_at=?"])
        values.extend(["À synchroniser", "", now().isoformat(timespec="seconds")])
        values.append(cid)

        con.execute(
            f"UPDATE clients SET {', '.join(sets)} WHERE id=?",
            values
        )
        updated_clients += 1
        updated_fields += len([
            f for f in allowed
            if str((row.get("fill") or {}).get(f) or "").strip()
            and not str(current[f] or "").strip()
        ])

    con.commit()
    con.close()

    audit_event(
        "GOOGLE_CSV_IMPORT_APPLY",
        (
            f"{updated_clients} clients; {updated_fields} champs complétés; "
            f"{merged_duplicates} doublons fusionnés; "
            f"{moved_repairs} réparations; {moved_quotes} devis déplacés"
        ),
        request.remote_addr
    )

    if pending_path:
        try:
            pending_path.unlink()
        except OSError:
            pass
    session.pop("google_csv_import_token", None)

    flash(
        f"Google CSV : {updated_clients} client(s) enrichi(s), "
        f"{updated_fields} champ(s) complété(s), "
        f"{merged_duplicates} doublon(s) local(aux) fusionné(s). "
        "Aucune valeur existante n'a été écrasée."
    )
    return redirect(url_for("contacts_page"))


@app.route("/contacts/import-google-csv/cancel", methods=["POST"])
def import_google_csv_cancel():
    _, pending_path = load_pending_google_csv_import()
    if pending_path:
        try:
            pending_path.unlink()
        except OSError:
            pass
    session.pop("google_csv_import_token", None)
    flash("Import Google CSV annulé. Aucune donnée n'a été modifiée.")
    return redirect(url_for("contacts_page"))



@app.route("/contacts/import-proton", methods=["GET", "POST"])
def import_proton_contacts():
    if request.method == "POST":
        f = request.files.get("vcf")
        if not f or not f.filename:
            flash("Choisis ton fichier Proton Contacts .vcf.")
            return redirect(url_for("import_proton_contacts"))

        if not f.filename.lower().endswith(".vcf"):
            flash("Le fichier doit être un export Proton .vcf.")
            return redirect(url_for("import_proton_contacts"))

        try:
            raw = f.read().decode("utf-8-sig", errors="replace")
            contacts = parse_proton_vcf(raw)
        except Exception as e:
            flash(f"Impossible de lire le fichier VCF : {e}")
            return redirect(url_for("import_proton_contacts"))

        if not contacts:
            flash("Aucun contact trouvé dans ce fichier VCF.")
            return redirect(url_for("import_proton_contacts"))

        google_index = None
        google_error = ""
        if google_credentials() is not None:
            try:
                service = google_service()
                google_index = google_contacts_bulk_index(service)
            except Exception as e:
                google_error = str(e)

        analyzed, summary = analyze_proton_contacts(contacts, google_index)
        payload = {
            "created_at": now().isoformat(timespec="seconds"),
            "source_filename": safe_filename(Path(f.filename).stem) + ".vcf",
            "google_checked": google_index is not None,
            "google_error": google_error,
            "summary": summary,
            "contacts": analyzed,
        }
        save_pending_proton_import(payload)

        audit_event(
            "PROTON_IMPORT_ANALYZE",
            f"{len(contacts)} contacts analysés; google_checked={google_index is not None}",
            request.remote_addr
        )
        return redirect(url_for("import_proton_preview"))

    return render_template(
        "proton_import.html",
        google_connected=google_credentials() is not None
    )


@app.route("/contacts/import-proton/preview")
def import_proton_preview():
    payload, _ = load_pending_proton_import()
    if not payload:
        flash("Aucune analyse Proton en attente. Recharge le fichier VCF.")
        return redirect(url_for("import_proton_contacts"))
    return render_template("proton_import_preview.html", payload=payload)


@app.route("/contacts/import-proton/confirm", methods=["POST"])
def import_proton_confirm():
    payload, pending_path = load_pending_proton_import()
    if not payload:
        flash("Analyse Proton expirée. Recharge le fichier VCF.")
        return redirect(url_for("import_proton_contacts"))

    contacts = payload.get("contacts", [])
    # Tous les contacts Proton importés sont considérés comme des clients WOPR.
    # Google est un miroir : les contacts absents y sont créés automatiquement.
    create_missing_google = True

    backup_database(force=True, tag="avant_import_proton")
    audit_event("PROTON_IMPORT_START", f"{len(contacts)} contacts", request.remote_addr)

    # Recalcule les index au moment exact de l'import.
    con = db()
    current_rows = con.execute("SELECT * FROM clients ORDER BY id").fetchall()
    con.close()
    local_index = build_local_contact_index(current_rows)

    source_phone_counts = {}
    for c in contacts:
        for phone in c.get("phones", []):
            pk = normalize_phone(phone)
            if pk:
                source_phone_counts[pk] = source_phone_counts.get(pk, 0) + 1

    service = google_service() if google_credentials() is not None else None
    google_index = None
    group_resource = None
    google_scan_error = ""
    if service:
        try:
            google_index = google_contacts_bulk_index(service)
            group_resource = google_find_group(service)
        except Exception as e:
            google_scan_error = str(e)
            google_index = None

    created_local = 0
    merged_local = 0
    local_ambiguous = 0
    google_linked = 0
    google_created = 0
    google_ambiguous = 0
    google_errors = 0

    for contact in contacts:
        # 1) Rattachement local : UID Proton > e-mail > téléphone unique.
        local_matches, _ = _unique_contact_matches(contact, local_index, source_phone_counts)
        client_id = None

        if len(local_matches) == 1:
            client_id = local_matches[0]
            con = db()
            existing = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
            if existing:
                name = existing["name"] or contact.get("name", "")
                email = existing["email"] or contact.get("email", "")
                phone = existing["phone"] or contact.get("phone", "")
                street = existing["address_street"] or existing["address"] or contact.get("address_street", "")
                postal = existing["postal_code"] or contact.get("postal_code", "")
                city = existing["city"] or contact.get("city", "")
                address = "\n".join(x for x in [street, " ".join(x for x in [postal, city] if x).strip()] if x)
                notes = _merge_notes(existing["notes"], contact.get("notes", ""))

                con.execute("""
                    UPDATE clients SET
                        name=?, email=?, phone=?, address=?, address_street=?,
                        postal_code=?, city=?, notes=?,
                        proton_uid=COALESCE(NULLIF(proton_uid,''), ?),
                        proton_imported_at=?, updated_at=?
                    WHERE id=?
                """, (
                    name, email, phone, address, street, postal, city, notes,
                    contact.get("uid", ""), now().isoformat(timespec="seconds"),
                    now().isoformat(timespec="seconds"), client_id
                ))
                con.commit()
                merged_local += 1
            con.close()

        elif len(local_matches) > 1:
            # Ne jamais fusionner arbitrairement plusieurs clients locaux.
            local_ambiguous += 1

        if client_id is None:
            con = db()
            address = "\n".join(
                x for x in [
                    contact.get("address_street", ""),
                    " ".join(x for x in [contact.get("postal_code", ""), contact.get("city", "")] if x).strip()
                ] if x
            )
            cur = con.execute("""
                INSERT INTO clients(
                    name,address,address_street,postal_code,city,phone,email,
                    notes,proton_uid,proton_imported_at,
                    google_sync_status,google_sync_error,created_at,updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                contact.get("name") or "Client Proton",
                address,
                contact.get("address_street", ""),
                contact.get("postal_code", ""),
                contact.get("city", ""),
                contact.get("phone", ""),
                contact.get("email", ""),
                contact.get("notes", ""),
                contact.get("uid", ""),
                now().isoformat(timespec="seconds"),
                "À synchroniser",
                "",
                now().isoformat(timespec="seconds"),
                now().isoformat(timespec="seconds"),
            ))
            client_id = cur.lastrowid
            con.commit()
            con.close()
            created_local += 1

        # Actualise l'index local afin qu'un même UID Proton réimporté ne se duplique pas.
        con = db()
        fresh = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        con.close()
        if fresh:
            fresh_index = build_local_contact_index([fresh])
            for key in ("email", "phone", "name", "uid"):
                for val, ids in fresh_index[key].items():
                    local_index[key].setdefault(val, [])
                    for rid in ids:
                        if rid not in local_index[key][val]:
                            local_index[key][val].append(rid)

        # 2) Google : rattache un contact unique existant. Ne modifie pas son contenu,
        # pour éviter d'effacer ses éventuels champs secondaires.
        if google_index is not None and service:
            google_matches, _ = _unique_contact_matches(contact, google_index, source_phone_counts)

            if len(google_matches) == 1:
                resource = google_matches[0]
                try:
                    if group_resource:
                        service.contactGroups().members().modify(
                            resourceName=group_resource,
                            body={"resourceNamesToAdd": [resource]}
                        ).execute()
                    set_google_sync_state(client_id, "Synchronisé", resource_name=resource)
                    google_linked += 1
                except HttpError as e:
                    if getattr(e.resp, "status", None) in (400, 409):
                        set_google_sync_state(client_id, "Synchronisé", resource_name=resource)
                        google_linked += 1
                    else:
                        set_google_sync_state(client_id, "Erreur", error=str(e))
                        google_errors += 1
                except Exception as e:
                    set_google_sync_state(client_id, "Erreur", error=str(e))
                    google_errors += 1

            elif len(google_matches) > 1:
                set_google_sync_state(
                    client_id,
                    "Erreur",
                    error=f"Doublon Google à vérifier : {len(google_matches)} contacts correspondent."
                )
                google_ambiguous += 1

            elif create_missing_google:
                try:
                    resource = google_create_from_proton(service, contact, group_resource)
                    if resource:
                        set_google_sync_state(client_id, "Synchronisé", resource_name=resource)
                        google_created += 1
                    else:
                        set_google_sync_state(client_id, "Erreur", error="Google n'a renvoyé aucun identifiant.")
                        google_errors += 1
                except Exception as e:
                    set_google_sync_state(client_id, "Erreur", error=str(e))
                    google_errors += 1

    if pending_path:
        try:
            pending_path.unlink()
        except OSError:
            pass
    session.pop("proton_import_token", None)

    audit_event(
        "PROTON_IMPORT_DONE",
        f"created={created_local}; merged={merged_local}; google_linked={google_linked}; google_created={google_created}; google_ambiguous={google_ambiguous}",
        request.remote_addr
    )

    message = (
        f"Import Proton terminé : {created_local} nouveau(x) client(s), "
        f"{merged_local} fiche(s) locale(s) rapprochée(s)."
    )
    if local_ambiguous:
        message += f" {local_ambiguous} rapprochement(s) local(aux) ambigu(s) laissé(s) séparé(s)."
    if google_index is not None:
        message += (
            f" Google : {google_linked} contact(s) existant(s) rattaché(s), "
            f"{google_created} créé(s), {google_ambiguous} doublon(s) à vérifier"
        )
        if google_errors:
            message += f", {google_errors} erreur(s)"
        message += "."
    elif google_scan_error:
        message += f" Vérification Google impossible : {google_scan_error}"

    flash(message)
    return redirect(url_for("contacts_page"))


@app.route("/contacts/import-proton/cancel", methods=["POST"])
def import_proton_cancel():
    _, pending_path = load_pending_proton_import()
    if pending_path:
        try:
            pending_path.unlink()
        except OSError:
            pass
    session.pop("proton_import_token", None)
    flash("Import Proton annulé. Aucune donnée n'a été modifiée.")
    return redirect(url_for("contacts_page"))



@app.route("/recherche")
def global_search():
    """Recherche globale WOPR : multi-mots, accents et ponctuation ignorés."""
    q = " ".join(str(request.args.get("q") or "").split()).strip()
    results = {"clients": [], "repairs": [], "ledger": [], "quotes": []}

    if q:
        normalized_q = normalize_global_search(q)
        tokens = [t for t in normalized_q.split() if t][:8]

        def build_where(expressions):
            # Chaque mot saisi doit apparaître quelque part dans l'élément.
            # Exemple : "benoit gaucher" peut matcher prénom + nom séparément.
            token_clauses = []
            params = []
            for token in tokens:
                token_clauses.append(
                    "(" + " OR ".join(f"WOPR_NORM({expr}) LIKE ?" for expr in expressions) + ")"
                )
                params.extend([f"%{token}%"] * len(expressions))
            return " AND ".join(token_clauses) if token_clauses else "1=0", params

        con = db()

        client_expr = [
            "COALESCE(name,'')",
            "COALESCE(first_name,'')",
            "COALESCE(last_name,'')",
            "COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')",
            "COALESCE(last_name,'') || ' ' || COALESCE(first_name,'')",
            "COALESCE(company,'')",
            "COALESCE(phone,'')",
            "COALESCE(email,'')",
            "COALESCE(address_street,'')",
            "COALESCE(postal_code,'')",
            "COALESCE(city,'')",
        ]
        where, params = build_where(client_expr)
        results["clients"] = con.execute(f"""
            SELECT * FROM clients
            WHERE {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT 30
        """, params).fetchall()

        repair_expr = [
            "COALESCE(r.dossier_no,'')",
            "COALESCE(c.name,'')",
            "COALESCE(c.first_name,'')",
            "COALESCE(c.last_name,'')",
            "COALESCE(c.first_name,'') || ' ' || COALESCE(c.last_name,'')",
            "COALESCE(c.last_name,'') || ' ' || COALESCE(c.first_name,'')",
            "COALESCE(c.company,'')",
            "COALESCE(c.phone,'')",
            "COALESCE(c.email,'')",
            "COALESCE(r.device_type,'')",
            "COALESCE(r.brand_model,'')",
            "COALESCE(r.serial_no,'')",
            "COALESCE(r.system_name,'')",
            "COALESCE(r.problem,'')",
            "COALESCE(r.diagnosis,'')",
            "COALESCE(r.status,'')",
            "COALESCE(r.invoice_no,'')",
            "COALESCE(r.accessories,'')",
        ]
        where, params = build_where(repair_expr)
        results["repairs"] = con.execute(f"""
            SELECT r.*, c.name AS client_name, c.first_name AS client_first_name,
                   c.last_name AS client_last_name, c.phone AS client_phone
            FROM repairs r
            JOIN clients c ON c.id=r.client_id
            WHERE {where}
            ORDER BY r.received_date DESC, r.id DESC
            LIMIT 50
        """, params).fetchall()

        ledger_expr = [
            "COALESCE(party,'')",
            "COALESCE(operation,'')",
            "COALESCE(entry_date,'')",
            "COALESCE(description,'')",
            "COALESCE(invoice_no,'')",
            "COALESCE(remarks,'')",
            "COALESCE(document_original_name,'')",
            "printf('%.2f',COALESCE(amount_ttc,0))",
        ]
        where, params = build_where(ledger_expr)
        results["ledger"] = con.execute(f"""
            SELECT * FROM ledger_entries
            WHERE {where}
            ORDER BY entry_date DESC, id DESC
            LIMIT 50
        """, params).fetchall()

        quote_expr = [
            "COALESCE(q.quote_no,'')",
            "COALESCE(q.client_name,'')",
            "COALESCE(q.client_company,'')",
            "COALESCE(q.contact_name,'')",
            "COALESCE(q.status,'')",
            "COALESCE(q.notes,'')",
            "COALESCE(ql.description,'')",
        ]
        where, params = build_where(quote_expr)
        results["quotes"] = con.execute(f"""
            SELECT DISTINCT q.*
            FROM quotes q
            LEFT JOIN quote_lines ql ON ql.quote_id=q.id
            WHERE {where}
            ORDER BY q.quote_date DESC, q.id DESC
            LIMIT 30
        """, params).fetchall()

        con.close()

    total = sum(len(v) for v in results.values())
    return render_template("global_search.html", q=q, results=results, total=total)


@app.route("/contacts/<int:client_id>/historique")
def client_history(client_id):
    """Historique client complet : lecture seule, accès direct aux dossiers/devis."""
    con = db()
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        con.close()
        return "Client introuvable", 404
    repairs = con.execute("""
        SELECT * FROM repairs WHERE client_id=?
        ORDER BY received_date DESC, id DESC
    """, (client_id,)).fetchall()
    # Les devis historiques peuvent ne pas avoir de client_id (anciens imports).
    # On les rattache uniquement si le nom correspond sans ambiguïté à ce client.
    def _client_name_keys(row):
        keys = set()
        values = [
            row["name"],
            row["company"],
            f"{row['first_name'] or ''} {row['last_name'] or ''}",
            f"{row['last_name'] or ''} {row['first_name'] or ''}",
        ]
        for value in values:
            key = normalize_history_name(value)
            if key:
                keys.add(key)
        return keys

    client_keys = _client_name_keys(client)

    # On construit l'index des noms de tous les clients pour éviter tout rattachement
    # automatique lorsqu'un même nom peut désigner plusieurs fiches.
    key_owners = {}
    for c in con.execute("SELECT * FROM clients").fetchall():
        for key in _client_name_keys(c):
            key_owners.setdefault(key, set()).add(int(c["id"]))

    legacy_quotes = con.execute("""
        SELECT * FROM quotes
        WHERE client_id IS NULL
        ORDER BY quote_date DESC, id DESC
    """).fetchall()

    linked_quote_ids = []
    for q in legacy_quotes:
        qkey = normalize_history_name(q["client_name"])
        if not qkey or qkey not in client_keys:
            continue
        owners = key_owners.get(qkey, set())
        if owners == {int(client_id)}:
            con.execute("UPDATE quotes SET client_id=?, updated_at=? WHERE id=? AND client_id IS NULL",
                        (client_id, now().isoformat(timespec="seconds"), q["id"]))
            linked_quote_ids.append(int(q["id"]))

    if linked_quote_ids:
        con.commit()

    quotes = con.execute("""
        SELECT * FROM quotes WHERE client_id=?
        ORDER BY quote_date DESC, id DESC
    """, (client_id,)).fetchall()
    con.close()
    total_billed = sum(float(r["service_amount"] or 0) + float(r["goods_amount"] or 0) for r in repairs)
    total_paid = sum(
        float(r["accounting_service_amount"] or 0) + float(r["accounting_goods_amount"] or 0)
        for r in repairs if int(r["paid"] or 0) == 1
    )
    unpaid_total = sum(
        float(r["service_amount"] or 0) + float(r["goods_amount"] or 0)
        for r in repairs if int(r["paid"] or 0) == 0 and (float(r["service_amount"] or 0) + float(r["goods_amount"] or 0)) > 0
    )
    active_statuses = {"Reçu", "Diagnostic", "En attente accord", "En attente pièce", "En réparation", "Terminé"}
    active_repairs = [r for r in repairs if str(r["status"] or "") in active_statuses]
    to_return = [r for r in repairs if str(r["status"] or "") == "Terminé"]

    invoice_repairs = [r for r in repairs if str(r["invoice_no"] or "").strip()]
    invoice_numbers = []
    seen_invoice_numbers = set()
    for r in invoice_repairs:
        no = str(r["invoice_no"] or "").strip()
        if no and no not in seen_invoice_numbers:
            seen_invoice_numbers.add(no)
            invoice_numbers.append(no)

    def _repair_activity_date(row):
        # La dernière interaction réelle est plus utile qu'une simple date d'entrée.
        for key in ("returned_at", "finished_at", "received_date", "created_at"):
            value = str(row[key] or "").strip()
            if value:
                return value[:10]
        return ""

    last_repair = max(repairs, key=_repair_activity_date) if repairs else None
    last_intervention_date = _repair_activity_date(last_repair) if last_repair else None
    last_invoice = invoice_repairs[0] if invoice_repairs else None
    last_quote = quotes[0] if quotes else None

    return render_template(
        "client_history.html",
        client=client,
        repairs=repairs,
        quotes=quotes,
        total_billed=total_billed,
        total_paid=total_paid,
        unpaid_total=unpaid_total,
        active_repairs=active_repairs,
        to_return=to_return,
        invoice_count=len(invoice_numbers),
        last_repair=last_repair,
        last_intervention_date=last_intervention_date,
        last_invoice=last_invoice,
        last_quote=last_quote,
    )




@app.route("/achats-ventes/vente/<int:entry_id>/facture")
def achats_ventes_sale_invoice_view(entry_id):
    """Ouvre le vrai PDF de vente client sans fabriquer un nom ni dépendre d'un RID ambigu."""
    con = db()
    row = con.execute("SELECT * FROM ledger_entries WHERE id=?", (entry_id,)).fetchone()
    con.close()
    if not row:
        return "Ligne introuvable", 404
    if (row["operation"] or "").casefold() != "vente":
        return "Cette ligne n'est pas une vente", 400
    invoice_no = str(row["invoice_no"] or "").strip()
    if not invoice_no:
        return "Aucun numéro de facture", 404

    canonical_invoice_no = canonical_client_invoice_no(invoice_no)
    pdf = find_client_invoice_pdf(canonical_invoice_no, row["party"] or "")
    if pdf and pdf.exists():
        return send_file(pdf, mimetype="application/pdf", as_attachment=False, download_name=pdf.name)

    # Fallback : s'il n'existe aucun PDF historique classé, on retombe sur la facture WOPR.
    con = db()
    members = con.execute("""
        SELECT r.id, c.name AS client_name, r.legacy_imported
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE trim(COALESCE(r.invoice_no,'')) IN (?, ?)
        ORDER BY r.id DESC
    """, (invoice_no, canonical_invoice_no)).fetchall()
    con.close()
    party_key = normalize_client_filename_name(row["party"] or "")
    best = None
    best_score = -1
    for member in members:
        ck = normalize_client_filename_name(member["client_name"] or "")
        sc = 100 if ck and ck == party_key else (50 if ck and party_key and (ck in party_key or party_key in ck) else 0)
        if sc > best_score:
            best, best_score = member, sc
    if best:
        return redirect(url_for("invoice_pdf", rid=int(best["id"])))
    return "Facture client introuvable", 404


@app.route("/achats-ventes/controle-justificatifs")
def supplier_documents_audit():
    """Contrôle non destructif : ne crée, ne déplace, ne renomme et ne supprime aucun fichier."""
    con = db()
    rows = con.execute("""
        SELECT * FROM ledger_entries
        WHERE lower(COALESCE(operation,''))='achat'
          AND COALESCE(document_path,'')<>''
        ORDER BY entry_date DESC, id DESC
    """).fetchall()
    con.close()
    ok_rows, broken_rows = [], []
    for row in rows:
        path = ledger_document_file(row)
        (ok_rows if path and path.is_file() else broken_rows).append(row)
    return render_template("supplier_documents_audit.html", ok_rows=ok_rows, broken_rows=broken_rows,
                           linked_count=len(rows))


@app.route("/contacts")
def contacts_page():
    q = " ".join(request.args.get("q", "").split()).strip()
    show_archived = str(request.args.get("archived") or "").strip().lower() in {"1", "true", "yes", "oui"}
    archive_clause = "COALESCE(archived,0)=1" if show_archived else "COALESCE(archived,0)=0"
    con = db()

    if q:
        like = f"%{q}%"
        clients = con.execute(f"""
            SELECT * FROM clients
            WHERE {archive_clause}
              AND (
                   COALESCE(last_name,'') LIKE ? COLLATE NOCASE
                OR COALESCE(first_name,'') LIKE ? COLLATE NOCASE
                OR COALESCE(name,'') LIKE ? COLLATE NOCASE
                OR COALESCE(company,'') LIKE ? COLLATE NOCASE
                OR COALESCE(phone,'') LIKE ? COLLATE NOCASE
                OR COALESCE(email,'') LIKE ? COLLATE NOCASE
                OR COALESCE(address_street,'') LIKE ? COLLATE NOCASE
                OR COALESCE(postal_code,'') LIKE ? COLLATE NOCASE
                OR COALESCE(city,'') LIKE ? COLLATE NOCASE
                OR COALESCE(notes,'') LIKE ? COLLATE NOCASE
              )
            ORDER BY
                COALESCE(first_name,'') COLLATE NOCASE,
                COALESCE(NULLIF(last_name,''), name) COLLATE NOCASE,
                id
        """, (like, like, like, like, like, like, like, like, like, like)).fetchall()
    else:
        clients = con.execute(f"""
            SELECT * FROM clients
            WHERE {archive_clause}
            ORDER BY
                COALESCE(first_name,'') COLLATE NOCASE,
                COALESCE(NULLIF(last_name,''), name) COLLATE NOCASE,
                id
        """).fetchall()

    total_clients = con.execute(
        f"SELECT COUNT(*) FROM clients WHERE {archive_clause}"
    ).fetchone()[0]
    archived_clients_count = con.execute(
        "SELECT COUNT(*) FROM clients WHERE COALESCE(archived,0)=1"
    ).fetchone()[0]

    # Résumé Google des clients actifs uniquement.
    google_sync_stats = con.execute("""
        SELECT
            SUM(CASE WHEN google_sync_status='Synchronisé' THEN 1 ELSE 0 END) AS synced,
            SUM(CASE WHEN google_sync_status='Erreur' THEN 1 ELSE 0 END) AS errors,
            SUM(CASE
                    WHEN COALESCE(google_sync_status,'') NOT IN ('Synchronisé','Erreur')
                    THEN 1 ELSE 0
                END) AS pending
        FROM clients
        WHERE COALESCE(archived,0)=0
    """).fetchone()
    google_synced_count = int(google_sync_stats["synced"] or 0)
    google_pending_count = int(google_sync_stats["pending"] or 0)
    google_error_count = int(google_sync_stats["errors"] or 0)

    safe_duplicate_groups = len(find_safe_local_duplicate_groups(con))
    con.close()

    connected = google_credentials() is not None
    return render_template(
        "contacts.html",
        clients=clients,
        q=q,
        total_clients=total_clients,
        google_connected=connected,
        google_client_secret=GOOGLE_CLIENT_SECRET.exists(),
        google_libs_ok=GOOGLE_LIBS_OK,
        safe_duplicate_groups=safe_duplicate_groups,
        show_archived=show_archived,
        archived_clients_count=archived_clients_count,
        google_synced_count=google_synced_count,
        google_pending_count=google_pending_count,
        google_error_count=google_error_count,
        business_name=str(cfg().get("business_name") or "WOPR").strip() or "WOPR",
        google_contact_group=str(
            cfg().get("google_contact_group")
            or cfg().get("business_name")
            or "WOPR"
        ).strip() or "WOPR",
    )




@app.route("/contacts/merge-safe-duplicates", methods=["POST"])
def contacts_merge_safe_duplicates():
    result = merge_safe_local_duplicates()
    audit_event(
        "CLIENT_SAFE_DEDUP",
        (
            f"{result['merged_clients']} fiches fusionnées; "
            f"{result['moved_repairs']} réparations déplacées; "
            f"{result['moved_quotes']} devis déplacés"
        ),
        request.remote_addr
    )

    if result["merged_clients"]:
        flash(
            f"Doublons sûrs : {result['merged_clients']} fiche(s) fusionnée(s), "
            f"{result['moved_repairs']} réparation(s) et "
            f"{result['moved_quotes']} devis rattaché(s)."
        )
    else:
        flash("Aucun doublon sûr à fusionner.")
    return redirect(url_for("contacts_page"))




@app.route("/contacts/<int:client_id>/merge", methods=["GET", "POST"])
def client_merge(client_id):
    con = db()
    source = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not source:
        con.close()
        return "Client introuvable", 404

    if request.method == "POST":
        try:
            target_id = int(request.form.get("target_id", "0"))
        except ValueError:
            target_id = 0

        if not target_id or target_id == client_id:
            con.close()
            flash("Choisis une autre fiche client à conserver.")
            return redirect(url_for("client_merge", client_id=client_id))

        target = con.execute("SELECT * FROM clients WHERE id=?", (target_id,)).fetchone()
        if not target:
            con.close()
            flash("La fiche client à conserver est introuvable.")
            return redirect(url_for("client_merge", client_id=client_id))

        if request.form.get("confirm_merge") != "FUSIONNER":
            con.close()
            flash("Fusion annulée : confirmation invalide.")
            return redirect(url_for("client_merge", client_id=client_id))

        backup_database(force=True, tag="avant_fusion_manuelle_clients")
        result = _merge_manual_local_client(con, target_id, client_id)
        if not result["merged"]:
            con.close()
            flash("Fusion impossible.")
            return redirect(url_for("client_merge", client_id=client_id))

        con.commit()
        con.close()

        audit_event(
            "CLIENT_MANUAL_MERGE",
            (
                f"source_client_id={client_id}; master_client_id={target_id}; "
                f"repairs={result['repairs']}; quotes={result['quotes']}"
            ),
            request.remote_addr
        )
        flash(
            f"Fusion terminée : {result['repairs']} suivi(s)/facture(s) et "
            f"{result['quotes']} devis rattaché(s) à la fiche conservée."
        )

        return_q = request.form.get("return_q", "").strip()
        target_url = url_for("contacts_page", q=return_q or None)
        return redirect(target_url + f"#client-{target_id}")

    source_dict = dict(source)
    source_sigs = _contact_name_signature(
        source_dict.get("first_name"),
        source_dict.get("last_name"),
        source_dict.get("name"),
        ""
    )

    rows = [dict(x) for x in con.execute("""
        SELECT * FROM clients
        WHERE id<>? AND COALESCE(archived,0)=0
        ORDER BY COALESCE(NULLIF(last_name,''), name) COLLATE NOCASE,
                 COALESCE(first_name,'') COLLATE NOCASE,
                 id
    """, (client_id,)).fetchall()]

    candidates = []
    for row in rows:
        sigs = _contact_name_signature(
            row.get("first_name"), row.get("last_name"), row.get("name"), ""
        )
        exact_name = bool(source_sigs & sigs)
        repairs_count = con.execute(
            "SELECT COUNT(*) FROM repairs WHERE client_id=?", (row["id"],)
        ).fetchone()[0]
        quotes_count = con.execute(
            "SELECT COUNT(*) FROM quotes WHERE client_id=?", (row["id"],)
        ).fetchone()[0]
        candidates.append({
            "client": row,
            "exact_name": exact_name,
            "repairs_count": int(repairs_count or 0),
            "quotes_count": int(quotes_count or 0),
        })

    source_repairs = con.execute(
        "SELECT COUNT(*) FROM repairs WHERE client_id=?", (client_id,)
    ).fetchone()[0]
    source_quotes = con.execute(
        "SELECT COUNT(*) FROM quotes WHERE client_id=?", (client_id,)
    ).fetchone()[0]
    con.close()

    # Les correspondances de nom exact passent en premier.
    candidates.sort(
        key=lambda x: (
            0 if x["exact_name"] else 1,
            str(x["client"].get("last_name") or x["client"].get("name") or "").casefold(),
            str(x["client"].get("first_name") or "").casefold(),
            int(x["client"]["id"])
        )
    )

    return render_template(
        "client_merge.html",
        source=source,
        candidates=candidates,
        source_repairs=int(source_repairs or 0),
        source_quotes=int(source_quotes or 0),
        q=request.args.get("q", "").strip(),
    )


@app.route("/contacts/<int:client_id>/edit", methods=["GET", "POST"])
def client_edit(client_id):
    con = db()
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        con.close()
        return "Client introuvable", 404

    if request.method == "POST":
        last_name = request.form.get("last_name", "").strip()
        first_name = request.form.get("first_name", "").strip()
        company = request.form.get("company", "").strip()
        # Une fiche peut représenter soit une personne, soit une entreprise.
        # Pour une entreprise pure, prénom/nom sont facultatifs : le nom affiché
        # et historique reprend alors la raison sociale saisie dans `company`.
        name = compose_client_name(last_name, first_name) or company
        address_street = request.form.get("address_street", "").strip()
        postal_code = request.form.get("postal_code", "").strip()
        city = request.form.get("city", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        notes = request.form.get("notes", "").strip()

        if not name:
            flash("Le nom du client est obligatoire.")
            con.close()
            return render_template("client_edit.html", client=client)

        address = "\n".join(
            x for x in [address_street, (postal_code + " " + city).strip()] if x
        )

        con.execute("""
            UPDATE clients
            SET name=?, last_name=?, first_name=?, company=?,
                address=?, address_street=?, postal_code=?, city=?,
                phone=?, email=?, notes=?, updated_at=?,
                google_sync_status='À synchroniser', google_sync_error=''
            WHERE id=?
        """, (
            name, last_name, first_name, company,
            address, address_street, postal_code, city,
            phone, email, notes, now().isoformat(timespec="seconds"), client_id
        ))
        con.commit()
        con.close()

        # V2.3.215 : aucune écriture Google automatique.
        # La fiche reste "À synchroniser" jusqu'au bouton WOPR → Google.
        flash("Client modifié. Google n'a pas été modifié automatiquement.")

        # Revenir exactement dans le contexte de la liste d'où vient la modification :
        # recherche éventuelle + archives éventuelles + ligne du client.
        return_q = request.form.get("return_q", "").strip()
        return_archived = request.form.get("return_archived", "") == "1"
        if return_archived:
            target = url_for("contacts_page", q=return_q or None, archived=1)
        else:
            target = url_for("contacts_page", q=return_q or None)
        return redirect(target + f"#client-{client_id}")

    con.close()
    return render_template("client_edit.html", client=client)


@app.route("/contacts/<int:client_id>/delete", methods=["GET", "POST"])
def client_delete(client_id):
    con = db()
    client = con.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        con.close()
        return "Client introuvable", 404

    stats = con.execute("""
        SELECT COUNT(*) AS repairs_count,
               SUM(CASE WHEN invoice_no IS NOT NULL AND trim(invoice_no)<>'' THEN 1 ELSE 0 END) AS invoices_count
        FROM repairs WHERE client_id=?
    """, (client_id,)).fetchone()
    quotes_count = con.execute(
        "SELECT COUNT(*) FROM quotes WHERE client_id=?",
        (client_id,)
    ).fetchone()[0]

    repairs_count = int(stats["repairs_count"] or 0)
    invoices_count = int(stats["invoices_count"] or 0)
    quotes_count = int(quotes_count or 0)
    has_history = bool(repairs_count or invoices_count or quotes_count)
    is_archived = int(client["archived"] or 0) == 1

    if request.method == "POST":
        action = request.form.get("action", "").strip()

        # Restauration d'une fiche archivée.
        if is_archived and action == "restore":
            con.execute("""
                UPDATE clients
                SET archived=0, archived_at=NULL,
                    google_sync_status='À synchroniser',
                    google_sync_error='',
                    updated_at=?
                WHERE id=?
            """, (now().isoformat(timespec="seconds"), client_id))
            con.commit()
            con.close()
            audit_event("CLIENT_RESTORE", f"client_id={client_id}", request.remote_addr)
            flash(f"Client « {client['name']} » restauré.")
            return redirect(url_for("contacts_page"))

        confirm = request.form.get("confirm_delete") == "yes"
        if not confirm:
            con.close()
            flash("Opération annulée : confirmation manquante.")
            return redirect(url_for("contacts_page"))

        backup_database(force=True, tag="avant_archivage_suppression_client")

        # Suppression TOTALE volontaire : réservée aux fiches de test / erreurs.
        # Cette action efface le client ET tout l'historique WOPR associé.
        if action == "delete_all":
            if request.form.get("confirm_delete_all") != "SUPPRIMER":
                con.close()
                flash("Suppression totale annulée : confirmation invalide.")
                return redirect(url_for("contacts_page"))

            google_warning = ""
            if request.form.get("delete_google") == "on" and client["google_resource_name"]:
                try:
                    service = google_service()
                    if service:
                        service.people().deleteContact(
                            resourceName=client["google_resource_name"]
                        ).execute()
                    else:
                        google_warning = " Contact Google non supprimé : Google n'est pas connecté."
                except HttpError as exc:
                    if getattr(exc.resp, "status", None) != 404:
                        google_warning = f" Contact Google non supprimé : {exc}"
                except Exception as exc:
                    google_warning = f" Contact Google non supprimé : {exc}"

            repairs = con.execute("""
                SELECT id, signature_path
                FROM repairs
                WHERE client_id=?
            """, (client_id,)).fetchall()
            repair_ids = [int(row["id"]) for row in repairs]

            quotes = con.execute("""
                SELECT id
                FROM quotes
                WHERE client_id=?
            """, (client_id,)).fetchall()
            quote_ids = [int(row["id"]) for row in quotes]

            if repair_ids:
                placeholders = ",".join("?" for _ in repair_ids)
                con.execute(
                    f"DELETE FROM invoice_lines WHERE repair_id IN ({placeholders})",
                    repair_ids
                )
                con.execute(
                    f"DELETE FROM repair_status_history WHERE repair_id IN ({placeholders})",
                    repair_ids
                )
                con.execute(
                    f"DELETE FROM repairs WHERE id IN ({placeholders})",
                    repair_ids
                )

            if quote_ids:
                placeholders = ",".join("?" for _ in quote_ids)
                con.execute(
                    f"DELETE FROM quote_documents WHERE quote_id IN ({placeholders})",
                    quote_ids
                )
                con.execute(
                    f"DELETE FROM quote_lines WHERE quote_id IN ({placeholders})",
                    quote_ids
                )
                con.execute(
                    f"DELETE FROM quotes WHERE id IN ({placeholders})",
                    quote_ids
                )

            con.execute("DELETE FROM clients WHERE id=?", (client_id,))
            con.commit()
            con.close()

            # Nettoyage des signatures locales rattachées aux suivis supprimés.
            for repair in repairs:
                path = repair["signature_path"]
                if path:
                    try:
                        p = resolve_signature_path(path)
                        if p and p.exists() and p.resolve().parent == SIGNATURES.resolve():
                            p.unlink()
                    except Exception:
                        pass

            audit_event(
                "CLIENT_DELETE_ALL",
                (
                    f"client_id={client_id}; repairs={len(repair_ids)}; "
                    f"invoices={invoices_count}; quotes={len(quote_ids)}"
                ),
                request.remote_addr
            )
            flash(
                f"Client « {client['name']} » supprimé définitivement avec tout son historique."
                f"{google_warning}"
            )
            return redirect(url_for("contacts_page"))

        # Si le client possède un historique, on l'archive et on ne touche
        # ni aux réparations, ni aux factures, ni aux devis.
        if has_history:
            google_warning = ""
            google_deleted = False

            if request.form.get("delete_google") == "on" and client["google_resource_name"]:
                try:
                    service = google_service()
                    if service:
                        service.people().deleteContact(
                            resourceName=client["google_resource_name"]
                        ).execute()
                        google_deleted = True
                    else:
                        google_warning = " Contact Google non supprimé : Google n'est pas connecté."
                except HttpError as exc:
                    if getattr(exc.resp, "status", None) == 404:
                        # Déjà absent de Google : résultat équivalent à une suppression réussie.
                        google_deleted = True
                    else:
                        google_warning = f" Contact Google non supprimé : {exc}"
                except Exception as exc:
                    google_warning = f" Contact Google non supprimé : {exc}"

            stamp = now().isoformat(timespec="seconds")
            if google_deleted:
                con.execute("""
                    UPDATE clients
                    SET archived=1, archived_at=?,
                        google_resource_name=NULL,
                        google_sync_hash=NULL,
                        google_sync_status='Archivé',
                        google_sync_error='',
                        google_synced_at=?,
                        updated_at=?
                    WHERE id=?
                """, (stamp, stamp, stamp, client_id))
            else:
                con.execute("""
                    UPDATE clients
                    SET archived=1, archived_at=?,
                        google_sync_status='Archivé',
                        updated_at=?
                    WHERE id=?
                """, (stamp, stamp, client_id))

            con.commit()
            con.close()
            audit_event(
                "CLIENT_ARCHIVE",
                f"client_id={client_id}; repairs={repairs_count}; invoices={invoices_count}; quotes={quotes_count}",
                request.remote_addr
            )
            flash(
                f"Client « {client['name']} » archivé. "
                f"Ses {repairs_count} suivi(s), {invoices_count} facture(s) et {quotes_count} devis sont conservés."
                f"{google_warning} Pour voir les archives : /contacts?archived=1"
            )
            return redirect(url_for("contacts_page"))

        # Aucun historique : vraie suppression autorisée.
        google_warning = ""
        if request.form.get("delete_google") == "on" and client["google_resource_name"]:
            try:
                service = google_service()
                if service:
                    service.people().deleteContact(
                        resourceName=client["google_resource_name"]
                    ).execute()
                else:
                    google_warning = " Contact Google non supprimé : Google n'est pas connecté."
            except HttpError as exc:
                if getattr(exc.resp, "status", None) != 404:
                    google_warning = f" Contact Google non supprimé : {exc}"
            except Exception as exc:
                google_warning = f" Contact Google non supprimé : {exc}"

        con.execute("DELETE FROM clients WHERE id=?", (client_id,))
        con.commit()
        con.close()
        audit_event("CLIENT_DELETE", f"client_id={client_id}; no_history=1", request.remote_addr)
        flash(f"Client « {client['name']} » supprimé.{google_warning}")
        return redirect(url_for("contacts_page"))

    con.close()
    return render_template(
        "client_delete.html",
        client=client,
        repairs_count=repairs_count,
        invoices_count=invoices_count,
        quotes_count=quotes_count,
        has_history=has_history,
        is_archived=is_archived,
        google_connected=google_credentials() is not None,
    )


@app.route("/google/credentials", methods=["POST"])
def google_credentials_upload():
    if not GOOGLE_LIBS_OK:
        flash("Les bibliothèques Google ne sont pas installées. Relance pip install -r requirements.txt.")
        return redirect(url_for("contacts_page"))
    f = request.files.get("credentials")
    if not f or not f.filename:
        flash("Choisis le fichier JSON OAuth téléchargé depuis Google Cloud.")
        return redirect(url_for("contacts_page"))
    try:
        raw = f.read().decode("utf-8")
        parsed = json.loads(raw)
        if not (parsed.get("installed") or parsed.get("web")):
            raise ValueError("JSON OAuth Google invalide")
        GOOGLE_CLIENT_SECRET.write_text(raw, encoding="utf-8")
        flash("Clé Google enregistrée. Clique maintenant sur Connecter Google.")
    except Exception as e:
        flash(f"Fichier Google invalide : {e}")
    return redirect(url_for("contacts_page"))


GOOGLE_OAUTH_REDIRECT_URI = "http://127.0.0.1:5000/google/callback"


@app.route("/google/connect")
def google_connect():
    if not GOOGLE_LIBS_OK:
        flash("Bibliothèques Google manquantes. Relance pip install -r requirements.txt.")
        return redirect(url_for("contacts_page"))
    if not GOOGLE_CLIENT_SECRET.exists():
        flash("Ajoute d'abord le fichier JSON OAuth Google.")
        return redirect(url_for("contacts_page"))

    flow = Flow.from_client_secrets_file(
        str(GOOGLE_CLIENT_SECRET),
        scopes=GOOGLE_SCOPE,
        redirect_uri=GOOGLE_OAUTH_REDIRECT_URI,
        autogenerate_code_verifier=True
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )

    # PKCE : le même code_verifier doit impérativement être réutilisé
    # au callback pour échanger le code d'autorisation contre le token.
    session["google_oauth_state"] = state
    session["google_oauth_code_verifier"] = flow.code_verifier
    return redirect(auth_url)


@app.route("/google/callback")
def google_callback():
    if not GOOGLE_CLIENT_SECRET.exists():
        return redirect(url_for("contacts_page"))

    state = session.get("google_oauth_state")
    code_verifier = session.get("google_oauth_code_verifier")

    if not code_verifier:
        flash("Session OAuth expirée ou incomplète. Clique à nouveau sur Connecter Google Contacts.")
        return redirect(url_for("contacts_page"))

    flow = Flow.from_client_secrets_file(
        str(GOOGLE_CLIENT_SECRET),
        scopes=GOOGLE_SCOPE,
        state=state,
        redirect_uri=GOOGLE_OAUTH_REDIRECT_URI,
        code_verifier=code_verifier,
        autogenerate_code_verifier=False
    )

    try:
        # Google renvoie ?code=...&state=... sur notre callback local HTTP.
        # Ne pas transmettre l'URL HTTP à OAuthlib : on lui donne uniquement
        # le code d'autorisation, puis l'échange du jeton se fait vers
        # l'endpoint HTTPS de Google.
        error = request.args.get("error")
        if error:
            raise RuntimeError(f"Google a refusé l'autorisation : {error}")

        returned_state = request.args.get("state")
        if state and returned_state and returned_state != state:
            raise RuntimeError("État OAuth invalide. Relance la connexion Google.")

        code = request.args.get("code")
        if not code:
            raise RuntimeError("Google n'a renvoyé aucun code d'autorisation.")

        flow.fetch_token(code=code)
        GOOGLE_TOKEN.write_text(flow.credentials.to_json(), encoding="utf-8")

        session.pop("google_oauth_state", None)
        session.pop("google_oauth_code_verifier", None)

        service = google_service()
        group = google_find_group(service) if service else None
        if group:
            flash("Google Contacts connecté : groupe configuré trouvé, synchro automatique activée.")
        else:
            flash("Google connecté, mais le groupe configuré n'a pas été trouvé.")
    except Exception as e:
        flash(f"Connexion Google impossible : {e}")

    return redirect(url_for("contacts_page"))


@app.route("/google/disconnect", methods=["POST"])
def google_disconnect():
    if GOOGLE_TOKEN.exists():
        GOOGLE_TOKEN.unlink()
    flash("Google Contacts déconnecté de WOPR.")
    return redirect(url_for("contacts_page"))


def import_google_group_to_wopr():
    """Google -> WOPR, non destructif.

    Seuls les contacts du groupe Google configuré sont considérés.
    Les fiches WOPR existantes sont uniquement complétées : aucune valeur locale
    existante n'est remplacée. Les contacts Google sans correspondance locale
    sont créés dans WOPR.
    """
    service = google_service()
    if not service:
        return False, "Google n'est pas connecté"

    group_resource = google_find_group(service)
    if not group_resource:
        return False, "Le groupe Google configuré est introuvable"

    token = None
    people = []
    while True:
        result = google_execute_with_retry(service.people().connections().list(
            resourceName="people/me",
            pageSize=1000,
            pageToken=token,
            personFields="names,emailAddresses,phoneNumbers,addresses,organizations,biographies,memberships"
        ))
        for person in result.get("connections", []):
            groups = {
                (m.get("contactGroupMembership") or {}).get("contactGroupResourceName")
                for m in person.get("memberships", [])
            }
            if group_resource in groups:
                people.append(person)
        token = result.get("nextPageToken")
        if not token:
            break

    con = db()
    created = enriched = skipped = 0

    for person in people:
        resource = (person.get("resourceName") or "").strip()
        names = person.get("names", [])
        name0 = names[0] if names else {}
        first_name = (name0.get("givenName") or "").strip()
        last_name = (name0.get("familyName") or "").strip()
        display_name = (name0.get("displayName") or "").strip()

        emails = [(x.get("value") or "").strip() for x in person.get("emailAddresses", []) if (x.get("value") or "").strip()]
        phones = [(x.get("value") or "").strip() for x in person.get("phoneNumbers", []) if (x.get("value") or "").strip()]
        addresses = person.get("addresses", [])
        organizations = person.get("organizations", [])
        biographies = person.get("biographies", [])

        email = emails[0] if emails else ""
        phone = phones[0] if phones else ""
        adr = addresses[0] if addresses else {}
        street = (adr.get("streetAddress") or "").strip()
        postal = (adr.get("postalCode") or "").strip()
        city = (adr.get("city") or "").strip()
        company = ((organizations[0].get("name") if organizations else "") or "").strip()
        notes = ((biographies[0].get("value") if biographies else "") or "").strip()

        local = None
        if resource:
            local = con.execute(
                "SELECT * FROM clients WHERE google_resource_name=? LIMIT 1",
                (resource,)
            ).fetchone()

        if local is None and email:
            rows = con.execute(
                "SELECT * FROM clients WHERE lower(trim(COALESCE(email,'')))=?",
                (email.casefold(),)
            ).fetchall()
            if len(rows) == 1:
                local = rows[0]

        if local is None and phone:
            wanted_phone = normalize_phone(phone)
            rows = con.execute(
                "SELECT * FROM clients WHERE trim(COALESCE(phone,''))<>''"
            ).fetchall()
            matches = [r for r in rows if normalize_phone(r["phone"]) == wanted_phone]
            if len(matches) == 1:
                local = matches[0]

        composed = compose_client_name(last_name, first_name) or display_name or company or "Contact Google"
        address = "\n".join(x for x in [street, " ".join(x for x in [postal, city] if x).strip()] if x)
        stamp = now().isoformat(timespec="seconds")

        if local is None:
            con.execute("""
                INSERT INTO clients(
                    name,last_name,first_name,company,
                    address,address_street,postal_code,city,
                    phone,email,notes,
                    google_resource_name,google_sync_status,google_sync_error,
                    google_synced_at,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                composed,last_name,first_name,company,
                address,street,postal,city,
                phone,email,notes,
                resource,"Synchronisé","",stamp,stamp,stamp
            ))
            created += 1
            continue

        sets = []
        vals = []
        changed = False

        candidates = {
            "first_name": first_name,
            "last_name": last_name,
            "company": company,
            "address_street": street,
            "postal_code": postal,
            "city": city,
            "phone": phone,
            "email": email,
            "notes": notes,
        }

        for field, value in candidates.items():
            if value and not str(local[field] or "").strip():
                sets.append(f"{field}=?")
                vals.append(value)
                changed = True

        if not str(local["name"] or "").strip() and composed:
            sets.append("name=?")
            vals.append(composed)
            changed = True

        if not str(local["address"] or "").strip() and address:
            sets.append("address=?")
            vals.append(address)
            changed = True

        sets += [
            "google_resource_name=?",
            "google_sync_status=?",
            "google_sync_error=?",
            "google_synced_at=?",
            "updated_at=?"
        ]
        vals += [resource, "Synchronisé", "", stamp, stamp, local["id"]]

        con.execute(f"UPDATE clients SET {', '.join(sets)} WHERE id=?", vals)
        if changed:
            enriched += 1
        else:
            skipped += 1

    con.commit()
    con.close()
    return True, f"Google → WOPR : {created} créé(s), {enriched} complété(s), {skipped} déjà à jour."


@app.route("/contacts/import-google-live", methods=["POST"])
def contacts_import_google_live():
    ok, msg = import_google_group_to_wopr()
    flash(msg if ok else f"Erreur Google : {msg}")
    return redirect(url_for("contacts_page"))


# V2.3.228 — état de la synchro Google en arrière-plan.
_google_sync_progress = {
    "running": False,
    "total": 0,
    "done": 0,
    "ok": 0,
    "errors": 0,
    "finished_at": None,
}
_google_sync_progress_lock = threading.Lock()


@app.route("/contacts/sync-google/status")
def contacts_sync_google_status():
    with _google_sync_progress_lock:
        return jsonify(dict(_google_sync_progress))


@app.route("/contacts/sync-google", methods=["POST"])
def contacts_sync_google():
    con = db()
    ids = [r[0] for r in con.execute("""
        SELECT id
        FROM clients
        WHERE COALESCE(archived,0)=0
          AND COALESCE(google_sync_status, '') != 'Synchronisé'
        ORDER BY id
    """).fetchall()]
    con.close()

    if not ids:
        flash("Google : aucun contact en attente de synchronisation.")
        return redirect(url_for("contacts_page"))

    with _google_sync_progress_lock:
        _google_sync_progress.update({
            "running": True,
            "total": len(ids),
            "done": 0,
            "ok": 0,
            "errors": 0,
            "finished_at": None,
        })

    def _bulk_worker(contact_ids):
        ok_count = 0
        error_count = 0

        for cid in contact_ids:
            try:
                ok, _msg = sync_client_to_google(cid)
                if ok:
                    ok_count += 1
                else:
                    error_count += 1
            except Exception as exc:
                error_count += 1
                try:
                    set_google_sync_state(cid, "Erreur", error=str(exc))
                except Exception:
                    pass

            with _google_sync_progress_lock:
                _google_sync_progress["done"] = ok_count + error_count
                _google_sync_progress["ok"] = ok_count
                _google_sync_progress["errors"] = error_count

            time.sleep(1.0)

        with _google_sync_progress_lock:
            _google_sync_progress["running"] = False
            _google_sync_progress["done"] = len(contact_ids)
            _google_sync_progress["ok"] = ok_count
            _google_sync_progress["errors"] = error_count
            _google_sync_progress["finished_at"] = now().isoformat(timespec="seconds")

    threading.Thread(
        target=_bulk_worker,
        args=(ids,),
        name="wopr-google-bulk-sync",
        daemon=True,
    ).start()

    flash(f"Google : synchronisation de {len(ids)} contact(s) lancée en arrière-plan.")
    return redirect(url_for("contacts_page", sync_watch=1))


@app.route("/contacts/<int:client_id>/sync-google", methods=["POST"])
def contact_sync_google(client_id):
    ok, msg = sync_client_to_google(client_id)
    flash("Contact Google synchronisé." if ok else f"Erreur Google : {msg}")
    return redirect(url_for("contacts_page"))


@app.route("/contacts/export/google.csv")
def export_google_contacts():
    con=db(); clients=con.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall(); con.close()
    rows=[["First Name","Email 1 - Label","Email 1 - Value","Phone 1 - Label","Phone 1 - Value",
           "Address 1 - Label","Address 1 - Street","Address 1 - City","Address 1 - Postal Code","Address 1 - Country","Labels","Notes"]]
    for c in clients:
        rows.append([c["name"],"Home",c["email"] or "","Mobile",c["phone"] or "","Home",
                     c["address_street"] or "",c["city"] or "",c["postal_code"] or "","France",str(cfg().get("google_contact_group") or cfg().get("business_name") or "WOPR"),c["notes"] or ""])
    return csv_response("FoulFix_Contacts_Google.csv", rows)


@app.route("/contacts/export/proton.csv")
def export_proton_contacts():
    con=db(); clients=con.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall(); con.close()
    rows=[["first name","email","mobile","address 1","postal code","city","country","group membership","notes"]]
    for c in clients:
        rows.append([c["name"],c["email"] or "",c["phone"] or "",c["address_street"] or "",
                     c["postal_code"] or "",c["city"] or "","France",str(cfg().get("google_contact_group") or cfg().get("business_name") or "WOPR"),c["notes"] or ""])
    return csv_response("FoulFix_Contacts_Proton.csv", rows)


@app.route("/contacts/export/all.vcf")
def export_vcard_contacts():
    con=db(); clients=con.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall(); con.close()
    cards=[]
    for c in clients:
        lines=["BEGIN:VCARD","VERSION:3.0",f"FN:{vcard_escape(c['name'])}",f"N:;{vcard_escape(c['name'])};;;" ]
        if c["email"]: lines.append(f"EMAIL;TYPE=INTERNET:{vcard_escape(c['email'])}")
        if c["phone"]: lines.append(f"TEL;TYPE=CELL:{vcard_escape(c['phone'])}")
        street=c["address_street"] or ""
        if street or c["city"] or c["postal_code"]:
            lines.append(f"ADR;TYPE=HOME:;;{vcard_escape(street)};{vcard_escape(c['city'])};;{vcard_escape(c['postal_code'])};France")
        lines.append("CATEGORIES:" + str(cfg().get("google_contact_group") or cfg().get("business_name") or "WOPR"))
        if c["notes"]:
            lines.append(f"NOTE:{vcard_escape(c['notes'])}")
        lines.append("END:VCARD")
        cards.append("\r\n".join(lines))
    data="\r\n".join(cards)+"\r\n"
    return Response(data, mimetype="text/vcard; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="FoulFix_Contacts.vcf"'})

@app.route("/export/suivi.csv")
def export_suivi():
    con = db()
    rows = con.execute("""
        SELECT c.name client, r.received_date date, r.problem panne, r.invoice_no,
               r.service_amount, r.goods_amount, r.payment_method, r.payment_mode,
               r.sent_via, r.remarks, r.status, r.service_description, r.goods_description
        FROM repairs r JOIN clients c ON c.id=r.client_id
        ORDER BY r.received_date, r.id
    """).fetchall()
    con.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Client","Date","Panne","Désignation prestation","Pièce / marchandise","Facture/devis N°","Prestations de services BIC",
                     "Vente de marchandises BIC","Total","Mode","Remise / Envoi","Remarques","Statut"])
    for x in rows:
        writer.writerow([x["client"],x["date"],x["panne"], x["service_description"] or "", x["goods_description"] or "", x["invoice_no"] or "",
                         f'{x["service_amount"]:.2f}',f'{x["goods_amount"]:.2f}',
                         f"{float(x['service_amount'] or 0)+float(x['goods_amount'] or 0):.2f}",
                         x["payment_mode"] or x["payment_method"] or "",
                         x["sent_via"] or "",x["remarks"] or "",x["status"]])
    data = output.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=Suivi_Reparations.csv"})

@app.route("/export/ventes.csv")
def export_ventes():
    con = db()
    rows = con.execute("""
        SELECT c.name client, r.finished_at, r.service_description, r.goods_description,
               r.tests_validation, r.problem, r.service_amount, r.goods_amount,
               r.payment_method, r.invoice_no
        FROM repairs r JOIN clients c ON c.id=r.client_id
        WHERE r.finished_at IS NOT NULL
        ORDER BY r.finished_at
    """).fetchall()
    con.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Opération","Fournisseur / client","Date","Articles et Quantité",
                     "Règlement TTC","Type","Facture N°"])
    for x in rows:
        total = (x["service_amount"] or 0) + (x["goods_amount"] or 0)
        items = " / ".join([
            y for y in [
                x["service_description"] or x["tests_validation"] or x["problem"],
                x["goods_description"]
            ] if y
        ])
        writer.writerow(["Vente", x["client"], (x["finished_at"] or "")[:10],
                         items, f"{total:.2f}", x["payment_method"] or "", x["invoice_no"] or ""])
    data = output.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=Achats_Ventes_Ventes.csv"})

if __name__ == "__main__":
    # Utilisé par les scripts d'arrêt : le serveur est déjà terminé, on capture
    # donc le dernier état SQLite entièrement validé de la session.
    if "--backup-arret" in sys.argv:
        try:
            path = backup_database(
                force=False,
                tag="arret",
                only_if_changed=True
            )
            if path:
                verify_tmp = DB.parent / f".wopr_cli_verify_{secrets.token_hex(4)}.db"
                try:
                    _extract_backup_to_sqlite(path, verify_tmp)
                finally:
                    verify_tmp.unlink(missing_ok=True)
                print(str(path))
            else:
                # Le launcher sait interpréter ce marqueur : aucune nouvelle
                # sauvegarde n'est nécessaire car la base n'a pas changé.
                print("UNCHANGED")
            raise SystemExit(0)
        except Exception as exc:
            print(f"ERREUR BACKUP ARRET: {exc}", file=sys.stderr)
            raise SystemExit(1)

    backup_database(force=False, tag="demarrage")
    init_db()
    harden_local_permissions()
    print("WOPR : http://127.0.0.1:5000")
    print("Signature téléphone : http://%s:5000" % local_ip())
    print("Mode sécurité : actif — debug désactivé")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
