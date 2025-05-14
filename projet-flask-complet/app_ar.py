import os
import google.generativeai as genai
import requests
from flask import Flask, request, render_template, redirect, url_for, flash, session, jsonify
from dotenv import load_dotenv
import mysql.connector
import json
import re

load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_CONFIG = {
    'host': os.getenv("DB_HOST"), 'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD"), 'database': os.getenv("DB_NAME"),
    'charset': 'utf8mb4' # Très important pour l'arabe
}

# --- Initialisation des Modèles IA ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_model_instance = None # Renommé pour clarté
gemini_model_name = 'models/gemini-1.5-flash-latest'
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model_instance = genai.GenerativeModel(gemini_model_name)
        print(f"نموذج Gemini '{gemini_model_name}' تم تهيئته بنجاح.") # Arabe
    except Exception as e:
        print(f"خطأ في تهيئة Gemini: {e}") # Arabe
        gemini_model_instance = None
else:
    print("خطأ : GOOGLE_API_KEY غير محدد.") # Arabe

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_model_name = "llama3-8b-8192"
if not GROQ_API_KEY:
    print("خطأ : GROQ_API_KEY غير محدد.") # Arabe
# ------------------------------------

def get_db_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"خطأ في الاتصال بقاعدة البيانات: {err}") # Arabe
        return None

# --- Fonctions Métier (IA et Parsing - PROMPTS EN ARABE) ---
def generer_questions_ia_ar(texte_source_arabe): # Nom de fonction spécifique pour l'arabe
    if not gemini_model_instance: return None, "نموذج Gemini غير مهيأ."
    if not texte_source_arabe or not texte_source_arabe.strip():
        return None, "النص المصدر المقدم لإنشاء الأسئلة فارغ."

    prompt_generation_arabe = f"""
    أنت مساعد تعليمي متخصص في اللغة العربية. مهمتك هي قراءة النص التالي الذي قدمه المعلم وإنشاء 5 أسئلة **مفتوحة** بناءً عليه.
    يجب أن تتطلب هذه الأسئلة تفكيرًا وفهمًا للنص، وليس مجرد استرجاع مباشر للمعلومات.
    ركز على الأسباب، النتائج، المقارنات، أو التطبيقات المحتملة المذكورة أو التي يمكن استنتاجها من النص.
    تجنب الأسئلة التي يمكن الإجابة عليها بـ "نعم" أو "لا" أو بكلمة واحدة.

    النص المقدم من المعلم (باللغة العربية):
    ---
    {texte_source_arabe}
    ---

    الأسئلة المقترحة (اكتب 5 أسئلة مفتوحة هنا، كل سؤال على سطر جديد، باللغة العربية، بدون ترقيم صريح مثل "1." في بداية كل سطر، فقط نص السؤال):
    """
    try:
        response = gemini_model_instance.generate_content(prompt_generation_arabe)
        if response and hasattr(response, 'text') and response.text:
            questions_list = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
            cleaned_questions = []
            for q_text in questions_list:
                match_num = re.match(r"^\d+\.\s*(.*)", q_text) # Gérer la numérotation si l'IA l'ajoute quand même
                if match_num: cleaned_questions.append(match_num.group(1))
                else: cleaned_questions.append(q_text)
            
            if not cleaned_questions and response.text.strip():
                 if "Please provide me with a prompt" in response.text: # Garder cette vérification générique
                     return None, "واجهة Gemini API تطلب موجهًا (prompt)."
                 return None, f"تنسيق استجابة غير متوقع من Gemini : {response.text[:200]}"
            return cleaned_questions, None
        else: return None, "استجابة فارغة أو خاصية 'text' مفقودة من Gemini API."
    except Exception as e: return None, f"خطأ في Gemini API: {e}"

