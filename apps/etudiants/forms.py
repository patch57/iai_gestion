"""
Formulaires pour la gestion des étudiants
IAI-Cameroun - Centre de Douala
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder
from .models import Etudiant, Filiere, DocumentEtudiant, AnneeAcademique, Niveau, Classe, DocumentObligatoire


class EtudiantForm(forms.ModelForm):
    """Formulaire pour créer/modifier un étudiant"""
    
    class Meta:
        model = Etudiant
        fields = [
            'matricule', 'nom', 'prenom', 'date_naissance', 'lieu_naissance',
            'sexe', 'nationalite', 'telephone', 'email', 'adresse',
            'filiere', 'classe', 'annee_academique', 'statut', 'photo',
            'recu_preinscription', 'recu_preinscription_valide',
            'carte_etudiant_delivree', 'date_delivrance_carte',
            'nom_tuteur', 'telephone_tuteur', 'email_tuteur',
            'groupe_sanguin', 'allergies', 'informations_medicales'
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_delivrance_carte': forms.DateInput(attrs={'type': 'date'}),
            'adresse': forms.Textarea(attrs={'rows': 3}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'informations_medicales': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les années académiques
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.all()
        
        # Filtrer les classes actives
        if 'classe' in self.fields:
            self.fields['classe'].queryset = Classe.objects.filter(est_active=True)
        
        # Filtrer les filières actives
        if 'filiere' in self.fields:
            self.fields['filiere'].queryset = Filiere.objects.filter(est_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Fieldset(
                'Informations d\'identification',
                Row(
                    Column('matricule', css_class='col-md-6'),
                    Column('statut', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Informations personnelles',
                Row(
                    Column('nom', css_class='col-md-6'),
                    Column('prenom', css_class='col-md-6'),
                ),
                Row(
                    Column('date_naissance', css_class='col-md-6'),
                    Column('lieu_naissance', css_class='col-md-6'),
                ),
                Row(
                    Column('sexe', css_class='col-md-6'),
                    Column('nationalite', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Contact',
                Row(
                    Column('telephone', css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
                'adresse',
            ),
            Fieldset(
                'Informations académiques',
                Row(
                    Column('filiere', css_class='col-md-6'),
                    Column('classe', css_class='col-md-6'),
                ),
                Row(
                    Column('annee_academique', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Documents',
                Row(
                    Column('photo', css_class='col-md-6'),
                    Column('recu_preinscription', css_class='col-md-6'),
                ),
                Row(
                    Column('recu_preinscription_valide', css_class='col-md-6'),
                    Column('carte_etudiant_delivree', css_class='col-md-6'),
                ),
                'date_delivrance_carte',
            ),
            Fieldset(
                'Informations du tuteur',
                Row(
                    Column('nom_tuteur', css_class='col-md-6'),
                    Column('telephone_tuteur', css_class='col-md-6'),
                ),
                'email_tuteur',
            ),
            Fieldset(
                'Informations de santé (optionnel)',
                Row(
                    Column('groupe_sanguin', css_class='col-md-6'),
                ),
                'allergies',
                'informations_medicales',
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class FiliereForm(forms.ModelForm):
    """Formulaire pour créer/modifier une filière"""
    
    class Meta:
        model = Filiere
        fields = ['code', 'nom', 'description', 'duree_ans', 'est_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('code', css_class='col-md-6'),
                Column('nom', css_class='col-md-6'),
            ),
            Row(
                Column('duree_ans', css_class='col-md-6'),
                Column('est_active', css_class='col-md-6'),
            ),
            'description',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class NiveauForm(forms.ModelForm):
    """Formulaire pour créer/modifier un niveau"""
    
    class Meta:
        model = Niveau
        fields = ['numero', 'filiere']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les filières actives
        self.fields['filiere'].queryset = Filiere.objects.filter(est_active=True)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('numero', css_class='col-md-6'),
                Column('filiere', css_class='col-md-6'),
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class ClasseForm(forms.ModelForm):
    """Formulaire pour créer/modifier une classe"""
    
    class Meta:
        model = Classe
        fields = ['nom', 'filiere', 'niveau', 'annee_academique', 'effectif_max', 'est_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les filières actives
        self.fields['filiere'].queryset = Filiere.objects.filter(est_active=True)
        # Filtrer les années académiques
        self.fields['annee_academique'].queryset = AnneeAcademique.objects.all()
        
        # Filtrer les niveaux en fonction de la filière sélectionnée
        if 'filiere' in self.data:
            try:
                filiere_id = int(self.data.get('filiere'))
                self.fields['niveau'].queryset = Niveau.objects.filter(filiere_id=filiere_id)
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.filiere:
            self.fields['niveau'].queryset = Niveau.objects.filter(filiere=self.instance.filiere)
        else:
            self.fields['niveau'].queryset = Niveau.objects.none()
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('nom', css_class='col-md-6'),
                Column('filiere', css_class='col-md-6'),
            ),
            Row(
                Column('niveau', css_class='col-md-6'),
                Column('annee_academique', css_class='col-md-6'),
            ),
            Row(
                Column('effectif_max', css_class='col-md-6'),
                Column('est_active', css_class='col-md-6'),
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class DocumentEtudiantForm(forms.ModelForm):
    """Formulaire pour ajouter un document à un étudiant"""
    
    class Meta:
        model = DocumentEtudiant
        fields = ['type_document', 'fichier', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            'type_document',
            'fichier',
            'description',
            ButtonHolder(
                Submit('submit', 'Ajouter le document', css_class='btn btn-primary'),
            )
        )


class DocumentObligatoireForm(forms.ModelForm):
    """Formulaire pour créer/modifier un document obligatoire (administration)"""
    
    class Meta:
        model = DocumentObligatoire
        fields = [
            'type_document', 'nom', 'description', 
            'format_accepte', 'taille_max_mb',
            'filiere', 'niveau',
            'est_actif', 'est_obligatoire', 'ordre_affichage'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'format_accepte': forms.TextInput(attrs={'placeholder': 'PDF, JPG, PNG'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les filières actives
        self.fields['filiere'].queryset = Filiere.objects.filter(est_active=True)
        # Filtrer les niveaux
        self.fields['niveau'].queryset = Niveau.objects.all()
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Informations générales',
                Row(
                    Column('type_document', css_class='col-md-6'),
                    Column('nom', css_class='col-md-6'),
                ),
                'description',
            ),
            Fieldset(
                'Format et taille',
                Row(
                    Column('format_accepte', css_class='col-md-6'),
                    Column('taille_max_mb', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Filtrage (optionnel)',
                Row(
                    Column('filiere', css_class='col-md-6'),
                    Column('niveau', css_class='col-md-6'),
                ),
                'description_filtre',
            ),
            Fieldset(
                'Statut et affichage',
                Row(
                    Column('est_actif', css_class='col-md-4'),
                    Column('est_obligatoire', css_class='col-md-4'),
                    Column('ordre_affichage', css_class='col-md-4'),
                ),
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )
    
    def description_filtre(self):
        """Texte d'aide pour le filtrage"""
        return forms.CharField(
            required=False,
            widget=forms.Textarea(attrs={
                'rows': 2,
                'disabled': True,
                'value': 'Laisser vide pour appliquer à tous les étudiants.\n'
                         'Sélectionner une filière pour appliquer uniquement aux étudiants de cette filière.\n'
                         'Sélectionner un niveau pour appliquer uniquement aux étudiants de ce niveau.',
                'class': 'form-control text-muted'
            }),
            label=""
        )


