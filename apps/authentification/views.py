"""
Vues pour l'application d'authentification
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login as auth_login
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from .models import DemandeInscription, Utilisateur
import secrets
import string
import re
from django.contrib.auth import logout
from django.http import HttpResponseRedirect

def logout_get(request):
    """Vue de déconnexion acceptant GET (solution temporaire)"""
    logout(request)
    return HttpResponseRedirect('/login/')


def inscription(request):
    """Page d'inscription avec upload de document ou inscription directe pour apprenants"""
    print("=== VUE INSCRIPTION APPELEE ===")
    print(f"Method: {request.method}")
    print(f"User authenticated: {request.user.is_authenticated}")
    
    # Rediriger si déjà connecté
    if request.user.is_authenticated:
        print("Utilisateur déjà connecté, redirection vers tableau de bord")
        return redirect('tableau_bord:tableau_bord')
    
    if request.method == 'POST':
        print("=== TRAITEMENT DU FORMULAIRE ===")
        
        # Récupérer les données du formulaire
        type_utilisateur = request.POST.get('type_utilisateur')
        nom = request.POST.get('last_name', '').strip()
        prenom = request.POST.get('first_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        confirm_email = request.POST.get('confirm_email', '').strip().lower()
        telephone = request.POST.get('telephone', '').strip()
        date_naissance = request.POST.get('date_naissance')
        document = request.FILES.get('document')
        accept_conditions = request.POST.get('accept_conditions')
        
        # Pour les apprenants
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        print(f"Type utilisateur: {type_utilisateur}")
        print(f"Email: {email}")
        
        # Validation des champs obligatoires
        errors = []
        
        if not type_utilisateur:
            errors.append("Veuillez sélectionner un type de compte.")
        if not nom:
            errors.append("Le nom est obligatoire.")
        if not prenom:
            errors.append("Le prénom est obligatoire.")
        if not email:
            errors.append("L'email est obligatoire.")
        elif email != confirm_email:
            errors.append("Les emails ne correspondent pas.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors.append("L'email n'est pas valide.")
        
        if not telephone:
            errors.append("Le téléphone est obligatoire.")
        elif not re.match(r'^(6|2)\d{8}$', telephone):
            errors.append("Le numéro de téléphone doit être au format 6XXXXXXXX ou 2XXXXXXXX.")
        
        # Le justificatif n'est pas obligatoire pour l'apprenant à la création de son compte
        if type_utilisateur != 'APPRENANT':
            if not document:
                errors.append("Le document justificatif (Reçu ou Note de service) est obligatoire.")
            else:
                if document.size > 5 * 1024 * 1024:
                    errors.append("Le document ne doit pas dépasser 5 Mo.")
        else:
            # Pour l'apprenant, le mot de passe est obligatoire
            if not password:
                errors.append("Le mot de passe est obligatoire pour les apprenants.")
            elif password != confirm_password:
                errors.append("Les mots de passe ne correspondent pas.")
            elif len(password) < 8:
                errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        
        if not accept_conditions:
            errors.append("Vous devez accepter les conditions d'utilisation.")
        
        if email and Utilisateur.objects.filter(email=email).exists():
            errors.append("Cet email est déjà utilisé. Veuillez vous connecter.")
        
        # Validation spécifique pour les étudiants
        if type_utilisateur == 'ETUDIANT' and not errors:
            filiere = request.POST.get('filiere')
            type_bac = request.POST.get('type_bac')
            annee_bac = request.POST.get('annee_bac')
            
            if not filiere:
                errors.append("La filière souhaitée est obligatoire.")
            if not type_bac:
                errors.append("Le type de baccalauréat est obligatoire.")
            if annee_bac:
                try:
                    annee = int(annee_bac)
                    if annee < 2000 or annee > timezone.now().year:
                        errors.append("L'année d'obtention du bac n'est pas valide.")
                except ValueError:
                    errors.append("L'année d'obtention du bac doit être un nombre.")
            
            if type_bac and type_bac.startswith('A') and filiere != 'GL':
                errors.append("Les titulaires d'un Baccalauréat série A ne peuvent postuler qu'en Génie Logiciel (GL).")
        
        # Validation spécifique pour le personnel
        if type_utilisateur in ['ENSEIGNANT', 'CHEF_SCOLARITE', 'CHEF_ETUDES', 'CHEF_ANONYMAT', 'CHEF_COMPTABILITE'] and not errors:
            fonction = request.POST.get('fonction')
            departement = request.POST.get('departement')
            
            if not fonction:
                errors.append("La fonction est obligatoire.")
            if not departement:
                errors.append("Le département est obligatoire.")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('authentification:inscription')
        
        try:
            if type_utilisateur == 'APPRENANT':
                # Créer l'apprenant directement actif
                user = Utilisateur.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=prenom,
                    last_name=nom,
                    telephone=telephone,
                    is_active=True,
                    type_utilisateur='APPRENANT',
                    statut_inscription='COMPTE_ACTIF'
                )
                
                # Envoyer un e-mail de bienvenue simple
                sujet = "🎓 Bienvenue sur la plateforme IAI-Gestion !"
                message = f"""Bonjour {prenom} {nom},
                
Votre compte d'apprenant a été créé avec succès.
Vous pouvez maintenant vous connecter avec votre adresse e-mail et votre mot de passe pour vous inscrire à des formations.
                
🔗 Lien de connexion : {settings.SITE_URL}/login/
                
Cordialement,
L'équipe administrative IAI-Cameroun
"""
                try:
                    send_mail(
                        sujet,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=True,
                    )
                except:
                    pass
                
                messages.success(request, '✅ Votre compte apprenant a été créé avec succès ! Vous pouvez maintenant vous connecter.')
                return redirect('login')
                
            else:
                alphabet = string.ascii_letters + string.digits
                temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
                
                # Créer l'utilisateur (étudiant ou personnel) inactif au départ
                user = Utilisateur.objects.create_user(
                    username=email,
                    email=email,
                    password=temp_password,
                    first_name=prenom,
                    last_name=nom,
                    telephone=telephone,
                    is_active=False,
                    type_utilisateur=type_utilisateur,
                    statut_inscription='DOCUMENT_EN_COURS'
                )
                
                user.save()
                
                # Créer la demande d'inscription
                demande = DemandeInscription.objects.create(
                    user=user,
                    type_utilisateur='ETUDIANT' if type_utilisateur == 'ETUDIANT' else 'PERSONNEL',
                    document=document,
                    type_document='RECU_BANCAIRE' if type_utilisateur == 'ETUDIANT' else 'NOTE_SERVICE',
                    filiere_souhaitee=request.POST.get('filiere') if type_utilisateur == 'ETUDIANT' else None,
                    type_baccalaureat=request.POST.get('type_bac') if type_utilisateur == 'ETUDIANT' else None,
                    annee_obtention_bac=request.POST.get('annee_bac') if type_utilisateur == 'ETUDIANT' else None,
                    fonction=request.POST.get('fonction') if type_utilisateur != 'ETUDIANT' else None,
                    departement=request.POST.get('departement') if type_utilisateur != 'ETUDIANT' else None
                )
                
                # Traitement par l'Agent IA en tâche de fond immédiate
                demande.analyser_par_ia()
                
                if demande.statut == 'VALIDE':
                    messages.success(
                        request,
                        f"✅ Inscription validée automatiquement par l'IA ! Votre matricule unique est : {user.matricule}.\nUn email contenant vos accès vous a été envoyé."
                    )
                else:
                    messages.warning(
                        request,
                        "⏳ Document soumis. Des vérifications complémentaires sont requises par notre service de comptabilité."
                    )
                return redirect('authentification:inscription_confirmation')
                
        except Exception as e:
            print(f"Erreur lors de l'inscription: {e}")
            messages.error(request, f"Une erreur s'est produite: {str(e)}")
            return redirect('authentification:inscription')
    
    return render(request, 'authentification/inscription_standalone.html', {'titre': 'Inscription à la plateforme'})


def envoyer_email_confirmation(user, temp_password, demande_id):
    """Envoie l'email de confirmation d'inscription"""
    sujet = "Confirmation de votre inscription - IAI-Cameroun"
    message = f"""
    Bonjour {user.first_name} {user.last_name},
    
    Nous vous remercions pour votre inscription à la plateforme de gestion universitaire de l'IAI-Cameroun.
    
    📝 Récapitulatif de votre demande :
    • Numéro de demande : {demande_id}
    • Type de compte : {user.get_type_utilisateur_display()}
    • Email : {user.email}
    
    🔑 Vos informations de connexion temporaires sont :
    • Identifiant : {user.email}
    • Mot de passe temporaire : {temp_password}
    
    ⏳ Statut de votre demande :
    Votre demande d'inscription est en cours de traitement.
    Vous recevrez un email dès que votre compte sera activé.
    
    📄 Pour les étudiants : Après vérification de votre reçu de pré-inscription (50 000 FCFA), votre matricule vous sera attribué.
    📄 Pour le personnel : Après vérification de votre justificatif, votre compte sera activé.
    
    🔗 Lien de connexion : {settings.SITE_URL}/login/
    
    💡 Conseil : Conservez ce email précieusement. Vous en aurez besoin pour vous connecter.
    
    Cordialement,
    L'équipe administrative IAI-Cameroun
    """
    
    try:
        send_mail(
            sujet,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        print(f"Email envoyé à {user.email}")
    except Exception as e:
        print(f"Erreur d'envoi d'email: {e}")


def inscription_confirmation(request):
    """Page de confirmation d'inscription"""
    return render(request, 'authentification/inscription_confirmation.html', {'titre': 'Inscription confirmée'})


def login_view(request):
    """Vue de connexion personnalisée acceptant matricule, email ou username"""
    if request.user.is_authenticated:
        return redirect('tableau_bord:tableau_bord')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        
        # Authentification avec matricule, email ou username
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            auth_login(request, user)
            
            # Gérer la session "Se souvenir de moi"
            if not remember:
                request.session.set_expiry(0)  # Session expire à la fermeture du navigateur
            else:
                request.session.set_expiry(1209600)  # 2 semaines
            
            messages.success(request, f"Bienvenue {user.get_full_name() or user.username} !")
            
            # Redirection
            next_url = request.GET.get('next', 'tableau_bord:tableau_bord')
            return redirect(next_url)
        else:
            messages.error(request, "Matricule, email ou mot de passe incorrect.")
    
    return render(request, 'base/login.html', {'titre': 'Connexion'})


@login_required
def profil(request):
    """Page de profil utilisateur"""
    user = request.user
    
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.telephone = request.POST.get('telephone', user.telephone)
        user.adresse = request.POST.get('adresse', user.adresse)
        
        if request.FILES.get('photo'):
            user.photo = request.FILES.get('photo')
        
        user.save()
        messages.success(request, '✅ Votre profil a été mis à jour avec succès.')
        return redirect('authentification:profil')
    
    context = {
        'user': user,
        'titre': 'Mon profil'
    }
    return render(request, 'authentification/profil.html', context)


@login_required
def modifier_profil(request):
    """Modifier le profil utilisateur"""
    if request.method == 'POST':
        messages.success(request, '✅ Profil modifié avec succès.')
        return redirect('authentification:profil')
    
    context = {
        'titre': 'Modifier mon profil'
    }
    return render(request, 'authentification/modifier_profil.html', context)


@staff_member_required
def liste_demandes(request):
    """Liste des demandes d'inscription pour l'admin"""
    demandes = DemandeInscription.objects.select_related('user').all()
    
    statut = request.GET.get('statut')
    if statut:
        demandes = demandes.filter(statut=statut)
    
    type_utilisateur = request.GET.get('type')
    if type_utilisateur:
        demandes = demandes.filter(type_utilisateur=type_utilisateur)
    
    context = {
        'demandes': demandes,
        'statuts': DemandeInscription.STATUT_CHOICES,
        'types': DemandeInscription.TYPE_UTILISATEUR,
        'titre': 'Gestion des demandes d\'inscription'
    }
    return render(request, 'authentification/liste_demandes.html', context)


@staff_member_required
def detail_demande(request, pk):
    """Détail d'une demande d'inscription"""
    demande = get_object_or_404(DemandeInscription, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'valider':
            demande.activer_compte()
            messages.success(
                request, 
                f'✅ Compte activé avec succès !\nMatricule: {demande.user.matricule}'
            )
        elif action == 'rejeter':
            motif = request.POST.get('motif', '')
            demande.rejeter_demande(motif)
            messages.warning(request, '⚠️ Demande rejetée.')
        
        return redirect('authentification:liste_demandes')
    
    context = {
        'demande': demande,
        'titre': f'Détail de la demande - {demande.user}'
    }
    return render(request, 'authentification/detail_demande.html', context)


@staff_member_required
def valider_demande(request, pk):
    """Valider une demande d'inscription"""
    demande = get_object_or_404(DemandeInscription, pk=pk)
    
    if request.method == 'POST':
        demande.activer_compte()
        messages.success(
            request, 
            f'✅ Compte de {demande.user.get_full_name()} activé avec succès !\n'
            f'Matricule: {demande.user.matricule}'
        )
        return redirect('authentification:liste_demandes')
    
    context = {
        'demande': demande,
        'titre': 'Valider la demande'
    }
    return render(request, 'authentification/valider_demande.html', context)


@staff_member_required
def rejeter_demande(request, pk):
    """Rejeter une demande d'inscription"""
    demande = get_object_or_404(DemandeInscription, pk=pk)
    
    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        demande.rejeter_demande(motif)
        messages.warning(request, f'⚠️ Demande de {demande.user.get_full_name()} rejetée.')
        return redirect('authentification:liste_demandes')
    
    context = {
        'demande': demande,
        'titre': 'Rejeter la demande'
    }
    return render(request, 'authentification/rejeter_demande.html', context)