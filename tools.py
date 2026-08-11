"""
tools.py
--------
Outils (tools) LangChain utilisés par les agents du chatbot cvjob.org.
"""

from langchain_core.tools import tool
from urllib.parse import urlencode
from typing import Optional
import db


BASE_JOBS_URL = "https://www.cvjob.org/offres-emploi"
BASE_INTERNSHIPS_URL = "https://www.cvjob.org/offres-stage"

VALID_EXPERIENCE_LEVELS = {"all", "confirme", "debutant", "expert", "jeune_diplome", "senior"}
VALID_JOB_TYPES = {"all", "full_time"}
VALID_EDUCATION_LEVELS = {"all", "bac", "bac_plus_2", "bac_plus_3", "bac_plus_5"}
VALID_DURATIONS = {"", "1-2", "2-3", "3-4", "4-6"}
VALID_WORK_TYPES = {"", "teletravail", "hybride", "sur_site"}

PARENT_DOMAINS_MAPPING = {
    # ──────────────────────────────────────────────────────
    # 1. Intelligence Artificielle / الذكاء الاصطناعي
    # ──────────────────────────────────────────────────────
    "machine learning": "intelligence artificielle",
    "ml": "intelligence artificielle",
    "deep learning": "intelligence artificielle",
    "dl": "intelligence artificielle",
    "computer vision": "intelligence artificielle",
    "vision par ordinateur": "intelligence artificielle",
    "nlp": "intelligence artificielle",
    "traitement du langage naturel": "intelligence artificielle",
    "llm": "intelligence artificielle",
    "prompt engineering": "intelligence artificielle",
    "generative ai": "intelligence artificielle",
    "ia générative": "intelligence artificielle",
    "ia generative": "intelligence artificielle",
    "artificial intelligence": "intelligence artificielle",
    "intelligence artificielle": "intelligence artificielle",
    "الذكاء الاصطناعي": "intelligence artificielle",
    "تعلم الآلة": "intelligence artificielle",
    "تعلم عميق": "intelligence artificielle",
    "رؤية حاسوبية": "intelligence artificielle",

    # ──────────────────────────────────────────────────────
    # 2. Data / البيانات
    # ──────────────────────────────────────────────────────
    "data science": "data",
    "data scientist": "data",
    "data analyst": "data",
    "data analytics": "data",
    "data engineer": "data",
    "data engineering": "data",
    "big data": "data",
    "business intelligence": "data",
    "bi": "data",
    "science des données": "data",
    "science des donnees": "data",
    "analyse de données": "data",
    "analyse de donnees": "data",
    "علم البيانات": "data",
    "تحليل البيانات": "data",
    "هندسة البيانات": "data",

    # ──────────────────────────────────────────────────────
    # 3. Développement Web / تطوير الويب
    # ──────────────────────────────────────────────────────
    "développement web": "développement web",
    "developpement web": "développement web",
    "web development": "développement web",
    "développeur web": "développement web",
    "developpeur web": "développement web",
    "web developer": "développement web",
    "frontend": "développement web",
    "front-end": "développement web",
    "front end": "développement web",
    "backend": "développement web",
    "back-end": "développement web",
    "back end": "développement web",
    "fullstack": "développement web",
    "full-stack": "développement web",
    "full stack": "développement web",
    "react": "développement web",
    "angular": "développement web",
    "vue.js": "développement web",
    "vuejs": "développement web",
    "node.js": "développement web",
    "nodejs": "développement web",
    "django": "développement web",
    "flask": "développement web",
    "laravel": "développement web",
    "php": "développement web",
    "html": "développement web",
    "css": "développement web",
    "javascript": "développement web",
    "typescript": "développement web",
    "تطوير الويب": "développement web",
    "مطور ويب": "développement web",
    "تطوير مواقع": "développement web",

    # ──────────────────────────────────────────────────────
    # 4. Développement Mobile / تطوير التطبيقات
    # ──────────────────────────────────────────────────────
    "développement mobile": "développement mobile",
    "developpement mobile": "développement mobile",
    "mobile development": "développement mobile",
    "développeur mobile": "développement mobile",
    "developpeur mobile": "développement mobile",
    "mobile developer": "développement mobile",
    "android": "développement mobile",
    "ios": "développement mobile",
    "flutter": "développement mobile",
    "react native": "développement mobile",
    "swift": "développement mobile",
    "kotlin": "développement mobile",
    "تطوير تطبيقات الهاتف": "développement mobile",
    "تطوير الموبايل": "développement mobile",
    "مطور تطبيقات": "développement mobile",

    # ──────────────────────────────────────────────────────
    # 5. Informatique / Développement logiciel / هندسة البرمجيات
    # ──────────────────────────────────────────────────────
    "informatique": "informatique",
    "développeur logiciel": "informatique",
    "developpeur logiciel": "informatique",
    "software engineer": "informatique",
    "software engineering": "informatique",
    "software developer": "informatique",
    "génie logiciel": "informatique",
    "genie logiciel": "informatique",
    "programmation": "informatique",
    "programmer": "informatique",
    "développeur": "informatique",
    "developpeur": "informatique",
    "developer": "informatique",
    "java": "informatique",
    "python": "informatique",
    "c++": "informatique",
    "c#": "informatique",
    ".net": "informatique",
    "dotnet": "informatique",
    "هندسة البرمجيات": "informatique",
    "برمجة": "informatique",
    "مبرمج": "informatique",
    "معلوميات": "informatique",

    # ──────────────────────────────────────────────────────
    # 6. DevOps / Cloud / Systèmes
    # ──────────────────────────────────────────────────────
    "devops": "systèmes et réseaux",
    "cloud": "systèmes et réseaux",
    "cloud computing": "systèmes et réseaux",
    "aws": "systèmes et réseaux",
    "azure": "systèmes et réseaux",
    "gcp": "systèmes et réseaux",
    "docker": "systèmes et réseaux",
    "kubernetes": "systèmes et réseaux",
    "système et réseaux": "systèmes et réseaux",
    "systeme et reseaux": "systèmes et réseaux",
    "systèmes et réseaux": "systèmes et réseaux",
    "systemes et reseaux": "systèmes et réseaux",
    "administrateur système": "systèmes et réseaux",
    "administrateur systeme": "systèmes et réseaux",
    "system administrator": "systèmes et réseaux",
    "sysadmin": "systèmes et réseaux",
    "réseau": "systèmes et réseaux",
    "reseau": "systèmes et réseaux",
    "network": "systèmes et réseaux",
    "infrastructure": "systèmes et réseaux",
    "linux": "systèmes et réseaux",
    "إدارة الأنظمة": "systèmes et réseaux",
    "شبكات": "systèmes et réseaux",
    "الحوسبة السحابية": "systèmes et réseaux",

    # ──────────────────────────────────────────────────────
    # 7. Cybersécurité / الأمن السيبراني
    # ──────────────────────────────────────────────────────
    "cybersécurité": "cybersécurité",
    "cybersecurite": "cybersécurité",
    "cybersecurity": "cybersécurité",
    "sécurité informatique": "cybersécurité",
    "securite informatique": "cybersécurité",
    "information security": "cybersécurité",
    "pentesting": "cybersécurité",
    "pentest": "cybersécurité",
    "soc analyst": "cybersécurité",
    "الأمن السيبراني": "cybersécurité",
    "أمن المعلومات": "cybersécurité",

    # ──────────────────────────────────────────────────────
    # 8. Marketing / التسويق
    # ──────────────────────────────────────────────────────
    "marketing": "marketing",
    "marketing digital": "marketing",
    "digital marketing": "marketing",
    "community manager": "marketing",
    "community management": "marketing",
    "social media": "marketing",
    "réseaux sociaux": "marketing",
    "reseaux sociaux": "marketing",
    "seo": "marketing",
    "sem": "marketing",
    "content marketing": "marketing",
    "marketing de contenu": "marketing",
    "growth hacking": "marketing",
    "branding": "marketing",
    "publicité": "marketing",
    "publicite": "marketing",
    "advertising": "marketing",
    "تسويق": "marketing",
    "تسويق رقمي": "marketing",
    "التسويق الرقمي": "marketing",
    "مدير مجتمع": "marketing",
    "إشهار": "marketing",

    # ──────────────────────────────────────────────────────
    # 9. Commerce / Vente / التجارة
    # ──────────────────────────────────────────────────────
    "commerce": "commerce",
    "commercial": "commerce",
    "vente": "commerce",
    "sales": "commerce",
    "business development": "commerce",
    "account manager": "commerce",
    "chargé de clientèle": "commerce",
    "charge de clientele": "commerce",
    "relation client": "commerce",
    "customer relationship": "commerce",
    "e-commerce": "commerce",
    "ecommerce": "commerce",
    "تجارة": "commerce",
    "مبيعات": "commerce",
    "تجارة إلكترونية": "commerce",
    "مسؤول تجاري": "commerce",

    # ──────────────────────────────────────────────────────
    # 10. Finance / Comptabilité / المالية والمحاسبة
    # ──────────────────────────────────────────────────────
    "finance": "finance",
    "comptabilité": "finance",
    "comptabilite": "finance",
    "accounting": "finance",
    "comptable": "finance",
    "accountant": "finance",
    "audit": "finance",
    "auditeur": "finance",
    "auditor": "finance",
    "contrôle de gestion": "finance",
    "controle de gestion": "finance",
    "gestion financière": "finance",
    "gestion financiere": "finance",
    "financial management": "finance",
    "trésorerie": "finance",
    "tresorerie": "finance",
    "fiscalité": "finance",
    "fiscalite": "finance",
    "tax": "finance",
    "banque": "finance",
    "banking": "finance",
    "assurance": "finance",
    "insurance": "finance",
    "مالية": "finance",
    "محاسبة": "finance",
    "تدقيق": "finance",
    "مراجعة حسابات": "finance",
    "بنك": "finance",
    "تأمين": "finance",

    # ──────────────────────────────────────────────────────
    # 11. Ressources Humaines / الموارد البشرية
    # ──────────────────────────────────────────────────────
    "ressources humaines": "ressources humaines",
    "human resources": "ressources humaines",
    "rh": "ressources humaines",
    "hr": "ressources humaines",
    "recrutement": "ressources humaines",
    "recruitment": "ressources humaines",
    "paie": "ressources humaines",
    "payroll": "ressources humaines",
    "gestion du personnel": "ressources humaines",
    "formation": "ressources humaines",
    "training": "ressources humaines",
    "الموارد البشرية": "ressources humaines",
    "توظيف": "ressources humaines",
    "تدريب": "ressources humaines",

    # ──────────────────────────────────────────────────────
    # 12. Logistique / Supply Chain / اللوجستيك
    # ──────────────────────────────────────────────────────
    "logistique": "logistique",
    "logistics": "logistique",
    "supply chain": "logistique",
    "chaîne d'approvisionnement": "logistique",
    "chaine d'approvisionnement": "logistique",
    "transport": "logistique",
    "transportation": "logistique",
    "entreposage": "logistique",
    "warehousing": "logistique",
    "import export": "logistique",
    "import-export": "logistique",
    "douane": "logistique",
    "customs": "logistique",
    "achat": "logistique",
    "achats": "logistique",
    "procurement": "logistique",
    "purchasing": "logistique",
    "لوجستيك": "logistique",
    "سلسلة التوريد": "logistique",
    "نقل": "logistique",
    "مشتريات": "logistique",
    "استيراد": "logistique",
    "تصدير": "logistique",

    # ──────────────────────────────────────────────────────
    # 13. Droit / Juridique / القانون
    # ──────────────────────────────────────────────────────
    "droit": "juridique",
    "juridique": "juridique",
    "legal": "juridique",
    "juriste": "juridique",
    "lawyer": "juridique",
    "avocat": "juridique",
    "attorney": "juridique",
    "contentieux": "juridique",
    "litigation": "juridique",
    "droit des affaires": "juridique",
    "business law": "juridique",
    "conformité": "juridique",
    "conformite": "juridique",
    "compliance": "juridique",
    "قانون": "juridique",
    "محامي": "juridique",
    "مستشار قانوني": "juridique",
    "القانون": "juridique",

    # ──────────────────────────────────────────────────────
    # 14. Communication / الاتصال
    # ──────────────────────────────────────────────────────
    "communication": "communication",
    "communications": "communication",
    "relations publiques": "communication",
    "public relations": "communication",
    "pr": "communication",
    "journalisme": "communication",
    "journalism": "communication",
    "rédaction": "communication",
    "redaction": "communication",
    "copywriting": "communication",
    "média": "communication",
    "media": "communication",
    "presse": "communication",
    "press": "communication",
    "اتصال": "communication",
    "صحافة": "communication",
    "علاقات عامة": "communication",
    "إعلام": "communication",

    # ──────────────────────────────────────────────────────
    # 15. Design / Graphisme / التصميم
    # ──────────────────────────────────────────────────────
    "design": "design",
    "graphisme": "design",
    "graphic design": "design",
    "design graphique": "design",
    "ui design": "design",
    "ux design": "design",
    "ui/ux": "design",
    "ux/ui": "design",
    "webdesign": "design",
    "web design": "design",
    "infographie": "design",
    "infographiste": "design",
    "directeur artistique": "design",
    "art director": "design",
    "photoshop": "design",
    "illustrator": "design",
    "figma": "design",
    "تصميم": "design",
    "تصميم جرافيك": "design",
    "مصمم": "design",

    # ──────────────────────────────────────────────────────
    # 16. Ingénierie / Industrie / الهندسة
    # ──────────────────────────────────────────────────────
    "ingénierie": "ingénierie",
    "ingenierie": "ingénierie",
    "engineering": "ingénierie",
    "ingénieur": "ingénierie",
    "ingenieur": "ingénierie",
    "engineer": "ingénierie",
    "génie civil": "ingénierie",
    "genie civil": "ingénierie",
    "civil engineering": "ingénierie",
    "génie mécanique": "ingénierie",
    "genie mecanique": "ingénierie",
    "mechanical engineering": "ingénierie",
    "génie électrique": "ingénierie",
    "genie electrique": "ingénierie",
    "electrical engineering": "ingénierie",
    "génie industriel": "ingénierie",
    "genie industriel": "ingénierie",
    "industrial engineering": "ingénierie",
    "automatisme": "ingénierie",
    "automation": "ingénierie",
    "maintenance": "ingénierie",
    "production": "ingénierie",
    "manufacturing": "ingénierie",
    "qualité": "ingénierie",
    "qualite": "ingénierie",
    "quality": "ingénierie",
    "qhse": "ingénierie",
    "hse": "ingénierie",
    "هندسة": "ingénierie",
    "مهندس": "ingénierie",
    "هندسة مدنية": "ingénierie",
    "هندسة ميكانيكية": "ingénierie",
    "هندسة كهربائية": "ingénierie",
    "صيانة": "ingénierie",
    "جودة": "ingénierie",
    "إنتاج": "ingénierie",

    # ──────────────────────────────────────────────────────
    # 17. BTP / Construction / البناء والأشغال العمومية
    # ──────────────────────────────────────────────────────
    "btp": "btp",
    "construction": "btp",
    "bâtiment": "btp",
    "batiment": "btp",
    "building": "btp",
    "travaux publics": "btp",
    "public works": "btp",
    "architecture": "btp",
    "architecte": "btp",
    "architect": "btp",
    "urbanisme": "btp",
    "topographie": "btp",
    "بناء": "btp",
    "أشغال عمومية": "btp",
    "هندسة معمارية": "btp",
    "معماري": "btp",

    # ──────────────────────────────────────────────────────
    # 18. Santé / Médical / الصحة
    # ──────────────────────────────────────────────────────
    "santé": "santé",
    "sante": "santé",
    "health": "santé",
    "healthcare": "santé",
    "médical": "santé",
    "medical": "santé",
    "médecine": "santé",
    "medecine": "santé",
    "medicine": "santé",
    "pharmacie": "santé",
    "pharmacy": "santé",
    "infirmier": "santé",
    "infirmière": "santé",
    "infirmiere": "santé",
    "nurse": "santé",
    "nursing": "santé",
    "dentiste": "santé",
    "dentist": "santé",
    "paramédical": "santé",
    "paramedical": "santé",
    "صحة": "santé",
    "طب": "santé",
    "صيدلة": "santé",
    "تمريض": "santé",
    "ممرض": "santé",

    # ──────────────────────────────────────────────────────
    # 19. Éducation / Enseignement / التعليم
    # ──────────────────────────────────────────────────────
    "éducation": "éducation",
    "education": "éducation",
    "enseignement": "éducation",
    "teaching": "éducation",
    "professeur": "éducation",
    "teacher": "éducation",
    "formateur": "éducation",
    "trainer": "éducation",
    "pédagogie": "éducation",
    "pedagogie": "éducation",
    "tuteur": "éducation",
    "tutor": "éducation",
    "تعليم": "éducation",
    "تدريس": "éducation",
    "أستاذ": "éducation",
    "مدرس": "éducation",

    # ──────────────────────────────────────────────────────
    # 20. Hôtellerie / Tourisme / Restauration / السياحة والفندقة
    # ──────────────────────────────────────────────────────
    "hôtellerie": "hôtellerie et tourisme",
    "hotellerie": "hôtellerie et tourisme",
    "hospitality": "hôtellerie et tourisme",
    "tourisme": "hôtellerie et tourisme",
    "tourism": "hôtellerie et tourisme",
    "restauration": "hôtellerie et tourisme",
    "restaurant": "hôtellerie et tourisme",
    "catering": "hôtellerie et tourisme",
    "hôtel": "hôtellerie et tourisme",
    "hotel": "hôtellerie et tourisme",
    "chef cuisinier": "hôtellerie et tourisme",
    "chef": "hôtellerie et tourisme",
    "réception": "hôtellerie et tourisme",
    "reception": "hôtellerie et tourisme",
    "guide touristique": "hôtellerie et tourisme",
    "tour guide": "hôtellerie et tourisme",
    "فندقة": "hôtellerie et tourisme",
    "سياحة": "hôtellerie et tourisme",
    "مطعم": "hôtellerie et tourisme",
    "طباخ": "hôtellerie et tourisme",

    # ──────────────────────────────────────────────────────
    # 21. Agriculture / Agroalimentaire / الفلاحة
    # ──────────────────────────────────────────────────────
    "agriculture": "agriculture",
    "agroalimentaire": "agriculture",
    "agro-alimentaire": "agriculture",
    "agro alimentaire": "agriculture",
    "agribusiness": "agriculture",
    "agronomie": "agriculture",
    "agronomy": "agriculture",
    "farming": "agriculture",
    "élevage": "agriculture",
    "elevage": "agriculture",
    "فلاحة": "agriculture",
    "زراعة": "agriculture",
    "صناعة غذائية": "agriculture",

    # ──────────────────────────────────────────────────────
    # 22. Environnement / Énergie / البيئة والطاقة
    # ──────────────────────────────────────────────────────
    "environnement": "environnement",
    "environment": "environnement",
    "énergie": "environnement",
    "energie": "environnement",
    "energy": "environnement",
    "énergie renouvelable": "environnement",
    "energie renouvelable": "environnement",
    "renewable energy": "environnement",
    "solaire": "environnement",
    "solar": "environnement",
    "éolien": "environnement",
    "eolien": "environnement",
    "wind energy": "environnement",
    "développement durable": "environnement",
    "developpement durable": "environnement",
    "sustainable development": "environnement",
    "بيئة": "environnement",
    "طاقة": "environnement",
    "طاقة متجددة": "environnement",
    "تنمية مستدامة": "environnement",

    # ──────────────────────────────────────────────────────
    # 23. Gestion de Projet / إدارة المشاريع
    # ──────────────────────────────────────────────────────
    "gestion de projet": "gestion de projet",
    "project management": "gestion de projet",
    "chef de projet": "gestion de projet",
    "project manager": "gestion de projet",
    "scrum": "gestion de projet",
    "agile": "gestion de projet",
    "scrum master": "gestion de projet",
    "product owner": "gestion de projet",
    "product manager": "gestion de projet",
    "pmo": "gestion de projet",
    "إدارة المشاريع": "gestion de projet",
    "مدير مشروع": "gestion de projet",

    # ──────────────────────────────────────────────────────
    # 24. Administration / Secrétariat / الإدارة
    # ──────────────────────────────────────────────────────
    "administration": "administration",
    "secrétariat": "administration",
    "secretariat": "administration",
    "secrétaire": "administration",
    "secretaire": "administration",
    "secretary": "administration",
    "assistante de direction": "administration",
    "assistant de direction": "administration",
    "executive assistant": "administration",
    "office manager": "administration",
    "accueil": "administration",
    "front office": "administration",
    "إدارة": "administration",
    "سكرتارية": "administration",
    "كاتب": "administration",
    "استقبال": "administration",

    # ──────────────────────────────────────────────────────
    # 25. Télécommunications / الاتصالات
    # ──────────────────────────────────────────────────────
    "télécommunications": "télécommunications",
    "telecommunications": "télécommunications",
    "telecom": "télécommunications",
    "télécoms": "télécommunications",
    "telecoms": "télécommunications",
    "اتصالات": "télécommunications",
    "اتصالات سلكية": "télécommunications",

    # ──────────────────────────────────────────────────────
    # 26. Automobile / السيارات
    # ──────────────────────────────────────────────────────
    "automobile": "automobile",
    "automotive": "automobile",
    "mécanique automobile": "automobile",
    "mecanique automobile": "automobile",
    "auto mechanic": "automobile",
    "سيارات": "automobile",
    "ميكانيك": "automobile",

    # ──────────────────────────────────────────────────────
    # 27. Textile / Mode / النسيج
    # ──────────────────────────────────────────────────────
    "textile": "textile",
    "mode": "textile",
    "fashion": "textile",
    "confection": "textile",
    "couture": "textile",
    "stylisme": "textile",
    "fashion design": "textile",
    "نسيج": "textile",
    "أزياء": "textile",
    "خياطة": "textile",

    # ──────────────────────────────────────────────────────
    # 28. Call Center / Centre d'appel / مركز الاتصال
    # ──────────────────────────────────────────────────────
    "call center": "call center",
    "centre d'appel": "call center",
    "centre d'appels": "call center",
    "téléconseiller": "call center",
    "teleconseiller": "call center",
    "service client": "call center",
    "customer service": "call center",
    "support client": "call center",
    "customer support": "call center",
    "helpdesk": "call center",
    "help desk": "call center",
    "مركز الاتصال": "call center",
    "خدمة العملاء": "call center",
    "خدمة الزبناء": "call center",

    # ──────────────────────────────────────────────────────
    # 29. Immobilier / العقارات
    # ──────────────────────────────────────────────────────
    "immobilier": "immobilier",
    "real estate": "immobilier",
    "agent immobilier": "immobilier",
    "real estate agent": "immobilier",
    "promotion immobilière": "immobilier",
    "promotion immobiliere": "immobilier",
    "عقارات": "immobilier",
    "وكيل عقاري": "immobilier",
}


