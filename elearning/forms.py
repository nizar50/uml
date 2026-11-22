from django import forms

from comptes.forms import BootstrapMixin

from .importation import extraire_texte
from .models import Chapitre, Choix, Cours, Lecon, Question, Quiz, Ressource


class CoursForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Cours
        fields = ("titre", "description", "niveau")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ChapitreForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Chapitre
        fields = ("titre", "ordre")


class LeconForm(BootstrapMixin, forms.ModelForm):
    fichier_import = forms.FileField(
        label="Importer un fichier PDF ou Word (.docx)", required=False,
        help_text="Le texte du fichier est copié dans le contenu (si celui-ci est vide) "
                  "et le fichier est ajouté comme ressource téléchargeable.")

    class Meta:
        model = Lecon
        fields = ("titre", "contenu", "ordre", "duree_estimee")
        widgets = {"contenu": forms.Textarea(attrs={"rows": 8})}

    def clean_fichier_import(self):
        f = self.cleaned_data.get("fichier_import")
        if not f:
            return f
        nom = f.name.lower()
        if nom.endswith(".doc"):
            raise forms.ValidationError("Le format .doc n'est pas supporté : enregistrez le fichier en .docx ou en PDF.")
        if not nom.endswith((".pdf", ".docx")):
            raise forms.ValidationError("Formats acceptés : PDF et Word (.docx).")
        if f.size > 20 * 1024 * 1024:
            raise forms.ValidationError("Fichier trop volumineux (20 Mo maximum).")
        return f

    def clean(self):
        data = super().clean()
        self.fichier_sans_texte = False
        f = data.get("fichier_import")
        if f:
            try:
                texte = extraire_texte(f)
            except Exception:
                self.add_error("fichier_import", "Impossible de lire ce fichier (corrompu ou protégé par mot de passe).")
                return data
            if texte and not data.get("contenu"):
                data["contenu"] = texte
            self.fichier_sans_texte = not texte
        return data

    def apres_enregistrement(self, lecon):
        """Ajoute le fichier importé comme ressource de la leçon."""
        f = self.cleaned_data.get("fichier_import")
        if f:
            f.seek(0)
            type_res = Ressource.Type.PDF if f.name.lower().endswith(".pdf") else Ressource.Type.DOC
            Ressource.objects.create(lecon=lecon, titre=f.name.rsplit(".", 1)[0][:200],
                                     type=type_res, fichier=f, niveau="DEBUTANT")


class RessourceForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Ressource
        fields = ("titre", "type", "fichier", "niveau")


class QuizForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ("titre", "niveau", "note_min", "duree_max")


class QuestionForm(BootstrapMixin, forms.Form):
    enonce = forms.CharField(label="Énoncé", widget=forms.Textarea(attrs={"rows": 2}))
    difficulte = forms.ChoiceField(label="Difficulté", choices=[("1", "Facile"), ("2", "Moyenne"), ("3", "Difficile")])
    points = forms.IntegerField(label="Points", min_value=1, initial=1)
    choix_1 = forms.CharField(label="Choix 1")
    choix_2 = forms.CharField(label="Choix 2")
    choix_3 = forms.CharField(label="Choix 3 (facultatif)", required=False)
    choix_4 = forms.CharField(label="Choix 4 (facultatif)", required=False)
    bonne_reponse = forms.ChoiceField(label="Bonne réponse",
                                      choices=[("1", "Choix 1"), ("2", "Choix 2"), ("3", "Choix 3"), ("4", "Choix 4")])

    def clean(self):
        data = super().clean()
        bonne = data.get("bonne_reponse")
        if bonne and not data.get(f"choix_{bonne}"):
            self.add_error("bonne_reponse", "La bonne réponse doit correspondre à un choix rempli.")
        return data

    def enregistrer(self, quiz):
        d = self.cleaned_data
        question = Question.objects.create(quiz=quiz, enonce=d["enonce"],
                                           difficulte=int(d["difficulte"]), points=d["points"])
        for i in range(1, 5):
            texte = d.get(f"choix_{i}")
            if texte:
                Choix.objects.create(question=question, texte=texte, est_correct=(d["bonne_reponse"] == str(i)))
        return question
