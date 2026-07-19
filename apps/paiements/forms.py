import os
from django import forms
from django.core.exceptions import ValidationError
from .models import RecuPaiement

ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 Mo

def valider_fichier_recu(file):
    if not file:
        return file
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Format de fichier non supporté '{ext}'. Extensions autorisées : {', '.join(ALLOWED_EXTENSIONS)}"
        )
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"Fichier trop volumineux ({round(file.size / (1024 * 1024), 2)} Mo). Taille maximale : 5 Mo."
        )
    return file

class RecuPaiementForm(forms.ModelForm):
    class Meta:
        model = RecuPaiement
        fields = ['tranche', 'recu_fichier', 'montant_mentionne', 'reference_recu']

    def clean_recu_fichier(self):
        file = self.cleaned_data.get('recu_fichier')
        return valider_fichier_recu(file)
