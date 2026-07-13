from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, ButtonHolder
from .models import Requete


class RequeteForm(forms.ModelForm):
    """Formulaire permettant aux étudiants et apprenants de soumettre une requête"""
    
    class Meta:
        model = Requete
        fields = ['titre', 'nature', 'description', 'piece_jointe']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Expliquez en détail l\'objet de votre requête...'}),
            'titre': forms.TextInput(attrs={'placeholder': 'Objet de la requête'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.enctype = 'multipart/form-data'
        self.helper.layout = Layout(
            Row(
                Column('titre', css_class='col-md-8'),
                Column('nature', css_class='col-md-4'),
            ),
            'description',
            'piece_jointe',
            ButtonHolder(
                Submit('submit', 'Soumettre la requête', css_class='btn btn-primary'),
            )
        )


class ReponsePersonnelForm(forms.ModelForm):
    """Formulaire permettant au personnel de répondre à une requête"""
    
    class Meta:
        model = Requete
        fields = ['reponse']
        widgets = {
            'reponse': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Saisissez votre réponse finale pour l\'étudiant...'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'reponse',
            ButtonHolder(
                Submit('submit', 'Envoyer la réponse', css_class='btn btn-success'),
            )
        )


class EscaladerRequeteForm(forms.Form):
    """Formulaire pour escalader une requête au Directeur avec commentaire interne"""
    commentaire_interne = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Pourquoi escaladez-vous cette requête au Directeur ?'}),
        required=True,
        label="Commentaire ou motif de l'escalade"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'commentaire_interne',
            ButtonHolder(
                Submit('submit', 'Escalader au Directeur', css_class='btn btn-danger'),
            )
        )


class RenvoyerPersonnelForm(forms.ModelForm):
    """Formulaire permettant au Directeur de renvoyer une requête au personnel"""
    
    class Meta:
        model = Requete
        fields = ['assigne_a', 'reponse_interne']
        widgets = {
            'reponse_interne': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Instructions / Décisions pour le personnel...'}),
        }
        labels = {
            'assigne_a': 'Renvoyer à (Personnel)',
            'reponse_interne': 'Instructions internes'
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer uniquement les utilisateurs ayant un type de personnel (comptabilité, études, anonymat, scolarité)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['assigne_a'].queryset = User.objects.filter(
            type_utilisateur__in=['CHEF_SCOLARITE', 'CHEF_ETUDES', 'CHEF_ANONYMAT', 'CHEF_COMPTABILITE', 'ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR']
        ).order_by('first_name')
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'assigne_a',
            'reponse_interne',
            ButtonHolder(
                Submit('submit', 'Renvoyer au personnel', css_class='btn btn-warning'),
            )
        )
