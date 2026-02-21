# ============================================================
# VIO 83 AI ORCHESTRA — Copyright (c) 2026 Viorica Porcu (vio83)
# DUAL LICENSE: Proprietary + AGPL-3.0 — See LICENSE files
# ALL RIGHTS RESERVED — https://github.com/vio83/vio83-ai-orchestra
# ============================================================
"""
VIO 83 AI ORCHESTRA — Biblioteca Digitale Universale
=====================================================
Database strutturato che rappresenta il corpus umano scritto nei libri
dalla nascita dell'essere umano fino al 20 febbraio 2026.

CATEGORIE (42 — copertura globale completa):

=== FONTI E FORMATI (5) ===
 1. Libri — tutte le lingue, tutti i generi, tutte le epoche
 2. Articoli accademici e scientifici — peer-reviewed, riviste, giornali
 3. Documenti storici e archivistici — archivi, biblioteche, musei
 4. Fonti online — Wikipedia, enciclopedie, siti di conoscenza certificati
 5. Ricerche e studi universitari — tesi, dissertazioni, pubblicazioni

=== SCIENZE NATURALI E FORMALI (6) ===
 6. Matematica — algebra, analisi, geometria, logica, statistica, topologia
 7. Fisica — classica, quantistica, relativistica, astrofisica, nucleare
 8. Chimica — generale, organica, inorganica, biochimica, farmaceutica
 9. Biologia — cellulare, molecolare, genetica, ecologia, evoluzione
10. Scienze della Terra — geologia, meteorologia, oceanografia, vulcanologia
11. Astronomia e Scienze spaziali — astrofisica, planetologia, cosmologia

=== SCIENZE MEDICHE E DELLA SALUTE (5) ===
12. Medicina — clinica, chirurgia, diagnostica, specializzazioni
13. Farmacia e Farmacologia — farmacognosia, farmacocinetica, tossicologia
14. Psicologia — clinica, cognitiva, sociale, dello sviluppo, neuropsicologia
15. Scienze infermieristiche e della salute — nursing, riabilitazione, ostetricia
16. Veterinaria — animali domestici, selvatici, zootecnia, patologia

=== SCIENZE UMANE E SOCIALI (8) ===
17. Storia — tutte le epoche, civilta, aree geografiche
18. Filosofia — metafisica, etica, estetica, epistemologia, logica
19. Linguistica e Filologia — fonetica, semantica, sociolinguistica, NLP
20. Sociologia e Antropologia — sociale, culturale, etnografia, demografia
21. Scienze politiche — teoria politica, relazioni internazionali, geopolitica
22. Diritto e Giurisprudenza — civile, penale, internazionale, costituzionale
23. Pedagogia e Scienze dell'educazione — didattica, pedagogia speciale
24. Religioni e Teologia — comparata, studi biblici, islamici, orientali

=== SCIENZE ECONOMICHE E GESTIONALI (3) ===
25. Economia — micro, macro, econometria, sviluppo, comportamentale
26. Management e Business — strategia, marketing, finanza, HR, operations
27. Contabilita e Finanza — ragioneria, auditing, mercati finanziari

=== TECNOLOGIA E INGEGNERIA (4) ===
28. Informatica e Computer Science — algoritmi, AI, ML, cybersecurity, DB
29. Ingegneria — civile, meccanica, elettrica, chimica, aerospaziale, nucleare
30. Telecomunicazioni e Elettronica — reti, IoT, 5G/6G, microelettronica
31. Biotecnologia e Nanotecnologia — genomica applicata, nanomateriali

=== ARTI, DESIGN E COMUNICAZIONE (4) ===
32. Arti visive e Performative — pittura, scultura, teatro, danza, fotografia
33. Musica e Musicologia — teoria, composizione, etnomusicologia
34. Cinema, Media e Comunicazione — regia, giornalismo, semiotica, PR
35. Design, Moda e Architettura — industrial design, fashion, urbanistica

=== SCIENZE APPLICATE E PROFESSIONALI (5) ===
36. Agraria e Scienze alimentari — agronomia, enologia, nutrizione, sicurezza
37. Scienze ambientali e Sostenibilita — ecologia, cambiamento climatico, ESG
38. Scienze motorie e Sport — fisiologia sportiva, biomeccanica, coaching
39. Turismo e Ospitalita — hospitality management, cultural tourism
40. Criminologia e Scienze forensi — profiling, balistica, tossicologia forense

=== INTERDISCIPLINARE E EMERGENTE (2) ===
41. Biblioteconomia, Archivistica e Museologia — catalogazione, conservazione
42. Studi di genere, Interculturali e Postcoloniali — gender studies, diaspora

STRUTTURA:
- Database SQLite relazionale con tabelle dedicate per ogni categoria
- Full-Text Search (FTS5) per ricerca semantica
- Indici per autore, anno, lingua, dominio, affidabilita
- Metadati completi: ISBN, DOI, ISSN, classificazione Dewey/LOC
- Punteggio di affidabilita per ogni fonte (0.0 - 1.0)
- Integrazione con Knowledge Base Engine per embedding e retrieval
"""

import os
import re
import sqlite3
import json
import uuid
import time
from typing import Optional
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager


# ============================================================
# CONFIGURAZIONE
# ============================================================

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
BIBLIOTECA_DB = os.path.join(DB_DIR, "biblioteca_digitale.db")


# ============================================================
# CATEGORIE DELLA BIBLIOTECA
# ============================================================

