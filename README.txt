PLATEFORME E-LEARNING ADAPTATIVE  (Django + SQLite/PostgreSQL + Bootstrap + Chart.js + Pandas + Scikit-learn)

LANCER LE PROJET (Windows)
  1. Dezippez ce dossier (par exemple dans C:\elearning_adaptatif).
  2. Double-cliquez sur start.bat  (ou, dans un terminal : start.bat)
     Le script cree l'environnement, installe les paquets, cree la base,
     ajoute des donnees de demonstration, puis ouvre http://127.0.0.1:8000
  3. Pour arreter : Ctrl+C dans la fenetre. Pour relancer : start.bat.

COMPTES DE DEMONSTRATION
  Administrateur : admin  / admin123   (aussi sur http://127.0.0.1:8000/admin/)
  Enseignant     : prof   / prof1234
  Apprenants     : sara, ali, amine, nour, mounir  / appr1234
    sara   = apprenante performante      ali    = en difficulte + inactive
    amine  = moyen                       nour   = bonne
    mounir = inscrit, aucune activite

PARCOURS DE DEMO CONSEILLE
  1. Connectez-vous en "ali" -> Tableau de bord : difficulte detectee + recommandations
     (revision, ressources d'appui) + niveau de quiz conseille (debutant).
  2. Connectez-vous en "sara" -> recommandations de contenu avance.
  3. Connectez-vous en "mounir" -> ouvrez une lecon, restez 1 minute sans bouger
     (suivi du temps et de l'inactivite), puis passez un quiz et ratez-le :
     le tableau de bord se met a jour et le niveau d'exercices s'adapte.
  4. Connectez-vous en "prof" -> Mes cours -> Statistiques : scores par quiz,
     temps par lecon, profils des apprenants (Scikit-learn), liste des difficultes.
  5. Admin -> Parametres plateforme : changer les seuils (score, inactivite...).

STRUCTURE
  config/                 parametres Django
  comptes/                utilisateurs, roles, inscription, connexion
  elearning/models.py     classes du diagramme de classes
  elearning/views.py      cas d'utilisation (apprenant, enseignant)
  elearning/adaptation.py moteur d'analyse et d'adaptation (Pandas, Scikit-learn)
  static/js/tracker.js    suivi comportemental en temps reel (navigateur)
  templates/              pages HTML (Bootstrap) et graphiques (Chart.js)

IMPORT DE FICHIERS
  Lors de la creation d'une lecon, l'enseignant peut importer un PDF ou un Word (.docx) :
  le texte est extrait dans le contenu de la lecon et le fichier devient une ressource.
  (Le format .doc ancien n'est pas supporte : l'enregistrer en .docx.)

REGLES D'ADAPTATION (modifiables dans l'admin : Parametres plateforme)
  - Difficulte si le dernier score < seuil (50 %), si 3 tentatives sans reussite,
    ou si l'inactivite depasse 40 % du temps passe.
  - Niveau d'exercices : moyenne des 2 derniers scores
    < 50 % -> Debutant ; < 80 % -> Intermediaire ; >= 80 % -> Avance.
  - Difficulte -> recommandation de revision + ressources de niveau debutant.
  - Score >= 80 % -> ressources ou quiz de niveau avance.

POSTGRESQL (facultatif)
  pip install psycopg2-binary ; definir USE_POSTGRES=1, DB_NAME, DB_USER, DB_PASSWORD
  avant de lancer. Par defaut le projet utilise SQLite (aucune installation).

REINITIALISER LES DONNEES
  Supprimer db.sqlite3 et le dossier media, puis relancer start.bat.
