"""
Vues pour la gestion des paiements
IAI-Cameroun - Centre de Douala
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator

from .models import RecuPaiement, TranchePaiement, SessionConcours, EcheanceSessionNiveau1, ResultatConcours
from apps.etudiants.models import Etudiant



@login_required
def liste_recus(request):
    """Liste des reçus"""
    recus = RecuPaiement.objects.select_related('etudiant', 'tranche').order_by('-date_televersement')
    
    # Filtres
    statut = request.GET.get('statut')
    if statut:
        recus = recus.filter(statut=statut)
    
    paginator = Paginator(recus, 20)
    page = request.GET.get('page', 1)
    recus_page = paginator.get_page(page)
    
    context = {
        'recus': recus_page,
        'titre': 'Liste des reçus'
    }
    return render(request, 'paiements/recus/liste.html', context)


from django.core.exceptions import ValidationError
from .forms import valider_fichier_recu

@login_required
def televerser_recu(request, etudiant_id):
    etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
    
    # Sécurité supplémentaire
    if request.user.type_utilisateur == 'ETUDIANT' and etudiant.utilisateur != request.user:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    # Vérifier si le profil de l'étudiant est incomplet
    if not (etudiant.date_naissance and etudiant.lieu_naissance and etudiant.sexe and etudiant.nationalite and etudiant.telephone and etudiant.adresse and etudiant.nom_tuteur and etudiant.telephone_tuteur):
        messages.warning(request, "⚠️ Veuillez compléter vos informations de profil (informations personnelles, contact, tuteur) avant de pouvoir téléverser un reçu de paiement.")
        return redirect(reverse('tableau_bord:modifier_profil') + f'?compte_incomplet=1&next={request.path}')
        
    from apps.inscriptions.utils import get_current_academic_year_code
    tranches = TranchePaiement.objects.filter(annee_academique=etudiant.annee_academique.code if etudiant.annee_academique else get_current_academic_year_code(), est_actif=True)
    
    if request.method == 'POST':
        tranche_id = request.POST.get('tranche')
        file = request.FILES.get('recu_fichier')
        montant = request.POST.get('montant_mentionne')
        reference = request.POST.get('reference_recu', '')
        
        if not file or not tranche_id or not montant:
            messages.error(request, 'Veuillez remplir tous les champs obligatoires.')
        else:
            try:
                valider_fichier_recu(file)
            except ValidationError as e:
                messages.error(request, f"❌ {e.message}")
                return render(request, 'paiements/recus/televerser.html', {
                    'etudiant': etudiant,
                    'tranches': tranches,
                    'titre': 'Téléverser un reçu'
                })
            
            tranche = None
            commentaires = ""
            
            if tranche_id in ['totalite', 'autre']:
                commentaires = f"OPTION:{tranche_id.upper()}"
            else:
                try:
                    tranche = TranchePaiement.objects.get(pk=tranche_id)
                except (TranchePaiement.DoesNotExist, ValueError):
                    pass

            recu = RecuPaiement.objects.create(
                etudiant=etudiant,
                tranche=tranche,
                recu_fichier=file,
                montant_mentionne=montant,
                reference_recu=reference,
                statut='EN_ATTENTE',
                commentaires=commentaires
            )
            
            # Analyse OCR réelle du reçu
            recu.analyser_par_ia()
            
            # Message basé sur le résultat réel
            if recu.statut == 'VALIDE':
                montant_detecte = recu.verification_ia.get('montant_principal', '')
                banque = recu.verification_ia.get('banque', 'Banque détectée')
                messages.success(
                    request,
                    f"✅ Reçu analysé par OCR — Score de confiance : {recu.score_confiance:.0%}. "
                    f"{'Montant: {:,.0f} FCFA. '.format(montant_detecte) if montant_detecte else ''}"
                    f"{'Banque: ' + banque + '. ' if banque else ''}"
                    f"Vérifié et validé automatiquement !"
                )
            elif recu.score_confiance and recu.score_confiance >= 0.50:
                messages.warning(
                    request,
                    f"⏳ Reçu téléversé (score OCR : {recu.score_confiance:.0%}). "
                    f"Vérification manuelle requise par le service comptabilité."
                )
            else:
                anomalies = recu.anomalies_detectees.get('anomalies', []) if isinstance(recu.anomalies_detectees, dict) else []
                messages.warning(
                    request,
                    f"⚠️ Reçu téléversé mais score faible ({recu.score_confiance:.0%}). "
                    f"{anomalies[0] if anomalies else 'Document peu lisible.'} "
                    f"Vérification manuelle requise."
                )
                
            return redirect('tableau_bord:tableau_bord')

            
    context = {
        'etudiant': etudiant,
        'tranches': tranches,
        'titre': 'Téléverser un reçu'
    }
    return render(request, 'paiements/recus/televerser.html', context)


@login_required
def televerser_recu_tranche(request, etudiant_id, tranche_id):
    """Téléverser un reçu pour une tranche spécifique"""
    etudiant = get_object_or_404(Etudiant, pk=etudiant_id)
    
    # Sécurité supplémentaire
    if request.user.type_utilisateur == 'ETUDIANT' and etudiant.utilisateur != request.user:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    # Vérifier si le profil de l'étudiant est incomplet
    if not (etudiant.date_naissance and etudiant.lieu_naissance and etudiant.sexe and etudiant.nationalite and etudiant.telephone and etudiant.adresse and etudiant.nom_tuteur and etudiant.telephone_tuteur):
        messages.warning(request, "⚠️ Veuillez compléter vos informations de profil (informations personnelles, contact, tuteur) avant de pouvoir téléverser un reçu de paiement.")
        return redirect(reverse('tableau_bord:modifier_profil') + f'?compte_incomplet=1&next={request.path}')
        
    tranche = get_object_or_404(TranchePaiement, pk=tranche_id)
    
    if request.method == 'POST':
        file = request.FILES.get('recu_fichier')
        reference = request.POST.get('reference_recu', '')
        
        if not file:
            messages.error(request, 'Veuillez sélectionner un fichier.')
        else:
            recu = RecuPaiement.objects.create(
                etudiant=etudiant,
                tranche=tranche,
                recu_fichier=file,
                montant_mentionne=tranche.montant,
                reference_recu=reference,
                statut='EN_ATTENTE'
            )
            
            # Analyse OCR réelle du reçu
            recu.analyser_par_ia()
            
            # Message basé sur le résultat réel
            if recu.score_confiance and recu.score_confiance >= 0.90:
                montant_detecte = recu.verification_ia.get('montant_principal', '')
                banque = recu.verification_ia.get('banque', '')
                messages.success(
                    request,
                    f"✅ Reçu analysé par OCR — Score : {recu.score_confiance:.0%}. "
                    f"{'Montant: {:,.0f} FCFA. '.format(montant_detecte) if montant_detecte else ''}"
                    f"{'Banque: ' + banque + '. ' if banque else ''}"
                    f"Vérifié automatiquement !"
                )
            elif recu.score_confiance and recu.score_confiance >= 0.50:
                messages.warning(
                    request,
                    f"⏳ Reçu téléversé (score OCR : {recu.score_confiance:.0%}). "
                    f"Vérification manuelle requise par le service comptabilité."
                )
            else:
                anomalies = recu.anomalies_detectees.get('anomalies', []) if isinstance(recu.anomalies_detectees, dict) else []
                messages.warning(
                    request,
                    f"⚠️ Reçu téléversé mais score faible ({recu.score_confiance:.0%}). "
                    f"{anomalies[0] if anomalies else 'Document peu lisible.'} "
                    f"Vérification manuelle requise."
                )
                
            return redirect('tableau_bord:tableau_bord')
            
    context = {
        'etudiant': etudiant,
        'tranche': tranche,
        'titre': f'Téléverser {tranche.get_numero_display()}'
    }
    return render(request, 'paiements/recus/televerser_tranche.html', context)


@login_required
def detail_recu(request, pk):
    """Détail d'un reçu"""
    recu = get_object_or_404(RecuPaiement, pk=pk)
    
    context = {
        'recu': recu,
        'titre': f'Détail du reçu'
    }
    return render(request, 'paiements/recus/detail.html', context)