class RechercheEtudiantForm(forms.Form):
    """Formulaire de recherche d'étudiants"""
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
        choices=[('', 'Tous les statuts')] + Etudiant.STATUT_CHOICES,
        required=False
    )
    sexe = forms.ChoiceField(
        choices=[('', 'Tous les sexes')] + Etudiant.SEXE_CHOICES,
        required=False
    )
    classe = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Classe...',
            'class': 'form-control'
        })
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
                Column('sexe', css_class='col-md-2'),
                Column('classe', css_class='col-md-2'),
            ),
            ButtonHolder(
                Submit('submit', 'Rechercher', css_class='btn btn-primary'),
                Submit('reset', 'Réinitialiser', css_class='btn btn-secondary'),
            )
        )


class ImportEtudiantForm(forms.Form):
    """Formulaire pour importer des étudiants depuis un fichier Excel/CSV"""
    fichier = forms.FileField(
        label='Fichier Excel/CSV',
        help_text='Format: matricule, nom, prénom, email, filière, ...'
    )
    annee_academique = forms.ModelChoiceField(
        queryset=AnneeAcademique.objects.filter(est_active=True),
        label='Année académique'
    )
    mise_a_jour = forms.BooleanField(
        required=False,
        label='Mettre à jour les étudiants existants',
        help_text='Si coché, met à jour les informations des étudiants déjà existants'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            'fichier',
            'annee_academique',
            'mise_a_jour',
            ButtonHolder(
                Submit('submit', 'Importer', css_class='btn btn-primary'),
            )
        )


class ExportEtudiantForm(forms.Form):
    """Formulaire pour exporter les étudiants"""
    format_export = forms.ChoiceField(
        choices=[
            ('excel', 'Excel (.xlsx)'),
            ('csv', 'CSV (.csv)'),
            ('pdf', 'PDF (.pdf)'),
        ],
        label='Format d\'export'
    )
    filiere = forms.ModelChoiceField(
        queryset=Filiere.objects.filter(est_active=True),
        required=False,
        empty_label='Toutes les filières'
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + Etudiant.STATUT_CHOICES,
        required=False,
        label='Statut'
    )
    inclure_documents = forms.BooleanField(
        required=False,
        label='Inclure les informations des documents',
        help_text='Ajoute les colonnes pour les documents (photo, reçu, carte)'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('format_export', css_class='col-md-4'),
                Column('filiere', css_class='col-md-4'),
                Column('statut', css_class='col-md-4'),
            ),
            'inclure_documents',
            ButtonHolder(
                Submit('submit', 'Exporter', css_class='btn btn-primary'),
            )
        )