import os
import google.generativeai as genai
import requests
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify # jsonify est crucial
from dotenv import load_dotenv
import mysql.connector
import json
import re

load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24) # Pour les flash messages de l'UI web et la session

DB_CONFIG = {
    'host': os.getenv("DB_HOST"), 'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"), 'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4'
}

# --- Initialisation des Modèles IA ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_model_instance = None
gemini_model_name = 'models/gemini-1.5-flash-latest'
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_instance = genai.GenerativeModel(gemini_model_name)
        print(f"Modèle Gemini '{gemini_model_name}' initialisé.")
    except Exception as e:
        print(f"ERREUR initialisation Gemini: {e}")
        gemini_model_instance = None # S'assurer qu'il est None en cas d'échec
else:
    print("ERREUR : GOOGLE_API_KEY non définie.")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_model_name = "llama3-8b-8192"
if not GROQ_API_KEY:
    print("ERREUR : GROQ_API_KEY non définie.")
# ------------------------------------

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        # Pour l'API, on ne flashera pas, on loguera ou on retournera une erreur JSON
        print(f"Erreur de connexion à la base de données: {err}")
        return None

# --- Fonctions Métier (IA et Parsing) ---
def generer_questions_ia(texte_source_francais):
    if not gemini_model_instance: return None, "Modèle Gemini non initialisé."
    if not texte_source_francais or not texte_source_francais.strip():
        return None, "Le texte source fourni pour la génération de questions est vide."
    
    prompt_generation_francais = f"""
    Vous êtes un assistant pédagogique spécialisé en langue française. Votre tâche est de lire le texte suivant fourni par un enseignant et de créer 5 questions **ouvertes** basées sur ce texte.
    Ces questions doivent exiger une réflexion et une compréhension du texte, et non une simple récupération directe d'informations.
    Concentrez-vous sur les causes, les conséquences, les comparaisons ou les applications potentielles mentionnées ou pouvant être déduites du texte.
    Évitez les questions auxquelles on peut répondre par "oui" ou "non" ou par un seul mot.
    Les questions et le format de sortie doivent être ENTIÈREMENT EN FRANÇAIS.

    Texte fourni par l'enseignant (en français) :
    ---
    {texte_source_francais}
    ---

    Questions suggérées (écrivez 5 questions ouvertes ici, chaque question sur une nouvelle ligne, EN FRANÇAIS, sans numérotation explicite comme "1." au début de chaque ligne, juste le texte de la question) :
    """
    try:
        response = gemini_model_instance.generate_content(prompt_generation_francais)
        if response and hasattr(response, 'text') and response.text:
            # Séparer par saut de ligne, enlever les lignes vides
            questions_list = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
            # Enlever une éventuelle numérotation (ex: "1. Question" -> "Question")
            cleaned_questions = []
            for q_text in questions_list:
                match_num = re.match(r"^\d+\.\s*(.*)", q_text)
                if match_num:
                    cleaned_questions.append(match_num.group(1))
                else:
                    cleaned_questions.append(q_text)
            
            if not cleaned_questions and response.text.strip():
                 if "Please provide me with a prompt" in response.text:
                     return None, "L'API Gemini demande un prompt."
                 return None, f"Format de réponse inattendu de Gemini : {response.text[:200]}"
            return cleaned_questions, None
        else: return None, "Réponse vide ou attribut 'text' manquant de l'API Gemini."
    except Exception as e: return None, f"Erreur API Gemini: {e}"

