from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date
import re

class Command(BaseCommand):
    help = "Clôture l'année académique active et transitionne vers la nouvelle année (Octobre à Octobre)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Début du processus de transition annuelle..."))
        
        try:
            with transaction.atomic():
                # 1. Récupérer l'année active
                from apps.etudiants.models import AnneeAcademique as AA_etud
                from apps.inscriptions.models import AnneeAcademique as AA_insc
                
                active_etud = AA_etud.get_active() or AA_etud.objects.filter(est_active=True).first()
                active_insc = AA_insc.get_active() or AA_insc.objects.filter(est_actuelle=True).first()
                
                if not active_etud:
                    self.stdout.write(self.style.ERROR("Aucune année académique active trouvée dans le module Étudiants."))
                    return
                
                # Calculer les dates et codes de la nouvelle année académique
                # Format code attendu: YYYY-YYYY (ex: 2025-2026)
                code_courant = active_etud.code
                match = re.match(r'^(\d{4})-(\d{4})$', code_courant)
                if not match:
                    self.stdout.write(self.style.ERROR(f"Format de code d'année académique invalide : {code_courant}"))
                    return
                
                annee_debut_courante = int(match.group(1))
                annee_fin_courante = int(match.group(2))
                
                nouvel_annee_debut = annee_fin_courante
                nouvel_annee_fin = annee_fin_courante + 1
                nouveau_code = f"{nouvel_annee_debut}-{nouvel_annee_fin}"
                
                self.stdout.write(self.style.SUCCESS(f"Année en cours : {code_courant}"))
                self.stdout.write(self.style.SUCCESS(f"Nouvelle année identifiée : {nouveau_code}"))
                
                # Dates : Octobre à Octobre
                date_debut_nouveau = date(nouvel_annee_debut, 10, 1)
                date_fin_nouveau = date(nouvel_annee_fin, 9, 30)
                
                # 2. Désactiver l'ancienne année
                AA_etud.objects.filter(est_active=True).update(est_active=False)
                AA_insc.objects.filter(est_actuelle=True).update(est_actuelle=False)
                
                # 3. Créer ou activer la nouvelle année
                nouveau_etud, created_etud = AA_etud.objects.get_or_create(
                    code=nouveau_code,
                    defaults={
                        'date_debut': date_debut_nouveau,
                        'date_fin': date_fin_nouveau,
                        'est_active': True
                    }
                )
                if not created_etud:
                    nouveau_etud.est_active = True
                    nouveau_etud.save()
                    
                nouveau_insc, created_insc = AA_insc.objects.get_or_create(
                    code=nouveau_code,
                    defaults={
                        'date_debut': date_debut_nouveau,
                        'date_fin': date_fin_nouveau,
                        'est_actuelle': True,
                        'est_ouverte_inscription': True
                    }
                )
                if not created_insc:
                    nouveau_insc.est_actuelle = True
                    nouveau_insc.est_ouverte_inscription = True
                    nouveau_insc.save()
                    
                # 4. Archiver les étudiants de l'année précédente
                from apps.etudiants.models import Etudiant, Classe
                
                # Les étudiants de Niveau 2 (GL2, SR2, etc.) qui étaient INSCRIT ou ACTIF passent à DIPLOME
                diplomes_count = Etudiant.objects.filter(
                    annee_academique=active_etud,
                    niveau__numero=2,
                    statut__in=['INSCRIT', 'ACTIF']
                ).update(statut='DIPLOME')
                
                # Désactiver les classes (salles académiques) de l'année précédente
                classes_archivees_count = Classe.objects.filter(
                    annee_academique=active_etud,
                    est_active=True
                ).update(est_active=False)
                
                # Bilan
                self.stdout.write(self.style.SUCCESS("✓ Anciennes années académiques désactivées."))
                self.stdout.write(self.style.SUCCESS(f"✓ Nouvelle année {nouveau_code} créée et activée (Octobre {nouvel_annee_debut} - Septembre {nouvel_annee_fin})."))
                self.stdout.write(self.style.SUCCESS(f"✓ {diplomes_count} étudiant(s) de niveau 2 diplômé(s) et archivé(s)."))
                self.stdout.write(self.style.SUCCESS(f"✓ {classes_archivees_count} classe(s) de l'année précédente archivée(s)."))
                self.stdout.write(self.style.SUCCESS("🎉 Transition de l'année universitaire effectuée avec succès !"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur durant la transition : {str(e)}"))
