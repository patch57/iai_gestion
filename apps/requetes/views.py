import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Requete
from .forms import RequeteForm, ReponsePersonnelForm, EscaladerRequeteForm, RenvoyerPersonnelForm


@login_required
def liste_requetes(request):
    """Affiche la liste des requêtes selon le rôle de l'utilisateur"""
    user = request.user
    role = user.type_utilisateur
    is_directeur = user.is_superuser or role in ['DIRECTEUR', 'ADMIN_SYSTEME']
    
    queryset = Requete.objects.all().select_related('auteur', 'assigne_a')
    
    # Statistiques pour la direction / staff
    total_requetes = queryset.count()
    nb_escaladees = queryset.filter(statut='ESCALADE').count()
    nb_en_cours = queryset.filter(statut__in=['SOUMIS', 'EN_COURS', 'RENVOYE']).count()
    nb_traitees = queryset.filter(statut='TRAITE').count()

    # Filtrer selon le rôle
    if role in ['ETUDIANT', 'APPRENANT']:
        queryset = queryset.filter(auteur=user)
    elif role == 'CHEF_SCOLARITE':
        queryset = queryset.filter(Q(assigne_a=user) | Q(assigne_a__isnull=True, nature='SCOLARITE'))
    elif role == 'CHEF_ETUDES':
        queryset = queryset.filter(Q(assigne_a=user) | Q(assigne_a__isnull=True, nature='ETUDES'))
    elif role == 'CHEF_ANONYMAT':
        queryset = queryset.filter(Q(assigne_a=user) | Q(assigne_a__isnull=True, nature='ANONYMAT'))
    elif role == 'CHEF_COMPTABILITE':
        queryset = queryset.filter(Q(assigne_a=user) | Q(assigne_a__isnull=True, nature='COMPTABILITE'))
    elif role in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE']:
        queryset = queryset.filter(Q(assigne_a=user) | Q(assigne_a__isnull=True, auteur__type_utilisateur='APPRENANT'))
    elif is_directeur:
        # Le Directeur voit l'ensemble du registre de requêtes
        pass
    else:
        queryset = queryset.none()
        
    # Filtres de recherche
    q = request.GET.get('q', '')
    if q:
        queryset = queryset.filter(
            Q(titre__icontains=q) | 
            Q(description__icontains=q) |
            Q(auteur__first_name__icontains=q) |
            Q(auteur__last_name__icontains=q) |
            Q(auteur__username__icontains=q)
        )
        
    statut = request.GET.get('statut', '')
    if statut:
        queryset = queryset.filter(statut=statut)
        
    nature = request.GET.get('nature', '')
    if nature:
        queryset = queryset.filter(nature=nature)
        
    paginator = Paginator(queryset.order_by('-date_creation'), 15)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'requetes': page_obj,
        'natures': Requete.NATURE_CHOICES,
        'statuts': Requete.STATUT_CHOICES,
        'is_directeur': is_directeur,
        'total_requetes': total_requetes,
        'nb_escaladees': nb_escaladees,
        'nb_en_cours': nb_en_cours,
        'nb_traitees': nb_traitees,
        'titre': 'Espace Requêtes - Direction & Suivi' if is_directeur else 'Suivi des Requêtes'
    }
    return render(request, 'requetes/liste.html', context)