def parse_feedback_structuré(feedback_brut_ia):
    parsed_data = {"reponse_corrigee": "N/A", "erreurs_detectees": "N/A", "evaluation_note": "N/A", "justification_evaluation": "N/A"}
    if not feedback_brut_ia: return parsed_data
    
    match_rc = re.search(r"\*\*Réponse corrigée\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia, re.IGNORECASE)
    if match_rc: parsed_data["reponse_corrigee"] = match_rc.group(1).strip()
    match_ed = re.search(r"\*\*Erreurs détectées\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia, re.IGNORECASE)
    if match_ed: parsed_data["erreurs_detectees"] = match_ed.group(1).strip()
    match_en = re.search(r"\*\*Évaluation\s*:\*\*\s*(?:Je donne à cette réponse\s*:)?\s*([\d\.\s\/]+)\s*\/\s*10", feedback_brut_ia, re.IGNORECASE)
    if match_en: parsed_data["evaluation_note"] = match_en.group(1).strip() + "/10"
    else:
        match_en_simple = re.search(r"\*\*Évaluation\s*:\*\*\s*([\d\.]+)\s*\/\s*10", feedback_brut_ia, re.IGNORECASE)
        if match_en_simple: parsed_data["evaluation_note"] = match_en_simple.group(1).strip() + "/10"
    match_je = re.search(r"\*\*(?:Justification de l'évaluation|Raison de l'évaluation)\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia, re.IGNORECASE)
    if match_je: parsed_data["justification_evaluation"] = match_je.group(1).strip()
    
    # Nettoyages pour éviter les chevauchements des regex
    if parsed_data["reponse_corrigee"] != "N/A" and "**Erreurs détectées" in parsed_data["reponse_corrigee"]:
        parsed_data["reponse_corrigee"] = parsed_data["reponse_corrigee"].split("**Erreurs détectées")[0].strip()
    if parsed_data["erreurs_detectees"] != "N/A" and "**Évaluation" in parsed_data["erreurs_detectees"]:
        parsed_data["erreurs_detectees"] = parsed_data["erreurs_detectees"].split("**Évaluation")[0].strip()
    if parsed_data["evaluation_note"] != "N/A" and "**Justification" in parsed_data["evaluation_note"]: # Peu probable mais sait-on jamais
        # Cela ne devrait pas arriver si la regex de la note est bonne
        parsed_data["evaluation_note"] = parsed_data["evaluation_note"].split("**Justification")[0].strip()

    return parsed_data

def evaluer_reponse_ia(texte_source_eval_francais, question_eval_francais, reponse_etudiant_eval_francais):
    if not GROQ_API_KEY: return None, None, "Clé API Groq non configurée."
    if not all([texte_source_eval_francais, question_eval_francais, reponse_etudiant_eval_francais]):
        return None, None, "Champs manquants pour l'évaluation."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt_evaluation_francais = f"""
    Vous êtes un professeur de français expérimenté. Votre mission est de corriger la réponse d'un étudiant à une question portant sur un texte donné.
    L'ensemble de votre feedback doit être ENTIÈREMENT EN FRANÇAIS.

    👇 Informations fournies :
    Texte source (en français) : {texte_source_eval_francais}
    Question (en français) : {question_eval_francais}
    Réponse de l'étudiant (en français) : {reponse_etudiant_eval_francais}

    ✅ Veuillez fournir le résultat au format suivant (et UNIQUEMENT EN FRANÇAIS), en utilisant exactement ces intitulés en gras :

    **Réponse corrigée :**
    [Votre texte pour la réponse corrigée ici]

    **Erreurs détectées :**
    [Vos listes ou paragraphes pour les erreurs ici]

    **Évaluation :**
    [Note ici, par exemple 7.5] / 10

    **Justification de l'évaluation :**
    [Votre texte pour la justification ici]
    """
    data = {"model": groq_model_name, "messages": [{"role": "user", "content": prompt_evaluation_francais}], "temperature": 0.3}
    try:
        response_api = requests.post(url, headers=headers, json=data, timeout=60)
        response_api.raise_for_status()
        result = response_api.json()
        if result.get("choices") and result["choices"][0].get("message", {}).get("content"):
            feedback_brut = result["choices"][0]["message"]["content"]
            parsed_feedback = parse_feedback_structuré(feedback_brut)
            return feedback_brut, parsed_feedback, None
        return None, None, f"Réponse inattendue de l'API Groq: {result}"
    except Exception as e:
        return None, None, f"Erreur API Groq: {e}"
# ------------------------------------

# --- ENDPOINTS API POUR UNITY ---
@app.route('/api/textes', methods=['POST'])
def api_creer_texte():
    if not request.is_json:
        return jsonify({"erreur": "La requête doit être au format JSON"}), 415 # Unsupported Media Type
    data = request.get_json()
    if not data or 'texteContent' not in data:
        return jsonify({"erreur": "Données manquantes : 'texteContent' est requis"}), 400

    texte_manuel = data['texteContent']
    niveau_l = data.get('niveauL', 'A')
    niveau_c_str = str(data.get('niveauC', '1')) # S'assurer que c'est une chaîne pour isdigit
    
    if not isinstance(texte_manuel, str) or not texte_manuel.strip():
        return jsonify({"erreur": "'texteContent' doit être une chaîne non vide"}), 400
    if not isinstance(niveau_l, str) or len(niveau_l) > 10: # Limite arbitraire pour niveauL
        return jsonify({"erreur": "'niveauL' doit être une chaîne courte"}), 400
    if not niveau_c_str.isdigit():
        return jsonify({"erreur": "'niveauC' doit être un entier"}), 400
    niveau_c = int(niveau_c_str)


    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "Connexion BDD impossible"}), 500
    
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO texte (texteContent, niveauL, niveauC) VALUES (%s, %s, %s)"
            cursor.execute(sql, (texte_manuel, niveau_l, niveau_c))
            conn.commit()
            id_texte_cree = cursor.lastrowid
        return jsonify({"message": "Texte créé avec succès", "idTexte": id_texte_cree}), 201
    except mysql.connector.Error as err:
        return jsonify({"erreur": f"Erreur BDD lors de la création du texte: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/textes/<int:id_texte>/generer_questions_proposees', methods=['GET'])
def api_generer_questions_pour_texte(id_texte):
    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "Connexion BDD impossible"}), 500

    texte_a_utiliser = None
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT texteContent FROM texte WHERE idTexte = %s", (id_texte,))
            texte_obj = cursor.fetchone()
            if texte_obj:
                texte_a_utiliser = texte_obj['texteContent']
            else:
                return jsonify({"erreur": f"Texte avec ID {id_texte} non trouvé"}), 404
    except mysql.connector.Error as err:
        return jsonify({"erreur": f"Erreur DB: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close() # Fermer la connexion après lecture

    if texte_a_utiliser:
        liste_questions_ia, err_api = generer_questions_ia(texte_a_utiliser)
        if err_api:
            return jsonify({"erreur": f"Erreur API génération: {err_api}"}), 500
        elif liste_questions_ia is not None: # Peut être une liste vide si l'IA ne retourne rien
            return jsonify({
                "idTexte": id_texte,
                "questionsProposeesIA": liste_questions_ia
            }), 200
        else: # Cas où generer_questions_ia retourne (None, "Message d'erreur")
             return jsonify({"erreur": "Aucune question générée ou erreur inattendue lors de la génération"}), 500


@app.route('/api/questions_ouvertes', methods=['POST'])
def api_sauvegarder_questions_validees():
    if not request.is_json:
        return jsonify({"erreur": "La requête doit être au format JSON"}), 415
    data = request.get_json()
    if not data or 'idTexte' not in data or 'questionsValidees' not in data:
        return jsonify({"erreur": "Données manquantes: 'idTexte' et 'questionsValidees' (liste) requis"}), 400

    id_texte_associe = data['idTexte']
    questions_validees = data['questionsValidees']
    niveau_question = str(data.get('niveauQuestion', '1')) # Niveau par défaut '1'

    if not isinstance(questions_validees, list):
        return jsonify({"erreur": "'questionsValidees' doit être une liste de chaînes"}), 400
    if not questions_validees: # Permettre une liste vide si l'enseignant ne valide aucune question
        return jsonify({"message": "Aucune question à sauvegarder.", "idsQuestionsInserees": []}), 200


    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "Connexion BDD impossible"}), 500

    ids_questions_inserees = []
    try:
        with conn.cursor() as cursor:
            # Vérifier si le idTexte existe
            cursor.execute("SELECT COUNT(*) FROM texte WHERE idTexte = %s", (id_texte_associe,))
            if cursor.fetchone()[0] == 0:
                 return jsonify({"erreur": f"Le texte avec idTexte {id_texte_associe} n'existe pas."}), 404
            
            for q_texte in questions_validees:
                if not isinstance(q_texte, str) or not q_texte.strip():
                    # Ignorer les questions invalides ou permettre une erreur selon la politique
                    print(f"INFO: Question invalide ou vide ignorée: '{q_texte}'")
                    continue 
                sql = "INSERT INTO questionouvert (idTexte, question, niveau) VALUES (%s, %s, %s)"
                cursor.execute(sql, (id_texte_associe, q_texte.strip(), niveau_question))
                ids_questions_inserees.append(cursor.lastrowid)
            conn.commit()
        return jsonify({
            "message": f"{len(ids_questions_inserees)} question(s) sauvegardée(s) avec succès.",
            "idsQuestionsInserees": ids_questions_inserees
        }), 201
    except mysql.connector.Error as err:
        return jsonify({"erreur": f"Erreur BDD lors de la sauvegarde des questions: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/evaluations', methods=['POST'])
def api_evaluer_reponse_etudiant():
    if not request.is_json:
        return jsonify({"erreur": "La requête doit être au format JSON"}), 415
    data = request.get_json()
    if not data or 'idQO' not in data or 'reponseEtudiant' not in data:
        return jsonify({"erreur": "Données manquantes: 'idQO' et 'reponseEtudiant' requis"}), 400

    id_qo = data['idQO']
    reponse_etudiant = data['reponseEtudiant']
    # Optionnel: idEleve = data.get('idEleve'), idHys = data.get('idHys')

    if not isinstance(reponse_etudiant, str) or not reponse_etudiant.strip():
         return jsonify({"erreur": "'reponseEtudiant' doit être une chaîne non vide"}), 400

    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "Connexion BDD impossible"}), 500

    texte_source_db, question_db = None, None
    try:
        with conn.cursor(dictionary=True) as cursor:
            sql_get_q_and_text = """
                SELECT qo.question, t.texteContent 
                FROM questionouvert qo JOIN texte t ON qo.idTexte = t.idTexte
                WHERE qo.idQO = %s """
            cursor.execute(sql_get_q_and_text, (id_qo,))
            q_data = cursor.fetchone()
            if not q_data:
                return jsonify({"erreur": f"Question ouverte avec ID {id_qo} non trouvée."}), 404
            texte_source_db, question_db = q_data['texteContent'], q_data['question']
    except mysql.connector.Error as err:
        return jsonify({"erreur": f"Erreur DB récupération question: {err}"}), 500
    # La connexion reste ouverte pour l'insertion du feedback

    feedback_brut_ia, feedback_parse_ia, err_api = evaluer_reponse_ia(
        texte_source_db, question_db, reponse_etudiant
    )

    if err_api:
        if conn and conn.is_connected(): conn.close()
        return jsonify({"erreur": f"Erreur API évaluation: {err_api}"}), 500
    
    if feedback_parse_ia and feedback_brut_ia:
        try:
            with conn.cursor() as cursor:
                sql_insert = """INSERT INTO repence (
                                idQO, reponseEtudiant, reponseCorrigeeIA, erreursDetecteesIA, 
                                evaluationNoteIA, evaluationJustificationIA, feedbackCompletIA
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                params = (
                    id_qo, reponse_etudiant,
                    feedback_parse_ia.get("reponse_corrigee"), feedback_parse_ia.get("erreurs_detectees"),
                    feedback_parse_ia.get("evaluation_note"), feedback_parse_ia.get("justification_evaluation"),
                    feedback_brut_ia
                )
                cursor.execute(sql_insert, params)
                id_repence_creee = cursor.lastrowid
                conn.commit()
            return jsonify({
                "message": "Évaluation et feedback sauvegardés.",
                "idRepence": id_repence_creee,
                "feedbackStructure": feedback_parse_ia,
                "feedbackCompletIA": feedback_brut_ia # Optionnel de le retourner
            }), 201
        except mysql.connector.Error as err:
            return jsonify({"erreur": f"Erreur BDD sauvegarde évaluation: {err}"}), 500
        finally:
            if conn and conn.is_connected(): conn.close()
    else:
        if conn and conn.is_connected(): conn.close()
        return jsonify({"erreur": "Aucun feedback (brut ou parsé) reçu de l'IA."}), 500

# --- Route pour l'Interface Web HTML (votre code existant) ---
@app.route('/', methods=['GET', 'POST'])
def index():
    # ... (Collez ici votre code complet de la fonction index() pour l'interface web)
    # ... (Assurez-vous qu'elle utilise bien le template index_fr_v3.html ou le nom correct)
    # ... (Par exemple, la version de notre dernière discussion sur index_fr_v3.html)
    conn = get_db_connection()
    if not conn: return render_template('index_fr_v3.html', erreur_critique="Connexion BDD impossible.") # Utilisez le nom correct du template

    textes_db = []
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT idTexte, texteContent, niveauL, niveauC FROM texte ORDER BY idTexte DESC LIMIT 20")
            textes_db = cursor.fetchall()
    except mysql.connector.Error as err: flash(f"Erreur chargement textes: {err}", "danger")

    view_data = {
        "textes_db": textes_db,
        "texte_original_generation": session.get('texte_original_generation', ''),
        "id_texte_pour_generation": session.get('id_texte_pour_generation', None),
        "questions_proposees_ia": session.get('questions_proposees_ia', []),
        "questions_sauvegardees_avec_ids": [],
        "erreur_generation": None,
        "evaluation_resultat_structuré": None, 
        "feedback_complet_ia_pour_affichage": None, 
        "texte_source_eval_input": "", "question_eval_input": "", "id_qo_evalue": None,
        "reponse_etudiant_eval_input": "", "erreur_evaluation": None,
        "show_question_selection": session.get('show_question_selection', False)
    }
    
    if view_data["id_texte_pour_generation"]:
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT idQO, question FROM questionouvert WHERE idTexte = %s", (view_data["id_texte_pour_generation"],))
                view_data["questions_sauvegardees_avec_ids"] = cursor.fetchall()
        except mysql.connector.Error as err: flash(f"Erreur chargement questions sauvegardées: {err}", "danger")

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'generer_questions_pour_selection':
            session.pop('questions_proposees_ia', None); session.pop('show_question_selection', None)
            session.pop('id_texte_pour_generation', None); session.pop('texte_original_generation', None)
            id_texte_selectionne = request.form.get('texte_selectionne')
            texte_manuel = request.form.get('texte_manuel_generation', '').strip()
            niveau_l_manuel = request.form.get('niveau_l_manuel', 'A'); niveau_c_manuel = request.form.get('niveau_c_manuel', '1')
            texte_a_utiliser = ""; id_texte_actuel = None
            if id_texte_selectionne and id_texte_selectionne != "manuel":
                try:
                    with conn.cursor(dictionary=True) as cursor:
                        cursor.execute("SELECT idTexte, texteContent FROM texte WHERE idTexte = %s", (id_texte_selectionne,))
                        texte_obj = cursor.fetchone()
                        if texte_obj: texte_a_utiliser = texte_obj['texteContent']; id_texte_actuel = texte_obj['idTexte']
                        else: view_data["erreur_generation"] = "Texte sélectionné non trouvé."
                except mysql.connector.Error as err: view_data["erreur_generation"] = f"Erreur DB: {err}"
            elif texte_manuel:
                texte_a_utiliser = texte_manuel
                try:
                    with conn.cursor() as cursor:
                        sql = "INSERT INTO texte (texteContent, niveauL, niveauC) VALUES (%s, %s, %s)"
                        cursor.execute(sql, (texte_manuel, niveau_l_manuel, int(niveau_c_manuel)))
                        conn.commit(); id_texte_actuel = cursor.lastrowid; flash("Nouveau texte sauvegardé.", "success")
                        return redirect(url_for('index'))
                except (mysql.connector.Error, ValueError) as err: view_data["erreur_generation"] = f"Erreur sauvegarde nouveau texte: {err}"
            else: view_data["erreur_generation"] = "Veuillez sélectionner ou saisir un texte."

            if texte_a_utiliser and id_texte_actuel and not view_data["erreur_generation"]:
                liste_questions_ia, err_api = generer_questions_ia(texte_a_utiliser)
                if err_api: view_data["erreur_generation"] = err_api
                elif liste_questions_ia is not None: # Peut être une liste vide
                    session['questions_proposees_ia'] = liste_questions_ia; session['id_texte_pour_generation'] = id_texte_actuel
                    session['texte_original_generation'] = texte_a_utiliser; session['show_question_selection'] = True
                    flash("Questions IA générées. Sélectionnez pour sauvegarde.", "info")
            view_data.update({k: session.get(k) for k in ['questions_proposees_ia', 'id_texte_pour_generation', 'texte_original_generation', 'show_question_selection'] if session.get(k) is not None})
        elif action == 'sauvegarder_questions_selectionnees':
            questions_selectionnees_textes = request.form.getlist('questions_choisies')
            id_texte_associe = session.get('id_texte_pour_generation')
            if not questions_selectionnees_textes: flash("Aucune question sélectionnée.", "warning")
            elif not id_texte_associe: flash("Erreur : ID texte source manquant.", "danger")
            else:
                try:
                    with conn.cursor() as cursor:
                        for q_texte in questions_selectionnees_textes:
                            cursor.execute("INSERT INTO questionouvert (idTexte, question, niveau) VALUES (%s, %s, %s)", (id_texte_associe, q_texte, '1'))
                        conn.commit(); flash(f"{len(questions_selectionnees_textes)} question(s) sauvegardée(s).", "success")
                        session.pop('questions_proposees_ia', None); session['show_question_selection'] = False
                        return redirect(url_for('index'))
                except mysql.connector.Error as err: flash(f"Erreur sauvegarde questions: {err}", "danger")
            view_data.update({k: session.get(k) for k in ['questions_proposees_ia', 'id_texte_pour_generation', 'texte_original_generation', 'show_question_selection'] if session.get(k) is not None})
        elif action == 'evaluer_reponse':
            view_data["texte_source_eval_input"] = request.form.get('texte_source_evaluation', '')
            view_data["question_eval_input"] = request.form.get('question_evaluation_text', '')
            view_data["reponse_etudiant_eval_input"] = request.form.get('reponse_etudiant_evaluation', '')
            id_qo_a_evaluer = request.form.get('id_qo_pour_evaluation')
            view_data["texte_original_generation"] = session.get('texte_original_generation', '') # Conserver pour l'affichage
            view_data["id_texte_pour_generation"] = session.get('id_texte_pour_generation')     # Conserver pour l'affichage

            if not all([view_data["texte_source_eval_input"], view_data["question_eval_input"], view_data["reponse_etudiant_eval_input"], id_qo_a_evaluer]):
                view_data["erreur_evaluation"] = "Tous les champs sont requis pour l'évaluation."
            else:
                view_data["id_qo_evalue"] = int(id_qo_a_evaluer)
                feedback_brut_ia, feedback_parse_ia, err_api = evaluer_reponse_ia(
                    view_data["texte_source_eval_input"], view_data["question_eval_input"], view_data["reponse_etudiant_eval_input"]
                )
                if err_api: view_data["erreur_evaluation"] = err_api
                elif feedback_parse_ia and feedback_brut_ia:
                    view_data["evaluation_resultat_structuré"] = feedback_parse_ia
                    view_data["feedback_complet_ia_pour_affichage"] = feedback_brut_ia
                    try:
                        with conn.cursor() as cursor:
                            sql = """INSERT INTO repence (idQO, reponseEtudiant, reponseCorrigeeIA, erreursDetecteesIA, evaluationNoteIA, evaluationJustificationIA, feedbackCompletIA) 
                                     VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                            params = (view_data["id_qo_evalue"], view_data["reponse_etudiant_eval_input"],
                                      feedback_parse_ia.get("reponse_corrigee"), feedback_parse_ia.get("erreurs_detectees"),
                                      feedback_parse_ia.get("evaluation_note"), feedback_parse_ia.get("justification_evaluation"),
                                      feedback_brut_ia)
                            cursor.execute(sql, params)
                            conn.commit()
                            flash("Évaluation et feedback structuré sauvegardés.", "success")
                    except mysql.connector.Error as err:
                        flash(f"Erreur sauvegarde évaluation structurée: {err}", "danger")
                        print(f"ERREUR BDD insertion feedback structuré: {err}")
                else: view_data["erreur_evaluation"] = "Aucun feedback (brut ou parsé) reçu de l'IA."
    
    if conn and conn.is_connected(): conn.close()
    # Assurez-vous que le nom du template est correct
    return render_template('index_fr.html', **view_data) # ou index_fr.html si vous avez renommé


if __name__ == '__main__':
    # Choisissez un port différent si le port 5000 est déjà utilisé
    app.run(debug=True, host='0.0.0.0', port=5001)