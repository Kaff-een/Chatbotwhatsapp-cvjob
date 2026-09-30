import os
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

TO_NUMBER = "xxxxx" 

# URL officielle Meta affichée sur ton écran (v25.0)
URL = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/messages"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

# Le payload exact demandé par Meta pour le test d'intégration
payload = {
    "messaging_product": "whatsapp",
    "to": TO_NUMBER,
    "type": "template",
    "template": {
        "name": "3p_direct_integration_test_template",
        "language": { "code": "en_US" }
    }
}

print("Envoi du template d'intégration...")
response = httpx.post(URL, headers=headers, json=payload)

print("Statut de la réponse :", response.status_code)
print("Contenu :", response.text)
