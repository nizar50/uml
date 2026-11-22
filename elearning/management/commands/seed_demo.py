from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from comptes.models import Utilisateur
from elearning.adaptation import DEFAUTS, DESCRIPTIONS, analyser_apprenant
from elearning.models import (ActiviteLog, Chapitre, Choix, Cours, Inscription, Lecon, Niveau,
                              ParametrePlateforme, Question, Quiz, Ressource, Tentative)
from elearning.views import maj_progression

QUESTIONS = {
    ("Variables et types", Niveau.DEBUTANT): [
        ("Quelle fonction affiche du texte à l'écran ?", ["print", "echo", "show", "display"], 0, 1),
        ("Quel est le type de la valeur 3.14 ?", ["int", "float", "str", "bool"], 1, 1),
        ("Comment écrire un commentaire en Python ?", ["# commentaire", "// commentaire", "/* commentaire */", "-- commentaire"], 0, 1),
        ("Quelle instruction crée une variable x égale à 5 ?", ["x = 5", "int x = 5", "var x := 5", "let x be 5"], 0, 1),
    ],
    ("Variables et types", Niveau.INTERMEDIAIRE): [
        ("Que vaut type('42') ?", ["int", "str", "float", "list"], 1, 2),
        ("Que vaut 7 // 2 ?", ["3.5", "3", "4", "2"], 1, 2),
        ("Que vaut int('12') + 3 ?", ["123", "15", "Erreur", "'12'3"], 1, 2),
    ],
    ("Variables et types", Niveau.AVANCE): [
        ("Que vaut bool([]) ?", ["True", "False", "None", "Erreur"], 1, 3),
        ("Que retourne 'abc' * 2 ?", ["abcabc", "abc2", "Erreur", "abcab"], 0, 3),
        ("Quel est le résultat de 2 ** 3 ** 2 ?", ["64", "512", "36", "128"], 1, 3),
    ],
    ("Conditions et boucles", Niveau.DEBUTANT): [
        ("Quel mot-clé introduit une condition ?", ["if", "when", "check", "case"], 0, 1),
        ("Quelle boucle répète tant qu'une condition est vraie ?", ["for", "while", "loop", "repeat"], 1, 1),
        ("Que produit range(3) ?", ["0, 1, 2", "1, 2, 3", "0, 1, 2, 3", "3"], 0, 1),
    ],
    ("Conditions et boucles", Niveau.INTERMEDIAIRE): [
        ("Quel mot-clé interrompt une boucle ?", ["stop", "exit", "break", "halt"], 2, 2),
        ("Combien de fois s'exécute : for i in range(2, 6) ?", ["4", "5", "6", "3"], 0, 2),
        ("Que fait continue dans une boucle ?", ["Passe à l'itération suivante", "Arrête le programme", "Quitte la boucle", "Recommence le programme"], 0, 2),
    ],
}

PLAN = [
    ("Variables et types", [
        ("Les variables", "Une variable associe un nom à une valeur.\n\nExemple :\n    age = 20\n    nom = 'Sara'\n\nPython détermine le type automatiquement."),
        ("Les types de données", "Les types de base : int (entiers), float (décimaux), str (texte), bool (vrai/faux).\n\nOn peut les convertir avec int(), float(), str()."),
    ]),
    ("Conditions et boucles", [
        ("Les conditions", "On teste une condition avec if / elif / else.\n\n    if note >= 10:\n        print('Admis')\n    else:\n        print('Refusé')"),
        ("Les boucles", "while répète tant qu'une condition est vraie ; for parcourt une séquence.\n\n    for i in range(3):\n        print(i)"),
    ]),
]