@login_required
def creer_requete(request):
    """Permet aux étudiants/apprenants de créer une requête"""
    if request.user.type_utilisateur not in ['ETUDIANT', 'APPRENANT']:
        messages.error(request, "Seuls les étudiants ou apprenants peuvent soumettre des requêtes.")
        return redirect('requetes:liste_requetes')
        
    if request.method == 'POST':
        form = RequeteForm(request.POST, request.FILES)
        if form.is_valid():
            requete = form.save(commit=False)
            requete.auteur = request.user
            requete.statut = 'SOUMIS'
            requete.ajouter_action_historique(
                action="Soumission",
                auteur=request.user,
                details=f"Requête soumise. Nature : {requete.get_nature_display()}."
            )
            requete.save()

            # Notifications ciblées selon la nature de la requête
            try:
                from apps.tableau_bord.services_notification import NotificationService
                from django.urls import reverse
                link = reverse('requetes:detail_requete', kwargs={'pk': requete.pk})
                auteur_nom = request.user.get_full_name() or request.user.username
                nature_str = requete.get_nature_display()
                titre_notif = f"Nouvelle Requête ({nature_str}) : {requete.titre[:30]}"
                msg_notif = f"Requête déposée par {auteur_nom} : {requete.titre}"

                # Toujours notifier le Directeur pour supervision
                NotificationService.notifier_directeur(titre_notif, msg_notif, type_notif='WARNING', lien=link)

                # Notifier le responsable du domaine
                if requete.nature == 'SCOLARITE':
                    NotificationService.notifier_chef_scolarite(titre_notif, msg_notif, type_notif='WARNING', lien=link)
                elif requete.nature == 'ETUDES':
                    NotificationService.notifier_chef_etudes(titre_notif, msg_notif, type_notif='WARNING', lien=link)
                elif requete.nature == 'ANONYMAT':
                    NotificationService.notifier_chef_anonymat(titre_notif, msg_notif, type_notif='WARNING', lien=link)
                elif requete.nature == 'COMPTABILITE':
                    NotificationService.notifier_admin_financier(titre_notif, msg_notif, type_notif='WARNING', lien=link)
            except Exception:
                pass

            messages.success(request, "✅ Votre requête a été soumise avec succès.")
            return redirect('requetes:liste_requetes')
    else:
        form = RequeteForm()
        
    context = {
        'form': form,
        'titre': 'Soumettre une requête'
    }
    return render(request, 'requetes/creer.html', context)


@login_required
def detail_requete(request, pk):
    """Affiche les détails et gère les actions de traitement sur une requête"""
    requete = get_object_or_404(Requete, pk=pk)
    user = request.user
    role = user.type_utilisateur
    is_directeur = user.is_superuser or role in ['DIRECTEUR', 'ADMIN_SYSTEME']
    
    # Sécurité de lecture
    if role in ['ETUDIANT', 'APPRENANT']:
        if requete.auteur != user:
            messages.error(request, "Accès refusé.")
            return redirect('requetes:liste_requetes')
    elif is_directeur:
        # Le Directeur a accès à tout
        pass
    else:
        # Personnel autre : vérifier s'il est l'assigné direct, ou si la requête n'est pas assignée et concerne son service
        est_autorise = False
        if requete.assigne_a == user:
            est_autorise = True
        elif requete.assigne_a is None:
            if role == 'CHEF_SCOLARITE' and requete.nature == 'SCOLARITE':
                est_autorise = True
            elif role == 'CHEF_ETUDES' and requete.nature == 'ETUDES':
                est_autorise = True
            elif role == 'CHEF_ANONYMAT' and requete.nature == 'ANONYMAT':
                est_autorise = True
            elif role == 'CHEF_COMPTABILITE' and requete.nature == 'COMPTABILITE':
                est_autorise = True
            elif role in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE'] and requete.auteur.type_utilisateur == 'APPRENANT':
                est_autorise = True
        
        if not est_autorise:
            messages.error(request, "Accès refusé : cette requête ne vous est pas destinée.")
            return redirect('requetes:liste_requetes')
        
    form_reponse = None
    form_escalade = None
    form_renvoi = None
    
    # Si la requête n'est pas déjà finalisée (TRAITE)
    if requete.statut != 'TRAITE':
        if is_directeur:
            # Le Directeur peut toujours soit répondre directement à l'expéditeur, soit renvoyer avec consignes
            form_reponse = ReponsePersonnelForm(instance=requete)
            form_renvoi = RenvoyerPersonnelForm(instance=requete)
        else:
            nature_correspondante = (
                (role == 'CHEF_SCOLARITE' and requete.nature == 'SCOLARITE') or
                (role == 'CHEF_ETUDES' and requete.nature == 'ETUDES') or
                (role == 'CHEF_ANONYMAT' and requete.nature == 'ANONYMAT') or
                (role == 'CHEF_COMPTABILITE' and requete.nature == 'COMPTABILITE') or
                (role in ['ENSEIGNANT', 'PROFESSEUR', 'FORMATEUR', 'CHEF_FORMATION_CONTINUE'] and requete.auteur.type_utilisateur == 'APPRENANT') or
                (requete.assigne_a == user)
            )
            if nature_correspondante:
                form_reponse = ReponsePersonnelForm(instance=requete)
                form_escalade = EscaladerRequeteForm()
            
    context = {
        'requete': requete,
        'form_reponse': form_reponse,
        'form_escalade': form_escalade,
        'form_renvoi': form_renvoi,
        'is_directeur': is_directeur,
        'titre': f"Requête #{requete.id} - {requete.titre}"
    }
    return render(request, 'requetes/detail.html', context)