@login_required
@permission_required('paiements.can_validate_paiements', raise_exception=True)
def valider_recu(request, pk):
    """Valider un reçu"""
    if request.user.type_utilisateur not in ['CHEF_COMPTABILITE', 'ADMIN_SYSTEME']:
        messages.error(request, "Seul le Chef de Service de la Comptabilité est autorisé à valider/rejeter les reçus de paiement.")
        return redirect('paiements:liste_recus')
        
    recu = get_object_or_404(RecuPaiement, pk=pk)
    recu.statut = 'VALIDE'
    recu.date_verification = timezone.now()
    recu.verifie_par = request.user
    recu.save()
    
    messages.success(request, f'✅ Reçu validé avec succès !')
    return redirect('paiements:liste_recus')


@login_required
@permission_required('paiements.can_validate_paiements', raise_exception=True)
def rejeter_recu(request, pk):
    """Rejeter un reçu"""
    if request.user.type_utilisateur not in ['CHEF_COMPTABILITE', 'ADMIN_SYSTEME']:
        messages.error(request, "Seul le Chef de Service de la Comptabilité est autorisé à valider/rejeter les reçus de paiement.")
        return redirect('paiements:liste_recus')
        
    recu = get_object_or_404(RecuPaiement, pk=pk)
    recu.statut = 'REJETE'
    recu.date_verification = timezone.now()
    recu.verifie_par = request.user
    recu.save()
    
    messages.warning(request, f'⚠️ Reçu rejeté.')
    return redirect('paiements:liste_recus')


@login_required
def liste_tranches(request):
    """Liste des tranches de paiement"""
    tranches = TranchePaiement.objects.all()
    
    context = {
        'tranches': tranches,
        'titre': 'Tranches de paiement'
    }
    return render(request, 'paiements/tranches/liste.html', context)


@login_required
@permission_required('paiements.add_tranche', raise_exception=True)
def ajouter_tranche(request):
    """Ajouter une tranche de paiement"""
    if request.method == 'POST':
        messages.success(request, '✅ Tranche ajoutée avec succès !')
        return redirect('paiements:liste_tranches')
    
    context = {
        'titre': 'Ajouter une tranche'
    }
    return render(request, 'paiements/tranches/form.html', context)


@login_required
@permission_required('paiements.change_tranche', raise_exception=True)
def modifier_tranche(request, pk):
    """Modifier une tranche de paiement"""
    tranche = get_object_or_404(TranchePaiement, pk=pk)
    
    if request.method == 'POST':
        messages.success(request, '✏️ Tranche modifiée avec succès !')
        return redirect('paiements:liste_tranches')
    
    context = {
        'tranche': tranche,
        'titre': 'Modifier la tranche'
    }
    return render(request, 'paiements/tranches/form.html', context)


@login_required
@permission_required('paiements.delete_tranche', raise_exception=True)
def supprimer_tranche(request, pk):
    """Supprimer une tranche de paiement"""
    tranche = get_object_or_404(TranchePaiement, pk=pk)
    
    if request.method == 'POST':
        tranche.delete()
        messages.success(request, '🗑️ Tranche supprimée avec succès !')
        return redirect('paiements:liste_tranches')
    
    context = {
        'tranche': tranche,
        'titre': 'Supprimer la tranche'
    }
    return render(request, 'paiements/tranches/supprimer.html', context)


@login_required
def statistiques_paiements(request):
    """Statistiques des paiements"""
    context = {
        'titre': 'Statistiques des paiements'
    }
    return render(request, 'paiements/statistiques.html', context)


@login_required
def api_recus_attente(request):
    """API pour le nombre de reçus en attente"""
    count = RecuPaiement.objects.filter(statut='EN_ATTENTE').count()
    return JsonResponse({'count': count})


from .services import calculer_penalites_etudiant
from .momo_service import CinetPayService
from .models import TransactionPaiement
import json as json_module
import logging

logger_paiement = logging.getLogger(__name__)


@login_required
def payer_penalites(request):
    """Page de checkout pour payer les pénalités accumulées"""
    etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    penalites_info = calculer_penalites_etudiant(etudiant)

    if penalites_info['total'] <= 0:
        messages.info(request, "Vous n'avez aucune pénalité en attente de paiement.")
        return redirect('tableau_bord:tableau_bord')

    context = {
        'etudiant': etudiant,
        'penalites_info': penalites_info,
        'total_a_payer': penalites_info['total'],
        'titre': 'Payer mes Pénalités'
    }
    return render(request, 'paiements/recus/payer_penalite.html', context)


@login_required
def initier_paiement_momo(request):
    """Initialise le paiement via CinetPay et retourne l'URL de redirection."""
    if request.method != 'POST':
        return JsonResponse({'status': 'FAILED', 'message': 'Méthode non autorisée.'}, status=405)

    etudiant = get_object_or_404(Etudiant, utilisateur=request.user)
    penalites_info = calculer_penalites_etudiant(etudiant)
    amount = penalites_info['total']

    if amount <= 0:
        return JsonResponse({'status': 'FAILED', 'message': 'Aucune pénalité à payer.'})

    # Créer la transaction en base
    transaction = TransactionPaiement(
        etudiant=etudiant,
        transaction_id=TransactionPaiement.generer_transaction_id(),
        montant=amount,
        type_paiement='PENALITE',
    )
    transaction.save()

    # URLs de callback
    from django.conf import settings as django_settings
    base_url = django_settings.SITE_BASE_URL.rstrip('/')
    notify_url = base_url + reverse('paiements:webhook_cinetpay')
    return_url = base_url + reverse('paiements:paiement_succes') + f'?transaction_id={transaction.transaction_id}'

    # Appeler CinetPay
    res = CinetPayService.initier_paiement(
        transaction_id=transaction.transaction_id,
        amount=amount,
        description=f"Pénalités de retard - {etudiant.get_nom_complet()} ({etudiant.matricule})",
        notify_url=notify_url,
        return_url=return_url,
        customer_name=etudiant.get_nom_complet(),
        customer_email=getattr(etudiant.utilisateur, 'email', ''),
    )

    if res['status'] == 'PENDING':
        transaction.cinetpay_payment_token = res.get('payment_token', '')
        transaction.payment_url = res.get('payment_url', '')
        transaction.save(update_fields=['cinetpay_payment_token', 'payment_url'])

    return JsonResponse(res)


