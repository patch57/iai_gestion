"""
Formulaires pour la gestion des professeurs
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder
from .models import Professeur, Departement, ChargeHoraire


class ProfesseurForm(forms.ModelForm):
    """Formulaire pour créer/modifier un professeur"""
    
    class Meta:
        model = Professeur
        fields = [
            'matricule', 'nom', 'prenom', 'date_naissance', 'lieu_naissance',
            'sexe', 'nationalite', 'telephone', 'email', 'adresse',
            'grade', 'departement', 'specialite', 'diplomes', 'annee_experience',
            'date_embauche', 'type_contrat', 'salaire_base',
            'photo', 'statut'
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_embauche': forms.DateInput(attrs={'type': 'date'}),
            'adresse': forms.Textarea(attrs={'rows': 3}),
            'diplomes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Fieldset(
                'Informations d\'identification',
                'matricule',
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
                'Informations professionnelles',
                Row(
                    Column('grade', css_class='col-md-6'),
                    Column('departement', css_class='col-md-6'),
                ),
                'specialite',
                'diplomes',
                Row(
                    Column('annee_experience', css_class='col-md-6'),
                    Column('statut', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Informations contractuelles',
                Row(
                    Column('date_embauche', css_class='col-md-6'),
                    Column('type_contrat', css_class='col-md-6'),
                ),
                'salaire_base',
            ),
            Fieldset(
                'Photo',
                'photo',
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class DepartementForm(forms.ModelForm):
    """Formulaire pour créer/modifier un département"""
    
    class Meta:
        model = Departement
        fields = ['code', 'nom', 'description', 'responsable', 'est_actif']
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
            'description',
            'responsable',
            'est_actif',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class ChargeHoraireForm(forms.ModelForm):
    """Formulaire pour ajouter une charge horaire"""
    
    class Meta:
        model = ChargeHoraire
        fields = [
            'annee_academique', 'heures_assignees', 'heures_effectuees',
            'taux_horaire', 'est_paye', 'date_paiement'
        ]
        widgets = {
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'annee_academique',
            Row(
                Column('heures_assignees', css_class='col-md-6'),
                Column('heures_effectuees', css_class='col-md-6'),
            ),
            'taux_horaire',
            Row(
                Column('est_paye', css_class='col-md-6'),
                Column('date_paiement', css_class='col-md-6'),
            ),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )
