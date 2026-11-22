from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import ConnexionForm

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("connexion/", auth_views.LoginView.as_view(template_name="comptes/login.html", authentication_form=ConnexionForm), name="connexion"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="deconnexion"),
    path("inscription/", views.inscription, name="inscription"),
    path("profil/", views.profil, name="profil"),
]
