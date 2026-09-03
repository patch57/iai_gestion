"""
Service iCalendar (.ics) pour l'exportation des emplois du temps IAI-Gestion.
Norme RFC 5545.
"""
from datetime import datetime, time, timedelta


def _parse_time_range(plage_code):
    """Mappe les plages IAI-Gestion vers des heures de début et de fin."""
    plages_map = {
        'P1': (time(7, 30), time(9, 30)),
        'P2': (time(9, 30), time(11, 30)),
        'PAUSE': (time(11, 30), time(12, 45)),
        'P3': (time(12, 45), time(14, 45)),
        'P4': (time(14, 45), time(16, 45)),
    }
    return plages_map.get(plage_code, (time(8, 0), time(10, 0)))


def _jour_offset(jour_code):
    """Retourne l'offset en jours par rapport au lundi (LUNDI=0)."""
    jours_offset = {
        'LUNDI': 0,
        'MARDI': 1,
        'MERCREDI': 2,
        'JEUDI': 3,
        'VENDREDI': 4,
        'SAMEDI': 5,
    }
    return jours_offset.get(jour_code.upper(), 0)


def generer_ics_emploi_du_temps(emploi, domain_url="http://localhost:8000"):
    """
    Génère un fichier iCalendar (.ics) respectant la norme RFC 5545.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//IAI-Cameroun Centre de Douala//IAI-Gestion iCal Generator//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:Emploi du Temps - {emploi.filiere.code} ({emploi.get_niveau_display()})",
        "X-WR-TIMEZONE:Africa/Douala",
    ]

    date_ref = emploi.date_debut_semaine

    for creneau in emploi.creneaux.all():
        if creneau.plage == 'PAUSE' or not creneau.intitule:
            continue

        h_debut, h_fin = _parse_time_range(creneau.plage)
        offset = _jour_offset(creneau.jour)
        date_evenement = date_ref + timedelta(days=offset)

        dtstart = datetime.combine(date_evenement, h_debut).strftime("%Y%m%dT%H%M%S")
        dtend = datetime.combine(date_evenement, h_fin).strftime("%Y%m%dT%H%M%S")
        dtstamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")

        summary = f"[{emploi.filiere.code}] {creneau.intitule}"
        description = []
        if creneau.enseignant_nom:
            description.append(f"Enseignant: {creneau.enseignant_nom}")
        if creneau.progression_heures:
            description.append(f"Progression: {creneau.progression_heures}")
        description.append(f"Filière: {emploi.filiere.nom}")
        description_str = " | ".join(description)

        location = creneau.salle_nom or (emploi.salle.code if emploi.salle else "Campus IAI Douala")

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:iai-creneau-{creneau.id}-{dtstart}@iaicameroun.com",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART;TZID=Africa/Douala:{dtstart}",
            f"DTEND;TZID=Africa/Douala:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description_str}",
            f"LOCATION:{location}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode('utf-8')
