import json
from collections import Counter
from datetime import timedelta

from django.contrib import messages
from django.db.models import Avg, Count, Sum
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from comptes.decorators import role_required

from .adaptation import analyser_apprenant, choisir_quiz, niveau_recommande, param, profils_classe
from .forms import ChapitreForm, CoursForm, LeconForm, QuestionForm, QuizForm, RessourceForm
from .models import (ActiviteLog, Chapitre, Cours, Difficulte, Inscription, Lecon, Niveau, Question,
                     Quiz, Recommandation, ReponseDonnee, Ressource, Tentative)

PROF = ("ENSEIGNANT", "ADMIN")


# =====================================================================
#  Utilitaires
# =====================================================================

def maj_progression(apprenant, cours):
    """Progression = part des leçons du cours déjà ouvertes."""
    total = Lecon.objects.filter(chapitre__cours=cours).count()
    vues = (ActiviteLog.objects.filter(apprenant=apprenant, lecon__chapitre__cours=cours,
                                       type_evenement=ActiviteLog.Evenement.OUVERTURE)
            .values("lecon").distinct().count())
    valeur = round(100 * vues / total, 1) if total else 0
    Inscription.objects.filter(apprenant=apprenant, cours=cours).update(progression=valeur)


def _cours_prof_or_404(user, pk):
    if user.role == "ADMIN":
        return get_object_or_404(Cours, pk=pk)
    return get_object_or_404(Cours, pk=pk, enseignant=user)


# =====================================================================
#  APPRENANT
# =====================================================================

@role_required("APPRENANT")
def catalogue(request):
    cours = Cours.objects.select_related("enseignant").annotate(nb_inscrits=Count("inscriptions"))
    inscrits = set(Inscription.objects.filter(apprenant=request.user).values_list("cours_id", flat=True))
    return render(request, "elearning/catalogue.html", {"cours": cours, "inscrits": inscrits})


@role_required("APPRENANT")
@require_POST
def inscrire(request, pk):
    cours = get_object_or_404(Cours, pk=pk)
    Inscription.objects.get_or_create(apprenant=request.user, cours=cours)
    messages.success(request, f"Vous êtes inscrit au cours « {cours.titre} ».")
    return redirect("cours_detail", pk=pk)


@role_required("APPRENANT")
def cours_detail(request, pk):
    cours = get_object_or_404(Cours.objects.select_related("enseignant"), pk=pk)
    inscription = Inscription.objects.filter(apprenant=request.user, cours=cours).first()
    if not inscription:
        return render(request, "elearning/cours_detail.html", {"cours": cours, "inscription": None})

    analyses = {r["chapitre"].id: r for r in analyser_apprenant(request.user, appliquer=False)}
    vues = set(ActiviteLog.objects.filter(
        apprenant=request.user, lecon__chapitre__cours=cours,
        type_evenement=ActiviteLog.Evenement.OUVERTURE).values_list("lecon_id", flat=True))
    chapitres = []
    for chap in cours.chapitres.prefetch_related("lecons", "quiz"):
        chapitres.append({
            "chapitre": chap,
            "lecons": [(lec, lec.id in vues) for lec in chap.lecons.all()],
            "quiz": list(chap.quiz.all()),
            "analyse": analyses.get(chap.id),
        })
    return render(request, "elearning/cours_detail.html",
                  {"cours": cours, "inscription": inscription, "chapitres": chapitres})


