"""
Formulaires pour la gestion des notes
IAI-Cameroun - Centre de Douala
"""
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Fieldset, ButtonHolder, HTML, Div
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import (
    TypeEvaluation, Evaluation, Note, Bulletin, 
    DetailBulletin, RecoursNote, NoteAnonyme, SessionAnonymat
)


class TypeEvaluationForm(forms.ModelForm):
    """Formulaire pour créer/modifier un type d'évaluation"""
    
    class Meta:
        model = TypeEvaluation
        fields = ['code', 'nom', 'description', 'coefficient_default', 'est_actif', 'couleur', 'icon']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'nom': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'coefficient_default': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'step': '0.01'}),
            'couleur': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'type': 'color'}),
            'icon': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'placeholder': 'fa-chart-line'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'space-y-4'
        self.helper.layout = Layout(
            Div(
                Row(
                    Column('code', css_class='md:col-span-6'),
                    Column('nom', css_class='md:col-span-6'),
                    css_class='grid grid-cols-1 md:grid-cols-2 gap-4'
                ),
                'description',
                Row(
                    Column('coefficient_default', css_class='md:col-span-4'),
                    Column('couleur', css_class='md:col-span-4'),
                    Column('icon', css_class='md:col-span-4'),
                    css_class='grid grid-cols-1 md:grid-cols-3 gap-4'
                ),
                'est_actif',
                HTML('<div class="flex justify-end space-x-3 pt-4">'),
                Submit('submit', 'Enregistrer', css_class='px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700'),
                HTML('</div>'),
            )
        )


class EvaluationForm(forms.ModelForm):
    """Formulaire pour créer/modifier une évaluation"""
    
    class Meta:
        model = Evaluation
        fields = [
            'cours', 'type_evaluation', 'titre', 'description',
            'coefficient', 'note_maximale',
            'date_evaluation', 'heure_debut', 'heure_fin', 'duree_minutes',
            'salle', 'statut'
        ]
        widgets = {
            'date_evaluation': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'heure_debut': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'heure_fin': forms.TimeInput(attrs={'type': 'time', 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'titre': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'coefficient': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'step': '0.01'}),
            'note_maximale': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg', 'step': '0.01'}),
            'duree_minutes': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'salle': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'cours': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'type_evaluation': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'statut': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'space-y-4'
        self.helper.layout = Layout(
            Div(
                Row(
                    Column('cours', css_class='md:col-span-6'),
                    Column('type_evaluation', css_class='md:col-span-6'),
                    css_class='grid grid-cols-1 md:grid-cols-2 gap-4'
                ),
                'titre',
                'description',
                Row(
                    Column('coefficient', css_class='md:col-span-6'),
                    Column('note_maximale', css_class='md:col-span-6'),
                    css_class='grid grid-cols-1 md:grid-cols-2 gap-4'
                ),
                Fieldset(
                    'Date et heure',
                    Row(
                        Column('date_evaluation', css_class='md:col-span-12'),
                        css_class='grid grid-cols-1 gap-4'
                    ),
                    Row(
                        Column('heure_debut', css_class='md:col-span-4'),
                        Column('heure_fin', css_class='md:col-span-4'),
                        Column('duree_minutes', css_class='md:col-span-4'),
                        css_class='grid grid-cols-1 md:grid-cols-3 gap-4'
                    ),
                ),
                Row(
                    Column('salle', css_class='md:col-span-6'),
                    Column('statut', css_class='md:col-span-6'),
                    css_class='grid grid-cols-1 md:grid-cols-2 gap-4'
                ),
                HTML('<div class="flex justify-end space-x-3 pt-4">'),
                Submit('submit', 'Enregistrer', css_class='px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700'),
                HTML('</div>'),
            )
        )


class NoteForm(forms.ModelForm):
    """Formulaire pour saisir une note"""
    
    class Meta:
        model = Note
        fields = ['valeur', 'observation']
        widgets = {
            'valeur': forms.NumberInput(attrs={
                'step': '0.25', 
                'min': '0', 
                'max': '20',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500'
            }),
            'observation': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-green-500',
                'placeholder': 'Observation facultative...'
            }),
        }
    
    def clean_valeur(self):
        valeur = self.cleaned_data.get('valeur')
        if valeur is not None and (valeur < 0 or valeur > 20):
            raise forms.ValidationError("La note doit être comprise entre 0 et 20.")
        return valeur


