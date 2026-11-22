from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import InscriptionForm, ProfilForm
from .models import Utilisateur


def accueil(request):
    if request.user.is_authenticated:
        if request.user.role == Utilisateur.Role.ENSEIGNANT:
            return redirect("enseignant_accueil")
        if request.user.role == Utilisateur.Role.APPRENANT:
            return redirect("dashboard_apprenant")
        return redirect("/admin/")
    return render(request, "comptes/accueil.html")


def inscription(request):
    if request.user.is_authenticated:
        return redirect("accueil")
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Compte créé. Bienvenue !")
        return redirect("accueil")
    return render(request, "comptes/register.html", {"form": form})


@login_required
def profil(request):
    form = ProfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profil mis à jour.")
        return redirect("profil")
    return render(request, "comptes/profil.html", {"form": form})