CATEGORIE = {
    # ═══════════════════════════════════════════════════════════
    # FONTI E FORMATI (5)
    # ═══════════════════════════════════════════════════════════
    "libri": {
        "nome": "Libri",
        "descrizione": "Tutti i libri scritti in ogni lingua dalla nascita della scrittura al 2026",
        "tabella": "libri",
        "gruppo": "fonti_formati",
    },
    "articoli_accademici": {
        "nome": "Articoli Accademici e Scientifici",
        "descrizione": "Articoli peer-reviewed pubblicati su riviste e giornali scientifici",
        "tabella": "articoli_accademici",
        "gruppo": "fonti_formati",
    },
    "documenti_storici": {
        "nome": "Documenti Storici e Archivistici",
        "descrizione": "Documenti storici da archivi, biblioteche, musei e collezioni",
        "tabella": "documenti_storici",
        "gruppo": "fonti_formati",
    },
    "fonti_online": {
        "nome": "Fonti Online",
        "descrizione": "Wikipedia, enciclopedie, open access, siti di conoscenza certificati",
        "tabella": "fonti_online",
        "gruppo": "fonti_formati",
    },
    "ricerche_universitarie": {
        "nome": "Ricerche e Studi Universitari",
        "descrizione": "Tesi, dissertazioni, pubblicazioni e rapporti universitari",
        "tabella": "ricerche_universitarie",
        "gruppo": "fonti_formati",
    },
    # ═══════════════════════════════════════════════════════════
    # SCIENZE NATURALI E FORMALI (6)
    # ═══════════════════════════════════════════════════════════
    "matematica": {
        "nome": "Matematica",
        "descrizione": "Algebra, analisi, geometria, logica, statistica, topologia, teoria dei numeri",
        "tabella": "matematica",
        "gruppo": "scienze_naturali_formali",
    },
    "fisica": {
        "nome": "Fisica",
        "descrizione": "Classica, quantistica, relativistica, astrofisica, nucleare, particelle",
        "tabella": "fisica",
        "gruppo": "scienze_naturali_formali",
    },
    "chimica": {
        "nome": "Chimica",
        "descrizione": "Generale, organica, inorganica, biochimica, analitica, farmaceutica",
        "tabella": "chimica",
        "gruppo": "scienze_naturali_formali",
    },
    "biologia": {
        "nome": "Biologia",
        "descrizione": "Cellulare, molecolare, genetica, ecologia, evoluzione, microbiologia",
        "tabella": "biologia",
        "gruppo": "scienze_naturali_formali",
    },
    "scienze_terra": {
        "nome": "Scienze della Terra",
        "descrizione": "Geologia, meteorologia, oceanografia, vulcanologia, sismologia",
        "tabella": "scienze_terra",
        "gruppo": "scienze_naturali_formali",
    },
    "astronomia": {
        "nome": "Astronomia e Scienze Spaziali",
        "descrizione": "Astrofisica, planetologia, cosmologia, astrobiologia, esplorazione spaziale",
        "tabella": "astronomia",
        "gruppo": "scienze_naturali_formali",
    },
    # ═══════════════════════════════════════════════════════════
    # SCIENZE MEDICHE E DELLA SALUTE (5)
    # ═══════════════════════════════════════════════════════════
    "medicina": {
        "nome": "Medicina",
        "descrizione": "Clinica, chirurgia, diagnostica, tutte le specializzazioni mediche",
        "tabella": "medicina",
        "gruppo": "scienze_mediche",
    },
    "farmacia_farmacologia": {
        "nome": "Farmacia e Farmacologia",
        "descrizione": "Farmacognosia, farmacocinetica, tossicologia, sviluppo farmaci",
        "tabella": "farmacia_farmacologia",
        "gruppo": "scienze_mediche",
    },
    "psicologia": {
        "nome": "Psicologia",
        "descrizione": "Clinica, cognitiva, sociale, dello sviluppo, neuropsicologia",
        "tabella": "psicologia",
        "gruppo": "scienze_mediche",
    },
    "scienze_infermieristiche": {
        "nome": "Scienze Infermieristiche e della Salute",
        "descrizione": "Nursing, fisioterapia, riabilitazione, ostetricia, logopedia",
        "tabella": "scienze_infermieristiche",
        "gruppo": "scienze_mediche",
    },
    "veterinaria": {
        "nome": "Veterinaria",
        "descrizione": "Animali domestici, selvatici, zootecnia, patologia veterinaria",
        "tabella": "veterinaria",
        "gruppo": "scienze_mediche",
    },
    # ═══════════════════════════════════════════════════════════
    # SCIENZE UMANE E SOCIALI (8)
    # ═══════════════════════════════════════════════════════════
    "storia": {
        "nome": "Storia",
        "descrizione": "Tutte le epoche, civiltà e aree geografiche del mondo",
        "tabella": "storia",
        "gruppo": "scienze_umane_sociali",
    },
    "filosofia": {
        "nome": "Filosofia",
        "descrizione": "Metafisica, etica, estetica, epistemologia, logica, filosofia della mente",
        "tabella": "filosofia",
        "gruppo": "scienze_umane_sociali",
    },
    "linguistica": {
        "nome": "Linguistica e Filologia",
        "descrizione": "Fonetica, semantica, sociolinguistica, NLP, filologia classica e moderna",
        "tabella": "linguistica",
        "gruppo": "scienze_umane_sociali",
    },
    "sociologia_antropologia": {
        "nome": "Sociologia e Antropologia",
        "descrizione": "Sociale, culturale, etnografia, demografia, ricerca sociale",
        "tabella": "sociologia_antropologia",
        "gruppo": "scienze_umane_sociali",
    },
    "scienze_politiche": {
        "nome": "Scienze Politiche",
        "descrizione": "Teoria politica, relazioni internazionali, geopolitica, governance",
        "tabella": "scienze_politiche",
        "gruppo": "scienze_umane_sociali",
    },
    "diritto": {
        "nome": "Diritto e Giurisprudenza",
        "descrizione": "Civile, penale, internazionale, costituzionale, commerciale, ambientale",
        "tabella": "diritto",
        "gruppo": "scienze_umane_sociali",
    },
    "pedagogia": {
        "nome": "Pedagogia e Scienze dell'Educazione",
        "descrizione": "Didattica, pedagogia speciale, educazione degli adulti, e-learning",
        "tabella": "pedagogia",
        "gruppo": "scienze_umane_sociali",
    },
    "religioni_teologia": {
        "nome": "Religioni e Teologia",
        "descrizione": "Comparata, studi biblici, islamici, orientali, storia delle religioni",
        "tabella": "religioni_teologia",
        "gruppo": "scienze_umane_sociali",
    },
    # ═══════════════════════════════════════════════════════════
    # SCIENZE ECONOMICHE E GESTIONALI (3)
    # ═══════════════════════════════════════════════════════════
    "economia": {
        "nome": "Economia",
        "descrizione": "Micro, macro, econometria, sviluppo, comportamentale, politica economica",
        "tabella": "economia",
        "gruppo": "scienze_economiche",
    },
    "management_business": {
        "nome": "Management e Business",
        "descrizione": "Strategia, marketing, risorse umane, operations, imprenditorialita",
        "tabella": "management_business",
        "gruppo": "scienze_economiche",
    },
    "contabilita_finanza": {
        "nome": "Contabilita e Finanza",
        "descrizione": "Ragioneria, auditing, mercati finanziari, risk management, compliance",
        "tabella": "contabilita_finanza",
        "gruppo": "scienze_economiche",
    },
    # ═══════════════════════════════════════════════════════════
    # TECNOLOGIA E INGEGNERIA (4)
    # ═══════════════════════════════════════════════════════════
    "informatica": {
        "nome": "Informatica e Computer Science",
        "descrizione": "Algoritmi, AI, ML, cybersecurity, database, cloud, software engineering",
        "tabella": "informatica",
        "gruppo": "tecnologia_ingegneria",
    },
    "ingegneria": {
        "nome": "Ingegneria",
        "descrizione": "Civile, meccanica, elettrica, chimica, aerospaziale, biomedica, nucleare",
        "tabella": "ingegneria",
        "gruppo": "tecnologia_ingegneria",
    },
    "telecomunicazioni": {
        "nome": "Telecomunicazioni e Elettronica",
        "descrizione": "Reti, IoT, 5G/6G, microelettronica, elaborazione dei segnali",
        "tabella": "telecomunicazioni",
        "gruppo": "tecnologia_ingegneria",
    },
    "biotecnologia_nanotecnologia": {
        "nome": "Biotecnologia e Nanotecnologia",
        "descrizione": "Genomica applicata, nanomateriali, ingegneria genetica, biofarmaci",
        "tabella": "biotecnologia_nanotecnologia",
        "gruppo": "tecnologia_ingegneria",
    },
    # ═══════════════════════════════════════════════════════════
    # ARTI, DESIGN E COMUNICAZIONE (4)
    # ═══════════════════════════════════════════════════════════
    "arti_visive_performative": {
        "nome": "Arti Visive e Performative",
        "descrizione": "Pittura, scultura, teatro, danza, fotografia, installazioni, street art",
        "tabella": "arti_visive_performative",
        "gruppo": "arti_comunicazione",
    },
    "musica": {
        "nome": "Musica e Musicologia",
        "descrizione": "Teoria musicale, composizione, etnomusicologia, storia della musica",
        "tabella": "musica",
        "gruppo": "arti_comunicazione",
    },
    "cinema_media": {
        "nome": "Cinema, Media e Comunicazione",
        "descrizione": "Regia, sceneggiatura, giornalismo, semiotica, media digitali, PR",
        "tabella": "cinema_media",
        "gruppo": "arti_comunicazione",
    },
    "design_moda_architettura": {
        "nome": "Design, Moda e Architettura",
        "descrizione": "Industrial design, fashion design, urbanistica, architettura sostenibile",
        "tabella": "design_moda_architettura",
        "gruppo": "arti_comunicazione",
    },
    # ═══════════════════════════════════════════════════════════
    # SCIENZE APPLICATE E PROFESSIONALI (5)
    # ═══════════════════════════════════════════════════════════
    "agraria_alimentare": {
        "nome": "Agraria e Scienze Alimentari",
        "descrizione": "Agronomia, enologia, nutrizione, sicurezza alimentare, food tech",
        "tabella": "agraria_alimentare",
        "gruppo": "scienze_applicate",
    },
    "scienze_ambientali": {
        "nome": "Scienze Ambientali e Sostenibilita",
        "descrizione": "Ecologia applicata, cambiamento climatico, ESG, energia rinnovabile",
        "tabella": "scienze_ambientali",
        "gruppo": "scienze_applicate",
    },
    "scienze_motorie_sport": {
        "nome": "Scienze Motorie e Sport",
        "descrizione": "Fisiologia sportiva, biomeccanica, coaching, medicina sportiva",
        "tabella": "scienze_motorie_sport",
        "gruppo": "scienze_applicate",
    },
    "turismo_ospitalita": {
        "nome": "Turismo e Ospitalita",
        "descrizione": "Hospitality management, turismo culturale, destination management",
        "tabella": "turismo_ospitalita",
        "gruppo": "scienze_applicate",
    },
    "criminologia_forensi": {
        "nome": "Criminologia e Scienze Forensi",
        "descrizione": "Profiling, balistica, tossicologia forense, digital forensics",
        "tabella": "criminologia_forensi",
        "gruppo": "scienze_applicate",
    },
    # ═══════════════════════════════════════════════════════════
    # INTERDISCIPLINARE E EMERGENTE (2)
    # ═══════════════════════════════════════════════════════════
    "biblioteconomia_archivistica": {
        "nome": "Biblioteconomia, Archivistica e Museologia",
        "descrizione": "Catalogazione, conservazione, digital preservation, data curation",
        "tabella": "biblioteconomia_archivistica",
        "gruppo": "interdisciplinare",
    },
    "studi_genere_interculturali": {
        "nome": "Studi di Genere, Interculturali e Postcoloniali",
        "descrizione": "Gender studies, diaspora studies, studi postcoloniali, intersezionalita",
        "tabella": "studi_genere_interculturali",
        "gruppo": "interdisciplinare",
    },
}