@role_required("APPRENANT")
def lecon_detail(request, pk):
    lecon = get_object_or_404(Lecon.objects.select_related("chapitre__cours"), pk=pk)
    cours = lecon.chapitre.cours
    if not Inscription.objects.filter(apprenant=request.user, cours=cours).exists():
        messages.warning(request, "Inscrivez-vous au cours pour accéder à ses leçons.")
        return redirect("cours_detail", pk=cours.pk)

    ActiviteLog.objects.create(apprenant=request.user, lecon=lecon,
                               type_evenement=ActiviteLog.Evenement.OUVERTURE)
    maj_progression(request.user, cours)

    toutes = list(Lecon.objects.filter(chapitre__cours=cours).order_by("chapitre__ordre", "ordre", "id"))
    idx = next((i for i, x in enumerate(toutes) if x.pk == lecon.pk), 0)
    return render(request, "elearning/lecon_detail.html", {
        "lecon": lecon, "cours": cours,
        "precedente": toutes[idx - 1] if idx > 0 else None,
        "suivante": toutes[idx + 1] if idx + 1 < len(toutes) else None,
        "ressources": lecon.ressources.all(),
        "quiz": lecon.chapitre.quiz.all(),
        "seuil_inactivite": int(param("seuil_inactivite_sec")),
    })


@role_required("APPRENANT")
@require_POST
def api_suivi(request):
    """Reçoit les événements comportementaux envoyés par static/js/tracker.js."""
    try:
        data = json.loads(request.body)
        lecon = Lecon.objects.get(pk=int(data["lecon_id"]))
        type_evt = data["type"]
        duree = max(0, min(int(data.get("duree", 0)), 3600))
    except (ValueError, KeyError, TypeError, Lecon.DoesNotExist):
        return HttpResponseBadRequest("requête invalide")
    if type_evt not in ActiviteLog.Evenement.values:
        return HttpResponseBadRequest("type inconnu")
    ActiviteLog.objects.create(apprenant=request.user, lecon=lecon, type_evenement=type_evt, duree_secondes=duree)
    return JsonResponse({"ok": True})


@role_required("APPRENANT")
def quiz_passer(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("chapitre__cours"), pk=pk)
    cours = quiz.chapitre.cours
    if not Inscription.objects.filter(apprenant=request.user, cours=cours).exists():
        messages.warning(request, "Inscrivez-vous au cours pour passer ce quiz.")
        return redirect("cours_detail", pk=cours.pk)
    questions = list(quiz.questions.prefetch_related("choix"))
    if not questions:
        messages.info(request, "Ce quiz ne contient pas encore de questions.")
        return redirect("cours_detail", pk=cours.pk)

    if request.method == "POST":
        tentative = get_object_or_404(Tentative, pk=request.POST.get("tentative_id"),
                                      apprenant=request.user, quiz=quiz, statut=Tentative.Statut.EN_COURS)
        total = sum(q.points for q in questions)
        obtenus = 0
        for q in questions:
            choix_id = request.POST.get(f"q_{q.id}")
            choix = next((c for c in q.choix.all() if str(c.id) == choix_id), None)
            correct = bool(choix and choix.est_correct)
            if correct:
                obtenus += q.points
            try:
                temps = max(0, min(int(request.POST.get(f"t_{q.id}", 0)), 3600))
            except ValueError:
                temps = 0
            ReponseDonnee.objects.create(tentative=tentative, question=q, choix=choix,
                                         est_correcte=correct, temps_reponse=temps)
        maintenant = timezone.now()
        depasse = (maintenant - tentative.date_debut).total_seconds() > quiz.duree_max * 60 + 60
        tentative.score = round(100 * obtenus / total, 1) if total else 0
        tentative.date_fin = maintenant
        tentative.statut = Tentative.Statut.EXPIREE if depasse else Tentative.Statut.CORRIGEE
        tentative.save()
        analyser_apprenant(request.user)
        return redirect("quiz_resultat", pk=tentative.pk)

    limite = timezone.now() - timedelta(minutes=quiz.duree_max)
    Tentative.objects.filter(apprenant=request.user, quiz=quiz, statut=Tentative.Statut.EN_COURS,
                             date_debut__lt=limite).update(statut=Tentative.Statut.ABANDONNEE)
    tentative = Tentative.objects.filter(apprenant=request.user, quiz=quiz,
                                         statut=Tentative.Statut.EN_COURS).first()
    if not tentative:
        numero = Tentative.objects.filter(apprenant=request.user, quiz=quiz).count() + 1
        tentative = Tentative.objects.create(apprenant=request.user, quiz=quiz, numero=numero)
    ecoule = (timezone.now() - tentative.date_debut).total_seconds()
    reste = max(0, int(quiz.duree_max * 60 - ecoule))
    return render(request, "elearning/quiz_passer.html",
                  {"quiz": quiz, "questions": questions, "tentative": tentative, "reste": reste})