def _normalize_arabic(text: str) -> str:
    """Normalise un texte arabe en supprimant les diacritiques (tashkeel) et en uniformisant les formes de alef/ya."""
    import unicodedata
    # Suppression des diacritiques arabes (harakat) : fatha, damma, kasra, shadda, sukun, tanwin etc.
    arabic_diacritics = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0670\u0640"
    for char in arabic_diacritics:
        text = text.replace(char, "")
    # Normaliser les variantes de alef (أ إ آ ا → ا)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    # Normaliser ta marbuta (ة → ه)
    text = text.replace("ة", "ه")
    # Normaliser ya (ى → ي)
    text = text.replace("ى", "ي")
    return text


def get_parent_domain(keyword: str) -> str:
    """Normalise un mot-clé vers son domaine parent le plus adapté (supporte FR/EN/AR)."""
    if not keyword:
        return ""

    kw_lower = keyword.lower().strip()

    # 1. Correspondance exacte
    if kw_lower in PARENT_DOMAINS_MAPPING:
        return PARENT_DOMAINS_MAPPING[kw_lower]

    # 2. Correspondance exacte après normalisation arabe
    kw_normalized = _normalize_arabic(kw_lower)
    for key, val in PARENT_DOMAINS_MAPPING.items():
        if _normalize_arabic(key) == kw_normalized:
            return val

    # 3. Correspondance par sous-chaîne (clés > 2 caractères pour éviter les faux positifs)
    for key, val in PARENT_DOMAINS_MAPPING.items():
        if len(key) > 2 and key in kw_lower:
            return val

    # 4. Sous-chaîne après normalisation arabe
    for key, val in PARENT_DOMAINS_MAPPING.items():
        normalized_key = _normalize_arabic(key)
        if len(normalized_key) > 2 and normalized_key in kw_normalized:
            return val

    return keyword


