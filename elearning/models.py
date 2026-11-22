from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Niveau(models.TextChoices):
    DEBUTANT = "DEBUTANT", "Débutant"
    INTERMEDIAIRE = "INTERMEDIAIRE", "Intermédiaire"
    AVANCE = "AVANCE", "Avancé"


# ---------- Contenu pédagogique ----------

class Cours(models.Model):
    enseignant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cours_crees")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    niveau = models.CharField(max_length=15, choices=Niveau.choices, default=Niveau.DEBUTANT)
    date_publication = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name_plural = "cours"
        ordering = ["-date_publication", "titre"]

    def __str__(self):
        return self.titre


class Chapitre(models.Model):
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="chapitres")
    titre = models.CharField(max_length=200)
    ordre = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["ordre", "id"]

    def __str__(self):
        return f"{self.cours.titre} - {self.titre}"


class Lecon(models.Model):
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name="lecons")
    titre = models.CharField(max_length=200)
    contenu = models.TextField(blank=True)
    ordre = models.PositiveIntegerField(default=1)
    duree_estimee = models.PositiveIntegerField("durée estimée (min)", default=10)

    class Meta:
        ordering = ["ordre", "id"]

    def __str__(self):
        return self.titre


class Ressource(models.Model):
    class Type(models.TextChoices):
        PDF = "PDF", "PDF"
        VIDEO = "VIDEO", "Vidéo"
        DOC = "DOC", "Document"

    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE, related_name="ressources")
    titre = models.CharField(max_length=200)
    type = models.CharField(max_length=5, choices=Type.choices, default=Type.PDF)
    fichier = models.FileField(upload_to="ressources/")
    niveau = models.CharField(max_length=15, choices=Niveau.choices, default=Niveau.DEBUTANT)

    def __str__(self):
        return self.titre


class Inscription(models.Model):
    apprenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inscriptions")
    cours = models.ForeignKey(Cours, on_delete=models.CASCADE, related_name="inscriptions")
    date_inscription = models.DateField(default=timezone.localdate)
    progression = models.FloatField(default=0)
    statut = models.CharField(max_length=20, default="EN_COURS")

    class Meta:
        unique_together = ("apprenant", "cours")

    def __str__(self):
        return f"{self.apprenant} -> {self.cours}"


# ---------- Quiz ----------

class Quiz(models.Model):
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name="quiz")
    titre = models.CharField(max_length=200)
    niveau = models.CharField(max_length=15, choices=Niveau.choices, default=Niveau.DEBUTANT)
    note_min = models.FloatField("note minimale (%)", default=50)
    duree_max = models.PositiveIntegerField("durée maximale (min)", default=30)

    class Meta:
        verbose_name_plural = "quiz"

    def __str__(self):
        return f"{self.titre} ({self.get_niveau_display()})"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    enonce = models.TextField("énoncé")
    difficulte = models.PositiveSmallIntegerField("difficulté (1 à 3)", default=1)
    points = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.enonce[:60]


class Choix(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choix")
    texte = models.CharField(max_length=300)
    est_correct = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "choix"

    def __str__(self):
        return self.texte


class Tentative(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "EN_COURS", "En cours"
        CORRIGEE = "CORRIGEE", "Corrigée"
        ABANDONNEE = "ABANDONNEE", "Abandonnée"
        EXPIREE = "EXPIREE", "Expirée"

    apprenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tentatives")
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="tentatives")
    numero = models.PositiveIntegerField(default=1)
    date_debut = models.DateTimeField(default=timezone.now)
    date_fin = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True, help_text="pourcentage 0-100")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_COURS)

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return f"{self.apprenant} - {self.quiz} #{self.numero}"


class ReponseDonnee(models.Model):
    tentative = models.ForeignKey(Tentative, on_delete=models.CASCADE, related_name="reponses")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choix = models.ForeignKey(Choix, on_delete=models.SET_NULL, null=True, blank=True)
    est_correcte = models.BooleanField(default=False)
    temps_reponse = models.PositiveIntegerField("temps de réponse (s)", default=0)


# ---------- Suivi comportemental ----------

class ActiviteLog(models.Model):
    """
    OUVERTURE  : ouverture d'une leçon
    TEMPS      : secondes d'activité réelle envoyées par le navigateur
    CLIC       : nombre de clics (interactions) envoyés par paquets
    INACTIVITE : durée (s) d'une période sans interaction
    FERMETURE  : réservé
    """

    class Evenement(models.TextChoices):
        OUVERTURE = "OUVERTURE", "Ouverture"
        TEMPS = "TEMPS", "Temps actif"
        CLIC = "CLIC", "Clics"
        INACTIVITE = "INACTIVITE", "Inactivité"
        FERMETURE = "FERMETURE", "Fermeture"

    apprenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="logs")
    lecon = models.ForeignKey(Lecon, on_delete=models.CASCADE, related_name="logs")
    type_evenement = models.CharField(max_length=12, choices=Evenement.choices)
    horodatage = models.DateTimeField(default=timezone.now)
    duree_secondes = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["apprenant", "lecon", "horodatage"])]


# ---------- Adaptation ----------

class Difficulte(models.Model):
    apprenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="difficultes")
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, related_name="difficultes")
    niveau = models.PositiveSmallIntegerField(default=1, help_text="1 faible, 2 moyen, 3 élevé")
    motif = models.CharField(max_length=255, blank=True)
    date_detection = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = ("apprenant", "chapitre")
        verbose_name = "difficulté"


class Recommandation(models.Model):
    class Type(models.TextChoices):
        REVISION = "REVISION", "Révision"
        RESSOURCE = "RESSOURCE", "Ressource supplémentaire"
        AVANCE = "AVANCE", "Contenu avancé"

    apprenant = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recommandations")
    chapitre = models.ForeignKey(Chapitre, on_delete=models.CASCADE, null=True, blank=True)
    ressource = models.ForeignKey(Ressource, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=Type.choices)
    motif = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(default=timezone.now)
    vue = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date_creation"]


class ParametrePlateforme(models.Model):
    cle = models.CharField(max_length=100, unique=True)
    valeur = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "paramètre"

    def __str__(self):
        return f"{self.cle} = {self.valeur}"