@login_required
def verifier_paiement_momo(request):
    """Vérifie le statut d'une transaction CinetPay (polling côté client)."""
    if request.method != 'POST':
        return JsonResponse({'status': 'FAILED', 'message': 'Méthode non autorisée.'}, status=405)

    data = json_module.loads(request.body)
    transaction_id = data.get('transaction_id')

    if not transaction_id:
        return JsonResponse({'status': 'FAILED', 'message': 'ID de transaction manquant.'})

    try:
        transaction = TransactionPaiement.objects.get(transaction_id=transaction_id)
    except TransactionPaiement.DoesNotExist:
        return JsonResponse({'status': 'FAILED', 'message': 'Transaction introuvable.'})

    # Si déjà traitée, retourner le statut
    if transaction.statut == 'SUCCESS':
        return JsonResponse({
            'status': 'SUCCESS',
            'message': 'Paiement déjà confirmé.',
            'redirect_url': reverse('paiements:paiement_succes') + f'?transaction_id={transaction_id}'
        })

    # Vérifier auprès de CinetPay
    res = CinetPayService.verifier_statut_paiement(transaction_id)

    if res['status'] == 'SUCCESS' and transaction.statut != 'SUCCESS':
        tx_data = res.get('data', {})
        transaction.marquer_succes(cinetpay_data=tx_data)
        CinetPayService.regler_penalites_etudiant(
            etudiant=transaction.etudiant,
            cinetpay_data=tx_data,
            amount_to_pay=float(transaction.montant)
        )
        messages.success(request, f"Paiement de {transaction.montant:,.0f} FCFA confirmé avec succès !")
        res['redirect_url'] = reverse('paiements:paiement_succes') + f'?transaction_id={transaction_id}'

    elif res['status'] in ('FAILED', 'CANCELLED'):
        transaction.marquer_echec(cinetpay_data=res.get('data', {}))

    return JsonResponse(res)


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def webhook_cinetpay(request):
    """
    Webhook CinetPay — reçoit les notifications de paiement automatiques.
    Pas de CSRF car appelé par les serveurs CinetPay.
    """
    if request.method == 'POST':
        try:
            # CinetPay envoie les données en POST form-encoded ou JSON
            cpm_trans_id = request.POST.get('cpm_trans_id') or ''
            if not cpm_trans_id and request.body:
                try:
                    body = json_module.loads(request.body)
                    cpm_trans_id = body.get('cpm_trans_id', '')
                except (json_module.JSONDecodeError, ValueError):
                    pass

            if not cpm_trans_id:
                logger_paiement.warning("[Webhook] Notification sans cpm_trans_id")
                return JsonResponse({'status': 'error', 'message': 'Missing transaction ID'})

            # Retrouver la transaction
            try:
                transaction = TransactionPaiement.objects.get(transaction_id=cpm_trans_id)
            except TransactionPaiement.DoesNotExist:
                logger_paiement.warning(f"[Webhook] Transaction inconnue: {cpm_trans_id}")
                return JsonResponse({'status': 'error', 'message': 'Unknown transaction'})

            # Vérifier le statut réel auprès de CinetPay (ne jamais faire confiance au webhook seul)
            res = CinetPayService.verifier_statut_paiement(cpm_trans_id)

            if res['status'] == 'SUCCESS' and transaction.statut != 'SUCCESS':
                tx_data = res.get('data', {})
                transaction.marquer_succes(cinetpay_data=tx_data)
                CinetPayService.regler_penalites_etudiant(
                    etudiant=transaction.etudiant,
                    cinetpay_data=tx_data,
                    amount_to_pay=float(transaction.montant)
                )
                logger_paiement.info(f"[Webhook] Paiement confirmé: {cpm_trans_id}")

            elif res['status'] in ('FAILED', 'CANCELLED') and transaction.statut == 'PENDING':
                transaction.marquer_echec(cinetpay_data=res.get('data', {}))
                logger_paiement.info(f"[Webhook] Paiement échoué/annulé: {cpm_trans_id}")

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            logger_paiement.exception(f"[Webhook] Erreur: {e}")
            return JsonResponse({'status': 'error'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'POST only'}, status=405)


from .models import SessionConcours, EcheanceSessionNiveau1

@login_required
def gestion_sessions_concours(request):
    """Vue de gestion des sessions de concours et de leurs échéances pour le Niveau 1"""
    user = request.user
    role = getattr(user, 'type_utilisateur', 'ETUDIANT')
    
    if role not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Accès réservé au Chef de Service de la Comptabilité et à la Direction.")
        return redirect('tableau_bord:tableau_bord')
        
    sessions = SessionConcours.objects.prefetch_related('echeances').order_by('-date_concours')
    
    context = {
        'sessions': sessions,
        'titre': 'Sessions de Concours & Échéances Niveau 1'
    }
    return render(request, 'paiements/sessions_concours_liste.html', context)


