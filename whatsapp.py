import requests
import os
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("WHATSAPP_TOKEN")         # Token de acceso de Meta
PHONE_ID = 876156402242406 # ID del número de WhatsApp Business

GRAPH_URL = f"https://graph.facebook.com/v17.0/876156402242406/messages"

def reply_whatsapp(to: str, body: str):
   
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": body},
    }
    r = requests.post(GRAPH_URL, headers=headers, json=payload)
    print("📤 Texto enviado:", r.status_code, r.text)
    return r

def enviar_botones(to: str, pregunta: str):
  
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": pregunta},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": "disco", "title": "🛒 Disco"}
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "tienda_inglesa", "title": "🛍 Tienda Inglesa"}
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "listar", "title": "📋 Listar productos"}
                    }
                ]
            }
        },
    }
    r = requests.post(GRAPH_URL, headers=headers, json=payload)
    print("📤 Botones enviados:", r.status_code, r.text)
    return r