@login_required
def repondre_requete(request, pk):
    """Permet de répondre finalement à l'expéditeur d'une requête (Clôture le ticket)"""
    requete = get_object_or_404(Requete, pk=pk)
    user = request.user
    is_directeur = user.is_superuser or user.type_utilisateur in ['DIRECTEUR', 'ADMIN_SYSTEME']

    if request.method == 'POST':
        form = ReponsePersonnelForm(request.POST, instance=requete)
        if form.is_valid():
            requete = form.save(commit=False)
            requete.statut = 'TRAITE'
            requete.assigne_a = user
            
            action_label = "Décision de la Direction" if is_directeur else "Résolution"
            details_label = f"Réponse transmise par {user.get_full_name() or user.username} : {requete.reponse[:120]}..."
            
            requete.ajouter_action_historique(
                action=action_label,
                auteur=user,
                details=details_label
            )
            requete.save()
            
            # Envoi d'email de notification à l'expéditeur (étudiant/apprenant)
            destinataire = requete.auteur.email
            if destinataire:
                try:
                    titre_emetteur = "la Direction / Représentant Résident" if is_directeur else "l'Administration"
                    sujet = f"[IAI-Cameroun] Réponse à votre requête #{requete.id} - {requete.titre}"
                    corps_email = (
                        f"Bonjour {requete.auteur.get_full_name() or requete.auteur.first_name},\n\n"
                        f"Une réponse officielle a été apportée à votre requête N° {requete.id} ('{requete.titre}') par {titre_emetteur}.\n\n"
                        f"DÉCISION / RÉPONSE :\n"
                        f"-----------------------------------------\n"
                        f"{requete.reponse}\n"
                        f"-----------------------------------------\n\n"
                        f"Vous pouvez consulter l'historique complet sur votre espace en ligne IAI-Gestion.\n\n"
                        f"Cordialement,\n"
                        f"Direction de l'IAI-Cameroun - Centre de Douala."
                    )
                    send_mail(
                        subject=sujet,
                        message=corps_email,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[destinataire],
                        fail_silently=True
                    )
                except Exception as e:
                    print(f"Erreur d'envoi d'email : {e}")
                    
            messages.success(request, f"✅ Votre réponse a été enregistrée et transmise directement à {requete.auteur.get_full_name() or requete.auteur.username}.")
            return redirect('requetes:detail_requete', pk=requete.id)
            
    return redirect('requetes:detail_requete', pk=pk)


