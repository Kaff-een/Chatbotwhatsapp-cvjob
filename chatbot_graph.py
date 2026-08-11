"""
chatbot_graph.py (v6) — NLU + RAG CV + anti-hallucination sur les résultats de recherche
--------------------------------------------------------------------
Corrections apportées sur la v5 :
  1. Classification d'intention déplacée dans un vrai NODE (plus de mutation
     fragile de state dans une fonction de routage conditionnel).
  2. Le Search Agent ne peut plus halluciner de fausses offres (faux noms
     d'entreprise, fausses descriptions) : le message final présenté au
     candidat est construit à partir du VRAI lien retourné par l'outil,
     jamais généré librement par le LLM après l'appel d'outil.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)
from typing import TypedDict, Annotated, Optional, Literal

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages, RemoveMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import InMemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage

import db
from tools import SEARCH_AGENT_TOOLS, ESCALATION_AGENT_TOOLS

# ============================================================
# 1. LLM (configurable via OLLAMA_MODEL)
# ============================================================
model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
print(f"[LLM] Chargement du modèle : {model_name}")
llm = ChatOllama(model=model_name, temperature=0)


# ============================================================
# 2. ETAT PARTAGÉ
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    phone_number: str
    candidate_name: Optional[str]
    preferred_language: str
    input_type: str
    status: str
    escalation_reason: Optional[str]
    detected_intent: Optional[str]
    request_id: Optional[int]


# ============================================================
# 3. FILTRAGE ET PURGE DU CONTEXTE DE MESSAGES (LLM CLEANUP)
# ============================================================
def filter_clean_recent_messages(messages: list, max_messages: int = 8) -> list:
    """
    Filtre et purge l'historique de messages pour le LLM :
    1. Supprime les ToolMessage (résultats d'outils bruts / URL techniques passés).
    2. Supprime les AIMessage purement techniques ne contenant que des tool_calls.
    3. Ne conserve que les messages conversationnels propres (HumanMessage et AIMessage textuels).
    4. Fenêtre glissante : conserve uniquement les max_messages les plus récents.
    """
    clean_msgs = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            continue
        if isinstance(msg, AIMessage):
            has_tool_calls = bool(getattr(msg, "tool_calls", None))
            has_text = bool(msg.content and str(msg.content).strip())
            if has_tool_calls and not has_text:
                continue
        clean_msgs.append(msg)
    return clean_msgs[-max_messages:]


# ============================================================
# 4. BOUCLE D'APPEL D'OUTILS GÉNÉRIQUE (mini "ReAct" manuel)
# ============================================================
def run_tool_calling_agent(system_prompt: str, tools: list, messages: list, max_iterations: int = 4, stop_tools: tuple = (), context: Optional[dict] = None):
    """
    stop_tools : tuple de noms d'outils qui, une fois appelés avec succès, arrêtent
    immédiatement la boucle (protection contre les modèles locaux qui répètent un
    appel d'outil au lieu de conclure).
    """
    tools_by_name = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    working_messages = [SystemMessage(content=system_prompt)] + list(messages)
    new_messages = []
    tool_calls_made = []

    for _ in range(max_iterations):
        response = llm_with_tools.invoke(working_messages)
        working_messages.append(response)
        new_messages.append(response)

        if not getattr(response, "tool_calls", None):
            break

        stop_triggered = False
        for call in response.tool_calls:
            tool_fn = tools_by_name.get(call["name"])
            if not tool_fn:
                result = f"Erreur: outil '{call['name']}' inconnu."
            else:
                try:
                    args = dict(call["args"])
                    if context and "request_id" in context:
                        import inspect
                        sig = inspect.signature(tool_fn.func if hasattr(tool_fn, 'func') else tool_fn)
                        if "request_id" in sig.parameters:
                            args["request_id"] = context["request_id"]
                    result = tool_fn.invoke(args)
                except Exception as e:
                    result = f"Erreur lors de l'exécution de l'outil: {e}"

            tool_calls_made.append((call["name"], result))
            tool_msg = ToolMessage(content=str(result), tool_call_id=call["id"], name=call["name"])
            working_messages.append(tool_msg)
            new_messages.append(tool_msg)

            if call["name"] in stop_tools and "introuvable" not in str(result) and "Erreur" not in str(result):
                stop_triggered = True

        if stop_triggered:
            break

    return new_messages, tool_calls_made


# ============================================================
# 4. NODE — CLASSIFICATION D'INTENTION (NLU)
# ============================================================
ROUTING_PROMPT = """Tu es un classificateur d'intention NLU expert pour le chatbot WhatsApp de cvjob.org (plateforme de recherche d'emploi et de stage).
Analyse sémantiquement le dernier message et classe-le dans l'une des catégories suivantes :

- "GREETING" : Salutations (ex: "bonjour", "salut", "salam", "hello").
- "THANKS" : Remerciements (ex: "merci", "choukran", "thanks").
- "SEARCH" : Recherche d'emploi/stage, ou question liée à son profil/CV (ex: "je cherche un job", "logistique").
- "ABOUT" : Question sur le fonctionnement du service (ex: "c'est quoi cvjob ?").
- "ESCALATE" : Demande EXPLICITE de parler à un humain/conseiller.
- "UNKNOWN" : Message trop vague ou incompréhensible.

Réponds UNIQUEMENT avec un JSON valide : {{"intent": "GREETING|THANKS|SEARCH|ABOUT|ESCALATE|UNKNOWN"}}

Message à classer : "{last_message}"
Historique récent :
{history}
"""


def classify_intent_node(state: AgentState) -> AgentState:
    if state["input_type"] == "document":
        print("[CLASSIFY] Document reçu -> DOCUMENT")
        return {"detected_intent": "DOCUMENT"}

    last_message = state["messages"][-1].content if state["messages"] else ""
    lower_msg = last_message.lower().strip()

    if lower_msg in ["bonjour", "salut", "salam", "hi", "hello", "hey"]:
        print("[CLASSIFY] Heuristique -> GREETING")
        return {"detected_intent": "GREETING"}
    if lower_msg in ["merci", "thanks", "choukran", "shukran", "شكرا"]:
        print("[CLASSIFY] Heuristique -> THANKS")
        return {"detected_intent": "THANKS"}

    # Routage sémantique NLU via le LLM (mots-clés rigides supprimés pour éviter les faux déclenchements)
    clean_history = filter_clean_recent_messages(state["messages"][:-1], max_messages=5)
    history_text = "\n".join(
        f"{'Candidat' if isinstance(m, HumanMessage) else 'Bot'}: {m.content}"
        for m in clean_history
    )
    prompt = ROUTING_PROMPT.format(last_message=last_message, history=history_text)

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw = response.content.strip().replace("```json", "").replace("```", "").strip()
        intent = json.loads(raw).get("intent", "UNKNOWN")
        print(f"[CLASSIFY] NLU Intent détecté: {intent}")
    except Exception as e:
        print(f"[CLASSIFY] ⚠️ Erreur NLU: {e}. Fallback UNKNOWN.")
        intent = "UNKNOWN"

    return {"detected_intent": intent}


def route_by_intent(state: AgentState) -> Literal["cv_agent", "search_agent", "clarify", "escalation_agent"]:
    intent = state.get("detected_intent")
    if intent == "DOCUMENT":
        return "cv_agent"
    if intent == "ESCALATE":
        return "escalation_agent"
    if intent == "SEARCH":
        return "search_agent"
    return "clarify"


# ============================================================
# 5. NODE — CV AGENT
# ============================================================
CV_ANALYSIS_PROMPT = """Tu es un assistant RH expert en analyse de CV.
Analyse le texte de CV fourni et extrais les informations suivantes de manière structurée :

1. Nom complet, 2. Domaine professionnel principal, 3. Compétences clés,
4. Niveau d'expérience, 5. Formation, 6. Localisation si mentionnée,
7. Type de poste recherché si mentionné (emploi, stage, alternance).

Si le texte est illisible ou trop court, dis-le clairement.

Texte du CV :
\"\"\"
{cv_text}
\"\"\"
"""


def cv_agent_node(state: AgentState) -> AgentState:
    print("[CV_AGENT] Début analyse CV...")
    cv_text = state["messages"][-1].content
    prompt = CV_ANALYSIS_PROMPT.format(cv_text=cv_text[:6000])
    response = llm.invoke([HumanMessage(content=prompt)])
    print(f"[CV_AGENT] Analyse terminée: {response.content.strip()[:200]}...")
    summary_message = AIMessage(content=f"[Analyse CV] {response.content.strip()}")
    return {"messages": [summary_message]}


# ============================================================
# 6. NODE — SEARCH AGENT
# ============================================================
SEARCH_SYSTEM_PROMPT = """Tu es un assistant de recherche d'emploi et de stage pour cvjob.org, sur WhatsApp.
Utilise les outils disponibles (search_job_offers, search_internship_offers) pour construire un lien de recherche pertinent.

RÈGLES STRICTES POUR LES PARAMÈTRES D'OUTIL :
- Le paramètre "keyword" doit contenir UNIQUEMENT un mot-clé que l'utilisateur a EXPLICITEMENT mentionné dans son message actuel ou dans le contexte CV fourni. Si l'utilisateur dit simplement "je cherche un travail" sans préciser de domaine, passe keyword="" (vide).
- Le paramètre "location" doit contenir UNIQUEMENT une ville que l'utilisateur a EXPLICITEMENT mentionnée dans son message actuel. Ne JAMAIS inventer ou deviner une ville depuis le CV ou depuis les exemples de ce prompt. Si aucune ville n'est mentionnée par l'utilisateur, passe location="" (vide).
- Détermine EMPLOI vs STAGE : si l'utilisateur mentionne "stage", "stagiaire", "étudiant", "internship" → utilise search_internship_offers. Sinon → utilise search_job_offers.
- Simplifie les compétences techniques trop spécifiques (Data, IA, ML, DL, NLP, etc.) en mots-clés génériques adaptés aux domaines parents.
- Si une recherche précédente existe dans l'historique, gère l'AFFINEMENT en ajustant uniquement le paramètre que l'utilisateur demande de changer.

RÈGLE ABSOLUE ANTI-HALLUCINATION :
- Tu n'as accès à AUCUNE liste réelle d'offres, uniquement à un outil qui construit un LIEN de recherche filtré.
- Tu ne dois JAMAIS inventer de fausses offres (noms d'entreprise, descriptions de poste, durées, salaires).
- Appelle l'outil de recherche approprié UNE SEULE FOIS.
- Le message final présentant le lien au candidat sera généré séparément, donc ne rédige PAS de liste d'offres toi-même.

Langue de réponse : {language}
Nom du candidat (si connu) : {name}
"""



def build_search_reply(tool_calls, language, name, used_cv):
    for tool_name, result in reversed(tool_calls):
        if tool_name in ("search_job_offers", "search_internship_offers") and str(result).startswith("https://www.cvjob.org"):
            return result
    return None


def format_search_message(url: str, language: str, name: Optional[str], is_internship: bool) -> str:
    from urllib.parse import urlparse, parse_qs, unquote
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    
    keyword = params.get("search", [""])[0]
    location = params.get("location", [""])[0]
    
    keyword_display = unquote(keyword) if keyword else ""
    location_display = unquote(location) if location else ""
    
    offer_type = "stage" if is_internship else "emploi"
    
    greeting_name = name.strip() if (name and name.strip() and name.lower() != "inconnu") else ""
        
    if language == "fr":
        salutation = f"Bonjour {greeting_name} ! 😊" if greeting_name else "Bonjour ! 😊"
        desc = f"des offres de *{offer_type}*"
        if keyword_display:
            desc += f" dans le domaine *{keyword_display}*"
        if location_display:
            desc += f" à *{location_display}*"
        
        message = (
            f"{salutation}\n\n"
            f"J'ai recherché sur cvjob.org {desc} et j'ai trouvé des opportunités intéressantes pour votre profil ! 👋\n\n"
            f"👉 {url}\n\n"
            f"💡 *Conseil* : N'hésitez pas à utiliser les différents filtres disponibles sur le site (ville, type de contrat, niveau d'expérience, etc.) pour affiner davantage votre recherche.\n\n"
            f"Bonne chance dans vos recherches et à très vite ! 🚀"
        )
        
    elif language == "en":
        salutation = f"Hello {greeting_name}! 😊" if greeting_name else "Hello! 😊"
        offer_type_en = "internship" if is_internship else "job"
        desc = f"*{offer_type_en}* opportunities"
        if keyword_display:
            desc += f" in *{keyword_display}*"
        if location_display:
            desc += f" in *{location_display}*"
            
        message = (
            f"{salutation}\n\n"
            f"I searched on cvjob.org for {desc} and found some great options for you! 👋\n\n"
            f"👉 {url}\n\n"
            f"💡 *Tip*: Feel free to use the various filters available on the website (city, job type, experience level, etc.) to further refine your search.\n\n"
            f"Good luck with your search! 🚀"
        )
        
    else:  # Arabic
        salutation = f"مرحباً {greeting_name}! 😊" if greeting_name else "مرحباً! 😊"
        offer_type_ar = "تدريب" if is_internship else "عمل"
        desc = f"عروض *{offer_type_ar}*"
        if keyword_display:
            desc += f" في مجال *{keyword_display}*"
        if location_display:
            desc += f" في *{location_display}*"
            
        message = (
            f"{salutation}\n\n"
            f"لقد بحثت في cvjob.org عن {desc} ووجدت عروضاً ممتازة تناسب ملفك الشخصي! 👋\n\n"
            f"👉 {url}\n\n"
            f"💡 *تلميح*: يمكنك استخدام الفلاتر المختلفة المتاحة على الموقع (المدينة، نوع العقد، مستوى الخبرة، إلخ) لتصفية بحثك بشكل أدق.\n\n"
            f"بالتوفيق في بحثك! 🚀"
        )
        
    return message


def search_agent_node(state: AgentState) -> AgentState:
    phone_number = state["phone_number"]
    cv_context = ""
    used_cv = False
    candidate = db.get_candidate_by_phone(phone_number)
    
    candidate_name = state.get("candidate_name")
    if not candidate_name and candidate:
        candidate_name = candidate.get("full_name")
        
    if candidate:
        cv = db.get_latest_cv_by_candidate(candidate["id"])
        if cv:
            cv_context = f"\n\n[CONTEXTE CV CANDIDAT]\n{cv['cv_extracted_text'][:3500]}\n"
            used_cv = True

    system_prompt = SEARCH_SYSTEM_PROMPT.format(
        language=state.get("preferred_language", "fr"),
        name=candidate_name or "inconnu",
    ) + cv_context

    # Purge des artefacts d'outils et fenêtrage aux 8 derniers messages conversationnels propres
    clean_history = filter_clean_recent_messages(state["messages"], max_messages=8)

    new_messages, tool_calls = run_tool_calling_agent(
        system_prompt, SEARCH_AGENT_TOOLS, clean_history,
        stop_tools=["search_job_offers", "search_internship_offers"],
        context={"request_id": state.get("request_id")},
    )

    # Déterminer si un tool a été appelé et si c'est un stage
    url = None
    is_internship = False
    for tool_name, result in reversed(tool_calls):
        if tool_name in ("search_job_offers", "search_internship_offers") and str(result).startswith("https://www.cvjob.org"):
            url = result
            is_internship = (tool_name == "search_internship_offers")
            break

    if url:
        formatted_reply = format_search_message(
            url=url,
            language=state.get("preferred_language", "fr"),
            name=candidate_name,
            is_internship=is_internship
        )
        final_message = AIMessage(content=formatted_reply)
        return {"messages": new_messages + [final_message], "status": "resolved"}

    # Aucun tool de recherche n'a abouti -> on demande une précision, PAS d'invention
    fallback = {
        "fr": "Pour vous trouver les meilleures offres, précisez : cherchez-vous un emploi ou un stage, et dans quel domaine/ville ? 😊",
        "en": "To find the best matches, could you specify: job or internship, and which field/city? 😊",
        "ar": "لأجد لك أفضل العروض، حدد: هل تبحث عن عمل أم تدريب، وفي أي مجال/مدينة؟ 😊",
    }
    lang = state.get("preferred_language", "fr")
    return {"messages": new_messages + [AIMessage(content=fallback.get(lang, fallback["fr"]))], "status": "processing"}


# ============================================================
# 7. NODE — CLARIFY (NLU adaptive, sans tools)
# ============================================================
CLARIFY_PROMPT = """Tu es un assistant de recrutement WhatsApp extrêmement bienveillant, chaleureux, dynamique, humain et professionnel pour cvjob.org.
Le routeur NLU a classé le dernier message dans la catégorie "{intent}".

Règles de style pour WhatsApp :
- Sois très accueillant et utilise un ton encourageant et poli.
- Utilise des émojis de manière naturelle et engageante (👋, 😊, 🚀, etc.).
- Utilise la mise en forme WhatsApp (ex: *texte en gras* pour mettre en valeur les éléments clés).
- Personnalise la réponse si tu connais le nom du candidat.

Instructions de contenu par catégorie :
- "GREETING" : Salue le candidat chaleureusement, présente-toi comme son compagnon de recherche d'emploi/stage sur cvjob.org, et demande-lui comment tu peux l'aider aujourd'hui avec enthousiasme.
- "THANKS" : Réponds avec gratitude et joie, et propose de l'aider à trouver d'autres opportunités ou à affiner ses critères.
- "ABOUT" : Explique de manière dynamique et professionnelle que cvjob.org est la plateforme marocaine de référence pour décrocher facilement des emplois et stages. Présente brièvement les fonctionnalités clés (analyse de CV, alertes, etc.).
- "UNKNOWN" : Demande-lui gentiment de préciser son domaine professionnel et s'il recherche plutôt un emploi ou un stage pour que tu puisses l'orienter au mieux.

Ne dis JAMAIS qu'un RH ou conseiller va le contacter (sauf si on est dans le flux d'escalade).

Langue de réponse : {language}
Dernier message : "{last_message}"
"""


def clarify_node(state: AgentState) -> AgentState:
    last_message = state["messages"][-1].content if state["messages"] else ""
    intent = state.get("detected_intent") or "UNKNOWN"
    print(f"[CLARIFY] Intention: {intent}")

    prompt = CLARIFY_PROMPT.format(
        intent=intent,
        language=state.get("preferred_language", "fr"),
        last_message=last_message,
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"messages": [AIMessage(content=response.content.strip())], "status": "resolved"}


# ============================================================
# 8. NODE — ESCALATION AGENT (sur demande explicite uniquement)
# ============================================================
ESCALATION_SYSTEM_PROMPT = """Tu es un routeur d'escalade pour cvjob.org, PAS un rédacteur de message commercial.

Contexte : le candidat (numéro {phone_number}) a demandé explicitement à parler à un humain.
Raison technique : {reason}

Étapes STRICTES :
1. Appelle list_staff_contacts.
2. Appelle UNE SEULE FOIS send_message_to_contact avec le contact choisi, la raison, et le numéro du candidat.

Langue de la réponse finale au candidat : {language}
"""


def escalation_agent_node(state: AgentState) -> AgentState:
    print("[ESCALATION] Début processus d'escalade...")
    system_prompt = ESCALATION_SYSTEM_PROMPT.format(
        reason=state.get("escalation_reason") or "Le candidat souhaite parler à un conseiller.",
        phone_number=state["phone_number"],
        language=state.get("preferred_language", "fr"),
    )
    new_messages, _ = run_tool_calling_agent(
        system_prompt, ESCALATION_AGENT_TOOLS, state["messages"], stop_tools=("send_message_to_contact",),
        context={"request_id": state.get("request_id")},
    )

    reassurance = {
        "fr": "Merci pour votre message. Un membre de notre équipe va examiner votre demande et revient vers vous rapidement.",
        "en": "Thank you for your message. A member of our team will review your request and get back to you shortly.",
        "ar": "شكرا لرسالتك. سيقوم أحد أعضاء فريقنا بمراجعة طلبك والرد عليك قريبا.",
    }
    lang = state.get("preferred_language", "fr")
    return {"messages": new_messages + [AIMessage(content=reassurance.get(lang, reassurance["fr"]))], "status": "needs_human"}


# ============================================================
# 9. CONSTRUCTION DU GRAPHE
# ============================================================
_graph = StateGraph(AgentState)

_graph.add_node("classify_intent", classify_intent_node)
_graph.add_node("cv_agent", cv_agent_node)
_graph.add_node("search_agent", search_agent_node)
_graph.add_node("clarify", clarify_node)
_graph.add_node("escalation_agent", escalation_agent_node)

_graph.set_entry_point("classify_intent")

_graph.add_conditional_edges(
    "classify_intent",
    route_by_intent,
    {
        "cv_agent": "cv_agent",
        "search_agent": "search_agent",
        "clarify": "clarify",
        "escalation_agent": "escalation_agent",
    },
)

_graph.add_edge("cv_agent", "search_agent")
_graph.add_edge("search_agent", END)
_graph.add_edge("clarify", END)
_graph.add_edge("escalation_agent", END)

# ============================================================
# 10. CHECKPOINTER — mémoire persistante (Postgres ou In-Memory)
# ============================================================
_USE_IN_MEMORY = os.getenv("USE_IN_MEMORY_CHECKPOINTER", "true").lower() == "true"

if _USE_IN_MEMORY:
    print("[CHECKPOINTER] Utilisation de la mémoire locale (InMemorySaver).")
    _checkpointer = InMemorySaver()
else:
    print("[CHECKPOINTER] Utilisation de la base de données PostgreSQL (PostgresSaver).")
    _DATABASE_URL = os.getenv("DATABASE_URL")
    if not _DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquante dans les variables d'environnement.")

    import psycopg
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # Utilisation d'un pool de connexions pour éviter les plantages lors des timeouts de Supabase
    _pool = ConnectionPool(
        conninfo=_DATABASE_URL,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        }
    )
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()  # crée les tables LangGraph si elles n'existent pas

app_graph = _graph.compile(checkpointer=_checkpointer)


# ============================================================
# 10. FONCTION D'ENTREE PUBLIQUE
# ============================================================
def process_candidate_message(
    phone_number: str,
    input_type: str,
    raw_text: Optional[str] = None,
    cv_text: Optional[str] = None,
    candidate_name: Optional[str] = None,
    preferred_language: str = "fr",
    request_id: Optional[int] = None,
) -> dict:
    config = {"configurable": {"thread_id": phone_number}}

    content = cv_text if input_type == "document" else raw_text
    new_human_message = HumanMessage(content=content or "")

    # Vérifie si un checkpoint existe déjà pour ce thread (conversation en cours)
    existing_state = app_graph.get_state(config)

    if existing_state and existing_state.values:
        history_msgs = existing_state.values.get("messages", [])
        print(f"[DEBUG MEMORY] Thread existant pour {phone_number}. Nombre de messages dans l'historique : {len(history_msgs)}")
        
        # Purge physique de sécurité pour supprimer les vieux messages du checkpointer (Postgres/InMemory) via RemoveMessage
        if len(history_msgs) > 10:
            to_remove = [RemoveMessage(id=m.id) for m in history_msgs[:-6] if getattr(m, "id", None)]
            if to_remove:
                print(f"[DEBUG MEMORY] Purge physique via RemoveMessage de {len(to_remove)} vieux messages du checkpointer.")
                app_graph.update_state(config, {"messages": to_remove})
                existing_state = app_graph.get_state(config)
                history_msgs = existing_state.values.get("messages", [])
                print(f"[DEBUG MEMORY] Nouveau nombre de messages dans l'historique après purge : {len(history_msgs)}")

        # Thread existant → on injecte seulement le nouveau message + métadonnées mises à jour
        # sans écraser l'historique des messages précédents
        app_graph.update_state(
            config,
            {
                "messages": [new_human_message],
                "phone_number": phone_number,
                "candidate_name": candidate_name,
                "preferred_language": preferred_language,
                "input_type": input_type,
                "status": "processing",
                "escalation_reason": None,
                "detected_intent": None,
                "request_id": request_id,
            },
            as_node="__start__",
        )
        result = app_graph.invoke(None, config=config)
    else:
        print(f"[DEBUG MEMORY] Nouvelle conversation ou historique vide pour {phone_number}.")
        # Première interaction → on initialise l'état complet normalement
        result = app_graph.invoke(
            {
                "messages": [new_human_message],
                "phone_number": phone_number,
                "candidate_name": candidate_name,
                "preferred_language": preferred_language,
                "input_type": input_type,
                "status": "processing",
                "escalation_reason": None,
                "detected_intent": None,
                "request_id": request_id,
            },
            config=config,
        )

    final_reply = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            final_reply = msg.content
            break

    # Extraction intelligente des informations pour la DB
    import re
    from langchain_core.messages import ToolMessage
    recommended_link = None
    
    # Chercher un lien vers cvjob.org dans le message final ou l'historique
    for msg in reversed(result["messages"]):
        if msg.content:
            urls = re.findall(r'https?://[^\s()<>]+', msg.content)
            for url in urls:
                if "cvjob.org" in url:
                    recommended_link = url
                    break
            if recommended_link:
                break

    # Si aucun lien n'est trouvé dans le texte, chercher dans les messages d'outils
    if not recommended_link:
        for msg in reversed(result["messages"]):
            if isinstance(msg, ToolMessage) and msg.name in ("search_job_offers", "search_internship_offers"):
                if msg.content.startswith("https://www.cvjob.org"):
                    recommended_link = msg.content
                    break

    # Détection du domaine recherché depuis l'URL de recherche
    detected_domain = None
    if recommended_link:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(recommended_link)
        params = parse_qs(parsed_url.query)
        if "search" in params and params["search"]:
            detected_domain = params["search"][0]

    # Extraction des compétences clés depuis l'analyse de CV (si présente)
    detected_skills = []
    for msg in result["messages"]:
        if isinstance(msg, AIMessage) and msg.content.startswith("[Analyse CV]"):
            content = msg.content
            match = re.search(
                r'(?:Compétences clés|Compétences|Compétence)\s*[:\-]*\s*(.*?)(?:\n\d+\.|\n\n|\n[A-Z]|$)', 
                content, 
                re.IGNORECASE | re.DOTALL
            )
            if match:
                skills_str = match.group(1).strip()
                skills = [s.strip(" *-•") for s in re.split(r'[,;\n]', skills_str) if s.strip(" *-•")]
                detected_skills = [s for s in skills if s][:15]  # Limite à 15 compétences
                break

    return {
        "reply": final_reply or "Merci pour votre message, nous revenons vers vous rapidement.",
        "status": result.get("status", "processing"),
        "escalation_reason": result.get("escalation_reason"),
        "detected_domain": detected_domain,
        "detected_skills": detected_skills,
        "recommended_link": recommended_link,
    }