@login_required
def creer_session_concours(request):
    """Créer une nouvelle session de concours Niveau 1 avec génération automatique des 4 échéances de base"""
    user = request.user
    role = getattr(user, 'type_utilisateur', 'ETUDIANT')
    
    if role not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes.")
        return redirect('paiements:gestion_sessions_concours')
        
    if request.method == 'POST':
        nom = request.POST.get('nom')
        code = request.POST.get('code')
        date_concours = request.POST.get('date_concours')
        from apps.inscriptions.utils import get_current_academic_year_code
        annee = request.POST.get('annee_academique', get_current_academic_year_code())
        description = request.POST.get('description', '')
        
        # Dates des 4 tranches
        d1 = request.POST.get('date_limite_t1')
        d2 = request.POST.get('date_limite_t2')
        d3 = request.POST.get('date_limite_t3')
        d4 = request.POST.get('date_limite_t4')
        
        if not nom or not code or not date_concours or not d1 or not d2 or not d3 or not d4:
            messages.error(request, "Veuillez remplir tous les champs obligatoires (session + les 4 échéances).")
        else:
            try:
                session = SessionConcours.objects.create(
                    nom=nom,
                    code=code,
                    date_concours=date_concours,
                    annee_academique=annee,
                    description=description,
                    est_active=True
                )
                
                # Création des 4 échéances standard Niveau 1 pour cette session (Pré-inscription = 84 000 FCFA)
                EcheanceSessionNiveau1.objects.create(
                    session_concours=session,
                    tranche_numero=1,
                    montant=84000,
                    date_limite=d1,
                    description="Frais de Pré-inscription / Inscription"
                )
                EcheanceSessionNiveau1.objects.create(
                    session_concours=session,
                    tranche_numero=2,
                    montant=175000,
                    date_limite=d2,
                    description="1ère Tranche Scolarité"
                )
                EcheanceSessionNiveau1.objects.create(
                    session_concours=session,
                    tranche_numero=3,
                    montant=115000,
                    date_limite=d3,
                    description="2ème Tranche Scolarité"
                )
                EcheanceSessionNiveau1.objects.create(
                    session_concours=session,
                    tranche_numero=4,
                    montant=100000,
                    date_limite=d4,
                    description="3ème Tranche Scolarité"
                )
                
                messages.success(request, f"✅ Session '{session.nom}' créée avec ses 4 échéances de paiement configurées avec succès !")
                return redirect('paiements:gestion_sessions_concours')
            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {e}")
                
    return redirect('paiements:gestion_sessions_concours')


@login_required
def editer_echeances_session(request, pk):
    """Mettre à jour les dates limites d'une session de concours"""
    session = get_object_or_404(SessionConcours, pk=pk)
    
    if request.user.type_utilisateur not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes.")
        return redirect('paiements:gestion_sessions_concours')
        
    if request.method == 'POST':
        for t_num in [1, 2, 3, 4]:
            d_limite = request.POST.get(f'date_limite_{t_num}')
            remarque = request.POST.get(f'remarque_{t_num}', '')
            if d_limite:
                EcheanceSessionNiveau1.objects.update_or_create(
                    session_concours=session,
                    tranche_numero=t_num,
                    defaults={
                        'montant': 84000 if t_num == 1 else (175000 if t_num == 2 else (115000 if t_num == 3 else 100000)),
                        'date_limite': d_limite,
                        'description': remarque
                    }
                )
        messages.success(request, f"Les échéances de la session '{session.nom}' ont été mises à jour.")
        
    return redirect('paiements:gestion_sessions_concours')



@login_required
def paiement_succes(request):
    """Page de succès après le paiement en ligne. Affiche les détails de la transaction."""
    transaction_id = request.GET.get('transaction_id')
    transaction = None
    if transaction_id:
        try:
            transaction = TransactionPaiement.objects.get(transaction_id=transaction_id)
        except TransactionPaiement.DoesNotExist:
            pass

    context = {
        'titre': 'Paiement Réussi',
        'transaction': transaction,
    }
    return render(request, 'paiements/recus/paiement_succes.html', context)


# ==============================================================================
# GESTION DES RÉSULTATS DU CONCOURS (NIVEAU 1)
# ==============================================================================

import csv
import io
from django.http import HttpResponse


