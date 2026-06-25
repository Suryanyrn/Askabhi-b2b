import os
import polib
from deep_translator import GoogleTranslator

LOCALE_DIR = r"d:\askabhi\b2b\b2b\locale"

# Language mappings from Django locale to deep-translator code
LANG_MAP = {
    'hi': 'hi', 'bn': 'bn', 'te': 'te', 'mr': 'mr', 'ta': 'ta', 
    'ur': 'ur', 'gu': 'gu', 'kn': 'kn', 'or': 'or', 'ml': 'ml', 
    'pa': 'pa', 'de': 'de', 'fr': 'fr', 'es': 'es', 'tr': 'tr', 
    'zh_Hans': 'zh-CN',
}

STRINGS_TO_TRANSLATE = [
    # Dashboard
    "Welcome", "Logout", "DISPATCHED", "New Delivery Assignment", "IN TRANSIT", 
    "GPS Active", "Delivery in Progress", "Order", "Client", "Destination Address", 
    "Start Delivery", "Click to enable GPS tracking and notify the client.", 
    "Mark as Delivered", "You must be within 50 meters of the destination to mark delivered.", 
    "No Active Shipments", "You currently have no pending deliveries. Sit tight!", 
    "Proof of Delivery", "Please capture an image of the client signature or warehouse seal to verify delivery.", 
    "Cancel", "Upload & Complete",
    
    # Login
    "Driver App", "Sign in to view your delivery assignments", "Phone Number", 
    "Enter your phone number", "Password", "Enter your password", "Sign In", 
    "Mobile Number", "Enter registered mobile no.", "Password (Sent via SMS)", 
    "Enter your temporary password", "Login to Dashboard",
    
    # Base/Sidebar
    "Dashboard - B2B Tracking Portal", "Dashboard", "Orders", "Previous Orders", 
    "Shipments", "Managers", "Drivers", "Audit Logs", "Inventory Logs", "Clients", 
    "Warehouse", "Products", "Edit Profile", "Change Password"
]

def create_translations():
    os.makedirs(LOCALE_DIR, exist_ok=True)
    
    for lang_dir, lang_code in LANG_MAP.items():
        lang_path = os.path.join(LOCALE_DIR, lang_dir, 'LC_MESSAGES')
        os.makedirs(lang_path, exist_ok=True)
        po_path = os.path.join(lang_path, 'django.po')
        mo_path = os.path.join(lang_path, 'django.mo')
        
        print(f"Generating translations for {lang_dir} ({lang_code})...")
        po = polib.POFile()
        po.metadata = {
            'Project-Id-Version': '1.0',
            'Report-Msgid-Bugs-To': 'askabhi@example.com',
            'POT-Creation-Date': '2026-06-24 15:00+0530',
            'PO-Revision-Date': '2026-06-24 15:00+0530',
            'Last-Translator': 'Auto Translator',
            'Language': lang_dir,
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Transfer-Encoding': '8bit',
        }
        
        translator = GoogleTranslator(source='en', target=lang_code)
        
        for text in set(STRINGS_TO_TRANSLATE):
            try:
                translation = translator.translate(text)
                entry = polib.POEntry(msgid=text, msgstr=translation)
                po.append(entry)
            except Exception as e:
                print(f"  Error translating '{text}': {e}")
                entry = polib.POEntry(msgid=text, msgstr=text)
                po.append(entry)
                
        po.save(po_path)
        po.save_as_mofile(mo_path)
        print(f"  Saved {po_path} and {mo_path}")

if __name__ == '__main__':
    create_translations()
