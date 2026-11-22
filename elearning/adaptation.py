"""
Moteur d'analyse comportementale et d'adaptation pédagogique.

- Pandas : agrégation des tentatives et des logs d'activité par chapitre.
- Règles de diagnostic (seuils modifiables dans ParametrePlateforme via l'admin).
- Scikit-learn : classement des apprenants d'un cours en profils (KMeans).
"""
import pandas as pd
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import (ActiviteLog, Chapitre, Difficulte, Niveau, ParametrePlateforme, Quiz,
                     Recommandation, Ressource, Tentative)

User = get_user_model()

DEFAUTS = {
    "seuil_score_difficulte": 50,   # un score en dessous = difficulté (%)
    "seuil_score_excellence": 80,   # un score au-dessus = contenu avancé (%)
    "tentatives_max": 3,            # tentatives sans réussite avant alerte
    "seuil_inactivite_sec": 60,     # secondes sans interaction = inactivité
    "ratio_inactivite_max": 0.4,    # part d'inactivité tolérée (0 à 1)
}
DESCRIPTIONS = {
    "seuil_score_difficulte": "Score (%) en dessous duquel une difficulté est détectée",
    "seuil_score_excellence": "Score (%) à partir duquel du contenu avancé est proposé",
    "tentatives_max": "Nombre de tentatives sans réussite avant alerte",
    "seuil_inactivite_sec": "Secondes sans interaction avant de compter de l'inactivité",
    "ratio_inactivite_max": "Part maximale d'inactivité tolérée (0 à 1)",
}
ORDRE_NIVEAUX = [Niveau.DEBUTANT.value, Niveau.INTERMEDIAIRE.value, Niveau.AVANCE.value]


def param(cle):
    try:
        return float(ParametrePlateforme.objects.get(cle=cle).valeur)
    except (ParametrePlateforme.DoesNotExist, ValueError):
        return float(DEFAUTS[cle])


# ---------- Chargement des données avec Pandas ----------

def _df_tentatives(**filtres):
    cols = ["apprenant_id", "quiz_id", "chapitre_id", "score", "date_debut"]
    rows = Tentative.objects.filter(score__isnull=False, **filtres).values_list(
        "apprenant_id", "quiz_id", "quiz__chapitre_id", "score", "date_debut")
    return pd.DataFrame(list(rows), columns=cols)


def _df_logs(**filtres):
    cols = ["apprenant_id", "lecon_id", "chapitre_id", "type", "duree"]
    rows = ActiviteLog.objects.filter(**filtres).values_list(
        "apprenant_id", "lecon_id", "lecon__chapitre_id", "type_evenement", "duree_secondes")
    return pd.DataFrame(list(rows), columns=cols)


def _stats(t, l):
    """Indicateurs d'un apprenant (ou d'un chapitre) à partir des DataFrames filtrés."""
    scores = t.sort_values("date_debut")["score"].tolist()
    nb = len(scores)
    temps = int(l.loc[l["type"] == "TEMPS", "duree"].sum())
    inactif = int(l.loc[l["type"] == "INACTIVITE", "duree"].sum())
    total = temps + inactif
    return {
        "nb_tentatives": nb,
        "scores": scores,
        "moyenne": round(sum(scores) / nb, 1) if nb else None,
        "derniere": scores[-1] if nb else None,
        "meilleur": max(scores) if nb else None,
        "temps": temps,
        "temps_min": round(temps / 60, 1),
        "inactivite": inactif,
        "ratio_inactivite": round(inactif / total, 2) if total else 0.0,
    }


# ---------- Diagnostic et choix du niveau ----------

def _diagnostic(st):
    seuil = param("seuil_score_difficulte")
    tmax = param("tentatives_max")
    rmax = param("ratio_inactivite_max")
    niveau, motifs = 0, []
    if st["nb_tentatives"]:
        if st["derniere"] < seuil:
            niveau += 1
            motifs.append(f"dernier score {st['derniere']:.0f} % (seuil {seuil:.0f} %)")
        if st["nb_tentatives"] >= tmax and st["meilleur"] < seuil:
            niveau += 1
            motifs.append(f"{st['nb_tentatives']} tentatives sans réussite")
    if st["temps"] + st["inactivite"] >= 120 and st["ratio_inactivite"] > rmax:
        niveau += 1
        motifs.append(f"inactivité élevée ({st['ratio_inactivite'] * 100:.0f} % du temps)")
    return min(niveau, 3), "; ".join(motifs)


def niveau_recommande(scores):
    """Niveau d'exercices adapté selon les deux derniers scores."""
    if not scores:
        return Niveau.DEBUTANT.value
    recents = scores[-2:]
    moyenne = sum(recents) / len(recents)
    if moyenne < param("seuil_score_difficulte"):
        return Niveau.DEBUTANT.value
    if moyenne < param("seuil_score_excellence"):
        return Niveau.INTERMEDIAIRE.value
    return Niveau.AVANCE.value


def choisir_quiz(chapitre, scores):
    """Quiz du chapitre dont le niveau est le plus proche du niveau recommandé."""
    quiz = list(Quiz.objects.filter(chapitre=chapitre).prefetch_related("questions"))
    quiz = [q for q in quiz if q.questions.exists()]
    if not quiz:
        return None
    cible = ORDRE_NIVEAUX.index(niveau_recommande(scores))
    quiz.sort(key=lambda q: (abs(ORDRE_NIVEAUX.index(q.niveau) - cible), ORDRE_NIVEAUX.index(q.niveau)))
    return quiz[0]


