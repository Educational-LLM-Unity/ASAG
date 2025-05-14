# ASAG
# Assistant Pédagogique Intelligent - API Backend

Ce document décrit les endpoints de l'API RESTful pour l'application "Assistant Pédagogique Intelligent". Cette API permet de gérer des textes, de générer des questions ouvertes à partir de ces textes, de valider ces questions, et d'évaluer les réponses des étudiants en utilisant des modèles d'Intelligence Artificielle.

L'API est conçue pour être utilisée par des applications clientes, comme un jeu éducatif développé sous Unity. Toutes les requêtes et réponses de l'API utilisent le format JSON et l'encodage UTF-8.

**URL de Base de l'API (exemple local) :** `http://127.0.0.1:5000/api` (Pour agent arabic)
**URL de Base de l'API (exemple local) :** `http://127.0.0.1:5001/api` (Pour agent francais)

## Table des Matières
1. [creation des variables d'environnements](#env)
2. [Endpoints pour les Textes](#endpoints-textes)
   - [Créer un Nouveau Texte](#creer-texte)
   - [Générer des Questions Proposées pour un Texte](#generer-questions-texte)
3. [Endpoints pour les Questions Ouvertes](#endpoints-questions)
   - [Sauvegarder les Questions Ouvertes Validées](#sauvegarder-questions)
4. [Endpoints pour les Évaluations](#endpoints-evaluations)
   - [Évaluer la Réponse d'un Étudiant](#evaluer-reponse)
5. [Codes de Statut HTTP Communs](#codes-statut)
6. [Format des Erreurs](#format-erreurs)

---

## 1. Variable d'envi (Note)
<a name="env"></a>

dans le fichier .env:
    
    GROQ_API_KEY = "ajoute_ton_grok_api_key"
    GOOGLE_API_KEY = "ejoute_ton_google_apu_key"
    DB_HOST=127.0.0.1
    DB_USER=ajouute_ton_db_user
    DB_PASSWORD=ajouter_ton_db_pwd
    DB_NAME=ajoute_ton_db_name

---

## 2. Endpoints pour les Textes
<a name="endpoints-textes"></a>

### 2.1 Créer un Nouveau Texte
<a name="creer-texte"></a>

Permet de stocker un nouveau texte source dans la base de données.

*   **Endpoint :** `/textes`
*   **Méthode :** `POST`
*   **Headers :**
    *   `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "texteContent": "النص الكامل باللغة العربية هنا...", // Requis, chaîne de caractères
        "niveauL": "أ", // Optionnel, chaîne (ex: 'أ', 'ب', 'ج'), défaut 'أ'
        "niveauC": 1     // Optionnel, entier (ex: 1, 2, 3), défaut 1
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم إنشاء النص بنجاح",
        "idTexte": 15 // L'ID du texte nouvellement créé
    }
    ```
*   **Réponses d'Erreur :**
    *   `400 Bad Request`: Données manquantes ou invalides (ex: `texteContent` manquant).
    *   `415 Unsupported Media Type`: Si le `Content-Type` n'est pas `application/json`.
    *   `500 Internal Server Error`: Erreur côté serveur (ex: problème de base de données).

### 2.2 Générer des Questions Proposées pour un Texte
<a name="generer-questions-texte"></a>

Récupère un texte existant par son ID, l'envoie à l'IA pour générer une liste de questions ouvertes proposées. Ces questions ne sont **pas** sauvegardées automatiquement ; elles sont retournées pour validation par un enseignant.

*   **Endpoint :** `/textes/<id_texte>/generer_questions_proposees`
    *   Remplacer `<id_texte>` par l'ID numérique du texte.
*   **Méthode :** `GET`
*   **Réponse de Succès (200 OK) :**
    ```json
    {
        "idTexte": 15,
        "questionsProposeesIA": [
            "السؤال المقترح الأول...",
            "السؤال المقترح الثاني...",
            "السؤال المقترح الثالث...",
            "السؤال المقترح الرابع...",
            "السؤال المقترح الخامس..."
        ]
    }
    ```
*   **Réponses d'Erreur :**
    *   `404 Not Found`: Si le texte avec l'`id_texte` spécifié n'existe pas.
    *   `500 Internal Server Error`: Erreur API IA ou problème de base de données.

---

## 3. Endpoints pour les Questions Ouvertes
<a name="endpoints-questions"></a>

### 3.1 Sauvegarder les Questions Ouvertes Validées
<a name="sauvegarder-questions"></a>

Permet à un enseignant de sauvegarder une sélection de questions (préalablement générées et validées) dans la base de données, associées à un texte source.

*   **Endpoint :** `/questions_ouvertes`
*   **Méthode :** `POST`
*   **Headers :**
    *   `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idTexte": 15, // Requis, ID du texte source auquel associer les questions
        "questionsValidees": [ // Requis, liste de chaînes de caractères (les questions)
            "نص السؤال الأول الذي تم التحقق منه.",
            "نص السؤال الثاني الذي تم التحقق منه."
        ],
        "niveauQuestion": "1" // Optionnel, chaîne (ex: '1', '2'), défaut '1'
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم حفظ 2 سؤال(أسئلة) بنجاح.",
        "idsQuestionsInserees": [ 25, 26 ] // Liste des ID des nouvelles questions ouvertes créées
    }
    ```
*   **Réponses d'Erreur :**
    *   `400 Bad Request`: Données manquantes ou invalides.
    *   `404 Not Found`: Si l'`idTexte` fourni n'existe pas.
    *   `415 Unsupported Media Type`.
    *   `500 Internal Server Error`.

---

## 4. Endpoints pour les Évaluations
<a name="endpoints-evaluations"></a>

### 4.1 Évaluer la Réponse d'un Étudiant
<a name="evaluer-reponse"></a>

Prend l'ID d'une question ouverte existante et la réponse d'un étudiant. L'API récupère le texte source et la question associés à l'ID de la question, envoie ces informations avec la réponse de l'étudiant à un modèle IA pour évaluation, puis sauvegarde la réponse de l'étudiant et le feedback structuré de l'IA dans la base de données.

*   **Endpoint :** `/evaluations`
*   **Méthode :** `POST`
*   **Headers :**
    *   `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idQO": 25, // Requis, ID de la question ouverte à laquelle l'étudiant répond
        "reponseEtudiant": "إجابة الطالب على السؤال...", // Requis, la réponse de l'étudiant
        "idEleve": 7,    // Optionnel, ID de l'élève
        "idHys": 22     // Optionnel, ID de l'historique de test/entraînement
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم حفظ التقييم والملاحظات بنجاح.",
        "idRepence": 5, // L'ID de l'enregistrement de la réponse/évaluation créé
        "feedbackStructure": {
            "reponse_corrigee": "نص الإجابة المصححة من الذكاء الاصطناعي...",
            "erreurs_detectees": "قائمة أو وصف الأخطاء المكتشفة...",
            "evaluation_note": "8.5/10",
            "justification_evaluation": "مبررات التقييم المفصلة..."
        },
        "feedbackCompletIA": "النص الكامل لتقييم الذكاء الاصطناعي (بما في ذلك العناوين)..." // Optionnel
    }
    ```
*   **Réponses d'Erreur :**
    *   `400 Bad Request`: Données manquantes ou invalides.
    *   `404 Not Found`: Si l'`idQO` (question ouverte) n'existe pas.
    *   `415 Unsupported Media Type`.
    *   `500 Internal Server Error`.

---

## 5. Codes de Statut HTTP Communs
<a name="codes-statut"></a>

*   `200 OK`: La requête a réussi (généralement pour les requêtes `GET`).
*   `201 Created`: La ressource a été créée avec succès (généralement pour les requêtes `POST` qui créent une nouvelle entité).
*   `400 Bad Request`: La requête du client était malformée ou contenait des données invalides. Le corps de la réponse JSON contiendra un message d'erreur.
*   `401 Unauthorized`: (Non implémenté) Le client n'est pas authentifié.
*   `403 Forbidden`: (Non implémenté) Le client est authentifié mais n'a pas les droits pour accéder à la ressource.
*   `404 Not Found`: La ressource demandée n'a pas été trouvée (ex: un texte ou une question avec un ID inexistant).
*   `415 Unsupported Media Type`: La requête a été envoyée avec un type de contenu incorrect (ex: pas `application/json` quand c'est attendu).
*   `500 Internal Server Error`: Une erreur s'est produite côté serveur (ex: problème de connexion à la base de données, erreur inattendue dans le code, erreur de l'API IA externe). Le corps de la réponse JSON peut contenir des détails sur l'erreur.

---

## 6. Format des Erreurs
<a name="format-erreurs"></a>

En cas d'erreur client (4xx) ou serveur (5xx), l'API essaiera de retourner une réponse JSON avec une clé `erreur` décrivant le problème :

```json
// Exemple d'erreur 400
{
    "erreur": "بيانات ناقصة: 'texteContent' مطلوب"
}
// Exemple d'erreur 500
{
    "erreur": "خطأ في قاعدة البيانات عند إنشاء النص: [détails de l'erreur SQL si applicable]"
}
