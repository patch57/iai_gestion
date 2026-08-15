from datetime import date
from django.utils import timezone
from .models import TranchePaiement, RecuPaiement

def calculer_penalites_etudiant(etudiant):
    """
    Calcule les pénalités de retard accumulées par un étudiant.
    Règle métier stricte IAI-Gestion :
    - Pré-inscription (Tranche 1) : 1500 FCFA par semaine de retard
    - Tranche 1, 2, 3 (Tranches 2, 3, 4) : 3000 FCFA par semaine de retard
    - Le PAIEMENT EN LIGNE d'une pénalité est conditionné à la VALIDATION (statut VALIDE) du reçu bancaire de la tranche associée.
    """
    penalites_totales = 0
    penalites_eligibles_totales = 0
    details_penalites = []
    
    annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"
    tranches = TranchePaiement.objects.filter(annee_academique=annee_code, est_actif=True)
    date_aujourdhui = date.today()
    
    for tranche in tranches:
        # Vérifier si le reçu de la tranche a été soumis et son statut
        recu_associe = RecuPaiement.objects.filter(
            etudiant=etudiant,
            tranche=tranche
        ).order_by('-date_televersement').first()
        
        est_valide = False
        if tranche.numero == 1 and etudiant.recu_preinscription_valide:
            est_valide = True
        elif recu_associe and recu_associe.statut == 'VALIDE':
            est_valide = True
            
        # Transposition du numéro de tranche vers le code PenalitePaiement
        tranche_code = {1: 'PREINSCRIPTION', 2: 'TRANCHE_1', 3: 'TRANCHE_2', 4: 'TRANCHE_3'}.get(tranche.numero, 'PREINSCRIPTION')
        from apps.tableau_bord.models import PenalitePaiement
        if PenalitePaiement.objects.filter(etudiant=etudiant, tranche=tranche_code, est_regle=True).exists():
            # Pénalité déjà réglée pour cette tranche, passer à la suivante
            continue

        if date_aujourdhui > tranche.date_limite:
            jours_retard = (date_aujourdhui - tranche.date_limite).days
            
            if jours_retard > 0:
                semaines_retard = (jours_retard + 6) // 7
                tarif_penalite = 1500 if tranche.numero == 1 else 3000
                montant_penalite = semaines_retard * tarif_penalite
                
                # Une pénalité est éligible au paiement en ligne SEULEMENT si le reçu de la tranche a été validé
                eligible_paiement = est_valide
                
                penalites_totales += montant_penalite
                if eligible_paiement:
                    penalites_eligibles_totales += montant_penalite
                
                details_penalites.append({
                    'tranche_id': tranche.id,
                    'tranche_numero': tranche.numero,
                    'tranche': tranche.get_numero_display(),
                    'date_limite': tranche.date_limite,
                    'semaines_retard': semaines_retard,
                    'tarif': tarif_penalite,
                    'montant': montant_penalite,
                    'recu_soumis': recu_associe is not None,
                    'recu_statut': recu_associe.get_statut_display() if recu_associe else "Non téléversé",
                    'recu_valide': est_valide,
                    'eligible_paiement': eligible_paiement
                })
                
    return {
        'total': penalites_eligibles_totales,  # Total des pénalités payables en ligne
        'total_global': penalites_totales,    # Cumul global de toutes les pénalités de retard
        'details': details_penalites
    }