def parse_feedback_structuré_ar(feedback_brut_ia_ar): # Nom de fonction spécifique
    parsed_data = {"reponse_corrigee": "غير متوفر", "erreurs_detectees": "غير متوفر", "evaluation_note": "غير متوفر", "justification_evaluation": "غير متوفر"}
    if not feedback_brut_ia_ar: return parsed_data
    
    # Regex adaptées pour les intitulés en arabe.
    # \s\S pour capturer les sauts de ligne. (?=\n\s*\*\*|$) pour s'arrêter à la prochaine section en gras ou à la fin.
    match_rc = re.search(r"\*\*(?:الإجابة المصححة|الاجابه المصححه)\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia_ar, re.IGNORECASE)
    if match_rc: parsed_data["reponse_corrigee"] = match_rc.group(1).strip()
    
    match_ed = re.search(r"\*\*(?:الأخطاء المكتشفة|الاخطاء المكتشفه)\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia_ar, re.IGNORECASE)
    if match_ed: parsed_data["erreurs_detectees"] = match_ed.group(1).strip()
    
    # Pour la note, ex: "التقييم: أعطي هذه الإجابة: 8 / 10" ou "التقييم: 8/10"
    match_en = re.search(r"\*\*(?:التقييم|التقويم)\s*:\*\*\s*(?:أعطي هذه الإجابة\s*:|تقييمي هو\s*:)?\s*([\d\.\s٬٫]+)\s*\/\s*10", feedback_brut_ia_ar, re.IGNORECASE)
    if match_en: 
        note_str = match_en.group(1).strip().replace('٬', '.').replace('٫', '.') # Gérer virgules arabes pour décimales
        parsed_data["evaluation_note"] = note_str + "/10"
    
    match_je = re.search(r"\*\*(?:سبب التقييم|سبب التقويم|مبررات التقييم)\s*:\*\*\s*([\s\S]*?)(?=\n\s*\*\*|$)", feedback_brut_ia_ar, re.IGNORECASE)
    if match_je: parsed_data["justification_evaluation"] = match_je.group(1).strip()

    # Nettoyages simples si une section capture la suivante (peut nécessiter des ajustements fins)
    if parsed_data["reponse_corrigee"] != "غير متوفر" and "**الأخطاء المكتشفة" in parsed_data["reponse_corrigee"]:
        parsed_data["reponse_corrigee"] = parsed_data["reponse_corrigee"].split("**الأخطاء المكتشفة")[0].strip()
    if parsed_data["erreurs_detectees"] != "غير متوفر" and "**التقييم" in parsed_data["erreurs_detectees"]:
        parsed_data["erreurs_detectees"] = parsed_data["erreurs_detectees"].split("**التقييم")[0].strip()
        
    return parsed_data

def evaluer_reponse_ia_ar(texte_source_ar, question_ar, reponse_etudiant_ar): # Nom de fonction spécifique
    if not GROQ_API_KEY: return None, None, "مفتاح Groq API غير مهيأ."
    if not all([texte_source_ar, question_ar, reponse_etudiant_ar]):
        return None, None, "حقول ناقصة لعملية التقييم."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    prompt_evaluation_arabe = f"""
    أنت أستاذ متخصص في اللغة العربية. مهمتك هي تصحيح إجابة طالب عن سؤال حول نص معين.

    يرجى تصحيح الإجابة مع مراعاة ما يلي:
    1. تصحيح الأخطاء الإملائية والنحوية.
    2. تحسين أسلوب الصياغة إن لزم.
    3. التأكد من صحة محتوى الإجابة مقارنة بالنص.
    4. تقديم تقييم نهائي من 0 إلى 10، مع شرح مفصل للعلامة.
    يجب أن يكون مجمل تقييمك باللغة العربية فقط.

    👇 المعلومات:
    النص:
    {texte_source_ar}

    السؤال:
    {question_ar}

    إجابة الطالب:
    {reponse_etudiant_ar}

    ✅ من فضلك أعطني النتيجة بالتنسيق التالي (وباللغة العربية فقط)، مستخدماً بالضبط هذه العناوين بالخط العريض:

    **الإجابة المصححة:**
    [نص إجابتك المصححة هنا]

    **الأخطاء المكتشفة:**
    [قائمتك أو فقراتك للأخطاء هنا]

    **التقييم:**
    [ضع العلامة هنا، مثلا ٧.٥] / 10

    **سبب التقييم:**
    [نص مبرراتك للتقييم هنا]
    """
    data = {"model": groq_model_name, "messages": [{"role": "user", "content": prompt_evaluation_arabe}], "temperature": 0.3}
    try:
        response_api = requests.post(url, headers=headers, json=data, timeout=60)
        response_api.raise_for_status()
        result = response_api.json()
        if result.get("choices") and result["choices"][0].get("message", {}).get("content"):
            feedback_brut = result["choices"][0]["message"]["content"]
            parsed_feedback = parse_feedback_structuré_ar(feedback_brut) # Utiliser le parser arabe
            return feedback_brut, parsed_feedback, None
        return None, None, f"استجابة غير متوقعة من Groq API: {result}"
    except Exception as e:
        return None, None, f"خطأ في Groq API: {e}"
# ------------------------------------

# --- ENDPOINTS API POUR UNITY (Les noms d'endpoints peuvent rester les mêmes) ---
@app.route('/api/textes', methods=['POST'])
def api_creer_texte():
    # ... (Logique identique à la version française, s'attendre à du JSON) ...
    # ... (Les messages d'erreur peuvent être traduits si vous le souhaitez pour la réponse JSON) ...
    if not request.is_json: return jsonify({"erreur": "يجب أن يكون الطلب بتنسيق JSON"}), 415
    data = request.get_json()
    if not data or 'texteContent' not in data: return jsonify({"erreur": "بيانات ناقصة: 'texteContent' مطلوب"}), 400
    texte_manuel = data['texteContent']; niveau_l = data.get('niveauL', 'أ'); niveau_c_str = str(data.get('niveauC', '1'))
    if not isinstance(texte_manuel, str) or not texte_manuel.strip(): return jsonify({"erreur": "'texteContent' يجب أن يكون نصًا غير فارغ"}), 400
    if not isinstance(niveau_l, str) or len(niveau_l) > 10: return jsonify({"erreur": "'niveauL' يجب أن يكون نصًا قصيرًا"}), 400
    if not niveau_c_str.isdigit(): return jsonify({"erreur": "'niveauC' يجب أن يكون رقمًا صحيحًا"}), 400
    niveau_c = int(niveau_c_str)
    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "اتصال قاعدة البيانات مستحيل"}), 500
    try:
        with conn.cursor() as cursor:
            sql = "INSERT INTO texte (texteContent, niveauL, niveauC) VALUES (%s, %s, %s)"
            cursor.execute(sql, (texte_manuel, niveau_l, niveau_c))
            conn.commit(); id_texte_cree = cursor.lastrowid
        return jsonify({"رسالة": "تم إنشاء النص بنجاح", "idTexte": id_texte_cree}), 201 # Message en arabe
    except mysql.connector.Error as err: return jsonify({"erreur": f"خطأ في قاعدة البيانات عند إنشاء النص: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()


@app.route('/api/textes/<int:id_texte>/generer_questions_proposees', methods=['GET'])
def api_generer_questions_pour_texte(id_texte):
    # ... (Logique identique, mais appelle generer_questions_ia_ar) ...
    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "اتصال قاعدة البيانات مستحيل"}), 500
    texte_a_utiliser = None
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT texteContent FROM texte WHERE idTexte = %s", (id_texte,))
            texte_obj = cursor.fetchone()
            if texte_obj: texte_a_utiliser = texte_obj['texteContent']
            else: return jsonify({"erreur": f"النص بالمعرف {id_texte} غير موجود"}), 404
    except mysql.connector.Error as err: return jsonify({"erreur": f"خطأ قاعدة البيانات: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()
    if texte_a_utiliser:
        liste_questions_ia, err_api = generer_questions_ia_ar(texte_a_utiliser) # Appel de la fonction arabe
        if err_api: return jsonify({"erreur": f"خطأ API إنشاء الأسئلة: {err_api}"}), 500
        elif liste_questions_ia is not None:
            return jsonify({"idTexte": id_texte, "questionsProposeesIA": liste_questions_ia}), 200
        else: return jsonify({"erreur": "لم يتم إنشاء أسئلة أو خطأ غير متوقع"}), 500

@app.route('/api/questions_ouvertes', methods=['POST'])
def api_sauvegarder_questions_validees():
    # ... (Logique identique) ...
    if not request.is_json: return jsonify({"erreur": "يجب أن يكون الطلب بتنسيق JSON"}), 415
    data = request.get_json()
    if not data or 'idTexte' not in data or 'questionsValidees' not in data:
        return jsonify({"erreur": "بيانات ناقصة: 'idTexte' و 'questionsValidees' (قائمة) مطلوبة"}), 400
    id_texte_associe = data['idTexte']; questions_validees = data['questionsValidees']
    niveau_question = str(data.get('niveauQuestion', '1'))
    if not isinstance(questions_validees, list): return jsonify({"erreur": "'questionsValidees' يجب أن تكون قائمة نصوص"}), 400
    if not questions_validees: return jsonify({"رسالة": "لا توجد أسئلة للحفظ.", "idsQuestionsInserees": []}), 200
    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "اتصال قاعدة البيانات مستحيل"}), 500
    ids_questions_inserees = []
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM texte WHERE idTexte = %s", (id_texte_associe,))
            if cursor.fetchone()[0] == 0: return jsonify({"erreur": f"النص بالمعرف {id_texte_associe} غير موجود."}), 404
            for q_texte in questions_validees:
                if not isinstance(q_texte, str) or not q_texte.strip(): continue 
                sql = "INSERT INTO questionouvert (idTexte, question, niveau) VALUES (%s, %s, %s)"
                cursor.execute(sql, (id_texte_associe, q_texte.strip(), niveau_question))
                ids_questions_inserees.append(cursor.lastrowid)
            conn.commit()
        return jsonify({"رسالة": f"تم حفظ {len(ids_questions_inserees)} سؤال(أسئلة) بنجاح.", "idsQuestionsInserees": ids_questions_inserees}), 201
    except mysql.connector.Error as err: return jsonify({"erreur": f"خطأ قاعدة البيانات عند حفظ الأسئلة: {err}"}), 500
    finally:
        if conn and conn.is_connected(): conn.close()

