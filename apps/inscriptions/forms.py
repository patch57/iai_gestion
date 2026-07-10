"""
Formulaires pour la gestion des inscriptions
IAI-Cameroun - Centre de Douala
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder
from .models import Inscription, DocumentInscription, AnneeAcademique
from apps.etudiants.models import Etudiant, Filiere


class InscriptionForm(forms.ModelForm):
    """Formulaire pour créer/modifier une inscription"""
    
    class Meta:
        model = Inscription
        fields = [
            'etudiant', 'annee_academique', 'type_inscription', 'filiere',
            'statut', 'recu_preinscription', 'recu_tranche_1', 'recu_tranche_2', 'recu_tranche_3',
            'documents_complets', 'commentaire'
        ]
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les étudiants non encore inscrits pour l'année en cours
        annee_active = AnneeAcademique.get_active()
        if annee_active:
            inscrits_ids = Inscription.objects.filter(
                annee_academique=annee_active
            ).values_list('etudiant_id', flat=True)
            self.fields['etudiant'].queryset = Etudiant.objects.exclude(
                id__in=inscrits_ids
            ).filter(statut__in=['PREINSCRIT', 'ACTIF'])
        
        # Filtrer les années académiques
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.all()
        
        # Filtrer les filières actives
        self.fields['filiere'].queryset = Filiere.objects.filter(est_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Fieldset(
                'Informations générales',
                Row(
                    Column('etudiant', css_class='col-md-6'),
                    Column('annee_academique', css_class='col-md-6'),
                ),
                Row(
                    Column('type_inscription', css_class='col-md-6'),
                    Column('filiere', css_class='col-md-6'),
                ),
                'statut',
            ),
            Fieldset(
                'Reçus de paiement (téléversement uniquement)',
                Row(
                    Column('recu_preinscription', css_class='col-md-6'),
                ),
                Row(
                    Column('recu_tranche_1', css_class='col-md-4'),
                    Column('recu_tranche_2', css_class='col-md-4'),
                    Column('recu_tranche_3', css_class='col-md-4'),
                ),
                'documents_complets',
                help_text="Les reçus sont téléversés pour vérification. Aucun paiement n'est effectué sur cette plateforme.",
            ),
            Fieldset(
                'Commentaire',
                'commentaire',
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class DocumentInscriptionForm(forms.ModelForm):
    """Formulaire pour ajouter un document à une inscription"""
    
    class Meta:
        model = DocumentInscription
        fields = ['type_document', 'fichier', 'commentaire']
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            'type_document',
            'fichier',
            'commentaire',
            ButtonHolder(
                Submit('submit', 'Ajouter le document', css_class='btn btn-primary'),
            )
        )


class RechercheInscriptionForm(forms.Form):
    """Formulaire de recherche d'inscriptions"""
    recherche = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Rechercher par matricule, nom, prénom...',
            'class': 'form-control'
        })
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(est_active=True),
        required=False,
        empty_label='Toutes les filières'
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + list(Inscription.STATUT_CHOICES),
        required=False
    )
    type_inscription = forms.ChoiceField(
        choices=[('', 'Tous les types')] + list(Inscription.TYPE_INSCRIPTION_CHOICES),
        required=False
    )
    annee_academique = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.all(),
        required=False,
        empty_label='Toutes les années'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.layout = Layout(
            Row(
                Column('recherche', css_class='col-md-4'),
                Column('filiere', css_class='col-md-2'),
                Column('statut', css_class='col-md-2'),
                Column('type_inscription', css_class='col-md-2'),
                Column('annee_academique', css_class='col-md-2'),
            ),
            ButtonHolder(
                Submit('submit', 'Rechercher', css_class='btn btn-primary'),
                Submit('reset', 'Réinitialiser', css_class='btn btn-secondary'),
            )
        )


class ValidationRecuForm(forms.Form):
    """Formulaire pour valider un reçu"""
    commentaire = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Commentaire optionnel...'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'commentaire',
            ButtonHolder(
                Submit('submit', 'Valider', css_class='btn btn-success'),
            )
        )


class RejetRecuForm(forms.Form):
    """Formulaire pour rejeter un reçu"""
    motif = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Motif du rejet...'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'motif',
            ButtonHolder(
                Submit('submit', 'Rejeter', css_class='btn btn-danger'),
            )
        )