class SaisieNotesForm(forms.Form):
    """Formulaire pour la saisie en masse des notes"""
    fichier_excel = forms.FileField(
        label="Fichier Excel",
        help_text='Fichier Excel avec les colonnes: matricule, note',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx, .xls, .csv',
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.form_class = 'space-y-4'
        self.helper.layout = Layout(
            Div(
                'fichier_excel',
                HTML('<p class="text-xs text-gray-500 mt-1">Formats acceptés: .xlsx, .xls, .csv</p>'),
                HTML('<div class="flex justify-end space-x-3 pt-4">'),
                Submit('submit', 'Importer les notes', css_class='px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700'),
                HTML('</div>'),
            )
        )


class RecoursNoteForm(forms.ModelForm):
    """Formulaire pour la demande de recours sur une note"""
    
    class Meta:
        model = RecoursNote
        fields = ['note_demandee', 'motif']
        widgets = {
            'note_demandee': forms.NumberInput(attrs={
                'step': '0.25',
                'min': '0',
                'max': '20',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-purple-500 focus:border-purple-500'
            }),
            'motif': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-purple-500 focus:border-purple-500',
                'placeholder': 'Expliquez les raisons de votre recours...'
            }),
        }
        labels = {
            'note_demandee': 'Note demandée',
            'motif': 'Motif du recours',
        }
        help_texts = {
            'note_demandee': 'La note que vous estimez mériter (entre 0 et 20)',
            'motif': 'Expliquez clairement pourquoi vous contestez cette note',
        }
    
    def clean_note_demandee(self):
        note = self.cleaned_data.get('note_demandee')
        if note is not None and (note < 0 or note > 20):
            raise forms.ValidationError("La note demandée doit être comprise entre 0 et 20.")
        return note


class BulletinForm(forms.ModelForm):
    """Formulaire pour les bulletins"""
    
    class Meta:
        model = Bulletin
        fields = ['etudiant', 'annee_academique', 'semestre', 'decision', 'mention']
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'annee_academique': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'semestre': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'decision': forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
            'mention': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'}),
        }


class DetailBulletinForm(forms.ModelForm):
    """Formulaire pour les détails de bulletin"""
    
    class Meta:
        model = DetailBulletin
        fields = ['note_cc', 'note_tp', 'note_examen']
        widgets = {
            'note_cc': forms.NumberInput(attrs={
                'step': '0.25',
                'class': 'w-24 px-2 py-1 border border-gray-300 rounded-lg text-center'
            }),
            'note_tp': forms.NumberInput(attrs={
                'step': '0.25',
                'class': 'w-24 px-2 py-1 border border-gray-300 rounded-lg text-center'
            }),
            'note_examen': forms.NumberInput(attrs={
                'step': '0.25',
                'class': 'w-24 px-2 py-1 border border-gray-300 rounded-lg text-center'
            }),
        }


class SaisieNotesTableForm(forms.Form):
    """Formulaire dynamique pour la saisie des notes en tableau"""
    
    def __init__(self, *args, **kwargs):
        etudiants = kwargs.pop('etudiants', [])
        super().__init__(*args, **kwargs)
        
        for etudiant in etudiants:
            self.fields[f'note_{etudiant.id}'] = forms.DecimalField(
                required=False,
                max_digits=5,
                decimal_places=2,
                validators=[MinValueValidator(0), MaxValueValidator(20)],
                widget=forms.NumberInput(attrs={
                    'class': 'w-24 px-2 py-1 border border-gray-300 rounded-lg text-center focus:ring-green-500',
                    'step': '0.25',
                    'placeholder': '-'
                }),
                label=f"{etudiant.matricule} - {etudiant.get_nom_complet()}"
            )


class ActiverAnonymatForm(forms.Form):
    """Formulaire pour activer l'anonymat"""
    confirmation = forms.BooleanField(
        required=True,
        label="Je confirme activer l'anonymat pour cette évaluation",
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-purple-600'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'confirmation',
            HTML('<div class="flex justify-end space-x-3 pt-4">'),
            Submit('submit', 'Activer l\'anonymat', css_class='px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700'),
            HTML('</div>'),
        )


class TraiterRecoursForm(forms.ModelForm):
    """Formulaire pour traiter un recours (admin)"""
    
    class Meta:
        model = RecoursNote
        fields = ['decision']
        widgets = {
            'decision': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-purple-500',
                'placeholder': 'Expliquez votre décision...'
            }),
        }
        labels = {
            'decision': 'Décision motivée',
        }
    
    action = forms.ChoiceField(
        choices=[('accepter', 'Accepter le recours'), ('rejeter', 'Rejeter le recours')],
        widget=forms.RadioSelect(attrs={'class': 'space-y-2'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'action',
            'decision',
            HTML('<div class="flex justify-end space-x-3 pt-4">'),
            Submit('submit', 'Traiter', css_class='px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700'),
            HTML('</div>'),
        )


class ExportNotesForm(forms.Form):
    """Formulaire pour l'export des notes"""
    format_export = forms.ChoiceField(
        choices=[('csv', 'CSV'), ('excel', 'Excel'), ('pdf', 'PDF')],
        initial='csv',
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg'})
    )
    inclure_observations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 text-green-600'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('format_export', css_class='md:col-span-6'),
                Column('inclure_observations', css_class='md:col-span-6'),
                css_class='grid grid-cols-1 md:grid-cols-2 gap-4'
            ),
            HTML('<div class="flex justify-end space-x-3 pt-4">'),
            Submit('submit', 'Exporter', css_class='px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700'),
            HTML('</div>'),
        )