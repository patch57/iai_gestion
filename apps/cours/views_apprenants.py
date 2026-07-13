from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse

from apps.etudiants.models import Apprenant, Formation
from apps.notes.models import NoteApprenant
from apps.notes.forms import NoteApprenantForm
from .models import SupportPedagogiqueApprenant
from .forms import SupportPedagogiqueApprenantForm


@login_required
def liste_apprenants_categories(request):
    """Consulter et imprimer la liste des apprenants par catégories"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'ADMIN_SYSTEME']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    apprenants = Apprenant.objects.all().prefetch_related('formations')
    
    # Filtres
    type_formation = request.GET.get('type_formation', '')
    if type_formation:
        apprenants = apprenants.filter(formations__type_formation=type_formation).distinct()
        
    module = request.GET.get('module', '')
    if module:
        apprenants = apprenants.filter(formations__nom=module).distinct()
        
    niveau = request.GET.get('niveau', '')
    if niveau:
        apprenants = apprenants.filter(niveau_etude__icontains=niveau)
        
    # Liste des modules et types pour le formulaire de filtrage
    formations = Formation.objects.all()
    
    context = {
        'apprenants': apprenants,
        'formations': formations,
        'type_formation_choices': Formation.TYPES,
        'module_choices': Formation.NOM_CHOICES,
        'titre': 'Registre des Apprenants'
    }
    return render(request, 'cours/apprenants/liste_apprenants.html', context)


@login_required
def saisir_notes_apprenants(request):
    """Saisie des notes d'évaluation des apprenants par formation"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'ADMIN_SYSTEME']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    formation_id = request.GET.get('formation_id', '')
    formation = None
    apprenants = []
    
    if formation_id:
        formation = get_object_or_404(Formation, id=formation_id)
        apprenants = Apprenant.objects.filter(formations=formation)
        
    if request.method == 'POST' and formation:
        # Enregistrement en lot des notes
        compteur = 0
        for key, value in request.POST.items():
            if key.startswith('note_'):
                apprenant_id = key.split('_')[1]
                note_val = value.strip()
                commentaire = request.POST.get(f'commentaire_{apprenant_id}', '')
                
                if note_val:
                    try:
                        apprenant = Apprenant.objects.get(id=apprenant_id)
                        # Récupérer ou créer la note pour cet apprenant et cette formation
                        note_obj, created = NoteApprenant.objects.get_or_create(
                            apprenant=apprenant,
                            formation=formation,
                            defaults={'formateur': request.user, 'note': 0}
                        )
                        note_obj.note = float(note_val)
                        note_obj.commentaire = commentaire
                        note_obj.formateur = request.user
                        note_obj.save()
                        compteur += 1
                    except Exception as e:
                        messages.error(request, f"Erreur lors de l'enregistrement pour {apprenant.nom_complet} : {str(e)}")
                        
        messages.success(request, f"✅ {compteur} note(s) d'évaluation enregistrée(s) avec succès.")
        return redirect(f"{request.path}?formation_id={formation.id}")
        
    # Charger les notes existantes sous forme de dictionnaire pour pré-remplir le tableau
    notes_dict = {}
    if formation:
        notes = NoteApprenant.objects.filter(formation=formation)
        for n in notes:
            notes_dict[n.apprenant_id] = {'note': n.note, 'commentaire': n.commentaire}
            
    formations = Formation.objects.filter(est_active=True)
    
    context = {
        'formations': formations,
        'formation_selectionnee': formation,
        'apprenants': apprenants,
        'notes_dict': notes_dict,
        'titre': 'Saisie des Notes - Certifications'
    }
    return render(request, 'cours/apprenants/saisie_notes.html', context)


@login_required
def ajouter_support_apprenant(request):
    """Dépôt de supports de cours ciblés pour les apprenants"""
    if request.user.type_utilisateur not in ['ENSEIGNANT', 'PROFESSEUR', 'ADMIN_SYSTEME']:
        messages.error(request, "Accès refusé.")
        return redirect('tableau_bord:tableau_bord')
        
    if request.method == 'POST':
        form = SupportPedagogiqueApprenantForm(request.POST, request.FILES)
        if form.is_valid():
            support = form.save(commit=False)
            support.formateur = request.user
            support.save()
            messages.success(request, "✅ Le support pédagogique a été chargé et envoyé aux apprenants concernés.")
            return redirect('cours:liste_supports_apprenant')
    else:
        form = SupportPedagogiqueApprenantForm()
        
    context = {
        'form': form,
        'titre': 'Charger un support de formation'
    }
    return render(request, 'cours/apprenants/supports.html', context)


@login_required
def liste_supports_apprenant(request):
    """Affiche la liste des supports de formation (cours/TP/TD) accessibles"""
    user = request.user
    role = user.type_utilisateur
    
    supports = SupportPedagogiqueApprenant.objects.all().select_related('formateur')
    
    # Si c'est un apprenant, on filtre selon son profil et ses inscriptions
    if role == 'APPRENANT':
        apprenant = getattr(user, 'profil_apprenant', None)
        if apprenant:
            formations_apprenant = apprenant.formations.all()
            modules_noms = [f.nom for f in formations_apprenant]
            types_formations = [f.type_formation for f in formations_apprenant]
            
            # Filtre : correspond aux modules, type ou tous, et optionnellement au niveau
            supports = supports.filter(
                (Q(module_formation__in=modules_noms) | Q(module_formation='TOUS')) &
                (Q(type_formation__in=types_formations) | Q(type_formation='TOUS'))
            )
            if apprenant.niveau_etude:
                supports = supports.filter(Q(niveau_etude=apprenant.niveau_etude) | Q(niveau_etude=''))
        else:
            supports = supports.none()
    elif role in ['ENSEIGNANT', 'PROFESSEUR']:
        # Le formateur voit ses propres dépôts ou tous
        supports = supports.filter(formateur=user)
        
    context = {
        'supports': supports,
        'titre': 'Supports de Formation'
    }
    return render(request, 'cours/apprenants/liste_supports.html', context)