@role_required("APPRENANT")
def quiz_resultat(request, pk):
    tentative = get_object_or_404(Tentative.objects.select_related("quiz__chapitre__cours"),
                                  pk=pk, apprenant=request.user)
    details = []
    for r in tentative.reponses.select_related("question", "choix"):
        details.append({"reponse": r, "bonne": r.question.choix.filter(est_correct=True).first()})
    chap = tentative.quiz.chapitre
    scores = list(Tentative.objects.filter(apprenant=request.user, quiz__chapitre=chap, score__isnull=False)
                  .order_by("date_debut").values_list("score", flat=True))
    return render(request, "elearning/quiz_resultat.html", {
        "tentative": tentative,
        "details": details,
        "reussi": tentative.score is not None and tentative.score >= tentative.quiz.note_min,
        "prochain": choisir_quiz(chap, scores),
        "niveau": Niveau(niveau_recommande(scores)).label,
        "recos": Recommandation.objects.filter(apprenant=request.user, chapitre=chap, vue=False)
                                       .select_related("ressource"),
    })


@role_required("APPRENANT")
def dashboard_apprenant(request):
    user = request.user
    resultats = analyser_apprenant(user)
    inscriptions = list(Inscription.objects.filter(apprenant=user).select_related("cours"))
    for ins in inscriptions:
        maj_progression(user, ins.cours)
    inscriptions = list(Inscription.objects.filter(apprenant=user).select_related("cours"))

    tentatives = list(Tentative.objects.filter(apprenant=user, score__isnull=False)
                      .select_related("quiz").order_by("date_debut"))[-15:]
    temps = (ActiviteLog.objects.filter(apprenant=user, type_evenement=ActiviteLog.Evenement.TEMPS)
             .values("lecon__titre").annotate(total=Sum("duree_secondes")).order_by("-total")[:8])
    donnees = {
        "scores": {"labels": [f"{t.quiz.titre} #{t.numero}" for t in tentatives],
                   "values": [t.score for t in tentatives]},
        "temps": {"labels": [x["lecon__titre"] for x in temps],
                  "values": [round(x["total"] / 60, 1) for x in temps]},
        "progression": {"labels": [i.cours.titre for i in inscriptions],
                        "values": [i.progression for i in inscriptions]},
    }
    return render(request, "elearning/dashboard_apprenant.html", {
        "donnees": donnees,
        "resultats": resultats,
        "difficultes": [r for r in resultats if r["difficulte"] > 0],
        "recommandations": Recommandation.objects.filter(apprenant=user, vue=False)
                                                 .select_related("ressource", "chapitre"),
        "inscriptions": inscriptions,
    })


@role_required("APPRENANT")
def reco_suivre(request, pk):
    reco = get_object_or_404(Recommandation, pk=pk, apprenant=request.user)
    reco.vue = True
    reco.save(update_fields=["vue"])
    if reco.ressource and reco.ressource.fichier:
        return redirect(reco.ressource.fichier.url)
    if reco.chapitre:
        if reco.type == Recommandation.Type.AVANCE:
            quiz = reco.chapitre.quiz.filter(niveau=Niveau.AVANCE).first()
            if quiz:
                return redirect("quiz_passer", pk=quiz.pk)
        lecon = reco.chapitre.lecons.first()
        if lecon:
            return redirect("lecon_detail", pk=lecon.pk)
        return redirect("cours_detail", pk=reco.chapitre.cours_id)
    return redirect("dashboard_apprenant")


# =====================================================================
#  ENSEIGNANT
# =====================================================================