# ============================================================
# SOTTO-DISCIPLINE PER CATEGORIA
# ============================================================

SOTTO_DISCIPLINE = {
    # ═══════════════════════════════════════════════════════════
    # FONTI E FORMATI
    # ═══════════════════════════════════════════════════════════
    "libri": [
        "narrativa", "poesia", "saggistica", "manualistica", "enciclopedie",
        "testi_sacri", "classici", "letteratura_contemporanea", "graphic_novel",
        "libri_per_ragazzi", "letteratura_comparata", "critica_letteraria",
        "antologie", "biografie", "autobiografie", "diari", "epistolari",
    ],
    "articoli_accademici": [
        "ricerca_originale", "review_articolo", "meta_analisi", "case_study",
        "lettera_editore", "commento", "erratum", "protocollo", "preprint",
        "short_communication", "editorial", "supplemento",
    ],
    "documenti_storici": [
        "manoscritti", "papiri", "pergamene", "codici", "incunaboli",
        "atti_ufficiali", "decreti", "trattati", "bolle_papali",
        "carteggi_diplomatici", "registri_parrocchiali", "censimenti",
        "diari_di_viaggio", "cronache", "epigrafi", "iscrizioni",
    ],
    "fonti_online": [
        "enciclopedia_wiki", "repository_open_access", "blog_accademici",
        "portali_dati", "archivi_digitali", "database_scientifici",
        "corsi_mooc", "podcast_educativi", "video_conferenze",
    ],
    "ricerche_universitarie": [
        "tesi_triennale", "tesi_magistrale", "tesi_dottorale", "post_doc",
        "rapporto_ricerca", "working_paper", "grant_proposal",
    ],

    # ═══════════════════════════════════════════════════════════
    # SCIENZE NATURALI E FORMALI
    # ═══════════════════════════════════════════════════════════
    "matematica": [
        "algebra_lineare", "algebra_astratta", "teoria_dei_gruppi", "teoria_degli_anelli",
        "analisi_reale", "analisi_complessa", "analisi_funzionale", "equazioni_differenziali",
        "geometria_euclidea", "geometria_differenziale", "geometria_algebrica",
        "topologia_generale", "topologia_algebrica", "teoria_dei_nodi",
        "teoria_dei_numeri", "combinatoria", "teoria_dei_grafi",
        "logica_matematica", "teoria_degli_insiemi", "teoria_dei_modelli",
        "probabilita", "statistica_matematica", "processi_stocastici",
        "calcolo_numerico", "ottimizzazione", "ricerca_operativa",
        "matematica_applicata", "matematica_finanziaria", "crittografia_matematica",
        "teoria_della_misura", "teoria_dell_informazione",
    ],
    "fisica": [
        "meccanica_classica", "meccanica_analitica", "meccanica_celeste",
        "termodinamica", "meccanica_statistica", "fisica_dei_fluidi",
        "elettromagnetismo", "ottica_classica", "ottica_quantistica", "fotonica",
        "acustica", "fisica_dello_stato_solido", "fisica_della_materia_condensata",
        "meccanica_quantistica", "teoria_dei_campi", "cromodinamica_quantistica",
        "relativita_ristretta", "relativita_generale", "gravitazione",
        "fisica_nucleare", "fisica_delle_particelle", "fisica_del_plasma",
        "astrofisica", "cosmologia", "fisica_delle_alte_energie",
        "biofisica", "geofisica", "fisica_medica", "fisica_computazionale",
        "nanofisica", "fisica_dei_materiali", "superconduttivita",
    ],
    "chimica": [
        "chimica_generale", "chimica_organica", "chimica_inorganica",
        "chimica_fisica", "chimica_analitica", "chimica_teorica",
        "biochimica", "chimica_farmaceutica", "chimica_dei_polimeri",
        "chimica_dei_materiali", "chimica_supramolecolare", "chimica_verde",
        "elettrochimica", "fotochimica", "termochimica",
        "chimica_nucleare", "chimica_ambientale", "chimica_alimentare",
        "chimica_industriale", "petrolchimica", "chimica_computazionale",
        "stereochimica", "chimica_dei_colloidi", "geochimica",
    ],
    "biologia": [
        "biologia_cellulare", "biologia_molecolare", "biologia_dello_sviluppo",
        "genetica_classica", "genetica_molecolare", "genomica", "epigenetica",
        "trascrittomica", "proteomica", "metabolomica",
        "microbiologia", "batteriologia", "virologia", "micologia", "parassitologia",
        "immunologia", "immunologia_molecolare",
        "ecologia", "ecologia_evolutiva", "biogeografia",
        "evoluzione", "filogenesi", "sistematica", "tassonomia",
        "neurobiologia", "neuroscienze", "bioinformatica",
        "biologia_marina", "biologia_vegetale", "botanica", "zoologia",
        "entomologia", "ornitologia", "erpetologia", "ittiologia",
        "fisiologia_animale", "fisiologia_vegetale", "etologia",
        "biologia_della_conservazione", "biologia_sintetica",
    ],
    "scienze_terra": [
        "geologia_generale", "geologia_strutturale", "geologia_regionale",
        "mineralogia", "petrografia", "petrologia", "geochimica",
        "geomorfologia", "sedimentologia", "stratigrafia",
        "paleontologia", "micropaleontologia", "paleobotanica", "paleoecologia",
        "vulcanologia", "sismologia", "geodesia", "geodinamica",
        "meteorologia", "climatologia", "idrologia", "idrogeologia",
        "oceanografia_fisica", "oceanografia_chimica", "oceanografia_biologica",
        "glaciologia", "pedologia", "cartografia", "telerilevamento", "GIS",
    ],
    "astronomia": [
        "astronomia_osservativa", "astronomia_radio", "astronomia_infrarossa",
        "astronomia_X", "astronomia_gamma", "astronomia_gravitazionale",
        "astrofisica_stellare", "astrofisica_galattica", "astrofisica_extragalattica",
        "cosmologia_osservativa", "cosmologia_teorica", "materia_oscura", "energia_oscura",
        "planetologia", "scienze_lunari", "scienze_marziane",
        "astrobiologia", "SETI", "esopianeti",
        "astrochimica", "astronautica", "ingegneria_spaziale",
        "meccanica_orbitale", "astrodinamica",
    ],

    # ═══════════════════════════════════════════════════════════
    # SCIENZE MEDICHE E DELLA SALUTE
    # ═══════════════════════════════════════════════════════════
    "medicina": [
        "medicina_interna", "cardiologia", "pneumologia", "gastroenterologia",
        "nefrologia", "ematologia", "endocrinologia", "reumatologia",
        "oncologia", "oncologia_medica", "radioterapia",
        "neurologia", "neurochirurgia", "psichiatria",
        "chirurgia_generale", "chirurgia_vascolare", "chirurgia_plastica",
        "ortopedia", "traumatologia", "medicina_dello_sport",
        "pediatria", "neonatologia", "geriatria", "gerontologia",
        "ginecologia", "ostetricia", "andrologia",
        "dermatologia", "allergologia", "immunologia_clinica",
        "oftalmologia", "otorinolaringoiatria", "odontoiatria",
        "urologia", "anestesiologia", "medicina_d_urgenza",
        "radiologia", "medicina_nucleare", "anatomia_patologica",
        "epidemiologia", "medicina_preventiva", "igiene", "sanita_pubblica",
        "medicina_legale", "medicina_del_lavoro", "medicina_tropicale",
        "medicina_palliativa", "rianimazione", "terapia_intensiva",
        "genetica_medica", "telemedicina", "medicina_personalizzata",
    ],
    "farmacia_farmacologia": [
        "farmacologia_generale", "farmacologia_clinica", "farmacocinetica",
        "farmacodinamica", "farmacogenetica", "farmacogenomica",
        "farmacognosia", "fitoterapia", "chimica_farmaceutica",
        "tossicologia", "tossicologia_clinica", "tossicologia_ambientale",
        "tecnologia_farmaceutica", "galenica", "formulazione",
        "farmacia_ospedaliera", "farmacia_clinica", "farmacovigilanza",
        "farmacoepidemiogia", "farmaco_economia",
    ],
    "psicologia": [
        "psicologia_clinica", "psicologia_cognitiva", "psicologia_sociale",
        "psicologia_dello_sviluppo", "psicologia_dell_educazione",
        "neuropsicologia", "psicologia_sperimentale",
        "psicologia_del_lavoro", "psicologia_delle_organizzazioni",
        "psicologia_giuridica", "psicologia_forense",
        "psicologia_della_salute", "psicologia_positiva",
        "psicoterapia", "psicoanalisi", "terapia_cognitivo_comportamentale",
        "psicologia_dinamica", "psicologia_della_personalita",
        "psicologia_ambientale", "psicologia_dello_sport",
        "psicologia_transculturale", "psicologia_dell_emergenza",
    ],
    "scienze_infermieristiche": [
        "infermieristica_generale", "infermieristica_clinica",
        "infermieristica_pediatrica", "infermieristica_geriatrica",
        "infermieristica_psichiatrica", "infermieristica_comunitaria",
        "fisioterapia", "terapia_occupazionale", "logopedia",
        "ostetricia_clinica", "riabilitazione_neurologica",
        "riabilitazione_cardiologica", "riabilitazione_respiratoria",
        "dietistica", "podologia", "ortottica",
        "educazione_sanitaria", "management_sanitario",
    ],
    "veterinaria": [
        "clinica_piccoli_animali", "clinica_grandi_animali", "clinica_equina",
        "chirurgia_veterinaria", "patologia_veterinaria",
        "farmacologia_veterinaria", "radiologia_veterinaria",
        "zootecnia", "alimentazione_animale", "igiene_veterinaria",
        "malattie_infettive_animali", "parassitologia_veterinaria",
        "epidemiologia_veterinaria", "medicina_legale_veterinaria",
        "fauna_selvatica", "animali_esotici", "acquacoltura",
        "etologia_veterinaria", "riproduzione_animale",
    ],

    # ═══════════════════════════════════════════════════════════
    # SCIENZE UMANE E SOCIALI
    # ═══════════════════════════════════════════════════════════
    "storia": [
        "preistoria", "protostoria", "storia_antica",
        "egitto_antico", "mesopotamia", "grecia_antica", "roma_antica",
        "civilta_indo_valle", "civilta_cinese_antica", "civilta_mesoamericane",
        "storia_medievale", "storia_bizantina", "storia_islamica_medievale",
        "storia_moderna", "rinascimento", "riforma_controriforma",
        "storia_contemporanea", "storia_del_novecento", "guerra_fredda",
        "storia_dell_arte", "storia_della_scienza", "storia_della_tecnologia",
        "storia_della_filosofia", "storia_della_medicina",
        "storia_del_diritto", "storia_economica", "storia_militare",
        "storia_delle_religioni", "storia_sociale", "storia_culturale",
        "storia_orale", "storia_digitale", "microstoria",
        "civilta_cinese", "civilta_indiana", "civilta_islamica",
        "civilta_giapponese", "civilta_coreana", "civilta_africane",
        "civilta_precolombiane", "civilta_nord_americane",
        "storia_dell_europa_orientale", "storia_dell_america_latina",
        "storia_dell_australia_oceania", "storia_dell_africa",
    ],
    "filosofia": [
        "metafisica", "ontologia", "epistemologia", "logica_filosofica", "etica",
        "etica_applicata", "bioetica", "etica_ambientale", "etica_dell_AI",
        "estetica", "filosofia_della_mente", "filosofia_del_linguaggio",
        "filosofia_della_scienza", "filosofia_della_matematica",
        "filosofia_politica", "filosofia_del_diritto", "filosofia_sociale",
        "ermeneutica", "fenomenologia", "esistenzialismo",
        "pragmatismo", "filosofia_analitica", "filosofia_continentale",
        "filosofia_antica", "filosofia_medievale", "scolastica",
        "filosofia_moderna", "illuminismo", "idealismo", "empirismo",
        "filosofia_contemporanea", "postmodernismo", "decostruzionismo",
        "filosofia_orientale", "filosofia_indiana", "filosofia_cinese",
        "filosofia_giapponese", "filosofia_africana",
        "filosofia_della_religione", "filosofia_della_storia",
        "filosofia_della_tecnologia",
    ],
    "linguistica": [
        "fonetica", "fonologia", "morfologia", "sintassi", "semantica",
        "pragmatica", "analisi_del_discorso",
        "sociolinguistica", "psicolinguistica", "neurolinguistica",
        "linguistica_computazionale", "NLP", "linguistica_dei_corpora",
        "tipologia_linguistica", "linguistica_storica", "linguistica_comparata",
        "dialettologia", "lessicografia", "lessicologia",
        "traduttologia", "interpretariato", "localizzazione",
        "filologia_classica", "filologia_romanza", "filologia_germanica",
        "filologia_slava", "filologia_semitica", "filologia_orientale",
        "grammatica_generativa", "linguistica_cognitiva",
        "linguistica_applicata", "glottodidattica",
        "semiotica", "scrittura_creativa", "retorica",
    ],
    "sociologia_antropologia": [
        "sociologia_generale", "sociologia_della_comunicazione",
        "sociologia_del_lavoro", "sociologia_della_famiglia",
        "sociologia_dell_educazione", "sociologia_della_religione",
        "sociologia_urbana", "sociologia_rurale",
        "sociologia_della_devianza", "sociologia_della_salute",
        "sociologia_della_cultura", "sociologia_digitale",
        "antropologia_culturale", "antropologia_sociale",
        "antropologia_fisica", "antropologia_medica",
        "antropologia_economica", "antropologia_politica",
        "antropologia_visuale", "antropologia_cognitiva",
        "etnografia", "etnologia", "etnolinguistica",
        "demografia", "metodologia_della_ricerca_sociale",
        "studi_sulla_migrazione", "studi_urbani",
    ],
    "scienze_politiche": [
        "teoria_politica", "filosofia_politica_applicata",
        "politica_comparata", "politica_internazionale",
        "relazioni_internazionali", "geopolitica", "geostrategia",
        "studi_europei", "studi_asiatici", "studi_africani", "studi_americani",
        "governance", "pubblica_amministrazione", "politiche_pubbliche",
        "comunicazione_politica", "sociologia_politica",
        "partiti_politici", "sistemi_elettorali",
        "studi_sulla_pace", "conflict_resolution",
        "intelligence", "sicurezza_internazionale",
        "organizzazioni_internazionali", "diplomazia",
    ],
    "diritto": [
        "diritto_civile", "diritto_penale", "diritto_costituzionale",
        "diritto_amministrativo", "diritto_commerciale",
        "diritto_del_lavoro", "diritto_tributario", "diritto_fallimentare",
        "diritto_internazionale_pubblico", "diritto_internazionale_privato",
        "diritto_europeo", "diritto_dell_UE",
        "diritto_processuale_civile", "diritto_processuale_penale",
        "diritto_della_navigazione", "diritto_marittimo",
        "diritto_ambientale", "diritto_dell_energia",
        "diritto_sanitario", "diritto_farmaceutico",
        "diritto_dell_informatica", "diritto_della_privacy",
        "diritto_d_autore", "proprieta_intellettuale", "brevetti",
        "diritto_di_famiglia", "diritto_minorile",
        "diritto_canonico", "diritto_islamico",
        "storia_del_diritto", "filosofia_del_diritto",
        "diritto_comparato", "criminologia_giuridica",
    ],
    "pedagogia": [
        "pedagogia_generale", "pedagogia_speciale", "pedagogia_sociale",
        "pedagogia_interculturale", "pedagogia_sperimentale",
        "didattica_generale", "didattica_disciplinare",
        "tecnologie_dell_educazione", "e_learning", "instructional_design",
        "educazione_degli_adulti", "formazione_professionale",
        "educazione_permanente", "lifelong_learning",
        "docimologia", "valutazione_educativa",
        "psicopedagogia", "pedagogia_della_prima_infanzia",
        "educazione_ambientale", "educazione_alla_salute",
        "educazione_motoria", "educazione_musicale",
        "pedagogia_montessori", "pedagogia_steineriana",
        "filosofia_dell_educazione", "storia_dell_educazione",
    ],
    "religioni_teologia": [
        "teologia_cristiana", "teologia_cattolica", "teologia_protestante",
        "teologia_ortodossa", "patristica", "esegesi_biblica",
        "studi_biblici", "antico_testamento", "nuovo_testamento",
        "studi_islamici", "coranica", "hadith", "fiqh", "sufismo",
        "studi_ebraici", "talmud", "kabbalah",
        "induismo", "buddhismo", "giainismo", "sikhismo",
        "taoismo", "confucianesimo", "shintoismo",
        "religioni_africane", "religioni_native_americane",
        "storia_delle_religioni", "fenomenologia_della_religione",
        "sociologia_della_religione", "psicologia_della_religione",
        "dialogo_interreligioso", "missiologia",
        "religioni_comparate", "nuovi_movimenti_religiosi",
    ],

    # ═══════════════════════════════════════════════════════════
    # SCIENZE ECONOMICHE E GESTIONALI
    # ═══════════════════════════════════════════════════════════
    "economia": [
        "microeconomia", "macroeconomia", "econometria",
        "economia_dello_sviluppo", "economia_internazionale",
        "economia_monetaria", "economia_pubblica", "economia_del_lavoro",
        "economia_industriale", "economia_comportamentale",
        "economia_sperimentale", "economia_ambientale",
        "economia_della_salute", "economia_dell_educazione",
        "economia_agraria", "economia_regionale",
        "politica_economica", "storia_del_pensiero_economico",
        "economia_digitale", "economia_circolare",
    ],
    "management_business": [
        "strategia_aziendale", "marketing_management", "marketing_digitale",
        "gestione_risorse_umane", "organizational_behavior",
        "operations_management", "supply_chain_management",
        "project_management", "change_management",
        "imprenditorialita", "startup_management", "venture_capital",
        "management_internazionale", "cross_cultural_management",
        "leadership", "decision_making",
        "business_ethics", "corporate_governance", "CSR",
        "innovation_management", "knowledge_management",
        "business_analytics", "data_driven_management",
    ],
    "contabilita_finanza": [
        "ragioneria_generale", "contabilita_analitica", "contabilita_internazionale",
        "revisione_contabile", "auditing", "internal_auditing",
        "finanza_aziendale", "corporate_finance",
        "mercati_finanziari", "investment_banking", "asset_management",
        "risk_management", "financial_engineering",
        "finanza_pubblica", "economia_monetaria_applicata",
        "finanza_comportamentale", "fintech",
        "assicurazioni", "scienze_attuariali",
        "compliance", "antiriciclaggio", "regolamentazione_finanziaria",
    ],

    # ═══════════════════════════════════════════════════════════
    # TECNOLOGIA E INGEGNERIA
    # ═══════════════════════════════════════════════════════════
    "informatica": [
        "algoritmi", "strutture_dati", "complessita_computazionale",
        "teoria_della_computazione", "linguaggi_formali",
        "intelligenza_artificiale", "machine_learning", "deep_learning",
        "NLP_computazionale", "computer_vision", "robotica_AI",
        "reinforcement_learning", "AI_generativa", "LLM",
        "cybersecurity", "crittografia", "sicurezza_delle_reti",
        "database", "big_data", "data_engineering", "data_science",
        "ingegneria_del_software", "DevOps", "architetture_software",
        "cloud_computing", "edge_computing", "serverless",
        "reti_di_calcolatori", "sistemi_distribuiti",
        "sistemi_operativi", "compilatori", "grafica_computazionale",
        "interazione_uomo_macchina", "UX_design",
        "blockchain", "quantum_computing", "realta_virtuale", "realta_aumentata",
    ],
    "ingegneria": [
        "ingegneria_civile", "ingegneria_strutturale", "geotecnica",
        "ingegneria_idraulica", "ingegneria_dei_trasporti",
        "ingegneria_meccanica", "meccanica_dei_solidi", "meccanica_dei_fluidi",
        "ingegneria_termica", "ingegneria_energetica",
        "ingegneria_elettrica", "ingegneria_elettronica",
        "ingegneria_chimica", "ingegneria_dei_processi",
        "ingegneria_aerospaziale", "ingegneria_aeronautica",
        "ingegneria_navale", "ingegneria_offshore",
        "ingegneria_biomedica", "ingegneria_clinica",
        "ingegneria_nucleare", "ingegneria_dei_materiali",
        "ingegneria_ambientale", "ingegneria_sismica",
        "robotica", "meccatronica", "automazione",
        "ingegneria_gestionale", "ingegneria_della_sicurezza",
        "ingegneria_acustica", "ingegneria_ottica",
    ],
    "telecomunicazioni": [
        "reti_di_telecomunicazione", "reti_wireless", "reti_5G_6G",
        "fibra_ottica", "comunicazioni_satellitari",
        "internet_of_things", "smart_city", "domotica",
        "elaborazione_dei_segnali", "teoria_dei_segnali",
        "microelettronica", "nanoelettronica", "VLSI",
        "sistemi_embedded", "FPGA", "circuiti_integrati",
        "antenne", "propagazione_elettromagnetica",
        "codifica_di_canale", "compressione_dati",
        "protocolli_di_rete", "software_defined_networking",
    ],
    "biotecnologia_nanotecnologia": [
        "biotecnologia_medica", "biotecnologia_farmaceutica",
        "biotecnologia_industriale", "biotecnologia_ambientale",
        "biotecnologia_agraria", "biotecnologia_alimentare",
        "ingegneria_genetica", "terapia_genica", "editing_genomico_CRISPR",
        "biofarmaci", "anticorpi_monoclonali", "vaccini_ricombinanti",
        "bioinformatica_strutturale", "proteomica_computazionale",
        "nanotecnologia", "nanomateriali", "nanoparticelle",
        "nanomedicina", "nanosensori", "nanoelettronica",
        "biologia_sintetica", "bioingegneria",
    ],

    # ═══════════════════════════════════════════════════════════
    # ARTI, DESIGN E COMUNICAZIONE
    # ═══════════════════════════════════════════════════════════
    "arti_visive_performative": [
        "pittura", "scultura", "disegno", "incisione", "stampa_d_arte",
        "fotografia", "fotografia_digitale", "video_arte",
        "installazioni", "arte_concettuale", "arte_contemporanea",
        "street_art", "land_art", "arte_digitale", "NFT_art",
        "teatro", "regia_teatrale", "drammaturgia", "recitazione",
        "danza_classica", "danza_contemporanea", "danza_moderna",
        "performance_art", "happening", "mimo",
        "storia_dell_arte", "critica_d_arte", "curatela",
        "restauro", "conservazione_beni_culturali",
    ],
    "musica": [
        "teoria_musicale", "armonia", "contrappunto", "orchestrazione",
        "composizione", "composizione_elettronica", "musica_elettroacustica",
        "musicologia", "etnomusicologia", "sociologia_della_musica",
        "storia_della_musica", "musica_medievale", "musica_rinascimentale",
        "musica_barocca", "musica_classica", "musica_romantica",
        "musica_contemporanea", "musica_pop", "musica_rock", "musica_jazz",
        "musica_elettronica", "musica_hip_hop", "musica_world",
        "acustica_musicale", "psicoacustica",
        "tecnologie_musicali", "produzione_musicale", "sound_design",
        "didattica_musicale", "musicoterapia",
    ],
    "cinema_media": [
        "regia_cinematografica", "sceneggiatura", "montaggio",
        "fotografia_cinematografica", "scenografia", "costumi",
        "produzione_cinematografica", "distribuzione", "festival",
        "storia_del_cinema", "teoria_del_cinema", "critica_cinematografica",
        "documentario", "animazione", "cortometraggio",
        "giornalismo", "giornalismo_investigativo", "giornalismo_digitale",
        "comunicazione_di_massa", "media_studies", "cultural_studies",
        "semiotica", "retorica_visiva", "analisi_del_discorso_mediale",
        "pubbliche_relazioni", "comunicazione_d_impresa",
        "social_media", "content_creation", "digital_marketing",
        "radio", "televisione", "podcast", "streaming",
    ],
    "design_moda_architettura": [
        "industrial_design", "product_design", "interaction_design",
        "UX_UI_design", "graphic_design", "typography",
        "fashion_design", "textile_design", "fashion_marketing",
        "gioielleria", "accessori",
        "architettura", "architettura_sostenibile", "bioarchitettura",
        "architettura_d_interni", "architettura_del_paesaggio",
        "urbanistica", "pianificazione_territoriale",
        "restauro_architettonico", "storia_dell_architettura",
        "design_thinking", "service_design",
    ],

    # ═══════════════════════════════════════════════════════════
    # SCIENZE APPLICATE E PROFESSIONALI
    # ═══════════════════════════════════════════════════════════
    "agraria_alimentare": [
        "agronomia", "coltivazioni_erbacee", "coltivazioni_arboree",
        "orticoltura", "viticoltura", "enologia",
        "selvicoltura", "scienze_forestali",
        "zootecnia", "acquacoltura", "apicoltura",
        "scienza_dell_alimentazione", "nutrizione_umana", "dietetica",
        "tecnologia_alimentare", "food_engineering",
        "sicurezza_alimentare", "HACCP", "controllo_qualita",
        "agricoltura_biologica", "agricoltura_di_precisione",
        "agroecologia", "sviluppo_rurale",
    ],
    "scienze_ambientali": [
        "ecologia_applicata", "ecologia_del_restauro",
        "cambiamento_climatico", "mitigazione", "adattamento",
        "energia_rinnovabile", "energia_solare", "energia_eolica",
        "energia_geotermica", "energia_idroelettrica", "bioenergia",
        "gestione_dei_rifiuti", "economia_circolare_applicata",
        "inquinamento_atmosferico", "inquinamento_idrico",
        "inquinamento_del_suolo", "bonifica_ambientale",
        "valutazione_impatto_ambientale", "VIA", "VAS",
        "ESG", "sostenibilita_aziendale", "green_finance",
        "biodiversita", "conservazione_della_natura", "aree_protette",
        "diritto_ambientale_applicato", "politiche_ambientali",
    ],
    "scienze_motorie_sport": [
        "fisiologia_dell_esercizio", "biomeccanica", "chinesiologia",
        "allenamento_sportivo", "coaching", "preparazione_atletica",
        "medicina_dello_sport", "traumatologia_sportiva",
        "psicologia_dello_sport", "mental_coaching",
        "nutrizione_sportiva", "supplementazione",
        "management_sportivo", "diritto_sportivo",
        "sport_per_disabili", "sport_adattato",
        "attivita_motoria_preventiva", "fitness", "wellness",
        "storia_dello_sport", "sociologia_dello_sport",
    ],
    "turismo_ospitalita": [
        "hospitality_management", "hotel_management", "food_beverage",
        "revenue_management", "event_management",
        "turismo_culturale", "turismo_enogastronomico",
        "turismo_sostenibile", "ecoturismo",
        "turismo_digitale", "destination_management",
        "marketing_turistico", "comunicazione_turistica",
        "geografia_del_turismo", "economia_del_turismo",
        "legislazione_turistica", "trasporti_turistici",
    ],
    "criminologia_forensi": [
        "criminologia_generale", "criminologia_clinica",
        "sociologia_della_devianza", "vittimologia",
        "criminal_profiling", "analisi_della_scena_del_crimine",
        "balistica", "dattiloscopia", "analisi_DNA_forense",
        "tossicologia_forense", "entomologia_forense",
        "antropologia_forense", "odontologia_forense",
        "digital_forensics", "cyber_forensics",
        "psicologia_giuridica_forense", "psichiatria_forense",
        "medicina_legale", "patologia_forense",
        "sicurezza_urbana", "politiche_penali",
    ],

    # ═══════════════════════════════════════════════════════════
    # INTERDISCIPLINARE E EMERGENTE
    # ═══════════════════════════════════════════════════════════
    "biblioteconomia_archivistica": [
        "biblioteconomia", "catalogazione", "classificazione",
        "reference_service", "information_literacy",
        "archivistica", "diplomatica", "paleografia",
        "museologia", "museografia", "curatela_museale",
        "conservazione_preventiva", "restauro_materiale_librario",
        "digitalizzazione", "digital_preservation", "digital_humanities",
        "data_curation", "open_access", "open_data",
        "gestione_collezioni", "bibliometria", "scientometria",
    ],
    "studi_genere_interculturali": [
        "gender_studies", "studi_femministi", "studi_maschili",
        "studi_LGBTQ", "queer_theory",
        "studi_postcoloniali", "studi_decoloniali",
        "studi_sulla_diaspora", "studi_sulla_migrazione",
        "studi_interculturali", "multiculturalismo",
        "intersezionalita", "critical_race_theory",
        "studi_subaltern", "studi_sul_corpo",
        "ecofemminismo", "transfemminismo",
        "disability_studies", "studi_sulla_disabilita",
    ],
}


