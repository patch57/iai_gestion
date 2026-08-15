"""
Formulaires pour la gestion des inscriptions
IAI-Cameroun - Centre de Douala
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder
from .models import Inscription, DocumentInscription, AnneeAcademique, Bourse
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


class BourseForm(forms.ModelForm):
    """Formulaire pour attribuer ou modifier une bourse d'études"""
    
    class Meta:
        model = Bourse
        fields = ['etudiant', 'type_bourse', 'montant', 'annee_academique', 'date_attribution', 'est_active', 'commentaire']
        widgets = {
            'commentaire': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Commentaires ou motif de la bourse...'}),
            'date_attribution': forms.DateInput(attrs={'type': 'date'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer uniquement les étudiants actifs, préinscrits ou inscrits
        self.fields['etudiant'].queryset = Etudiant.objects.filter(statut__in=['PREINSCRIT', 'ACTIF', 'INSCRIT']).order_by('nom')
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.all()
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('etudiant', css_class='col-md-6'),
                Column('annee_academique', css_class='col-md-6'),
            ),
            Row(
                Column('type_bourse', css_class='col-md-6'),
                Column('montant', css_class='col-md-6'),
            ),
            Row(
                Column('date_attribution', css_class='col-md-6'),
                Column('est_active', css_class='col-md-6'),
            ),
            'commentaire',
            ButtonHolder(
                Submit('submit', 'Enregistrer la bourse', css_class='btn btn-primary'),
            )
        )


class FicheRenseignementEtudiantForm(forms.Form):
    """
    Formulaire complet pour la Fiche de Renseignement officielle IAI-Cameroun
    Rempli par l'étudiant avec uploads obligatoires de photo et de reçu.
    """
    SITUATION_MATRIMONIALE_CHOICES = [
        ('Célibataire', 'Célibataire'),
        ('Marié(e)', 'Marié(e)'),
        ('Autre', 'Autre'),
    ]

    STATUT_ETUDIANT_CHOICES = [
        ('Nouvelle admission', 'Nouvelle admission'),
        ('Redoublant', 'Redoublant'),
    ]

    # Identité
    nom = forms.CharField(max_length=100, label="Noms (EN MAJUSCULES)", widget=forms.TextInput(attrs={'placeholder': 'EX: PATCHONG NJITACK', 'class': 'uppercase'}))
    prenom = forms.CharField(max_length=100, label="Prénoms", widget=forms.TextInput(attrs={'placeholder': 'Ex: Romuald'}))
    date_naissance = forms.DateField(label="Date de naissance", widget=forms.DateInput(attrs={'type': 'date'}))
    lieu_naissance = forms.CharField(max_length=100, label="Lieu de naissance", widget=forms.TextInput(attrs={'placeholder': 'Ex: Bafoussam'}))
    pays_naissance = forms.CharField(max_length=100, initial='Cameroun', label="Pays de naissance")
    situation_matrimoniale = forms.ChoiceField(choices=SITUATION_MATRIMONIALE_CHOICES, label="Situation matrimoniale")
    nationalite = forms.CharField(max_length=100, initial='Camerounaise', label="Nationalité")
    region_origine = forms.CharField(max_length=100, label="Région d'origine", widget=forms.TextInput(attrs={'placeholder': 'Ex: Ouest'}))
    adresse_permanente = forms.CharField(max_length=200, label="Adresse permanente", widget=forms.TextInput(attrs={'placeholder': 'Ex: EKOUNOU'}))
    telephone = forms.CharField(max_length=30, label="Votre N° Téléphone", widget=forms.TextInput(attrs={'placeholder': 'Ex: 652482992'}))
    lieu_residence = forms.CharField(max_length=100, label="Lieu de résidence", widget=forms.TextInput(attrs={'placeholder': 'Ex: EKOUNOU'}))
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={'placeholder': 'rnjitack@gmail.com'}))

    # Personne à contacter
    personne_contact_nom_prenom = forms.CharField(max_length=150, label="Personne à contacter (NOM et Prénom)", widget=forms.TextInput(attrs={'placeholder': 'Ex: METIEGAM SOLANGE'}))
    personne_contact_telephone = forms.CharField(max_length=30, label="Téléphone (personne à contacter)", widget=forms.TextInput(attrs={'placeholder': 'Ex: 699540134'}))
    personne_contact_residence = forms.CharField(max_length=100, label="Lieu de résidence (personne à contacter)", widget=forms.TextInput(attrs={'placeholder': 'Ex: EKOUNOU'}))

    # Parcours Académique
    filiere = forms.ModelChoiceField(queryset=Filiere.objects.filter(est_active=True), label="Filière")
    serie_bacc = forms.CharField(max_length=50, label="BACC (Série / Diplôme d'entrée)", widget=forms.TextInput(attrs={'placeholder': 'Ex: C, D, TI, A'}))
    niveau = forms.CharField(max_length=20, label="Niveau", widget=forms.TextInput(attrs={'placeholder': 'Ex: 1, 2, III'}))
    date_premiere_rentree = forms.DateField(required=False, label="Date de première rentrée académique", widget=forms.DateInput(attrs={'type': 'date'}))
    statut_etudiant_fiche = forms.ChoiceField(choices=STATUT_ETUDIANT_CHOICES, label="Statut étudiant")
    date_concours = forms.DateField(required=False, label="Date du concours", widget=forms.DateInput(attrs={'type': 'date'}))
    matricule = forms.CharField(max_length=50, required=False, label="Matricule", widget=forms.TextInput(attrs={'placeholder': 'Ex: GL_CMR_5043_2324A'}))

    # Uploads Obligatoires
    photo_identite = forms.ImageField(required=True, label="Photo d'identité (type Passeport/CNI)", help_text="Détection par Agent IA: visage centré, fond clair neutre.")
    recu_paiement_fichier = forms.FileField(required=True, label="Reçu de paiement bancaire (1ère tranche ou Totalité)", help_text="Document PDF ou Image lisible de votre versement bancaire.")