@tool
def search_job_offers(
    keyword: str,
    location: str = "",
    experience_level: str = "all",
    job_type: str = "all",
) -> str:
    """
    Recherche des offres d'EMPLOI (pas de stage) sur cvjob.org selon un mot-clé et des filtres optionnels.

    Args:
        keyword: mot-clé de recherche (ex: "développeur web", "commerce")
        location: ville (ex: "casablanca"), laisser vide si non précisé
        experience_level: un parmi all|confirme|debutant|expert|jeune_diplome|senior
        job_type: un parmi all|full_time

    Retourne l'URL directe vers les résultats filtrés.
    """
    if experience_level not in VALID_EXPERIENCE_LEVELS:
        experience_level = "all"
    if job_type not in VALID_JOB_TYPES:
        job_type = "all"

    keyword_normalized = get_parent_domain(keyword)
    params = {
        "search": keyword_normalized,
        "location": location,
        "experience_level": experience_level,
        "job_type": job_type,
    }
    return f"{BASE_JOBS_URL}?{urlencode(params)}"


@tool
def search_internship_offers(
    keyword: str,
    location: str = "",
    education_level: str = "all",
    duration: str = "",
    work_type: str = "",
) -> str:
    """
    Recherche des offres de STAGE sur cvjob.org selon un mot-clé et des filtres optionnels.

    Args:
        keyword: mot-clé de recherche (ex: "production", "marketing")
        location: ville (ex: "casablanca"), laisser vide si non précisé
        education_level: un parmi all|bac|bac_plus_2|bac_plus_3|bac_plus_5
        duration: un parmi ""|1-2|2-3|3-4|4-6 (mois), vide = toutes durées
        work_type: un parmi ""|teletravail|hybride|sur_site, vide = tous types

    Retourne l'URL directe vers les résultats filtrés.
    """
    if education_level not in VALID_EDUCATION_LEVELS:
        education_level = "all"
    if duration not in VALID_DURATIONS:
        duration = ""
    if work_type not in VALID_WORK_TYPES:
        work_type = ""

    keyword_normalized = get_parent_domain(keyword)
    params = {
        "search": keyword_normalized,
        "location": location,
        "education_level": education_level,
        "duration": duration,
        "work_type": work_type,
    }
    return f"{BASE_INTERNSHIPS_URL}?{urlencode(params)}"


