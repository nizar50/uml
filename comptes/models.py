from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """Utilisateur unique avec un champ role (Administrateur, Enseignant, Apprenant)."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        ENSEIGNANT = "ENSEIGNANT", "Enseignant"
        APPRENANT = "APPRENANT", "Apprenant"

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.APPRENANT)
    specialite = models.CharField("spécialité", max_length=100, blank=True)
    niveau_global = models.FloatField("niveau global", default=0)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    @property
    def nom_complet(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.nom_complet} ({self.get_role_display()})"
