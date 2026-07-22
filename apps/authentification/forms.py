from django import forms
from .models import Utilisateur

class PersonnelForm(forms.ModelForm):
    """Formulaire pour ajouter ou modifier un membre du personnel administratif ou enseignant"""
    
    # Rôles du personnel uniquement (on exclut les étudiants et apprenants)
    ROLES_PERSONNEL = [
        ('FORMATEUR', '👨‍🏫 Formateur (Certifications)'),
        ('PROFESSEUR', '👨‍🏫 Professeur'),
        ('ENSEIGNANT', '👨‍🏫 Enseignant'),
        ('ADMIN_PEDAGOGIQUE', '📚 Admin Pédagogique'),
        ('ADMIN_FINANCIER', '💰 Admin Financier'),
        ('CHEF_SCOLARITE', '🏫 Chef Scolarité'),
        ('CHEF_ETUDES', '📚 Chef Études'),
        ('CHEF_ANONYMAT', '🕵️ Chef Anonymat'),
        ('CHEF_COMPTABILITE', '💰 Chef Comptabilité'),
        ('ADMIN_SYSTEME', '⚙️ Admin Système'),
    ]

    type_utilisateur = forms.ChoiceField(
        choices=ROLES_PERSONNEL,
        label="Fonction / Rôle",
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'})
    )

    class Meta:
        model = Utilisateur
        fields = ['username', 'first_name', 'last_name', 'email', 'telephone', 'adresse', 'type_utilisateur', 'matricule']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'}),
            'telephone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500', 'placeholder': '6XXXXXXXX'}),
            'adresse': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500', 'rows': 2}),
            'matricule': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500', 'placeholder': 'Généré automatiquement si laissé vide'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Permettre au matricule d'être facultatif lors de la saisie (généré au besoin lors de l'activation/sauvegarde)
        self.fields['matricule'].required = False
        self.fields['email'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class CreationPersonnelForm(PersonnelForm):
    """Formulaire spécifique pour l'ajout avec mot de passe initial"""
    password = forms.CharField(
        label="Mot de passe initial",
        widget=forms.PasswordInput(attrs={'class': 'w-full px-4 py-2 border rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500'}),
        help_text="Mot de passe provisoire pour la première connexion."
    )

    class Meta(PersonnelForm.Meta):
        fields = PersonnelForm.Meta.fields + ['password']
