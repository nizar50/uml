from django.urls import path

from . import views

urlpatterns = [
    # apprenant
    path("catalogue/", views.catalogue, name="catalogue"),
    path("cours/<int:pk>/", views.cours_detail, name="cours_detail"),
    path("cours/<int:pk>/inscription/", views.inscrire, name="inscrire"),
    path("lecon/<int:pk>/", views.lecon_detail, name="lecon_detail"),
    path("api/suivi/", views.api_suivi, name="api_suivi"),
    path("quiz/<int:pk>/", views.quiz_passer, name="quiz_passer"),
    path("resultat/<int:pk>/", views.quiz_resultat, name="quiz_resultat"),
    path("tableau-de-bord/", views.dashboard_apprenant, name="dashboard_apprenant"),
    path("recommandation/<int:pk>/", views.reco_suivre, name="reco_suivre"),
    # enseignant
    path("enseignant/", views.enseignant_accueil, name="enseignant_accueil"),
    path("enseignant/cours/creer/", views.cours_creer, name="cours_creer"),
    path("enseignant/cours/<int:pk>/gerer/", views.cours_gerer, name="cours_gerer"),
    path("enseignant/cours/<int:pk>/stats/", views.cours_stats, name="cours_stats"),
    path("enseignant/chapitre/creer/<int:cours_id>/", views.chapitre_creer, name="chapitre_creer"),
    path("enseignant/lecon/creer/<int:chapitre_id>/", views.lecon_creer, name="lecon_creer"),
    path("enseignant/ressource/ajouter/<int:lecon_id>/", views.ressource_ajouter, name="ressource_ajouter"),
    path("enseignant/quiz/creer/<int:chapitre_id>/", views.quiz_creer, name="quiz_creer"),
    path("enseignant/quiz/<int:pk>/gerer/", views.quiz_gerer, name="quiz_gerer"),
    path("enseignant/<str:kind>/<int:pk>/modifier/", views.objet_modifier, name="objet_modifier"),
    path("enseignant/<str:kind>/<int:pk>/supprimer/", views.objet_supprimer, name="objet_supprimer"),
]