class Command(BaseCommand):
    help = "Crée les paramètres par défaut et des données de démonstration."

    def handle(self, *args, **options):
        for cle, valeur in DEFAUTS.items():
            ParametrePlateforme.objects.get_or_create(
                cle=cle, defaults={"valeur": str(valeur), "description": DESCRIPTIONS[cle]})

        if Utilisateur.objects.filter(username="prof").exists():
            self.stdout.write("Données de démonstration déjà présentes.")
            return

        Utilisateur.objects.create_superuser("admin", "admin@example.com", "admin123",
                                             first_name="Admin", last_name="Plateforme")
        prof = Utilisateur.objects.create_user(
            "prof", "prof@example.com", "prof1234", role=Utilisateur.Role.ENSEIGNANT,
            first_name="Karim", last_name="Ben Salah", specialite="Informatique")
        noms = {"sara": "Sara", "ali": "Ali", "amine": "Amine", "nour": "Nour", "mounir": "Mounir"}
        apprenants = {
            u: Utilisateur.objects.create_user(u, f"{u}@example.com", "appr1234",
                                               role=Utilisateur.Role.APPRENANT, first_name=prenom, last_name="Demo")
            for u, prenom in noms.items()
        }

        cours = Cours.objects.create(
            enseignant=prof, titre="Introduction à Python", niveau=Niveau.DEBUTANT,
            description="Les bases de la programmation avec Python : variables, types, conditions et boucles.")

        quiz_par_chapitre = {}
        for ordre, (titre_chap, lecons) in enumerate(PLAN, start=1):
            chap = Chapitre.objects.create(cours=cours, titre=titre_chap, ordre=ordre)
            premiere = None
            for i, (titre_lecon, contenu) in enumerate(lecons, start=1):
                lec = Lecon.objects.create(chapitre=chap, titre=titre_lecon, contenu=contenu,
                                           ordre=i, duree_estimee=10)
                premiere = premiere or lec
            for nom, niveau, texte in [
                (f"Aide-mémoire : {titre_chap}", Niveau.DEBUTANT, "Rappel des notions essentielles du chapitre."),
                (f"Exercices guidés : {titre_chap}", Niveau.DEBUTANT, "Exercices corrigés pas à pas."),
                (f"Défis avancés : {titre_chap}", Niveau.AVANCE, "Problèmes plus difficiles pour aller plus loin."),
            ]:
                res = Ressource(lecon=premiere, titre=nom, type=Ressource.Type.DOC, niveau=niveau)
                res.fichier.save(f"{nom[:20].replace(' ', '_').replace(':', '')}.txt", ContentFile(texte.encode("utf-8")))
            quiz_par_chapitre[titre_chap] = chap
            for niveau in (Niveau.DEBUTANT, Niveau.INTERMEDIAIRE, Niveau.AVANCE):
                questions = QUESTIONS.get((titre_chap, niveau))
                if not questions:
                    continue
                quiz = Quiz.objects.create(chapitre=chap, titre=f"Quiz {titre_chap}", niveau=niveau,
                                           note_min=50, duree_max=15)
                for enonce, choix, bonne, diff in questions:
                    q = Question.objects.create(quiz=quiz, enonce=enonce, difficulte=diff, points=1)
                    for k, texte in enumerate(choix):
                        Choix.objects.create(question=q, texte=texte, est_correct=(k == bonne))

        for u in apprenants.values():
            Inscription.objects.create(apprenant=u, cours=cours)

        maintenant = timezone.now()
        chap1 = Chapitre.objects.get(cours=cours, ordre=1)
        lecon1 = chap1.lecons.first()
        lecon2 = chap1.lecons.last()
        quiz = {q.niveau: q for q in chap1.quiz.all()}

        def tentatives(user, quiz_obj, scores):
            for n, score in enumerate(scores, start=1):
                debut = maintenant - timedelta(days=len(scores) - n + 1)
                Tentative.objects.create(apprenant=user, quiz=quiz_obj, numero=n, date_debut=debut,
                                         date_fin=debut + timedelta(minutes=8), score=score,
                                         statut=Tentative.Statut.CORRIGEE)

        def activite(user, lecon, temps, inactif, clics):
            for type_evt, duree in [("OUVERTURE", 0), ("TEMPS", temps), ("INACTIVITE", inactif), ("CLIC", clics)]:
                if type_evt == "OUVERTURE" or duree:
                    ActiviteLog.objects.create(apprenant=user, lecon=lecon, type_evenement=type_evt, duree_secondes=duree)

        a = apprenants
        # Sara : performante
        activite(a["sara"], lecon1, 900, 30, 40)
        activite(a["sara"], lecon2, 700, 20, 25)
        tentatives(a["sara"], quiz[Niveau.DEBUTANT], [75, 100])
        tentatives(a["sara"], quiz[Niveau.INTERMEDIAIRE], [90])
        # Ali : en difficulté, beaucoup d'inactivité
        activite(a["ali"], lecon1, 300, 700, 5)
        activite(a["ali"], lecon2, 200, 500, 3)
        tentatives(a["ali"], quiz[Niveau.DEBUTANT], [25, 25, 50, 25])
        # Amine : moyen
        activite(a["amine"], lecon1, 600, 150, 20)
        tentatives(a["amine"], quiz[Niveau.DEBUTANT], [50, 75])
        # Nour : bonne
        activite(a["nour"], lecon1, 800, 60, 30)
        tentatives(a["nour"], quiz[Niveau.DEBUTANT], [75, 75])
        # Mounir : inscrit sans activité

        for u in apprenants.values():
            analyser_apprenant(u)
            maj_progression(u, cours)

        self.stdout.write(self.style.SUCCESS("Données de démonstration créées."))
        self.stdout.write("Comptes : admin/admin123 - prof/prof1234 - sara, ali, amine, nour, mounir / appr1234")
