from datetime import date
from django.utils import timezone
from .models import TranchePaiement, RecuPaiement

def calculer_penalites_etudiant(etudiant):
    """
    Calcule les pénalités de retard accumulées par un étudiant.
    Règles :
    - Pré-inscription (Tranche 1) : 1500 FCFA par semaine de retard
    - Tranche 1, 2, 3 (Tranches 2, 3, 4) : 3000 FCFA par semaine de retard
    """
    penalites_totales = 0
    details_penalites = []
    
    # Récupérer l'année académique active
    annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"
    
    # Récupérer les tranches pour cette année
    tranches = TranchePaiement.objects.filter(annee_academique=annee_code, est_actif=True)
    
    date_aujourdhui = date.today()
    
    for tranche in tranches:
        # Vérifier si payé et validé
        deja_paye = False
        
        # Pour la pré-inscription (tranche 1), on vérifie aussi le champ sur le modèle étudiant
        if tranche.numero == 1:
            deja_paye = etudiant.recu_preinscription_valide
            
        if not deja_paye:
            deja_paye = RecuPaiement.objects.filter(
                etudiant=etudiant,
                tranche=tranche,
                statut='VALIDE'
            ).exists()
            
        if not deja_paye:
            # Si non payé et la date limite est dépassée
            if date_aujourdhui > tranche.date_limite:
                jours_retard = (date_aujourdhui - tranche.date_limite).days
                semaines_retard = jours_retard // 7
                
                if semaines_retard > 0:
                    tarif_penalite = 1500 if tranche.numero == 1 else 3000
                    montant_penalite = semaines_retard * tariff_penalite if 'tariff_penalite' in locals() else semaines_retard * tarif_penalite
                    penalites_totales += montant_penalite
                    
                    details_penalites.append({
                        'tranche': tranche.get_numero_display(),
                        'date_limite': tranche.date_limite,
                        'semaines_retard': semaines_retard,
                        'tarif': tarif_penalite,
                        'montant': montant_penalite
                    })
                    
    return {
        'total': penalites_totales,
        'details': details_penalites
    }