@role_required(*PROF)
def enseignant_accueil(request):
    qs = Cours.objects.all() if request.user.role == "ADMIN" else Cours.objects.filter(enseignant=request.user)
    cours = qs.annotate(nb_inscrits=Count("inscriptions", distinct=True),
                        nb_chapitres=Count("chapitres", distinct=True))
    return render(request, "elearning/enseignant_accueil.html", {"cours": cours})


def _formulaire(request, form_class, titre, cours, assigner):
    """Affiche/valide un formulaire de création. Retourne (objet, réponse)."""
    form = form_class(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        assigner(obj)
        obj.save()
        if hasattr(form, "apres_enregistrement"):
            form.apres_enregistrement(obj)
        messages.success(request, "Enregistré.")
        if getattr(form, "fichier_sans_texte", False):
            messages.warning(request, "Aucun texte n'a pu être extrait du fichier (PDF scanné ?). "
                                      "Il reste disponible en téléchargement dans les ressources.")
        return obj, None
    retour = reverse("cours_gerer", args=[cours.pk]) if cours else reverse("enseignant_accueil")
    return None, render(request, "elearning/form.html", {"form": form, "titre": titre, "retour": retour})


@role_required(*PROF)
def cours_creer(request):
    def assigner(o):
        o.enseignant = request.user
    obj, reponse = _formulaire(request, CoursForm, "Nouveau cours", None, assigner)
    if reponse is not None:
        return reponse
    return redirect("cours_gerer", pk=obj.pk)


@role_required(*PROF)
def cours_gerer(request, pk):
    cours = _cours_prof_or_404(request.user, pk)
    chapitres = cours.chapitres.prefetch_related("lecons__ressources", "quiz__questions")
    return render(request, "elearning/cours_gerer.html", {"cours": cours, "chapitres": chapitres})


@role_required(*PROF)
def chapitre_creer(request, cours_id):
    cours = _cours_prof_or_404(request.user, cours_id)

    def assigner(o):
        o.cours = cours
        o.ordre = cours.chapitres.count() + 1
    _, reponse = _formulaire(request, ChapitreForm, "Nouveau chapitre", cours, assigner)
    return reponse if reponse is not None else redirect("cours_gerer", pk=cours.pk)


@role_required(*PROF)
def lecon_creer(request, chapitre_id):
    chap = get_object_or_404(Chapitre.objects.select_related("cours"), pk=chapitre_id)
    cours = _cours_prof_or_404(request.user, chap.cours_id)

    def assigner(o):
        o.chapitre = chap
    _, reponse = _formulaire(request, LeconForm, f"Nouvelle leçon - {chap.titre}", cours, assigner)
    return reponse if reponse is not None else redirect("cours_gerer", pk=cours.pk)


@role_required(*PROF)
def ressource_ajouter(request, lecon_id):
    lecon = get_object_or_404(Lecon.objects.select_related("chapitre__cours"), pk=lecon_id)
    cours = _cours_prof_or_404(request.user, lecon.chapitre.cours_id)

    def assigner(o):
        o.lecon = lecon
    _, reponse = _formulaire(request, RessourceForm, f"Ressource pour la leçon « {lecon.titre} »", cours, assigner)
    return reponse if reponse is not None else redirect("cours_gerer", pk=cours.pk)


@role_required(*PROF)
def quiz_creer(request, chapitre_id):
    chap = get_object_or_404(Chapitre.objects.select_related("cours"), pk=chapitre_id)
    cours = _cours_prof_or_404(request.user, chap.cours_id)

    def assigner(o):
        o.chapitre = chap
    obj, reponse = _formulaire(request, QuizForm, f"Nouveau quiz - {chap.titre}", cours, assigner)
    return reponse if reponse is not None else redirect("quiz_gerer", pk=obj.pk)


@role_required(*PROF)
def quiz_gerer(request, pk):
    quiz = get_object_or_404(Quiz.objects.select_related("chapitre__cours"), pk=pk)
    _cours_prof_or_404(request.user, quiz.chapitre.cours_id)
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.enregistrer(quiz)
        messages.success(request, "Question ajoutée.")
        return redirect("quiz_gerer", pk=quiz.pk)
    return render(request, "elearning/quiz_gerer.html", {
        "quiz": quiz, "form": form, "questions": quiz.questions.prefetch_related("choix")})


KINDS = {
    "cours": (Cours, CoursForm, lambda o: o),
    "chapitre": (Chapitre, ChapitreForm, lambda o: o.cours),
    "lecon": (Lecon, LeconForm, lambda o: o.chapitre.cours),
    "quiz": (Quiz, QuizForm, lambda o: o.chapitre.cours),
    "ressource": (Ressource, RessourceForm, lambda o: o.lecon.chapitre.cours),
    "question": (Question, None, lambda o: o.quiz.chapitre.cours),
}


def _objet(request, kind, pk):
    if kind not in KINDS:
        raise Http404
    modele, form_class, get_cours = KINDS[kind]
    obj = get_object_or_404(modele, pk=pk)
    cours = _cours_prof_or_404(request.user, get_cours(obj).pk)
    return obj, form_class, cours


@role_required(*PROF)
def objet_modifier(request, kind, pk):
    obj, form_class, cours = _objet(request, kind, pk)
    if form_class is None:
        raise Http404
    form = form_class(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        if hasattr(form, "apres_enregistrement"):
            form.apres_enregistrement(obj)
        messages.success(request, "Modifications enregistrées.")
        return redirect("cours_gerer", pk=cours.pk)
    return render(request, "elearning/form.html", {
        "form": form, "titre": f"Modifier : {obj}", "retour": reverse("cours_gerer", args=[cours.pk])})


@role_required(*PROF)
def objet_supprimer(request, kind, pk):
    obj, _, cours = _objet(request, kind, pk)
    if request.method == "POST":
        quiz_pk = obj.quiz_id if kind == "question" else None
        obj.delete()
        messages.success(request, "Élément supprimé.")
        if kind == "cours":
            return redirect("enseignant_accueil")
        if quiz_pk:
            return redirect("quiz_gerer", pk=quiz_pk)
        return redirect("cours_gerer", pk=cours.pk)
    return render(request, "elearning/confirmer_suppression.html", {
        "objet": obj, "retour": reverse("cours_gerer", args=[cours.pk])})


@role_required(*PROF)
def cours_stats(request, pk):
    cours = _cours_prof_or_404(request.user, pk)
    profils = profils_classe(cours)

    par_quiz = (Tentative.objects.filter(quiz__chapitre__cours=cours, score__isnull=False)
                .values("quiz_id", "quiz__titre", "quiz__niveau")
                .annotate(moyenne=Avg("score"), nb=Count("id")).order_by("quiz_id"))
    par_lecon = (ActiviteLog.objects.filter(lecon__chapitre__cours=cours,
                                            type_evenement=ActiviteLog.Evenement.TEMPS)
                 .values("lecon_id", "lecon__titre")
                 .annotate(total=Sum("duree_secondes"), nb=Count("apprenant", distinct=True))
                 .order_by("lecon_id"))
    repartition = Counter(p["profil"] for p in profils)
    ordre = ["En difficulté", "Intermédiaire", "Performant", "Sans données"]

    donnees = {
        "quiz": {"labels": [f"{q['quiz__titre']} ({q['quiz__niveau'].lower()})" for q in par_quiz],
                 "values": [round(q["moyenne"], 1) for q in par_quiz]},
        "lecons": {"labels": [x["lecon__titre"] for x in par_lecon],
                   "values": [round(x["total"] / max(x["nb"], 1) / 60, 1) for x in par_lecon]},
        "profils": {"labels": ordre, "values": [repartition.get(n, 0) for n in ordre]},
    }
    return render(request, "elearning/cours_stats.html", {
        "cours": cours, "profils": profils, "donnees": donnees,
        "difficultes": Difficulte.objects.filter(chapitre__cours=cours)
                                         .select_related("apprenant", "chapitre").order_by("-niveau"),
    })