# ---------- Application : difficultés et recommandations ----------

def _appliquer(apprenant, chap, st):
    if st["difficulte"] > 0:
        Difficulte.objects.update_or_create(
            apprenant=apprenant, chapitre=chap,
            defaults={"niveau": st["difficulte"], "motif": st["motif"][:255],
                      "date_detection": timezone.localdate()})
        Recommandation.objects.get_or_create(
            apprenant=apprenant, chapitre=chap, type=Recommandation.Type.REVISION, ressource=None,
            defaults={"motif": f"Revoyez les leçons du chapitre « {chap.titre} » ({st['motif']})"[:255]})
        for res in Ressource.objects.filter(lecon__chapitre=chap, niveau=Niveau.DEBUTANT)[:3]:
            Recommandation.objects.get_or_create(
                apprenant=apprenant, chapitre=chap, type=Recommandation.Type.RESSOURCE, ressource=res,
                defaults={"motif": f"Ressource d'appui pour « {chap.titre} »"})
    else:
        Difficulte.objects.filter(apprenant=apprenant, chapitre=chap).delete()
        Recommandation.objects.filter(
            apprenant=apprenant, chapitre=chap, vue=False,
            type__in=[Recommandation.Type.REVISION, Recommandation.Type.RESSOURCE]).delete()

    if st["derniere"] is not None and st["derniere"] >= param("seuil_score_excellence"):
        avancees = list(Ressource.objects.filter(lecon__chapitre=chap, niveau=Niveau.AVANCE)[:3])
        for res in avancees:
            Recommandation.objects.get_or_create(
                apprenant=apprenant, chapitre=chap, type=Recommandation.Type.AVANCE, ressource=res,
                defaults={"motif": f"Excellent résultat sur « {chap.titre} » : allez plus loin"})
        if not avancees and Quiz.objects.filter(chapitre=chap, niveau=Niveau.AVANCE).exists():
            Recommandation.objects.get_or_create(
                apprenant=apprenant, chapitre=chap, type=Recommandation.Type.AVANCE, ressource=None,
                defaults={"motif": f"Excellent résultat sur « {chap.titre} » : tentez le quiz avancé"})


def analyser_apprenant(apprenant, appliquer=True):
    """Analyse chaque chapitre des cours suivis ; met à jour difficultés et recommandations."""
    chapitres = list(Chapitre.objects.filter(cours__inscriptions__apprenant=apprenant)
                     .select_related("cours").distinct())
    df_t = _df_tentatives(apprenant=apprenant)
    df_l = _df_logs(apprenant=apprenant)
    resultats = []
    for chap in chapitres:
        st = _stats(df_t[df_t["chapitre_id"] == chap.id], df_l[df_l["chapitre_id"] == chap.id])
        niveau, motif = _diagnostic(st)
        st.update(chapitre=chap, difficulte=niveau, motif=motif,
                  niveau_recommande=niveau_recommande(st["scores"]),
                  niveau_label=Niveau(niveau_recommande(st["scores"])).label,
                  quiz_recommande=choisir_quiz(chap, st["scores"]))
        if appliquer:
            _appliquer(apprenant, chap, st)
        resultats.append(st)
    return resultats


# ---------- Profils des apprenants d'un cours (Scikit-learn) ----------

def profils_classe(cours):
    inscrits = list(User.objects.filter(inscriptions__cours=cours, role="APPRENANT").distinct())
    df_t = _df_tentatives(quiz__chapitre__cours=cours)
    df_l = _df_logs(lecon__chapitre__cours=cours)
    lignes = []
    for u in inscrits:
        st = _stats(df_t[df_t["apprenant_id"] == u.id], df_l[df_l["apprenant_id"] == u.id])
        lignes.append({"apprenant": u, "moyenne": st["moyenne"], "tentatives": st["nb_tentatives"],
                       "temps_min": round(st["temps"] / 60, 1), "ratio_inactivite": st["ratio_inactivite"],
                       "profil": "Sans données"})
    actifs = [x for x in lignes if x["tentatives"] > 0]
    seuil = param("seuil_score_difficulte")
    excellence = param("seuil_score_excellence")

    if len(actifs) >= 3:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        X = [[x["moyenne"], x["tentatives"], x["temps_min"], x["ratio_inactivite"]] for x in actifs]
        etiquettes = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(StandardScaler().fit_transform(X))
        moyennes = {}
        for x, c in zip(actifs, etiquettes):
            moyennes.setdefault(int(c), []).append(x["moyenne"])
        ordre = sorted(moyennes, key=lambda c: sum(moyennes[c]) / len(moyennes[c]))
        noms = ["En difficulté", "Intermédiaire", "Performant"]
        correspondance = {c: noms[i] for i, c in enumerate(ordre)}
        for x, c in zip(actifs, etiquettes):
            profil = correspondance[int(c)]
            # garde-fou : un cluster ne doit pas contredire les seuils pédagogiques
            if profil == "En difficulté" and x["moyenne"] >= seuil + 20:
                profil = "Intermédiaire"
            if profil == "Performant" and x["moyenne"] < seuil:
                profil = "Intermédiaire"
            x["profil"] = profil
    else:
        for x in actifs:
            if x["moyenne"] < seuil:
                x["profil"] = "En difficulté"
            elif x["moyenne"] >= excellence:
                x["profil"] = "Performant"
            else:
                x["profil"] = "Intermédiaire"
    return lignes