@login_required
def detail_session_concours(request, pk):
    """
    Vue détaillée d'une session de concours : 
    Affichage des échéances, KPIs et de la liste des candidats admis importés.
    """
    session = get_object_or_404(SessionConcours, pk=pk)
    user = request.user
    role = getattr(user, 'type_utilisateur', 'ETUDIANT')
    
    if role not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes pour consulter les détails de la session.")
        return redirect('paiements:gestion_sessions_concours')
        
    # Nettoyage automatique des entrées parasites de l'OCR (ex: "9058", "IA!", "III.", "Listed'attente")
    from django.db.models import Q, Case, When, Value, IntegerField
    session.resultats.filter(
        Q(nom__in=['9058', 'IA!', 'III.', 'Listed\'attente', 'Listedattente']) |
        Q(nom__icontains='Listed\'attente') |
        Q(nom__icontains='Listedattente') |
        Q(nom__regex=r'^\d+$')
    ).delete()

    resultats = ResultatConcours.objects.filter(session_concours=session).select_related('filiere', 'etudiant_cree')
    
    # Recherche et Filtres par Pré-inscription, 1ère Tranche, 2ème Tranche, 3ème Tranche
    search_q = request.GET.get('q', '').strip()
    filiere_id = request.GET.get('filiere', '')
    statut_t1 = request.GET.get('statut_t1', '') or request.GET.get('statut_preinscr', '')
    statut_t2 = request.GET.get('statut_t2', '')
    statut_t3 = request.GET.get('statut_t3', '')
    statut_t4 = request.GET.get('statut_t4', '')
    
    if search_q:
        resultats = resultats.filter(
            Q(nom__icontains=search_q) | 
            Q(prenom__icontains=search_q) | 
            Q(email__icontains=search_q)
        )
    if filiere_id:
        resultats = resultats.filter(filiere_id=filiere_id)
    if statut_t1:
        resultats = resultats.filter(statut_preinscription=statut_t1)
    if statut_t2:
        resultats = resultats.filter(statut_tranche2=statut_t2)
    if statut_t3:
        resultats = resultats.filter(statut_tranche3=statut_t3)
    if statut_t4:
        resultats = resultats.filter(statut_tranche4=statut_t4)


    # Tri strict : 1. GL Admis -> 2. GL Liste d'attente -> 3. SR Admis -> 4. SR Liste d'attente
    resultats = resultats.annotate(
        filiere_order=Case(
            When(filiere__code='GL', then=Value(1)),
            When(filiere__code='SR', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        statut_order=Case(
            When(statut_admission='ADMIS', then=Value(1)),
            When(statut_admission='LISTE_ATTENTE', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('filiere_order', 'statut_order', 'nom', 'prenom', 'id')

        
    # KPIs (Pré-inscription = 84 000 FCFA)
    total_admis = session.resultats.count()
    total_preinscrits_payes = session.resultats.filter(statut_preinscription='PAYE').count()
    total_preinscrits_non_payes = total_admis - total_preinscrits_payes
    montant_recouvre = total_preinscrits_payes * 84000
    taux_recouvrement = round((total_preinscrits_payes / total_admis * 100), 1) if total_admis > 0 else 0
    
    from apps.etudiants.models import Filiere
    filieres = Filiere.objects.all()
    echeances = session.echeances.all()
    
    context = {
        'session': session,
        'resultats': resultats,
        'filieres': filieres,
        'echeances': echeances,
        'total_admis': total_admis,
        'total_preinscrits_payes': total_preinscrits_payes,
        'total_preinscrits_non_payes': total_preinscrits_non_payes,
        'filiere_id': filiere_id,
        'statut_t1': statut_t1,
        'statut_t2': statut_t2,
        'statut_t3': statut_t3,
        'statut_t4': statut_t4,
        'statut_preinscr': statut_t1,
        'search_q': search_q,
        'titre': f"Détails Session - {session.nom}"
    }
    return render(request, 'paiements/sessions_concours_detail.html', context)



@login_required
def importer_resultats_concours(request, pk):
    import re
    """

    Importation des résultats du concours (exclusif Centre de Douala).
    Prend en charge :
    1. CSV/TXT avec colonnes séparées par ; ou , ou tab
    2. PV officiel PDF de l'IAI-Cameroun (structuré par Sections de Centre, Filière et candidats séparés par ;)
    """
    session = get_object_or_404(SessionConcours, pk=pk)
    user = request.user
    role = getattr(user, 'type_utilisateur', 'ETUDIANT')
    
    if role not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Seul le Chef Comptabilité ou un administrateur peut importer les résultats du concours.")
        return redirect('paiements:gestion_sessions_concours')
        
    if request.method == 'POST':
        fichier = request.FILES.get('fichier_csv')
        saisie_manuelle = request.POST.get('saisie_manuelle', '').strip()
        
        full_text = ""
        lignes = []
        if fichier:
            fname = fichier.name.lower()
            if fname.endswith('.csv') or fname.endswith('.txt'):
                try:
                    full_text = fichier.read().decode('utf-8-sig', errors='ignore')
                    lignes = full_text.splitlines()
                except Exception as e:
                    messages.error(request, f"Erreur lors de la lecture du fichier : {e}")
                    return redirect('paiements:detail_session_concours', pk=session.pk)
            elif fname.endswith('.pdf'):
                try:
                    pdf_bytes = fichier.read()
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                    text_pages = []
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text_pages.append(extracted)
                    full_text = "\n".join(text_pages)

                    # Si le PDF est un scan (image CamScanner sans texte numérique), OCR Automatique
                    if not full_text.strip():
                        try:
                            import pypdfium2 as pdfium
                            from rapidocr_onnxruntime import RapidOCR
                            import numpy as np
                            
                            engine = RapidOCR()
                            pdf_doc = pdfium.PdfDocument(pdf_bytes)
                            ocr_pages = []
                            for i in range(len(pdf_doc)):
                                page = pdf_doc[i]
                                pil_image = page.render(scale=2.5).to_pil()
                                img_np = np.array(pil_image)
                                ocr_res, _ = engine(img_np)
                                if ocr_res:
                                    ocr_pages.append("\n".join([item[1] for item in ocr_res if item and len(item) > 1]))
                            full_text = "\n".join(ocr_pages)
                        except Exception as ocr_err:
                            messages.error(request, f"Erreur lors de l'OCR du document scanné : {ocr_err}")
                            return redirect('paiements:detail_session_concours', pk=session.pk)

                    lignes = full_text.splitlines()
                except Exception as e:
                    messages.error(request, f"Erreur lors de l'extraction du fichier PDF : {e}")
                    return redirect('paiements:detail_session_concours', pk=session.pk)


            else:
                messages.error(request, "Veuillez téléverser un fichier au format CSV (.csv), TXT (.txt) ou PDF (.pdf).")
                return redirect('paiements:detail_session_concours', pk=session.pk)
        elif saisie_manuelle:
            full_text = saisie_manuelle
            lignes = saisie_manuelle.splitlines()
        else:
            messages.error(request, "Veuillez fournir un fichier CSV/PDF ou remplir le champ de saisie rapide.")
            return redirect('paiements:detail_session_concours', pk=session.pk)

        import_count = 0
        update_count = 0
        error_count = 0
        
        from apps.etudiants.models import Filiere
        filieres = list(Filiere.objects.all())
        filiere_gl = Filiere.objects.filter(code='GL').first()
        filiere_sr = Filiere.objects.filter(code='SR').first()
        
        filieres_dict = {f.code.upper(): f for f in filieres}

        # Détection s'il s'agit du format Officiel Procès-Verbal IAI (avec "CENTRE DE FORMATION DE...")
        full_upper = full_text.upper()
        est_pv_officiel = 'CENTRE DE FORMATION' in full_upper or 'CENTRE D\'EXCELLENCE' in full_upper or 'DÉCLARÉS DÉFINITIVEMENT ADMIS' in full_upper or 'DECLARES DEFINITIVEMENT ADMIS' in full_upper

        if est_pv_officiel:
            # === MODE PARSER PROCÈS-VERBAL OFFICIEL IAI ===
            current_center = None
            current_filiere = None
            current_statut = 'ADMIS'
            
            for line in lignes:
                line_str = line.strip()
                if not line_str:
                    continue
                line_up = line_str.upper()
                
                # 1. Détection des sections de centres de formation (ex: "II. Centre de formation de Douala", "III. Centre de formation de Garoua")
                if 'CENTRE DE FORMATION' in line_up or re.search(r'^[I|V|X]+\.\s*CENTRE', line_up):
                    if 'DOUALA' in line_up or 'DLA' in line_up:
                        current_center = 'DOUALA'
                    else:
                        current_center = 'AUTRE'
                    continue

                    
                # Si nous ne sommes pas dans le centre de Douala, ignorer la ligne
                if current_center != 'DOUALA':
                    continue

                # 2. Détection de la filière et de la liste d'attente
                if 'FILIÈRE' in line_up or 'FILIERE' in line_up:
                    if 'LOGICIEL' in line_up or 'SOFTWARE' in line_up or 'GL' in line_up:
                        current_filiere = filiere_gl or (filieres[0] if filieres else None)
                    elif 'RÉSEAUX' in line_up or 'RESEAUX' in line_up or 'SYSTEMES' in line_up or 'SYSTÈMES' in line_up or 'SR' in line_up:
                        current_filiere = filiere_sr or (filieres[-1] if filieres else None)
                    else:
                        current_filiere = filieres[0] if filieres else None
                    current_statut = 'ADMIS'
                    continue

                if 'LISTE D\'ATTENTE' in line_up or 'LISTE D ATTENTE' in line_up:
                    current_statut = 'LISTE_ATTENTE'
                    continue

                # Ignorer les lignes d'en-tête / footer / pagination
                if any(h in line_up for h in ['PAGE', 'SCANNED WITH', 'CAMSCANNER', 'RÉSULTATS DU CONCOURS', 'RESULTATS DU CONCOURS', 'SESSION DU', 'PRÉINSCRITS AU PLUS TARD', 'LE REPRÉSENTANT', 'LE REPRESENTANT']):
                    continue

                # 3. Extraction des noms séparés par des point-virgules (;)
                candidates_raw = [c.strip() for c in line_str.split(';') if c.strip()]
                for cand_name in candidates_raw:
                    cand_clean = re.sub(r'^\d+[\.\)]\s*', '', cand_name).strip()
                    if len(cand_clean) < 3 or cand_clean.upper() in ['LISTE D\'ATTENTE', 'FILIÈRE GÉNIE LOGICIEL', 'FILIÈRE SYSTÈMES ET RÉSEAUX']:
                        continue
                        
                    parts = cand_clean.split()
                    if len(parts) >= 2:
                        nom = parts[0]
                        prenom = " ".join(parts[1:])
                    else:
                        nom = cand_clean
                        prenom = ""
                        
                    num_table = f"DLA-2026-{(import_count + update_count + 1):03d}"
                    
                    try:
                        res, created = ResultatConcours.objects.update_or_create(
                            session_concours=session,
                            numero_table=num_table,
                            defaults={
                                'nom': nom,
                                'prenom': prenom,
                                'filiere': current_filiere,
                                'statut_admission': current_statut,
                                'importe_par': request.user,
                            }
                        )
                        if created:
                            import_count += 1
                        else:
                            update_count += 1
                    except Exception:
                        error_count += 1

        else:
            # === MODE PARSER STANDARD (CSV, TXT, Saisie Manuelle) ===
            current_center = 'DOUALA'
            other_centers = ['YAOUNDE', 'GAROUA', 'MAROUA', 'BAMENDA', 'BAFOUSSAM', 'BERTOUA', 'EBOLOWA', 'YDE']
            
            for index, line in enumerate(lignes):
                line_str = line.strip()
                if not line_str:
                    continue
                line_upper = line_str.upper()

                if any(c in line_upper for c in other_centers) and 'DOUALA' not in line_upper and 'DLA' not in line_upper:
                    continue

                if any(hk in line_upper for hk in ['RÉPUBLIQUE', 'REPUBLIQUE', 'PAIX - TRAVAIL', 'INSTITUT AFRICAIN D\'INFORMATIQUE', 'DIRECTION FINANCIÈRE', 'LISTE OFFICIELLE DES LAURÉATS', 'SIGNATURE & CACHET', 'RÉCAPITULATIF', 'TOTAL ADMIS']):
                    continue
                if ('NOM' in line_upper and 'FILIÈRE' in line_upper) or ('TABLE' in line_upper and 'STATUT' in line_upper):
                    continue

                num_table = ""
                nom = ""
                prenom = ""
                email = ""
                telephone = ""
                code_filiere = ""
                filiere_obj = None
                statut_adm = 'ADMIS'

                if ';' in line_str or '\t' in line_str or (',' in line_str and not ' ' in line_str):
                    delimiter = ';' if ';' in line_str else ('\t' if '\t' in line_str else ',')
                    parts = [p.strip() for p in line_str.split(delimiter)]
                    if len(parts) >= 2:
                        num_table = parts[0]
                        nom = parts[1]
                        prenom = parts[2] if len(parts) > 2 else ""
                        email = parts[3] if len(parts) > 3 and '@' in parts[3] else ""
                        telephone = parts[4] if len(parts) > 4 and parts[4].isdigit() else ""
                        code_filiere = parts[5].upper() if len(parts) > 5 else ""
                        if len(parts) > 6 and 'ATTENTE' in parts[6].upper():
                            statut_adm = 'LISTE_ATTENTE'
                else:
                    tokens = line_str.split(';') if ';' in line_str else line_str.split()
                    if not tokens:
                        continue
                    found_filiere_idx = -1
                    for idx, tok in enumerate(tokens):
                        clean_tok = tok.upper().strip('(),.')
                        if clean_tok in filieres_dict:
                            filiere_obj = filieres_dict[clean_tok]
                            code_filiere = filiere_obj.code
                            found_filiere_idx = idx
                            break

                    if 'ATTENTE' in line_upper or 'RESERVE' in line_upper:
                        statut_adm = 'LISTE_ATTENTE'
                    else:
                        statut_adm = 'ADMIS'

                    first_tok = tokens[0].upper().strip('.,()')
                    if re.match(r'^[A-Z0-9\-/]+$', first_tok) and len(first_tok) <= 25 and not first_tok.isalpha():
                        num_table = first_tok
                        nom_tokens = tokens[1:found_filiere_idx] if found_filiere_idx > 1 else tokens[1:]
                    else:
                        num_table = f"DLA-2026-{(import_count + update_count + 1):03d}"
                        nom_tokens = tokens[0:found_filiere_idx] if found_filiere_idx > 0 else tokens

                    words = [t for t in nom_tokens if t.upper().strip('(),.') not in ['ADMIS', 'ATTENTE', 'LISTE', 'NIVEAU', 'DOUALA', 'DLA', code_filiere, 'PAYÉ', 'PAYE', 'NON', '84K', '50K', 'FCFA']]
                    if len(words) >= 2:
                        nom = words[0]
                        prenom = " ".join(words[1:])
                    elif len(words) == 1:
                        nom = words[0]
                        prenom = ""

                if not nom or len(nom) < 2:
                    error_count += 1
                    continue

                if not num_table:
                    num_table = f"DLA-2026-{(import_count + update_count + 1):03d}"

                if not filiere_obj and code_filiere:
                    filiere_obj = filieres_dict.get(code_filiere, None)

                try:
                    res, created = ResultatConcours.objects.update_or_create(
                        session_concours=session,
                        numero_table=num_table,
                        defaults={
                            'nom': nom,
                            'prenom': prenom,
                            'email': email,
                            'telephone': telephone,
                            'filiere': filiere_obj,
                            'statut_admission': statut_adm,
                            'importe_par': request.user,
                        }
                    )
                    if created:
                        import_count += 1
                    else:
                        update_count += 1
                except Exception:
                    error_count += 1

        msg = f"✅ Importation (Centre de Douala) terminée pour {session.nom} : {import_count} candidat(s) admis ajouté(s)"
        if update_count > 0:
            msg += f", {update_count} mis à jour"
        if error_count > 0:
            msg += f", {error_count} ligne(s) ignorée(s) ou hors Douala"
        msg += "."
        
        messages.success(request, msg)
        return redirect('paiements:detail_session_concours', pk=session.pk)

    return redirect('paiements:detail_session_concours', pk=session.pk)




@login_required
def marquer_preinscription_payee(request, pk):
    """Marquer ou basculer le statut de pré-inscription (84 000 FCFA) pour un candidat admis"""
    return marquer_tranche_payee(request, pk, tranche_num=1)


@login_required
def marquer_tranche_payee(request, pk, tranche_num=1):
    """Marquer ou basculer le statut d'une tranche (1, 2, 3 ou 4) pour un candidat admis"""
    resultat = get_object_or_404(ResultatConcours, pk=pk)
    
    if request.user.type_utilisateur not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes.")
        return redirect('paiements:detail_session_concours', pk=resultat.session_concours.pk)
        
    tranche_num = int(tranche_num)

    # RÈGLE STRICTE : Pré-inscription obligatoire (84 000 FCFA) avant de pouvoir verser toute autre tranche
    if tranche_num in [2, 3, 4] and resultat.statut_preinscription != 'PAYE':
        tranche_name = "1ère Tranche" if tranche_num == 2 else ("2ème Tranche" if tranche_num == 3 else "3ème Tranche")
        messages.error(request, f"⛔ Paiement bloqué : La pré-inscription (84 000 FCFA) de {resultat.nom} {resultat.prenom} doit être réglée au préalable avant de valider la {tranche_name} !")
        return redirect('paiements:detail_session_concours', pk=resultat.session_concours.pk)

    if tranche_num == 1:
        if resultat.statut_preinscription == 'PAYE':
            resultat.statut_preinscription = 'NON_PAYE'
            messages.warning(request, f"Pré-inscription (84k) de {resultat.nom} {resultat.prenom} marquée comme NON PAYÉE.")
        else:
            resultat.statut_preinscription = 'PAYE'
            messages.success(request, f"Pré-inscription (84k) de {resultat.nom} {resultat.prenom} marquée comme PAYÉE !")
    elif tranche_num == 2:
        if resultat.statut_tranche2 == 'PAYE':
            resultat.statut_tranche2 = 'NON_PAYE'
            messages.warning(request, f"1ère Tranche de {resultat.nom} {resultat.prenom} marquée comme NON PAYÉE.")
        else:
            resultat.statut_tranche2 = 'PAYE'
            messages.success(request, f"1ère Tranche de {resultat.nom} {resultat.prenom} marquée comme PAYÉE !")
    elif tranche_num == 3:
        if resultat.statut_tranche3 == 'PAYE':
            resultat.statut_tranche3 = 'NON_PAYE'
            messages.warning(request, f"2ème Tranche de {resultat.nom} {resultat.prenom} marquée comme NON PAYÉE.")
        else:
            resultat.statut_tranche3 = 'PAYE'
            messages.success(request, f"2ème Tranche de {resultat.nom} {resultat.prenom} marquée comme PAYÉE !")
    elif tranche_num == 4:
        if resultat.statut_tranche4 == 'PAYE':
            resultat.statut_tranche4 = 'NON_PAYE'
            messages.warning(request, f"3ème Tranche de {resultat.nom} {resultat.prenom} marquée comme NON PAYÉE.")
        else:
            resultat.statut_tranche4 = 'PAYE'
            messages.success(request, f"3ème Tranche de {resultat.nom} {resultat.prenom} marquée comme PAYÉE !")
            
    resultat.save()
    return redirect('paiements:detail_session_concours', pk=resultat.session_concours.pk)




@login_required
def supprimer_resultat_concours(request, pk):
    """Supprimer un résultat de concours"""
    resultat = get_object_or_404(ResultatConcours, pk=pk)
    session_id = resultat.session_concours.pk
    
    if request.user.type_utilisateur not in ['CHEF_COMPTABILITE', 'ADMIN_FINANCIER', 'ADMIN_SYSTEME', 'DIRECTEUR']:
        messages.error(request, "Permissions insuffisantes.")
        return redirect('paiements:detail_session_concours', pk=session_id)
        
    nom_candidat = f"{resultat.nom} {resultat.prenom}"
    resultat.delete()
    messages.success(request, f"🗑️ Candidat {nom_candidat} retiré des résultats de la session.")
    return redirect('paiements:detail_session_concours', pk=session_id)


@login_required
def exporter_resultats_concours(request, pk):
    """Exporter les résultats d'admission au format CSV (sans N° Table, avec les 4 tranches)"""
    session = get_object_or_404(SessionConcours, pk=pk)
    resultats = ResultatConcours.objects.filter(session_concours=session).select_related('filiere')
    
    # Prise en compte des filtres de recherche multi-tranches
    search_q = request.GET.get('q', '').strip()
    filiere_id = request.GET.get('filiere', '')
    statut_t1 = request.GET.get('statut_t1', '') or request.GET.get('statut_preinscr', '')
    statut_t2 = request.GET.get('statut_t2', '')
    statut_t3 = request.GET.get('statut_t3', '')
    statut_t4 = request.GET.get('statut_t4', '')
    
    from django.db.models import Q, Case, When, Value, IntegerField
    if search_q:
        resultats = resultats.filter(
            Q(nom__icontains=search_q) | 
            Q(prenom__icontains=search_q) | 
            Q(email__icontains=search_q)
        )
    if filiere_id:
        resultats = resultats.filter(filiere_id=filiere_id)
    if statut_t1:
        resultats = resultats.filter(statut_preinscription=statut_t1)
    if statut_t2:
        resultats = resultats.filter(statut_tranche2=statut_t2)
    if statut_t3:
        resultats = resultats.filter(statut_tranche3=statut_t3)
    if statut_t4:
        resultats = resultats.filter(statut_tranche4=statut_t4)

    resultats = resultats.annotate(
        filiere_order=Case(
            When(filiere__code='GL', then=Value(1)),
            When(filiere__code='SR', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        statut_order=Case(
            When(statut_admission='ADMIS', then=Value(1)),
            When(statut_admission='LISTE_ATTENTE', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('filiere_order', 'statut_order', 'nom', 'prenom', 'id')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="Resultats_Concours_{session.code}.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['NOM', 'PRENOM', 'FILIERE', 'STATUT_ADMISSION', 'PREINSCRIPTION_84K', '1ERE_TRANCHE', '2EME_TRANCHE', '3EME_TRANCHE', 'EMAIL', 'TELEPHONE'])
    
    for r in resultats:
        statut_adm = "En attente" if r.statut_admission == 'LISTE_ATTENTE' else "Admis"
        writer.writerow([
            r.nom,
            r.prenom,
            r.filiere.code if r.filiere else '',
            statut_adm,
            r.get_statut_preinscription_display(),
            r.get_statut_tranche2_display(),
            r.get_statut_tranche3_display(),
            r.get_statut_tranche4_display(),
            r.email or '',
            r.telephone or ''
        ])
        
    return response


@login_required
def telecharger_modele_csv_concours(request):
    """Générer un fichier d'exemple CSV pour l'importation des résultats"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="Modele_Import_Resultats_Concours.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['NOM', 'PRENOM', 'EMAIL', 'TELEPHONE', 'CODE_FILIERE', 'STATUT_ADMISSION'])
    writer.writerow(['KAMGA', 'Jean Marc', 'jean.kamga@example.com', '699000111', 'GL', 'ADMIS'])
    return response


@login_required
def exporter_resultats_concours_pdf(request, pk):
    """
    Génère un document PDF officiel de la liste des candidats admis du Centre de Douala (avec Pré-inscription, 1ère, 2ème et 3ème tranches).
    """
    session = get_object_or_404(SessionConcours, pk=pk)
    resultats = ResultatConcours.objects.filter(session_concours=session).select_related('filiere')

    # Prise en compte des filtres de recherche multi-tranches
    search_q = request.GET.get('q', '').strip()
    filiere_id = request.GET.get('filiere', '')
    statut_t1 = request.GET.get('statut_t1', '') or request.GET.get('statut_preinscr', '')
    statut_t2 = request.GET.get('statut_t2', '')
    statut_t3 = request.GET.get('statut_t3', '')
    statut_t4 = request.GET.get('statut_t4', '')
    
    from django.db.models import Q, Case, When, Value, IntegerField
    if search_q:
        resultats = resultats.filter(
            Q(nom__icontains=search_q) | 
            Q(prenom__icontains=search_q) | 
            Q(email__icontains=search_q)
        )
    if filiere_id:
        resultats = resultats.filter(filiere_id=filiere_id)
    if statut_t1:
        resultats = resultats.filter(statut_preinscription=statut_t1)
    if statut_t2:
        resultats = resultats.filter(statut_tranche2=statut_t2)
    if statut_t3:
        resultats = resultats.filter(statut_tranche3=statut_t3)
    if statut_t4:
        resultats = resultats.filter(statut_tranche4=statut_t4)

    resultats = resultats.annotate(
        filiere_order=Case(
            When(filiere__code='GL', then=Value(1)),
            When(filiere__code='SR', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        ),
        statut_order=Case(
            When(statut_admission='ADMIS', then=Value(1)),
            When(statut_admission='LISTE_ATTENTE', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('filiere_order', 'statut_order', 'nom', 'prenom', 'id')

    
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Resultats_Concours_Douala_{session.code}.pdf"'
    
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#064E3B'),
        alignment=1
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#D97706'),
        alignment=1
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=0
    )
    header_right_style = ParagraphStyle(
        'HeaderRightStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=2
    )
    
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10
    )

    elements = []
    
    header_text = "<b>RÉPUBLIQUE DU CAMEROUN</b><br/><font size=7 color='#666666'>Paix - Travail - Patrie</font><br/><b>INSTITUT AFRICAIN D'INFORMATIQUE</b><br/><font size=7 color='#064E3B'>CENTRE DE DOUALA</font>"
    header_right = f"<b>DIRECTION FINANCIÈRE & COMPTABILITÉ</b><br/><font size=7 color='#666666'>Année Académique : {session.annee_academique}</font><br/><font size=7 color='#666666'>Édité le : {timezone.now().strftime('%d/%m/%Y à %H:%M')}</font>"
    
    header_table = Table(
        [[Paragraph(header_text, header_style), Paragraph(header_right, header_right_style)]],
        colWidths=[9.5*cm, 8.5*cm]
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#064E3B'), spaceAfter=10))
    
    elements.append(Paragraph("LISTE OFFICIELLE DES LAURÉATS ET SUIVI DES TRANCHES DE PAIEMENT (DOUALA)", title_style))
    elements.append(Paragraph(f"SESSION : {session.nom.upper()} — CONCOURS DU {session.date_concours.strftime('%d/%m/%Y')}", subtitle_style))
    elements.append(Spacer(1, 0.4*cm))
    
    total_admis = resultats.count()
    total_t1_payes = resultats.filter(statut_preinscription='PAYE').count()
    total_t2_payes = resultats.filter(statut_tranche2='PAYE').count()
    total_t3_payes = resultats.filter(statut_tranche3='PAYE').count()
    total_t4_payes = resultats.filter(statut_tranche4='PAYE').count()
    
    kpi_data = [
        [
            Paragraph(f"<b>Effectif :</b> {total_admis}", cell_bold),
            Paragraph(f"<b>Pré-inscr. (84k) :</b> {total_t1_payes}", cell_bold),
            Paragraph(f"<b>1ère Tranche :</b> {total_t2_payes}", cell_bold),
            Paragraph(f"<b>2ème Tranche :</b> {total_t3_payes}", cell_bold),
            Paragraph(f"<b>3ème Tranche :</b> {total_t4_payes}", cell_bold),
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[3.2*cm, 3.7*cm, 3.7*cm, 3.7*cm, 3.7*cm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F0FDF4')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#BBF7D0')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.4*cm))
    
    table_header_style = ParagraphStyle(
        'THeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.white, alignment=1
    )
    
    table_data = [
        [
            Paragraph("<b>NOM & PRÉNOM(S)</b>", table_header_style),
            Paragraph("<b>FILIÈRE</b>", table_header_style),
            Paragraph("<b>STATUT</b>", table_header_style),
            Paragraph("<b>PRÉ-INSCR. (84K)</b>", table_header_style),
            Paragraph("<b>1ÈRE TRANCHE</b>", table_header_style),
            Paragraph("<b>2ÈME TRANCHE</b>", table_header_style),
            Paragraph("<b>3ÈME TRANCHE</b>", table_header_style)
        ]
    ]
    
    for r in resultats:
        t1_txt = "<font color='#047857'><b>PAYÉ</b></font>" if r.statut_preinscription == 'PAYE' else "<font color='#B91C1C'>NON PAYÉ</font>"
        t2_txt = "<font color='#047857'><b>PAYÉ</b></font>" if r.statut_tranche2 == 'PAYE' else "<font color='#B91C1C'>NON PAYÉ</font>"
        t3_txt = "<font color='#047857'><b>PAYÉ</b></font>" if r.statut_tranche3 == 'PAYE' else "<font color='#B91C1C'>NON PAYÉ</font>"
        t4_txt = "<font color='#047857'><b>PAYÉ</b></font>" if r.statut_tranche4 == 'PAYE' else "<font color='#B91C1C'>NON PAYÉ</font>"
        filiere_txt = r.filiere.code if r.filiere else "-"
        
        statut_adm_str = "<font color='#D97706'><b>En attente</b></font>" if r.statut_admission == 'LISTE_ATTENTE' else "Admis"
        nom_str = f"<b>{r.nom}</b> {r.prenom} <font color='#D97706'><b>(En attente)</b></font>" if r.statut_admission == 'LISTE_ATTENTE' else f"<b>{r.nom}</b> {r.prenom}"
        
        table_data.append([
            Paragraph(nom_str, cell_style),
            Paragraph(filiere_txt, cell_bold),
            Paragraph(statut_adm_str, cell_style),
            Paragraph(t1_txt, cell_style),
            Paragraph(t2_txt, cell_style),
            Paragraph(t3_txt, cell_style),
            Paragraph(t4_txt, cell_style)
        ])
        
    candidats_table = Table(table_data, colWidths=[5.6*cm, 1.6*cm, 2.4*cm, 2.1*cm, 2.1*cm, 2.1*cm, 2.1*cm])
    candidats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#064E3B')),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    
    elements.append(candidats_table)
    
    doc.build(elements)
    return response