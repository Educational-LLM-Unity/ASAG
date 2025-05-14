# ASAG
# Assistant Pédagogique Intelligent - API Backend

Ce document décrit les endpoints de l'API RESTful pour l'application "Assistant Pédagogique Intelligent". Cette API permet de gérer des textes, de générer des questions ouvertes à partir de ces textes, de valider ces questions, et d'évaluer les réponses des étudiants en utilisant des modèles d'Intelligence Artificielle.

L'API est conçue pour être utilisée par des applications clientes, comme un jeu éducatif développé sous Unity. Toutes les requêtes et réponses de l'API utilisent le format JSON et l'encodage UTF-8.

**URL de Base de l'API (exemple local) :** `http://127.0.0.1:5000/api` (Pour agent arabic)
**URL de Base de l'API (exemple local) :** `http://127.0.0.1:5001/api` (Pour agent francais)

## Table des Matières
1. [creation des variables d'environnements](#env)
2. [Endpoints pour les Textes (Version Française)](#endpoints-textes-fr)
   - [Créer un Nouveau Texte (Français)](#creer-texte-fr)
   - [Générer des Questions Proposées pour un Texte (Français)](#generer-questions-texte-fr)
3. [Endpoints pour les Questions Ouvertes (Version Française)](#endpoints-questions-fr)
   - [Sauvegarder les Questions Ouvertes Validées (Français)](#sauvegarder-questions-fr)
4. [Endpoints pour les Évaluations (Version Française)](#endpoints-evaluations-fr)
   - [Évaluer la Réponse d'un Étudiant (Français)](#evaluer-reponse-fr)
5. [Endpoints pour les Textes (Version Arabe)](#endpoints-textes-ar)
   - [Créer un Nouveau Texte (Arabe)](#creer-texte-ar)
   - [Générer des Questions Proposées pour un Texte (Arabe)](#generer-questions-texte-ar)
6. [Endpoints pour les Questions Ouvertes (Version Arabe)](#endpoints-questions-ar)
   - [Sauvegarder les Questions Ouvertes Validées (Arabe)](#sauvegarder-questions-ar)
7. [Endpoints pour les Évaluations (Version Arabe)](#endpoints-evaluations-ar)
   - [Évaluer la Réponse d'un Étudiant (Arabe)](#evaluer-reponse-ar)
8. [Codes de Statut HTTP Communs](#codes-statut)
9. [Format des Erreurs](#format-erreurs)
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


## 2. Endpoints pour les Textes (Version Française)
<a name="endpoints-textes-fr"></a>

Utilisez l'URL de base pour la version française (ex: `http://127.0.0.1:5001/api`).

### 2.1 Créer un Nouveau Texte (Français)
<a name="creer-texte-fr"></a>

Permet de stocker un nouveau texte source en français dans la base de données.

*   **Endpoint :** `/textes`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "texteContent": "Le texte complet en français ici...", // Requis, chaîne
        "niveauL": "A", // Optionnel, chaîne (ex: 'A', 'B', 'C'), défaut 'A'
        "niveauC": 1     // Optionnel, entier (ex: 1, 2, 3), défaut 1
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "message": "Texte créé avec succès", // Message en français
        "idTexte": 16 // L'ID du texte nouvellement créé
    }
    ```
*   **Réponses d'Erreur :** Voir [Codes de Statut](#codes-statut) et [Format des Erreurs](#format-erreurs).

### 2.2 Générer des Questions Proposées pour un Texte (Français)
<a name="generer-questions-texte-fr"></a>

Récupère un texte existant (en français) par son ID, l'envoie à l'IA pour générer une liste de questions ouvertes proposées en français.

*   **Endpoint :** `/textes/<id_texte>/generer_questions_proposees`
*   **Méthode :** `GET`
*   **Réponse de Succès (200 OK) :**
    ```json
    {
        "idTexte": 16,
        "questionsProposeesIA": [
            "La première question proposée en français...",
            "La deuxième question proposée en français..."
            // ... jusqu'à 5 questions
        ]
    }
    ```
*   **Réponses d'Erreur :** `404 Not Found`, `500 Internal Server Error`.

---

## 3. Endpoints pour les Questions Ouvertes (Version Française)
<a name="endpoints-questions-fr"></a>

### 3.1 Sauvegarder les Questions Ouvertes Validées (Français)
<a name="sauvegarder-questions-fr"></a>

Sauvegarde une sélection de questions en français (validées par un enseignant) associées à un texte source.

*   **Endpoint :** `/questions_ouvertes`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idTexte": 16, 
        "questionsValidees": [
            "Texte de la première question validée en français.",
            "Texte de la deuxième question validée en français."
        ],
        "niveauQuestion": "1" // Optionnel, défaut '1'
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "message": "2 question(s) sauvegardée(s) avec succès.", // Message en français
        "idsQuestionsInserees": [ 27, 28 ] 
    }
    ```
*   **Réponses d'Erreur :** `400 Bad Request`, `404 Not Found`, `500 Internal Server Error`.

---

## 4. Endpoints pour les Évaluations (Version Française)
<a name="endpoints-evaluations-fr"></a>

### 4.1 Évaluer la Réponse d'un Étudiant (Français)
<a name="evaluer-reponse-fr"></a>

Prend l'ID d'une question ouverte en français, la réponse de l'étudiant en français, et retourne une évaluation structurée en français.

*   **Endpoint :** `/evaluations`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idQO": 27, 
        "reponseEtudiant": "La réponse de l'étudiant en français...",
        "idEleve": 8,    // Optionnel
        "idHys": 23     // Optionnel
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "message": "Évaluation et feedback sauvegardés avec succès.", // Message en français
        "idRepence": 6, 
        "feedbackStructure": {
            "reponse_corrigee": "Texte de la réponse corrigée en français...",
            "erreurs_detectees": "Liste des erreurs détectées en français...",
            "evaluation_note": "7.5/10",
            "justification_evaluation": "Justification détaillée de l'évaluation en français..."
        },
        "feedbackCompletIA": "Le texte complet du feedback de l'IA en français..." // Optionnel
    }
    ```
*   **Réponses d'Erreur :** `400 Bad Request`, `404 Not Found`, `500 Internal Server Error`.

---

## 5. Endpoints pour les Textes (Version Arabe)
<a name="endpoints-textes-ar"></a>

Utilisez l'URL de base pour la version arabe (ex: `http://127.0.0.1:5000/api`).

### 5.1 Créer un Nouveau Texte (Arabe)
<a name="creer-texte-ar"></a>

Permet de stocker un nouveau texte source en arabe dans la base de données.

*   **Endpoint :** `/textes`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "texteContent": "النص الكامل باللغة العربية هنا...", // Requis, chaîne
        "niveauL": "أ", // Optionnel, chaîne (ex: 'أ', 'ب', 'ج'), défaut 'أ'
        "niveauC": 1     // Optionnel, entier (ex: 1, 2, 3), défaut 1
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم إنشاء النص بنجاح", // Message en arabe
        "idTexte": 15 
    }
    ```
*   **Réponses d'Erreur :** Voir [Codes de Statut](#codes-statut) et [Format des Erreurs](#format-erreurs).

### 5.2 Générer des Questions Proposées pour un Texte (Arabe)
<a name="generer-questions-texte-ar"></a>

Récupère un texte existant (en arabe) par son ID, l'envoie à l'IA pour générer une liste de questions ouvertes proposées en arabe.

*   **Endpoint :** `/textes/<id_texte>/generer_questions_proposees`
*   **Méthode :** `GET`
*   **Réponse de Succès (200 OK) :**
    ```json
    {
        "idTexte": 15,
        "questionsProposeesIA": [
            "السؤال المقترح الأول...",
            "السؤال المقترح الثاني..."
            // ... jusqu'à 5 questions
        ]
    }
    ```
*   **Réponses d'Erreur :** `404 Not Found`, `500 Internal Server Error`.

---

## 6. Endpoints pour les Questions Ouvertes (Version Arabe)
<a name="endpoints-questions-ar"></a>

### 6.1 Sauvegarder les Questions Ouvertes Validées (Arabe)
<a name="sauvegarder-questions-ar"></a>

Sauvegarde une sélection de questions en arabe (validées par un enseignant) associées à un texte source.

*   **Endpoint :** `/questions_ouvertes`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idTexte": 15, 
        "questionsValidees": [
            "نص السؤال الأول الذي تم التحقق منه.",
            "نص السؤال الثاني الذي تم التحقق منه."
        ],
        "niveauQuestion": "1" // Optionnel, défaut '1'
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم حفظ 2 سؤال(أسئلة) بنجاح.", // Message en arabe
        "idsQuestionsInserees": [ 25, 26 ] 
    }
    ```
*   **Réponses d'Erreur :** `400 Bad Request`, `404 Not Found`, `500 Internal Server Error`.

---

## 7. Endpoints pour les Évaluations (Version Arabe)
<a name="endpoints-evaluations-ar"></a>

### 7.1 Évaluer la Réponse d'un Étudiant (Arabe)
<a name="evaluer-reponse-ar"></a>

Prend l'ID d'une question ouverte en arabe, la réponse de l'étudiant en arabe, et retourne une évaluation structurée en arabe.

*   **Endpoint :** `/evaluations`
*   **Méthode :** `POST`
*   **Headers :** `Content-Type: application/json`
*   **Corps de la Requête (JSON) :**
    ```json
    {
        "idQO": 25, 
        "reponseEtudiant": "إجابة الطالب على السؤال...",
        "idEleve": 7,    // Optionnel
        "idHys": 22     // Optionnel
    }
    ```
*   **Réponse de Succès (201 Created) :**
    ```json
    {
        "رسالة": "تم حفظ التقييم والملاحظات بنجاح.", // Message en arabe
        "idRepence": 5, 
        "feedbackStructure": {
            "reponse_corrigee": "نص الإجابة المصححة من الذكاء الاصطناعي...",
            "erreurs_detectees": "قائمة أو وصف الأخطاء المكتشفة...",
            "evaluation_note": "8.5/10",
            "justification_evaluation": "مبررات التقييم المفصلة..."
        },
        "feedbackCompletIA": "النص الكامل لتقييم الذكاء الاصطناعي (بما في ذلك العناوين)..." // Optionnel
    }
    ```
*   **Réponses d'Erreur :** `400 Bad Request`, `404 Not Found`, `500 Internal Server Error`.

---

## 8. Codes de Statut HTTP Communs
<a name="codes-statut"></a>

*   `200 OK`: La requête a réussi (généralement pour les requêtes `GET`).
*   `201 Created`: La ressource a été créée avec succès (généralement pour les requêtes `POST` qui créent une nouvelle entité).
*   `400 Bad Request`: La requête du client était malformée ou contenait des données invalides. Le corps de la réponse JSON contiendra un message d'erreur.
*   `401 Unauthorized`: (Non implémenté) Le client n'est pas authentifié.
*   `403 Forbidden`: (Non implémenté) Le client est authentifié mais n'a pas les droits pour accéder à la ressource.
*   `404 Not Found`: La ressource demandée n'a pas été trouvée.
*   `415 Unsupported Media Type`: La requête a été envoyée avec un type de contenu incorrect.
*   `500 Internal Server Error`: Une erreur s'est produite côté serveur. Le corps de la réponse JSON peut contenir des détails.

---

## 9. Format des Erreurs
<a name="format-erreurs"></a>

En cas d'erreur client (4xx) ou serveur (5xx), l'API essaiera de retourner une réponse JSON avec une clé `erreur` décrivant le problème (en français ou en arabe selon l'endpoint appelé) :

```json
// Exemple d'erreur 400 (réponse de l'API française)
{
    "erreur": "Données manquantes : 'texteContent' est requis"
}

// Exemple d'erreur 400 (réponse de l'API arabe)
{
    "erreur": "بيانات ناقصة: 'texteContent' مطلوب"
}