@tool
def list_staff_contacts() -> str:
    """
    Liste les contacts humains disponibles (RH, support technique, etc.) que l'agent
    peut notifier en cas de besoin d'escalade. Retourne nom, rôle et spécialité de chacun.
    Utiliser ce tool AVANT send_message_to_contact pour choisir le bon destinataire.
    """
    contacts = db.list_staff_contacts()
    if not contacts:
        return "Aucun contact humain n'est actuellement enregistré."

    lines = [
        f"- {c['name']} ({c['role']}) — spécialité: {c.get('specialty') or 'générale'}"
        for c in contacts
    ]
    return "\n".join(lines)


@tool
def send_message_to_contact(contact_name: str, reason: str, candidate_phone: str, request_id: Optional[int] = None) -> str:
    """
    Transmet un problème à un membre du staff (RH/support) préalablement identifié
    via list_staff_contacts. Le message envoyé au contact est généré automatiquement
    à partir de la raison fournie (ne rédige pas toi-même un message de contact commercial
    ou de recruteur : indique uniquement la raison de l'escalade).

    Args:
        contact_name: nom exact du contact (doit exister dans list_staff_contacts)
        reason: raison courte et factuelle de l'escalade (ex: "CV illisible", "domaine non identifiable")
        candidate_phone: numéro de téléphone du candidat concerné
        request_id: ID optionnel de la requête à l'origine de l'escalation
    """
    contact = db.get_staff_contact_by_name(contact_name)
    if not contact:
        return f"Contact '{contact_name}' introuvable. Utilisez list_staff_contacts pour voir les contacts valides."

    message = (
        f"⚠️ Escalade cvjob.org\n"
        f"Candidat: {candidate_phone}\n"
        f"Raison: {reason}"
    )

    db.create_notification(recipient_phone=contact["phone_number"], message=message, reason=reason)
    db.create_escalation(request_id=request_id, reason=reason, notified_contact=contact["phone_number"])
    return f"NOTIFICATION_SENT::{contact['name']}"


