from datetime import date
from decimal import Decimal
from django.utils import timezone
from .models import TranchePaiement, RecuPaiement

def calculer_penalites_etudiant(etudiant):
    """
    Calcule les pénalités de retard accumulées par un étudiant.
    Règle métier stricte IAI-Gestion :
    - Pré-inscription (Tranche 1) : 1500 FCFA par semaine de retard
    - Tranche 1, 2, 3 (Tranches 2, 3, 4) : 3000 FCFA par semaine de retard
    - Le PAIEMENT EN LIGNE d'une pénalité est conditionné à la VALIDATION (statut VALIDE) du reçu bancaire de la tranche associée.
    - ARRÊT DE CALCUL DES PÉNALITÉS : Une fois le reçu de paiement d'une tranche (y compris la pré-inscription)
      soumis et validé sur la plateforme, le calcul des pénalités pour cette tranche s'arrête définitivement à la date 
      de paiement/soumission du reçu. L'étudiant ne paye que pour le retard accusé jusqu'à cette date.
    """
    penalites_totales = Decimal('0.00')
    penalites_eligibles_totales = Decimal('0.00')
    details_penalites = []
    
    annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"
    tranches = TranchePaiement.objects.filter(annee_academique=annee_code, est_actif=True)
    date_aujourdhui = date.today()
    
    for tranche in tranches:
        # Vérifier si le reçu de la tranche a été soumis et son statut
        # 1. Chercher d'abord un reçu VALIDE associé
        recu_associe = RecuPaiement.objects.filter(
            etudiant=etudiant,
            tranche=tranche,
            statut='VALIDE'
        ).order_by('-date_televersement').first()

        # 2. Si aucun reçu validé spécifique, prendre le dernier reçu soumis pour cette tranche
        if not recu_associe:
            recu_associe = RecuPaiement.objects.filter(
                etudiant=etudiant,
                tranche=tranche
            ).order_by('-date_televersement').first()

        # 3. Fallback pré-inscription (Tranche 1) sans relation FK explicite sur tranche
        if not recu_associe and tranche.numero == 1:
            recu_associe = RecuPaiement.objects.filter(
                etudiant=etudiant,
                tranche__isnull=True,
                statut='VALIDE'
            ).order_by('-date_televersement').first()
            if not recu_associe:
                recu_associe = RecuPaiement.objects.filter(
                    etudiant=etudiant,
                    tranche__isnull=True
                ).order_by('-date_televersement').first()
        
        # Récupération de l'inscription éventuelle pour vérifier les drapeaux de validation directs
        inscription_obj = etudiant.inscriptions.first() if hasattr(etudiant, 'inscriptions') else None

        est_valide = False
        if recu_associe and recu_associe.statut == 'VALIDE':
            est_valide = True
        elif tranche.numero == 1 and (etudiant.recu_preinscription_valide or (inscription_obj and inscription_obj.recu_preinscription_valide)):
            est_valide = True
        elif tranche.numero == 2 and inscription_obj and inscription_obj.recu_tranche_1_valide:
            est_valide = True
        elif tranche.numero == 3 and inscription_obj and inscription_obj.recu_tranche_2_valide:
            est_valide = True
        elif tranche.numero == 4 and inscription_obj and inscription_obj.recu_tranche_3_valide:
            est_valide = True

        # Déterminer la date de référence pour le calcul de pénalité de CETTE tranche spécifique.
        # Si le reçu de paiement de cette tranche est validé, le calcul de ses pénalités est définitivement
        # gelé à la date de paiement/téléversement de son reçu.
        if est_valide:
            if recu_associe:
                date_reference = recu_associe.date_paiement or recu_associe.date_televersement.date()
            else:
                date_reference = date_aujourdhui
        else:
            date_reference = date_aujourdhui
            
        # Transposition du numéro de tranche vers le code PenalitePaiement
        tranche_code = {1: 'PREINSCRIPTION', 2: 'TRANCHE_1', 3: 'TRANCHE_2', 4: 'TRANCHE_3'}.get(tranche.numero, 'PREINSCRIPTION')
        from apps.tableau_bord.models import PenalitePaiement
        penalite_existante = PenalitePaiement.objects.filter(etudiant=etudiant, tranche=tranche_code).first()

        if date_reference > tranche.date_limite:
            jours_retard = (date_reference - tranche.date_limite).days
            
            if jours_retard > 0:
                semaines_retard = (jours_retard + 6) // 7
                tarif_penalite = Decimal('1500.00') if tranche.numero == 1 else Decimal('3000.00')
                montant_brut = Decimal(str(semaines_retard)) * tarif_penalite
                
                montant_deja_paye = Decimal(str(penalite_existante.montant_penalite)) if (penalite_existante and (penalite_existante.est_regle or Decimal(str(penalite_existante.montant_penalite)) > Decimal('0.00'))) else Decimal('0.00')

                if penalite_existante and penalite_existante.est_regle and montant_deja_paye >= montant_brut:
                    # Pénalité intégralement réglée
                    continue

                montant_restant = max(Decimal('0.00'), montant_brut - montant_deja_paye)
                
                # Une pénalité est éligible au paiement en ligne SEULEMENT si le reçu de la tranche a été validé
                eligible_paiement = est_valide and montant_restant > Decimal('0.00')
                
                penalites_totales += montant_restant
                if eligible_paiement:
                    penalites_eligibles_totales += montant_restant
                
                details_penalites.append({
                    'tranche_id': tranche.id,
                    'tranche_numero': tranche.numero,
                    'tranche': tranche.get_numero_display(),
                    'date_limite': tranche.date_limite,
                    'semaines_retard': semaines_retard,
                    'tarif': tarif_penalite,
                    'montant_brut': montant_brut,
                    'montant_paye': montant_deja_paye,
                    'montant': montant_restant,
                    'recu_soumis': recu_associe is not None,
                    'recu_statut': recu_associe.get_statut_display() if recu_associe else ("Validé" if est_valide else "Non téléversé"),
                    'recu_valide': est_valide,
                    'eligible_paiement': eligible_paiement,
                    'penalite_stoppee': est_valide,
                    'date_arret_calcul': date_reference if est_valide else None
                })


                
    return {
        'total': penalites_totales,              # Cumul global de toutes les pénalités de retard dues
        'total_eligibles': penalites_eligibles_totales,  # Total éligible au paiement MM immédiat
        'total_global': penalites_totales,
        'details': details_penalites
    }


