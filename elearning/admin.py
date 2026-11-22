from django.contrib import admin

from . import models

for m in [models.Cours, models.Chapitre, models.Lecon, models.Ressource, models.Inscription,
          models.Quiz, models.Question, models.Choix, models.Tentative, models.ReponseDonnee,
          models.Recommandation, models.Difficulte]:
    admin.site.register(m)


@admin.register(models.ParametrePlateforme)
class ParametreAdmin(admin.ModelAdmin):
    list_display = ("cle", "valeur", "description")


@admin.register(models.ActiviteLog)
class ActiviteLogAdmin(admin.ModelAdmin):
    list_display = ("apprenant", "lecon", "type_evenement", "duree_secondes", "horodatage")
    list_filter = ("type_evenement",)