@tool
def create_escalation_ticket(reason: str, request_id: Optional[int] = None) -> str:
    """
    Enregistre un ticket d'escalade en base de données, sans forcément notifier quelqu'un
    immédiatement (pour suivi/traçabilité).
    """
    db.create_escalation(request_id=request_id, reason=reason, notified_contact=None)
    return "Ticket d'escalade enregistré."


@tool
def get_candidate_profile(phone_number: str) -> str:
    """
    Récupère le profil connu d'un candidat (langue préférée, dernière recherche effectuée,
    domaine détecté précédemment) pour donner du contexte à l'agent.
    """
    candidate = db.get_candidate_by_phone(phone_number)
    if not candidate:
        return "Aucun profil existant pour ce candidat."

    last_request = db.get_last_request(candidate["id"])
    profile_summary = (
        f"Nom: {candidate.get('full_name') or 'inconnu'}\n"
        f"Langue: {candidate.get('preferred_language') or 'non définie'}\n"
    )
    if last_request:
        profile_summary += (
            f"Dernière demande: {last_request.get('input_type')}, "
            f"domaine détecté: {last_request.get('detected_domain') or 'aucun'}"
        )
    return profile_summary


@tool
def get_candidate_cv(phone_number: str) -> str:
    """
    Récupère le contenu textuel complet du dernier CV envoyé par ce candidat.
    Utiliser cet outil pour faire du RAG et suggérer des offres basées sur les compétences du CV.
    """
    candidate = db.get_candidate_by_phone(phone_number)
    if not candidate:
        return "Candidat introuvable."

    cv = db.get_latest_cv_by_candidate(candidate["id"])
    if not cv:
        return "Aucun CV trouvé pour ce candidat en base de données."

    return f"Fichier: {cv['cv_filename']}\nContenu extrait du CV:\n{cv['cv_extracted_text']}"


SEARCH_AGENT_TOOLS = [search_job_offers, search_internship_offers, get_candidate_profile, get_candidate_cv]
ESCALATION_AGENT_TOOLS = [list_staff_contacts, send_message_to_contact, create_escalation_ticket]
ALL_TOOLS = SEARCH_AGENT_TOOLS + ESCALATION_AGENT_TOOLS