@login_required
def escalader_requete(request, pk):
    """Escalade la requête au Directeur"""
    requete = get_object_or_404(Requete, pk=pk)
    if request.method == 'POST':
        form = EscaladerRequeteForm(request.POST)
        if form.is_valid():
            commentaire = form.cleaned_data['commentaire_interne']
            requete.statut = 'ESCALADE'
            requete.reponse_interne = commentaire
            requete.ajouter_action_historique(
                action="Escalade au Directeur",
                auteur=request.user,
                details=f"Requête escaladée au Directeur pour arbitrage. Motif : {commentaire}",
                est_interne=True
            )
            requete.save()
            messages.warning(request, "⚠️ La requête a été escaladée au Directeur / Représentant Résident.")
            return redirect('requetes:detail_requete', pk=requete.id)
            
    return redirect('requetes:detail_requete', pk=pk)


@login_required
def renvoyer_requete(request, pk):
    """Permet au Directeur de renvoyer la requête à un membre du personnel avec consignes"""
    requete = get_object_or_404(Requete, pk=pk)
    is_directeur = request.user.is_superuser or request.user.type_utilisateur in ['DIRECTEUR', 'ADMIN_SYSTEME']
    
    if not is_directeur:
        messages.error(request, "Seul le Directeur peut renvoyer des requêtes.")
        return redirect('requetes:detail_requete', pk=pk)
        
    if request.method == 'POST':
        form = RenvoyerPersonnelForm(request.POST, instance=requete)
        if form.is_valid():
            requete = form.save(commit=False)
            requete.statut = 'RENVOYE'
            personnel = requete.assigne_a
            nom_personnel = personnel.get_full_name() if personnel else "Personnel assigné"
            
            requete.ajouter_action_historique(
                action="Renvoi au personnel",
                auteur=request.user,
                details=f"Renvoyée à {nom_personnel} par la Direction. Instructions : {requete.reponse_interne}",
                est_interne=True
            )
            requete.save()
            messages.success(request, f"Requête renvoyée à {nom_personnel} avec les consignes d'arbitrage.")
            return redirect('requetes:detail_requete', pk=requete.id)
            
    return redirect('requetes:detail_requete', pk=pk)


@login_required
def export_requetes_csv(request):
    """Exporte les requêtes au format CSV (Réservé au Directeur)"""
    if request.user.type_utilisateur != 'ADMIN_SYSTEME':
        return HttpResponse("Accès interdit", status=403)
        
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="requetes_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Auteur (Email)', 'Titre', 'Nature', 'Description', 'Statut', 'Date Création', 'Réponse'])
    
    for req in Requete.objects.all().select_related('auteur'):
        writer.writerow([
            req.id,
            req.auteur.email,
            req.titre,
            req.nature,
            req.description,
            req.statut,
            req.date_creation.isoformat(),
            req.reponse
        ])
        
    return response


@login_required
def import_requetes_csv(request):
    """Permet au Directeur de téléverser un fichier CSV pour mettre à jour les requêtes en lot"""
    if request.user.type_utilisateur != 'ADMIN_SYSTEME':
        messages.error(request, "Accès réservé au Directeur.")
        return redirect('requetes:liste_requetes')
        
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        
        # Vérification d'extension
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Le fichier doit être au format CSV.")
            return redirect('requetes:liste_requetes')
            
        try:
            file_data = csv_file.read().decode('utf-8')
            csv_data = csv.reader(io.StringIO(file_data))
            
            # Sauter l'en-tête
            header = next(csv_data)
            
            compteur_updates = 0
            for row in csv_data:
                if len(row) < 8:
                    continue
                req_id = row[0]
                nouveau_statut = row[5]
                nouvelle_reponse = row[7]
                
                try:
                    requete = Requete.objects.get(id=req_id)
                    requete.statut = nouveau_statut
                    requete.reponse = nouvelle_reponse
                    requete.ajouter_action_historique(
                        action="Mise à jour par lot",
                        auteur=request.user,
                        details="Modifiée par importation CSV."
                    )
                    requete.save()
                    compteur_updates += 1
                except Requete.DoesNotExist:
                    continue
                    
            messages.success(request, f"✅ Importation réussie ! {compteur_updates} requête(s) mise(s) à jour.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la lecture du fichier : {str(e)}")
            
    return redirect('requetes:liste_requetes')
