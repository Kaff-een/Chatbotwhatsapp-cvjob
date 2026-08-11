import os
import io
import httpx
import asyncio
from collections import deque
from fastapi import FastAPI, Request, Response, BackgroundTasks
from dotenv import load_dotenv

from chatbot_graph import process_candidate_message
import db
from pypdf import PdfReader

load_dotenv(override=True)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
WHATSAPP_API_URL = f"{GRAPH_API_BASE}/{PHONE_NUMBER_ID}/messages"

app = FastAPI()

# Structures pour stocker une fenêtre glissante des IDs de messages traités récemment afin d'éviter les doublons
processed_messages_queue = deque(maxlen=1000)
processed_messages_set = set()



# ============================================================
# 1. Vérification du webhook (Meta)
# ============================================================
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


# ============================================================
# 2. Réception des messages entrants
# ============================================================
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    print("Payload reçu:", data)

    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]["value"]

        if "messages" not in changes:
            return {"status": "ignored"}

        message = changes["messages"][0]
        from_number = message["from"]
        msg_type = message["type"]
        message_id = message.get("id")

        # Déduplication des messages avec fenêtre glissante pour éviter les traitements en double
        if message_id:
            if message_id in processed_messages_set:
                print(f"[DEDUPLICATE] Message déjà reçu ou en cours: {message_id}")
                return {"status": "already_processed"}
            
            if len(processed_messages_queue) >= 1000:
                oldest = processed_messages_queue.popleft()
                processed_messages_set.discard(oldest)
                
            processed_messages_queue.append(message_id)
            processed_messages_set.add(message_id)

        contacts = changes.get("contacts", [])
        contact_name = contacts[0].get("profile", {}).get("name") if contacts else None

        candidate = db.get_or_create_candidate(from_number, contact_name)

        if msg_type == "interactive":
            background_tasks.add_task(handle_interactive_reply, message, candidate)
            return {"status": "received"}

        if not candidate.get("preferred_language"):
            background_tasks.add_task(send_language_selection, from_number)
            return {"status": "awaiting_language"}

        # Lancement en tâche de fond pour répondre immédiatement HTTP 200 à Meta (timeout de 3s)
        background_tasks.add_task(process_inbound_message, message, candidate, msg_type)

    except (KeyError, IndexError) as e:
        print("Erreur parsing payload:", e)

    return {"status": "received"}


async def process_inbound_message(message: dict, candidate: dict, msg_type: str):
    try:
        if msg_type == "document":
            await handle_document_message(message, candidate)
        elif msg_type == "text":
            await handle_text_message(message, candidate)
        elif msg_type in ("audio", "voice"):
            await handle_audio_message(message, candidate)
        else:
            print(f"Type de message non géré: {msg_type}")
            return

        # Après traitement par l'agent, on dispatch toute notification en attente
        await dispatch_pending_notifications()
    except Exception as e:
        print("Erreur dans process_inbound_message:", e)



# ============================================================
# 3. Sélection de la langue (premier contact)
# ============================================================
async def send_language_selection(to: str):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Bienvenue sur cvjob.org 👋 / Welcome / مرحبا\nChoisissez votre langue / Choose your language / اختر لغتك"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "lang_fr", "title": "Français"}},
                    {"type": "reply", "reply": {"id": "lang_en", "title": "English"}},
                    {"type": "reply", "reply": {"id": "lang_ar", "title": "العربية"}},
                ]
            },
        },
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
        print("Sélection langue envoyée:", r.status_code, r.text)


async def handle_interactive_reply(message: dict, candidate: dict):
    button_id = message["interactive"]["button_reply"]["id"]
    lang_map = {"lang_fr": "fr", "lang_en": "en", "lang_ar": "ar"}
    language = lang_map.get(button_id)

    if language:
        db.set_candidate_language(candidate["phone_number"], language)
        confirmations = {
            "fr": "Langue définie sur Français ✅\nEnvoyez-moi votre CV (PDF) ou décrivez le poste/stage que vous recherchez.",
            "en": "Language set to English ✅\nSend me your CV (PDF) or describe the job/internship you're looking for.",
            "ar": "تم تعيين اللغة إلى العربية ✅\nأرسل لي سيرتك الذاتية (PDF) أو صف الوظيفة أو التدريب الذي تبحث عنه.",
        }
        await send_whatsapp_text(candidate["phone_number"], confirmations[language])


