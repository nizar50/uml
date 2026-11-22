from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Utilisateur


def appliquer_bootstrap(form):
    """Ajoute les classes Bootstrap aux champs d'un formulaire."""
    for champ in form.fields.values():
        w = champ.widget
        if isinstance(w, forms.CheckboxInput):
            w.attrs["class"] = "form-check-input"
        elif isinstance(w, forms.Select):
            w.attrs["class"] = "form-select"
        else:
            w.attrs["class"] = "form-control"


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        appliquer_bootstrap(self)


class InscriptionForm(BootstrapMixin, UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Utilisateur
        fields = ("username", "first_name", "last_name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            (Utilisateur.Role.APPRENANT, "Apprenant"),
            (Utilisateur.Role.ENSEIGNANT, "Enseignant"),
        ]
        self.fields["role"].initial = Utilisateur.Role.APPRENANT
        self.fields["email"].required = True
        appliquer_bootstrap(self)


class ProfilForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Utilisateur
        fields = ("first_name", "last_name", "email", "specialite")


class ConnexionForm(BootstrapMixin, AuthenticationForm):
    pass
