"""
Formulaires pour la gestion des cours
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder
from .models import Salle, Matiere, Cours, SeanceCours, RessourceCours


class SalleForm(forms.ModelForm):
    """Formulaire pour créer/modifier une salle"""
    
    class Meta:
        model = Salle
        fields = [
            'code', 'nom', 'type_salle', 'capacite', 'etage',
            'est_equipee', 'a_projecteur', 'a_climatisation',
            'description', 'est_disponible'
        ]
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
                Column('type_salle', css_class='col-md-6'),
                Column('capacite', css_class='col-md-6'),
            ),
            'etage',
            Row(
                Column('est_equipee', css_class='col-md-4'),
                Column('a_projecteur', css_class='col-md-4'),
                Column('a_climatisation', css_class='col-md-4'),
            ),
            'description',
            'est_disponible',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class MatiereForm(forms.ModelForm):
    """Formulaire pour créer/modifier une matière"""
    
    class Meta:
        model = Matiere
        fields = [
            'code', 'nom', 'description', 'credits',
            'heures_cours', 'heures_td', 'heures_tp',
            'semestre', 'est_optionnelle', 'prerequis'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'prerequis': forms.CheckboxSelectMultiple(),
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
            Row(
                Column('credits', css_class='col-md-6'),
                Column('semestre', css_class='col-md-6'),
            ),
            Row(
                Column('heures_cours', css_class='col-md-4'),
                Column('heures_td', css_class='col-md-4'),
                Column('heures_tp', css_class='col-md-4'),
            ),
            'est_optionnelle',
            'prerequis',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class CoursForm(forms.ModelForm):
    """Formulaire pour créer/modifier un cours"""
    
    class Meta:
        model = Cours
        fields = [
            'code', 'matiere', 'filiere', 'professeur', 'type_cours',
            'annee_academique', 'jour', 'heure_debut', 'heure_fin',
            'salle', 'capacite_max', 'date_debut', 'date_fin', 'est_actif'
        ]
        widgets = {
            'heure_debut': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time'}),
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Informations générales',
                'code',
                Row(
                    Column('matiere', css_class='col-md-6'),
                    Column('filiere', css_class='col-md-6'),
                ),
                Row(
                    Column('professeur', css_class='col-md-6'),
                    Column('type_cours', css_class='col-md-6'),
                ),
                'annee_academique',
            ),
            Fieldset(
                'Horaires',
                'jour',
                Row(
                    Column('heure_debut', css_class='col-md-6'),
                    Column('heure_fin', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Lieu et capacité',
                Row(
                    Column('salle', css_class='col-md-6'),
                    Column('capacite_max', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                'Période',
                Row(
                    Column('date_debut', css_class='col-md-6'),
                    Column('date_fin', css_class='col-md-6'),
                ),
            ),
            'est_actif',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class SeanceCoursForm(forms.ModelForm):
    """Formulaire pour créer/modifier une séance de cours"""
    
    class Meta:
        model = SeanceCours
        fields = [
            'date', 'heure_debut', 'heure_fin', 'duree_heures',
            'salle', 'titre', 'contenu', 'supports_cours'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'heure_debut': forms.TimeInput(attrs={'type': 'time'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time'}),
            'contenu': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Row(
                Column('date', css_class='col-md-6'),
                Column('salle', css_class='col-md-6'),
            ),
            Row(
                Column('heure_debut', css_class='col-md-4'),
                Column('heure_fin', css_class='col-md-4'),
                Column('duree_heures', css_class='col-md-4'),
            ),
            'titre',
            'contenu',
            'supports_cours',
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary'),
            )
        )


class RessourceCoursForm(forms.ModelForm):
    """Formulaire pour ajouter une ressource à un cours"""
    
    class Meta:
        model = RessourceCours
        fields = ['type_ressource', 'titre', 'description', 'fichier', 'lien_externe', 'est_public']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            'type_ressource',
            'titre',
            'description',
            'fichier',
            'lien_externe',
            'est_public',
            ButtonHolder(
                Submit('submit', 'Ajouter la ressource', css_class='btn btn-primary'),
            )
        )
