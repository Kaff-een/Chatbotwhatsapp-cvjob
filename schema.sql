-- schema.sql
-- Script de création et de mise à jour des tables Supabase / PostgreSQL pour le chatbot WhatsApp cvjob.org
-- Ce script crée toutes les tables nécessaires au bon fonctionnement de db.py et de l'application.
-- Il utilise 'IF NOT EXISTS' pour éviter d'écraser des données existantes en cas de réexécution.

BEGIN;

-- ============================================================
-- 1. Table : candidates
-- Enregistre les candidats, leur numéro de téléphone unique et leur langue préférée.
-- ============================================================
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    preferred_language VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour accélérer la recherche par numéro de téléphone
CREATE INDEX IF NOT EXISTS idx_candidates_phone ON candidates(phone_number);


-- ============================================================
-- 2. Table : requests
-- Enregistre chaque requête (message textuel ou envoi de CV) d'un candidat.
-- ============================================================
CREATE TABLE IF NOT EXISTS requests (
    id SERIAL PRIMARY KEY,
    candidate_id INT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    input_type VARCHAR(50) NOT NULL, -- Ex: 'text', 'document'
    raw_text TEXT,
    cv_filename VARCHAR(255),
    cv_extracted_text TEXT,
    detected_domain VARCHAR(255),
    detected_skills JSONB DEFAULT '[]'::jsonb,
    recommended_link TEXT,
    status VARCHAR(50) DEFAULT 'processing', -- Ex: 'processing', 'resolved', 'needs_human'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index sur candidate_id pour accélérer la récupération des historiques
CREATE INDEX IF NOT EXISTS idx_requests_candidate ON requests(candidate_id);
-- Index sur created_at pour trier efficacement par requête récente
CREATE INDEX IF NOT EXISTS idx_requests_created_at ON requests(created_at DESC);


-- ============================================================
-- 3. Table : messages
-- Journalise tous les messages échangés (candidat <-> bot) dans le cadre d'une requête.
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    request_id INT REFERENCES requests(id) ON DELETE CASCADE,
    candidate_id INT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    sender VARCHAR(50) NOT NULL, -- 'candidate' ou 'bot'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_request ON messages(request_id);


-- ============================================================
-- 4. Table : staff_contacts
-- Membres de l'équipe (RH, support technique) disponibles pour les escalades.
-- ============================================================
CREATE TABLE IF NOT EXISTS staff_contacts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255),
    specialty VARCHAR(255),
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staff_contacts_active ON staff_contacts(is_active) WHERE is_active = TRUE;


-- ============================================================
-- 5. Table : escalations
-- Enregistre les tickets d'escalade vers des conseillers humains.
-- ============================================================
CREATE TABLE IF NOT EXISTS escalations (
    id SERIAL PRIMARY KEY,
    request_id INT REFERENCES requests(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    notified_contact VARCHAR(50) REFERENCES staff_contacts(phone_number) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 6. Table : notifications
-- Enregistre les SMS/messages WhatsApp en attente d'envoi (ex: escalades pour le staff).
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    recipient_phone VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    reason TEXT,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour récupérer rapidement les notifications non envoyées ordonnées
CREATE INDEX IF NOT EXISTS idx_notifications_unsent ON notifications(sent, created_at) WHERE sent = FALSE;


-- ============================================================
-- 7. Insertion de données initiales pour le Staff (optionnel)
-- Permet de tester le système d'escalade immédiatement.
-- ============================================================
INSERT INTO staff_contacts (name, role, specialty, phone_number, is_active)
SELECT 'Responsable RH', 'RH', 'Emplois et CV', '212600000001', TRUE
WHERE NOT EXISTS (SELECT 1 FROM staff_contacts WHERE phone_number = '212600000001');

INSERT INTO staff_contacts (name, role, specialty, phone_number, is_active)
SELECT 'Support Technique', 'Support', 'Problèmes techniques', '212600000002', TRUE
WHERE NOT EXISTS (SELECT 1 FROM staff_contacts WHERE phone_number = '212600000002');

COMMIT;