@app.route('/api/evaluations', methods=['POST'])
def api_evaluer_reponse_etudiant():
    # ... (Logique identique, mais appelle evaluer_reponse_ia_ar et parse_feedback_structuré_ar) ...
    if not request.is_json: return jsonify({"erreur": "يجب أن يكون الطلب بتنسيق JSON"}), 415
    data = request.get_json()
    if not data or 'idQO' not in data or 'reponseEtudiant' not in data:
        return jsonify({"erreur": "بيانات ناقصة: 'idQO' و 'reponseEtudiant' مطلوبة"}), 400
    id_qo = data['idQO']; reponse_etudiant = data['reponseEtudiant']
    if not isinstance(reponse_etudiant, str) or not reponse_etudiant.strip(): return jsonify({"erreur": "'reponseEtudiant' يجب أن يكون نصًا غير فارغ"}), 400
    conn = get_db_connection()
    if not conn: return jsonify({"erreur": "اتصال قاعدة البيانات مستحيل"}), 500
    texte_source_db, question_db = None, None
    try:
        with conn.cursor(dictionary=True) as cursor:
            sql_get_q_and_text = "SELECT qo.question, t.texteContent FROM questionouvert qo JOIN texte t ON qo.idTexte = t.idTexte WHERE qo.idQO = %s"
            cursor.execute(sql_get_q_and_text, (id_qo,))
            q_data = cursor.fetchone()
            if not q_data: return jsonify({"erreur": f"السؤال المفتوح بالمعرف {id_qo} غير موجود."}), 404
            texte_source_db, question_db = q_data['texteContent'], q_data['question']
    except mysql.connector.Error as err: return jsonify({"erreur": f"خطأ قاعدة البيانات عند استرجاع السؤال: {err}"}), 500

    feedback_brut_ia, feedback_parse_ia, err_api = evaluer_reponse_ia_ar( # Appel de la fonction arabe
        texte_source_db, question_db, reponse_etudiant
    )
    if err_api:
        if conn and conn.is_connected(): conn.close()
        return jsonify({"erreur": f"خطأ API التقييم: {err_api}"}), 500
    if feedback_parse_ia and feedback_brut_ia:
        try:
            with conn.cursor() as cursor:
                sql_insert = """INSERT INTO repence (idQO, reponseEtudiant, reponseCorrigeeIA, erreursDetecteesIA, evaluationNoteIA, evaluationJustificationIA, feedbackCompletIA) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                params = (id_qo, reponse_etudiant, feedback_parse_ia.get("reponse_corrigee"), 
                          feedback_parse_ia.get("erreurs_detectees"), feedback_parse_ia.get("evaluation_note"), 
                          feedback_parse_ia.get("justification_evaluation"), feedback_brut_ia)
                cursor.execute(sql_insert, params); id_repence_creee = cursor.lastrowid; conn.commit()
            return jsonify({"رسالة": "تم حفظ التقييم والملاحظات بنجاح.", "idRepence": id_repence_creee, 
                            "feedbackStructure": feedback_parse_ia, "feedbackCompletIA": feedback_brut_ia}), 201
        except mysql.connector.Error as err: return jsonify({"erreur": f"خطأ قاعدة البيانات عند حفظ التقييم: {err}"}), 500
        finally:
            if conn and conn.is_connected(): conn.close()
    else:
        if conn and conn.is_connected(): conn.close()
        return jsonify({"erreur": "لم يتم استلام أي ملاحظات (خام أو مُحللة) من الذكاء الاصطناعي."}), 500

# --- Route pour l'Interface Web HTML en Arabe ---
@app.route('/', methods=['GET', 'POST'])
def index_ar(): # Renommer la fonction pour éviter conflit si vous gardez les deux UI
    conn = get_db_connection()
    if not conn: return render_template('index_ar_v3.html', erreur_critique="اتصال قاعدة البيانات مستحيل.")

    textes_db = []
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Option: filtrer les textes par langue si vous avez un champ pour cela dans la table 'texte'
            cursor.execute("SELECT idTexte, texteContent, niveauL, niveauC FROM texte ORDER BY idTexte DESC LIMIT 20")
            textes_db = cursor.fetchall()
    except mysql.connector.Error as err: flash(f"خطأ في تحميل النصوص: {err}", "danger")

    view_data = {
        "textes_db": textes_db,
        "texte_original_generation": session.get('texte_original_generation_ar', ''),
        "id_texte_pour_generation": session.get('id_texte_pour_generation_ar', None),
        "questions_proposees_ia": session.get('questions_proposees_ia_ar', []),
        "questions_sauvegardees_avec_ids": [],
        "erreur_generation": None,
        "evaluation_resultat_structuré": None, 
        "feedback_complet_ia_pour_affichage": None, 
        "texte_source_eval_input": "", "question_eval_input": "", "id_qo_evalue": None,
        "reponse_etudiant_eval_input": "", "erreur_evaluation": None,
        "show_question_selection": session.get('show_question_selection_ar', False)
    }
    
    if view_data["id_texte_pour_generation"]:
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT idQO, question FROM questionouvert WHERE idTexte = %s", (view_data["id_texte_pour_generation"],))
                view_data["questions_sauvegardees_avec_ids"] = cursor.fetchall()
        except mysql.connector.Error as err: flash(f"خطأ في تحميل الأسئلة المحفوظة: {err}", "danger")

    if request.method == 'POST':
        action = request.form.get('action')
        # Utiliser les fonctions IA spécifiques à l'arabe
        if action == 'generer_questions_pour_selection':
            session.pop('questions_proposees_ia_ar', None); session.pop('show_question_selection_ar', None) # Clés de session spécifiques
            session.pop('id_texte_pour_generation_ar', None); session.pop('texte_original_generation_ar', None)
            id_texte_selectionne = request.form.get('texte_selectionne')
            texte_manuel = request.form.get('texte_manuel_generation', '').strip()
            niveau_l_manuel = request.form.get('niveau_l_manuel', 'أ'); niveau_c_manuel = request.form.get('niveau_c_manuel', '1')
            texte_a_utiliser = ""; id_texte_actuel = None
            # ... (logique de récupération/création de texte identique à la version française) ...
            if id_texte_selectionne and id_texte_selectionne != "manuel": # ...
                try:
                    with conn.cursor(dictionary=True) as cursor:
                        cursor.execute("SELECT idTexte, texteContent FROM texte WHERE idTexte = %s", (id_texte_selectionne,))
                        texte_obj = cursor.fetchone()
                        if texte_obj: texte_a_utiliser = texte_obj['texteContent']; id_texte_actuel = texte_obj['idTexte']
                        else: view_data["erreur_generation"] = "النص المحدد غير موجود."
                except mysql.connector.Error as err: view_data["erreur_generation"] = f"خطأ قاعدة بيانات: {err}"
            elif texte_manuel:
                texte_a_utiliser = texte_manuel
                try:
                    with conn.cursor() as cursor:
                        sql = "INSERT INTO texte (texteContent, niveauL, niveauC) VALUES (%s, %s, %s)"
                        cursor.execute(sql, (texte_manuel, niveau_l_manuel, int(niveau_c_manuel)))
                        conn.commit(); id_texte_actuel = cursor.lastrowid; flash("تم حفظ النص الجديد بنجاح.", "success")
                        return redirect(url_for('index_ar')) # Rediriger vers la route arabe
                except (mysql.connector.Error, ValueError) as err: view_data["erreur_generation"] = f"خطأ في حفظ النص الجديد: {err}"
            else: view_data["erreur_generation"] = "الرجاء تحديد نص موجود أو إدخال نص جديد."

            if texte_a_utiliser and id_texte_actuel and not view_data["erreur_generation"]:
                liste_questions_ia, err_api = generer_questions_ia_ar(texte_a_utiliser) # Appel fonction arabe
                if err_api: view_data["erreur_generation"] = err_api
                elif liste_questions_ia is not None:
                    session['questions_proposees_ia_ar'] = liste_questions_ia; session['id_texte_pour_generation_ar'] = id_texte_actuel
                    session['texte_original_generation_ar'] = texte_a_utiliser; session['show_question_selection_ar'] = True
                    flash("تم إنشاء الأسئلة بواسطة الذكاء الاصطناعي. الرجاء تحديدها للحفظ.", "info")
            view_data.update({k: session.get(k + "_ar") for k in ['questions_proposees_ia', 'id_texte_pour_generation', 'texte_original_generation', 'show_question_selection'] if session.get(k + "_ar") is not None})

        elif action == 'sauvegarder_questions_selectionnees':
            # ... (logique identique, mais utilise les clés de session _ar) ...
            questions_selectionnees_textes = request.form.getlist('questions_choisies')
            id_texte_associe = session.get('id_texte_pour_generation_ar')
            if not questions_selectionnees_textes: flash("لم يتم تحديد أي أسئلة للحفظ.", "warning")
            elif not id_texte_associe: flash("خطأ: معرّف النص المصدر مفقود لحفظ الأسئلة.", "danger")
            else:
                try:
                    with conn.cursor() as cursor:
                        for q_texte in questions_selectionnees_textes:
                            cursor.execute("INSERT INTO questionouvert (idTexte, question, niveau) VALUES (%s, %s, %s)", (id_texte_associe, q_texte, '1')) # Adapter niveau si besoin
                        conn.commit(); flash(f"تم حفظ {len(questions_selectionnees_textes)} سؤال (أسئلة) بنجاح.", "success")
                        session.pop('questions_proposees_ia_ar', None); session['show_question_selection_ar'] = False
                        return redirect(url_for('index_ar'))
                except mysql.connector.Error as err: flash(f"خطأ في حفظ الأسئلة المحددة: {err}", "danger")
            view_data.update({k: session.get(k + "_ar") for k in ['questions_proposees_ia', 'id_texte_pour_generation', 'texte_original_generation', 'show_question_selection'] if session.get(k + "_ar") is not None})

        elif action == 'evaluer_reponse':
            # ... (logique identique, mais appelle evaluer_reponse_ia_ar) ...
            view_data["texte_source_eval_input"] = request.form.get('texte_source_evaluation', '')
            view_data["question_eval_input"] = request.form.get('question_evaluation_text', '')
            view_data["reponse_etudiant_eval_input"] = request.form.get('reponse_etudiant_evaluation', '')
            id_qo_a_evaluer = request.form.get('id_qo_pour_evaluation')
            view_data["texte_original_generation"] = session.get('texte_original_generation_ar', '')
            view_data["id_texte_pour_generation"] = session.get('id_texte_pour_generation_ar')

            if not all([view_data["texte_source_eval_input"], view_data["question_eval_input"], view_data["reponse_etudiant_eval_input"], id_qo_a_evaluer]):
                view_data["erreur_evaluation"] = "الرجاء ملء جميع الحقول للتقييم."
            else:
                view_data["id_qo_evalue"] = int(id_qo_a_evaluer)
                feedback_brut_ia, feedback_parse_ia, err_api = evaluer_reponse_ia_ar( # Appel fonction arabe
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
                            cursor.execute(sql, params); conn.commit()
                            flash("تم حفظ التقييم والملاحظات المنظمة بنجاح.", "success")
                    except mysql.connector.Error as err:
                        flash(f"خطأ في حفظ التقييم المنظم: {err}", "danger")
                        print(f"خطأ قاعدة بيانات في إدخال الملاحظات المنظمة: {err}")
                else: view_data["erreur_evaluation"] = "لم يتم استلام أي ملاحظات (خام أو مُحللة) من الذكاء الاصطناعي."

    if conn and conn.is_connected(): conn.close()
    return render_template('index_ar_v3.html', **view_data) # Template arabe


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # Port différent pour l'app arabe si besoin