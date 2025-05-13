import os
import google.generativeai as genai
import requests # Pour l'API Groq
from flask import Flask, request, render_template
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# --- Configuration de l'API Google Gemini (Génération de questions) ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
gemini_model = None
gemini_model_name = 'models/gemini-1.5-flash-latest'

if not GEMINI_API_KEY:
    print("ERREUR: GOOGLE_API_KEY non définie dans .env.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(gemini_model_name)
        print(f"Modèle Gemini '{gemini_model_name}' initialisé.")
    except Exception as e:
        print(f"ERREUR initialisation Gemini: {e}")
# --------------------------------------------------------------------

# --- Configuration de l'API Groq (Évaluation de réponses) ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_model_name = "llama3-8b-8192" # Modèle utilisé dans votre script d'évaluation

if not GROQ_API_KEY:
    print("ERREUR: GROQ_API_KEY non définie dans .env.")
# ------------------------------------------------------------

def generer_questions_gemini(texte_source):
    """Génère des questions en utilisant Gemini."""
    if not gemini_model:
        return None, "Modèle Gemini non initialisé."

    prompt_generation = f"""
    أنت مساعد تعليمي متخصص في اللغة العربية. مهمتك هي قراءة النص التالي الذي قدمه المعلم وإنشاء 5 أسئلة **مفتوحة** بناءً عليه.
    يجب أن تتطلب هذه الأسئلة تفكيرًا وفهمًا للنص، وليس مجرد استرجاع مباشر للمعلومات.
    ركز على الأسباب، النتائج، المقارنات، أو التطبيقات المحتملة المذكورة أو التي يمكن استنتاجها من النص.
    تجنب الأسئلة التي يمكن الإجابة عليها بـ "نعم" أو "لا" أو بكلمة واحدة.

    النص المقدم من المعلم:
    ---
    {texte_source}
    ---

    الأسئلة المقترحة (اكتب 5 أسئلة مفتوحة هنا، chaque question sur une nouvelle ligne, numérotée):
    """
    try:
        response = gemini_model.generate_content(prompt_generation)
        if response and hasattr(response, 'text') and response.text:
            return response.text.strip(), None
        else:
            error_details = "Réponse vide de Gemini."
            try:
                if response.prompt_feedback: error_details += f" Feedback: {response.prompt_feedback}"
                if response.candidates and response.candidates[0].finish_reason != 'STOP':
                    error_details += f" Raison: {response.candidates[0].finish_reason}."
            except Exception: pass
            return None, error_details
    except Exception as e:
        return None, f"Erreur API Gemini: {e}"

def evaluer_reponse_groq(texte_source_eval, question_eval, reponse_etudiant_eval):
    """Évalue une réponse en utilisant l'API Groq."""
    if not GROQ_API_KEY:
        return "Clé API Groq non configurée.", None # Erreur interne

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt_evaluation = f"""
    أنت أستاذ متخصص في اللغة العربية. مهمتك هي تصحيح إجابة طالب عن سؤال حول نص معين.

    يرجى تصحيح الإجابة مع مراعاة ما يلي:
    1. تصحيح الأخطاء الإملائية والنحوية.
    2. تحسين أسلوب الصياغة إن لزم.
    3. التأكد من صحة محتوى الإجابة مقارنة بالنص.
    4. تقديم تقييم نهائي من 0 إلى 10، مع شرح مفصل للعلامة.

    👇 المعلومات:
    النص:
    {texte_source_eval}

    السؤال:
    {question_eval}

    إجابة الطالب:
    {reponse_etudiant_eval}

    ✅ من فضلك أعطني النتيجة بالتنسيق التالي (وباللغة العربية فقط):

    **الإجابة المصححة:**
    ...

    **الأخطاء المكتشفة:**
    1. ...
    2. ...
    3. ...

    **التقييم:**
    أعطي هذه الإجابة: ... / 10

    **سبب التقييم:**
    ...
    """
    data = {
        "model": groq_model_name,
        "messages": [{"role": "user", "content": prompt_evaluation}],
        "temperature": 0.3
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=60) # Ajout d'un timeout
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
        result = response.json()
        if "choices" in result and result["choices"] and "message" in result["choices"][0] and "content" in result["choices"][0]["message"]:
            return result["choices"][0]["message"]["content"], None
        else:
            return None, f"Réponse inattendue de l'API Groq: {result}"
    except requests.exceptions.RequestException as e:
        return None, f"Erreur de connexion à l'API Groq: {e}"
    except Exception as e:
        return None, f"Erreur lors du traitement de la réponse Groq: {e}"


@app.route('/', methods=['GET', 'POST'])
def index():
    # Variables pour la génération
    questions_generees_str = None
    texte_original_generation = ""
    erreur_generation = None

    # Variables pour l'évaluation
    evaluation_resultat = None
    texte_source_eval_input = ""
    question_eval_input = ""
    reponse_etudiant_eval_input = ""
    erreur_evaluation = None

    # Vérifier si les modèles sont prêts
    if gemini_model is None:
         erreur_generation = "Erreur critique: Modèle Gemini non initialisé."
    if not GROQ_API_KEY:
        erreur_evaluation = "Erreur critique: Clé API Groq non configurée."


    if request.method == 'POST':
        action = request.form.get('action') # Pour distinguer les soumissions de formulaires

        if action == 'generer_questions':
            texte_original_generation = request.form.get('texte_enseignant_generation', '')
            if not texte_original_generation.strip():
                erreur_generation = "Veuillez fournir un texte source pour la génération."
            elif gemini_model: # S'assurer que le modèle est prêt
                questions_generees_str, erreur_generation = generer_questions_gemini(texte_original_generation)
                if questions_generees_str:
                     print("--- Questions générées avec succès ---")
                else:
                     print(f"--- Échec de la génération: {erreur_generation} ---")


        elif action == 'evaluer_reponse':
            texte_source_eval_input = request.form.get('texte_source_evaluation', '')
            question_eval_input = request.form.get('question_evaluation', '')
            reponse_etudiant_eval_input = request.form.get('reponse_etudiant_evaluation', '')

            # Conserver les entrées pour les réafficher
            texte_original_generation = request.form.get('texte_enseignant_generation_hidden', '') # Récupérer le texte original si transmis
            questions_generees_str = request.form.get('questions_generees_hidden', '') # Récupérer les questions générées si transmises


            if not texte_source_eval_input.strip() or not question_eval_input.strip() or not reponse_etudiant_eval_input.strip():
                erreur_evaluation = "Veuillez remplir tous les champs pour l'évaluation (texte source, question, et réponse de l'étudiant)."
            elif GROQ_API_KEY: # S'assurer que la clé est prête
                evaluation_resultat, erreur_evaluation = evaluer_reponse_groq(
                    texte_source_eval_input,
                    question_eval_input,
                    reponse_etudiant_eval_input
                )
                if evaluation_resultat:
                    print("--- Évaluation reçue avec succès ---")
                else:
                    print(f"--- Échec de l'évaluation: {erreur_evaluation} ---")

    return render_template('index.html',
                           # Pour la génération
                           questions_generees_str=questions_generees_str,
                           texte_original_generation=texte_original_generation,
                           erreur_generation=erreur_generation,
                           # Pour l'évaluation
                           evaluation_resultat=evaluation_resultat,
                           texte_source_eval_input=texte_source_eval_input,
                           question_eval_input=question_eval_input,
                           reponse_etudiant_eval_input=reponse_etudiant_eval_input,
                           erreur_evaluation=erreur_evaluation
                           )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)