# ============================================================
# 4. Traitement d'un CV (document PDF)
# ============================================================
async def handle_document_message(message: dict, candidate: dict):
    doc = message["document"]
    media_id = doc["id"]
    filename = doc.get("filename", "cv.pdf")

    if doc.get("mime_type") != "application/pdf":
        await send_whatsapp_text(
            candidate["phone_number"],
            "Merci d'envoyer votre CV au format PDF 🙏"
            if candidate["preferred_language"] == "fr"
            else "Please send your CV as a PDF file 🙏",
        )
        return

    pdf_bytes = await download_whatsapp_media(media_id)
    cv_text = extract_pdf_text(pdf_bytes)

    request_id = db.create_request(
        candidate_id=candidate["id"], input_type="document", cv_filename=filename, cv_extracted_text=cv_text,
    )
    db.log_message(candidate["id"], request_id, "candidate", f"[CV reçu: {filename}]")

    result = await asyncio.to_thread(
        process_candidate_message,
        phone_number=candidate["phone_number"],
        input_type="document",
        cv_text=cv_text,
        candidate_name=candidate.get("full_name"),
        preferred_language=candidate.get("preferred_language", "fr"),
        request_id=request_id,
    )

    await finalize_response(candidate, request_id, result)


# ============================================================
# 5. Traitement d'un message texte
# ============================================================
async def handle_text_message(message: dict, candidate: dict):
    text_body = message.get("text", {}).get("body", "")

    request_id = db.create_request(candidate_id=candidate["id"], input_type="text", raw_text=text_body)
    db.log_message(candidate["id"], request_id, "candidate", text_body)

    result = await asyncio.to_thread(
        process_candidate_message,
        phone_number=candidate["phone_number"],
        input_type="text",
        raw_text=text_body,
        candidate_name=candidate.get("full_name"),
        preferred_language=candidate.get("preferred_language", "fr"),
        request_id=request_id,
    )

    await finalize_response(candidate, request_id, result)


# ============================================================
# 5b. Traitement d'un message audio (vocal)
# ============================================================
async def handle_audio_message(message: dict, candidate: dict):
    # Log de la requête dans la base de données
    request_id = db.create_request(
        candidate_id=candidate["id"], 
        input_type="audio", 
        raw_text="[Message vocal reçu]"
    )
    db.log_message(candidate["id"], request_id, "candidate", "[Message vocal reçu]")
    
    # Message à envoyer selon la langue préférée du candidat
    lang = candidate.get("preferred_language", "fr")
    
    audio_responses = {
        "fr": "Je ne peux pas encore écouter les messages vocaux. Merci de m'écrire votre demande par texte ou de m'envoyer votre CV au format PDF. ✍️",
        "en": "I cannot listen to voice messages yet. Please write your request in a text message or send your CV as a PDF file. ✍️",
        "ar": "لا يمكنني الاستماع إلى الرسائل الصوتية بعد. يرجى كتابة طلبك في رسالة نصية أو إرسال سيرتك الذاتية بصيغة PDF. ✍️"
    }
    
    reply_text = audio_responses.get(lang, audio_responses["fr"])
    
    # Simulation du dictionnaire résultat pour finalize_response
    result = {
        "reply": reply_text,
        "status": "resolved",
        "detected_domain": None,
        "detected_skills": None,
        "recommended_link": None
    }
    
    await finalize_response(candidate, request_id, result)


# ============================================================
# 6. Finalisation commune
# ============================================================
async def finalize_response(candidate: dict, request_id: int, result: dict):
    db.update_request_result(
        request_id=request_id,
        detected_domain=result.get("detected_domain"),
        detected_skills=result.get("detected_skills"),
        recommended_link=result.get("recommended_link"),
        status=result["status"],
    )
    db.log_message(candidate["id"], request_id, "bot", result["reply"])

    await send_whatsapp_text(candidate["phone_number"], result["reply"])


async def dispatch_pending_notifications():
    """Envoie les notifications décidées de façon autonome par l'Escalation Agent (table `notifications`)."""
    for notif in db.get_unsent_notifications():
        await send_whatsapp_text(notif["recipient_phone"], notif["message"])
        db.mark_notification_sent(notif["id"])


# ============================================================
# 7. Utilitaires WhatsApp
# ============================================================
async def send_whatsapp_text(to: str, message: str):
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": message}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(WHATSAPP_API_URL, headers=headers, json=payload)
            print("Réponse envoyée:", r.status_code, r.text)
        except httpx.TimeoutException as e:
            print(f"⚠️ Timeout lors de l'envoi du message à {to}: {e}")


async def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    # Timeout augmenté : le téléchargement de fichiers PDF peut prendre du temps
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Étape 1 : récupérer l'URL du média
        print(f"[MEDIA] Récupération URL pour media_id={media_id}...")
        meta_resp = await client.get(f"{GRAPH_API_BASE}/{media_id}", headers=headers)
        media_url = meta_resp.json()["url"]
        print(f"[MEDIA] Téléchargement du fichier...")

        # Étape 2 : télécharger le fichier avec retry
        for attempt in range(3):
            try:
                file_resp = await client.get(media_url, headers=headers)
                print(f"[MEDIA] Fichier téléchargé ({len(file_resp.content)} bytes)")
                return file_resp.content
            except httpx.TimeoutException:
                print(f"[MEDIA] ⚠️ Timeout tentative {attempt + 1}/3, retry...")
                if attempt == 2:
                    raise
        return b""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        print("Erreur extraction PDF:", e)
        return ""