# ============================================================
# DATACLASSES
# ============================================================

@dataclass
class DocumentoBase:
    """Struttura base per ogni documento nella biblioteca."""
    id: str = ""
    titolo: str = ""
    autore: str = ""
    contenuto: str = ""
    lingua: str = "it"
    anno: Optional[int] = None
    categoria: str = ""
    sotto_disciplina: str = ""
    fonte_tipo: str = ""           # book, article, thesis, archive, online, patent
    isbn: str = ""
    doi: str = ""
    issn: str = ""
    editore: str = ""
    rivista: str = ""
    url: str = ""
    classificazione_dewey: str = ""
    classificazione_loc: str = ""  # Library of Congress
    affidabilita: float = 1.0      # 0.0 — 1.0
    peer_reviewed: bool = False
    parole_chiave: str = ""        # Comma-separated
    abstract: str = ""
    note: str = ""
    data_inserimento: float = 0.0


# ============================================================
# DATABASE MANAGER
# ============================================================

class BibliotecaDigitale:
    """
    Biblioteca Digitale Universale — Database relazionale strutturato
    con 42 categorie (copertura globale completa), FTS5 per ricerca
    testuale, indici ottimizzati, sotto-discipline per ogni categoria.
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or BIBLIOTECA_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_database()

    @contextmanager
    def _conn(self):
        """Context manager per connessione thread-safe."""
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        """Crea tutte le tabelle della biblioteca digitale."""
        with self._conn() as conn:
            # ── TABELLA PRINCIPALE: documenti (unificata) ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documenti (
                    id TEXT PRIMARY KEY,
                    titolo TEXT NOT NULL,
                    autore TEXT NOT NULL DEFAULT '',
                    contenuto TEXT NOT NULL DEFAULT '',
                    lingua TEXT DEFAULT 'it',
                    anno INTEGER,
                    categoria TEXT NOT NULL,
                    sotto_disciplina TEXT DEFAULT '',
                    fonte_tipo TEXT DEFAULT 'book',
                    isbn TEXT DEFAULT '',
                    doi TEXT DEFAULT '',
                    issn TEXT DEFAULT '',
                    editore TEXT DEFAULT '',
                    rivista TEXT DEFAULT '',
                    url TEXT DEFAULT '',
                    classificazione_dewey TEXT DEFAULT '',
                    classificazione_loc TEXT DEFAULT '',
                    affidabilita REAL DEFAULT 1.0,
                    peer_reviewed INTEGER DEFAULT 0,
                    parole_chiave TEXT DEFAULT '',
                    abstract TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    data_inserimento REAL DEFAULT 0,
                    word_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0
                )
            """)

            # ── TABELLE PER CATEGORIA (viste + tabelle specializzate) ──

            # Libri — dettagli editoriali
            conn.execute("""
                CREATE TABLE IF NOT EXISTS libri_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    edizione TEXT DEFAULT '',
                    numero_pagine INTEGER,
                    collana TEXT DEFAULT '',
                    traduttore TEXT DEFAULT '',
                    lingua_originale TEXT DEFAULT '',
                    genere_letterario TEXT DEFAULT ''
                )
            """)

            # Articoli accademici — dettagli pubblicazione
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articoli_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    volume TEXT DEFAULT '',
                    numero TEXT DEFAULT '',
                    pagine TEXT DEFAULT '',
                    impact_factor REAL,
                    citazioni INTEGER DEFAULT 0,
                    tipo_articolo TEXT DEFAULT ''
                )
            """)

            # Documenti storici — dettagli archivistici
            conn.execute("""
                CREATE TABLE IF NOT EXISTS storici_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    epoca TEXT DEFAULT '',
                    civilta TEXT DEFAULT '',
                    area_geografica TEXT DEFAULT '',
                    tipo_documento TEXT DEFAULT '',
                    archivio_provenienza TEXT DEFAULT '',
                    stato_conservazione TEXT DEFAULT ''
                )
            """)

            # Fonti online — dettagli web
            conn.execute("""
                CREATE TABLE IF NOT EXISTS online_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    nome_sito TEXT DEFAULT '',
                    tipo_contenuto TEXT DEFAULT '',
                    data_ultimo_accesso TEXT DEFAULT '',
                    licenza TEXT DEFAULT '',
                    verificato INTEGER DEFAULT 0
                )
            """)

            # Ricerche universitarie — dettagli accademici
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ricerche_dettagli (
                    doc_id TEXT PRIMARY KEY REFERENCES documenti(id),
                    universita TEXT DEFAULT '',
                    dipartimento TEXT DEFAULT '',
                    tipo_tesi TEXT DEFAULT '',
                    relatore TEXT DEFAULT '',
                    anno_accademico TEXT DEFAULT ''
                )
            """)

            # ── TABELLA AUTORI (normalizzata) ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS autori (
                    id TEXT PRIMARY KEY,
                    nome TEXT NOT NULL,
                    cognome TEXT NOT NULL DEFAULT '',
                    nazionalita TEXT DEFAULT '',
                    anno_nascita INTEGER,
                    anno_morte INTEGER,
                    specializzazione TEXT DEFAULT '',
                    istituzione TEXT DEFAULT '',
                    h_index INTEGER,
                    orcid TEXT DEFAULT ''
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS documento_autore (
                    doc_id TEXT REFERENCES documenti(id),
                    autore_id TEXT REFERENCES autori(id),
                    ruolo TEXT DEFAULT 'autore',
                    PRIMARY KEY (doc_id, autore_id)
                )
            """)

            # ── FTS5 per ricerca full-text ──
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documenti_fts USING fts5(
                    id, titolo, autore, contenuto, abstract, parole_chiave,
                    categoria, sotto_disciplina, lingua,
                    tokenize='unicode61 remove_diacritics 2'
                )
            """)

            # ── INDICI per performance ──
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_categoria ON documenti(categoria)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_sotto ON documenti(sotto_disciplina)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_lingua ON documenti(lingua)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_anno ON documenti(anno)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_autore ON documenti(autore)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_affid ON documenti(affidabilita)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_isbn ON documenti(isbn)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_doi ON documenti(doi)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_tipo ON documenti(fonte_tipo)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_peer ON documenti(peer_reviewed)")

            # ── STATISTICHE ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS statistiche_biblioteca (
                    chiave TEXT PRIMARY KEY,
                    valore TEXT,
                    aggiornato_il REAL
                )
            """)

    # ========================================================
    # INSERIMENTO DOCUMENTI
    # ========================================================

    def aggiungi_documento(self, doc: DocumentoBase) -> str:
        """Aggiungi un documento alla biblioteca."""
        if not doc.id:
            doc.id = str(uuid.uuid4())[:16]
        if not doc.data_inserimento:
            doc.data_inserimento = time.time()

        word_count = len(doc.contenuto.split())
        char_count = len(doc.contenuto)

        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO documenti
                (id, titolo, autore, contenuto, lingua, anno, categoria,
                 sotto_disciplina, fonte_tipo, isbn, doi, issn, editore,
                 rivista, url, classificazione_dewey, classificazione_loc,
                 affidabilita, peer_reviewed, parole_chiave, abstract, note,
                 data_inserimento, word_count, char_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc.id, doc.titolo, doc.autore, doc.contenuto, doc.lingua,
                doc.anno, doc.categoria, doc.sotto_disciplina, doc.fonte_tipo,
                doc.isbn, doc.doi, doc.issn, doc.editore, doc.rivista, doc.url,
                doc.classificazione_dewey, doc.classificazione_loc,
                doc.affidabilita, 1 if doc.peer_reviewed else 0,
                doc.parole_chiave, doc.abstract, doc.note,
                doc.data_inserimento, word_count, char_count,
            ))

            # Aggiorna FTS
            conn.execute(
                "INSERT OR REPLACE INTO documenti_fts "
                "(id, titolo, autore, contenuto, abstract, parole_chiave, "
                "categoria, sotto_disciplina, lingua) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (doc.id, doc.titolo, doc.autore, doc.contenuto,
                 doc.abstract, doc.parole_chiave, doc.categoria,
                 doc.sotto_disciplina, doc.lingua)
            )

        return doc.id

    def aggiungi_batch(self, documenti: list[DocumentoBase]) -> int:
        """Aggiungi batch di documenti (ottimizzato)."""
        count = 0
        with self._conn() as conn:
            for doc in documenti:
                if not doc.id:
                    doc.id = str(uuid.uuid4())[:16]
                if not doc.data_inserimento:
                    doc.data_inserimento = time.time()

                word_count = len(doc.contenuto.split())
                char_count = len(doc.contenuto)

                conn.execute("""
                    INSERT OR REPLACE INTO documenti
                    (id, titolo, autore, contenuto, lingua, anno, categoria,
                     sotto_disciplina, fonte_tipo, isbn, doi, issn, editore,
                     rivista, url, classificazione_dewey, classificazione_loc,
                     affidabilita, peer_reviewed, parole_chiave, abstract, note,
                     data_inserimento, word_count, char_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc.id, doc.titolo, doc.autore, doc.contenuto, doc.lingua,
                    doc.anno, doc.categoria, doc.sotto_disciplina, doc.fonte_tipo,
                    doc.isbn, doc.doi, doc.issn, doc.editore, doc.rivista, doc.url,
                    doc.classificazione_dewey, doc.classificazione_loc,
                    doc.affidabilita, 1 if doc.peer_reviewed else 0,
                    doc.parole_chiave, doc.abstract, doc.note,
                    doc.data_inserimento, word_count, char_count,
                ))

                conn.execute(
                    "INSERT OR REPLACE INTO documenti_fts "
                    "(id, titolo, autore, contenuto, abstract, parole_chiave, "
                    "categoria, sotto_disciplina, lingua) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (doc.id, doc.titolo, doc.autore, doc.contenuto,
                     doc.abstract, doc.parole_chiave, doc.categoria,
                     doc.sotto_disciplina, doc.lingua)
                )
                count += 1

        return count

    # ========================================================
    # RICERCA
    # ========================================================

    def cerca(
        self,
        query: str,
        categoria: Optional[str] = None,
        sotto_disciplina: Optional[str] = None,
        lingua: Optional[str] = None,
        anno_da: Optional[int] = None,
        anno_a: Optional[int] = None,
        min_affidabilita: float = 0.0,
        solo_peer_reviewed: bool = False,
        limite: int = 20,
    ) -> list[dict]:
        """
        Ricerca avanzata nella biblioteca con FTS5 + filtri.
        """
        with self._conn() as conn:
            # Sanitizza query per FTS5
            safe_query = re.sub(r'[^\w\s]', ' ', query)
            terms = [w for w in safe_query.split() if len(w) > 2]
            if not terms:
                return []
            fts_query = " OR ".join(terms)

            # Base query FTS5
            sql = """
                SELECT d.*, bm25(documenti_fts) as score
                FROM documenti_fts f
                JOIN documenti d ON d.id = f.id
                WHERE documenti_fts MATCH ?
            """
            params = [fts_query]

            # Filtri opzionali
            if categoria:
                sql += " AND d.categoria = ?"
                params.append(categoria)
            if sotto_disciplina:
                sql += " AND d.sotto_disciplina = ?"
                params.append(sotto_disciplina)
            if lingua:
                sql += " AND d.lingua = ?"
                params.append(lingua)
            if anno_da:
                sql += " AND d.anno >= ?"
                params.append(anno_da)
            if anno_a:
                sql += " AND d.anno <= ?"
                params.append(anno_a)
            if min_affidabilita > 0:
                sql += " AND d.affidabilita >= ?"
                params.append(min_affidabilita)
            if solo_peer_reviewed:
                sql += " AND d.peer_reviewed = 1"

            sql += " ORDER BY bm25(documenti_fts) LIMIT ?"
            params.append(limite)

            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def cerca_per_autore(self, autore: str, limite: int = 50) -> list[dict]:
        """Cerca documenti per autore."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM documenti WHERE autore LIKE ? ORDER BY anno DESC LIMIT ?",
                (f"%{autore}%", limite)
            ).fetchall()
            return [dict(row) for row in rows]

    def cerca_per_isbn(self, isbn: str) -> Optional[dict]:
        """Cerca documento per ISBN."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM documenti WHERE isbn = ?", (isbn.replace("-", ""),)
            ).fetchone()
            return dict(row) if row else None

    def cerca_per_doi(self, doi: str) -> Optional[dict]:
        """Cerca documento per DOI."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM documenti WHERE doi = ?", (doi,)).fetchone()
            return dict(row) if row else None

    # ========================================================
    # STATISTICHE
    # ========================================================

    def statistiche(self) -> dict:
        """Statistiche complete della biblioteca."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM documenti").fetchone()[0]

            # Per categoria
            cats = conn.execute(
                "SELECT categoria, COUNT(*) as n FROM documenti GROUP BY categoria ORDER BY n DESC"
            ).fetchall()

            # Per lingua
            lingue = conn.execute(
                "SELECT lingua, COUNT(*) as n FROM documenti GROUP BY lingua ORDER BY n DESC"
            ).fetchall()

            # Per tipo fonte
            tipi = conn.execute(
                "SELECT fonte_tipo, COUNT(*) as n FROM documenti GROUP BY fonte_tipo ORDER BY n DESC"
            ).fetchall()

            # Parole totali
            words = conn.execute("SELECT SUM(word_count) FROM documenti").fetchone()[0] or 0

            # Range anni
            anni = conn.execute(
                "SELECT MIN(anno), MAX(anno) FROM documenti WHERE anno IS NOT NULL"
            ).fetchone()

            return {
                "totale_documenti": total,
                "totale_parole": words,
                "per_categoria": {row[0]: row[1] for row in cats},
                "per_lingua": {row[0]: row[1] for row in lingue},
                "per_tipo_fonte": {row[0]: row[1] for row in tipi},
                "anno_piu_antico": anni[0] if anni else None,
                "anno_piu_recente": anni[1] if anni else None,
                "categorie_disponibili": list(CATEGORIE.keys()),
            }

    def lista_categorie(self) -> list[dict]:
        """Lista tutte le categorie con descrizione e conteggi."""
        with self._conn() as conn:
            result = []
            for key, info in CATEGORIE.items():
                count = conn.execute(
                    "SELECT COUNT(*) FROM documenti WHERE categoria = ?", (key,)
                ).fetchone()[0]
                result.append({
                    "chiave": key,
                    "nome": info["nome"],
                    "descrizione": info["descrizione"],
                    "documenti": count,
                    "sotto_discipline": SOTTO_DISCIPLINE.get(key, []),
                })
            return result


# ============================================================
# SINGLETON
# ============================================================

_biblioteca: Optional[BibliotecaDigitale] = None


def get_biblioteca(db_path: str = "") -> BibliotecaDigitale:
    """Ottieni l'istanza singleton della Biblioteca Digitale."""
    global _biblioteca
    if _biblioteca is None:
        _biblioteca = BibliotecaDigitale(db_path=db_path)
    return _biblioteca
