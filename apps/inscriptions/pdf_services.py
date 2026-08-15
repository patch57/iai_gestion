import io
import os
import hashlib
from django.conf import settings
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.barcode import qr


def generer_hash_document(prefixe, object_id, timestamp_str):
    raw = f"IAI-SECURE-{prefixe}-{object_id}-{timestamp_str}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16].upper()


def creer_qr_code(url_verification, width=70, height=70):
    qr_code = qr.QrCodeWidget(url_verification)
    bounds = qr_code.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    d = Drawing(width, height, transform=[width / w, 0, 0, height / h, 0, 0])
    d.add(qr_code)
    return d


def generer_carte_etudiant_pdf(etudiant, domain_url="http://localhost:8000"):
    buffer = io.BytesIO()
    card_width = 85.6 * mm
    card_height = 54 * mm
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=(card_width, card_height),
        leftMargin=2 * mm,
        rightMargin=2 * mm,
        topMargin=2 * mm,
        bottomMargin=2 * mm
    )
    
    date_str = etudiant.date_creation.strftime('%Y%m%d') if etudiant.date_creation else '20260101'
    hash_doc = generer_hash_document('CARD', etudiant.id, date_str)
    url_verif = f"{domain_url}/paiements/verifier-document/?hash={hash_doc}&type=carte&id={etudiant.id}"
    
    styles = getSampleStyleSheet()
    
    # Couleur du bandeau selon le niveau (Niveau 1: Vert, Niveau 2: Rouge)
    niveau_num = etudiant.niveau.numero if etudiant.niveau else 1
    if niveau_num == 1:
        banner_bg_color = colors.HexColor('#047857')  # Vert Émeraude
    else:
        banner_bg_color = colors.HexColor('#B91C1C')  # Rouge Cramoisi
        
    title_white_style = ParagraphStyle(
        'CardTitleWhite',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6,
        leading=7,
        textColor=colors.white,
        alignment=0
    )
    sub_title_white_style = ParagraphStyle(
        'CardSubTitleWhite',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=4.5,
        leading=5.5,
        textColor=colors.HexColor('#F3F4F6'),
        alignment=0
    )
    text_style = ParagraphStyle(
        'CardText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=5,
        leading=6,
        textColor=colors.HexColor('#1F2937')
    )
    bold_text_style = ParagraphStyle(
        'CardBoldText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=5,
        leading=6,
        textColor=colors.HexColor('#111827')
    )

    # Logo IAI dans le bandeau
    import os
    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_iai.png')
    logo_header = Image(logo_path, width=8.5 * mm, height=8.5 * mm) if os.path.exists(logo_path) else Paragraph("", text_style)

    header_text_p = Paragraph("<b>IAI-CAMEROUN — CENTRE DE DOUALA</b>", title_white_style)
    header_sub_p = Paragraph(f"CARTE D'ÉTUDIANT OFFICIELLE — NIVEAU {niveau_num}", sub_title_white_style)
    header_box = [header_text_p, header_sub_p]

    banner_table = Table([[logo_header, header_box]], colWidths=[10 * mm, 71.6 * mm])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), banner_bg_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
    ]))

    qr_draw = creer_qr_code(url_verif, width=30, height=30)

    elements = [banner_table, Spacer(1, 1.5 * mm)]

    photo_element = None
    if etudiant.photo:
        try:
            photo_element = Image(etudiant.photo.path, width=18 * mm, height=22 * mm)
        except Exception:
            photo_element = None
            
    if not photo_element:
        d_photo = Drawing(18 * mm, 22 * mm)
        d_photo.add(Rect(0, 0, 18 * mm, 22 * mm, fillColor=colors.HexColor('#F3F4F6'), strokeColor=colors.HexColor('#D1D5DB')))
        d_photo.add(String(3 * mm, 9 * mm, "PHOTO", fontName="Helvetica", fontSize=5.5, fillColor=colors.HexColor('#9CA3AF')))
        photo_element = d_photo

    nom_prenom = f"<b>{etudiant.nom.upper()}</b> {etudiant.prenom}"
    filiere_str = etudiant.filiere.nom if etudiant.filiere else "N/A"
    annee_str = etudiant.annee_academique.code if etudiant.annee_academique else "2024-2025"

    info_data = [
        [Paragraph("Matricule:", bold_text_style), Paragraph(etudiant.matricule or "En cours", bold_text_style)],
        [Paragraph("Nom/Prénom:", text_style), Paragraph(nom_prenom[:28], text_style)],
        [Paragraph("Filière:", text_style), Paragraph(filiere_str, text_style)],
        [Paragraph("Année Acad.:", text_style), Paragraph(annee_str, text_style)],
    ]
    info_table = Table(info_data, colWidths=[14 * mm, 33 * mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 0.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.5),
    ]))

    card_data = [
        [photo_element, info_table, qr_draw]
    ]
    card_table = Table(card_data, colWidths=[19 * mm, 47 * mm, 14 * mm])
    card_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (2,0), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    
    elements.append(card_table)
    elements.append(Spacer(1, 1 * mm))

    footer_p = Paragraph(f"Hash Sécurisé: {hash_doc} | Vérification QR Code", ParagraphStyle('Foot', parent=styles['Normal'], fontName='Helvetica', fontSize=4, leading=5, textColor=colors.HexColor('#6B7280'), alignment=1))
    elements.append(footer_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()



def generer_recu_paiement_pdf(recu, domain_url="http://localhost:8000"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    date_str = recu.date_televersement.strftime('%Y%m%d%H%M') if recu.date_televersement else '20260101'
    hash_doc = generer_hash_document('RECU', recu.id, date_str)
    url_verif = f"{domain_url}/paiements/verifier-document/?hash={hash_doc}&type=recu&id={recu.id}"

    styles = getSampleStyleSheet()
    h_left_style = ParagraphStyle('HLeft', fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#1E293B'), alignment=0)
    h_right_style = ParagraphStyle('HRight', fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#1E293B'), alignment=2)
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading2'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=11,
        textColor=colors.HexColor('#4B5563'),
        alignment=1
    )
    label_style = ParagraphStyle('Label', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#374151'))
    val_style = ParagraphStyle('Val', fontName='Helvetica', fontSize=9, leading=11, textColor=colors.HexColor('#111827'))

    elements = []

    # En-tête Officiel IAI avec Logo (Centré)
    import os
    from django.conf import settings
    from django.utils import timezone
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_iai.png')
    
    h_center_bold = ParagraphStyle('HCenterBold', fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, textColor=colors.HexColor('#1E293B'), alignment=1)
    h_center_sub = ParagraphStyle('HCenterSub', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#475569'), alignment=1)
    h_center_title = ParagraphStyle('HCenterTitle', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#065F46'), alignment=1)
    h_center_contacts = ParagraphStyle('HCenterContacts', fontName='Helvetica', fontSize=7, leading=9, textColor=colors.HexColor('#334155'), alignment=1)

    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=20 * mm, height=20 * mm)
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 2 * mm))

    elements.append(Paragraph("<b>ETABLISSEMENT INTER – ETATS D'ENSEIGNEMENT SUPÉRIEUR</b>", h_center_bold))
    elements.append(Paragraph("Représentation du Cameroun", h_center_sub))
    elements.append(Paragraph("<b>CENTRE D'EXCELLENCE TECHNOLOGIQUE PAUL BIYA</b>", h_center_title))
    elements.append(Paragraph("BP 13 719 Yaoundé (Cameroun) Tél. (237) 242 72 99 57/ 242 72 99 58/ 691 902 120", h_center_contacts))
    elements.append(Paragraph("Site web: www.iaicameroun.com &bull; Courriel: contact@iaicameroun.com", h_center_contacts))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("REÇU DE PAIEMENT CERTIFIÉ ET VALIDÉ", h1_style))
    elements.append(Spacer(1, 4 * mm))


    qr_draw = creer_qr_code(url_verif, width=80, height=80)

    etudiant = recu.etudiant
    tranche_str = f"Tranche {recu.tranche.numero} - {recu.tranche.get_numero_display()}" if recu.tranche else "Paiement Général"

    tableau_info = [
        [Paragraph("Référence Reçu :", label_style), Paragraph(recu.reference_recu or f"REC-{recu.id:06d}", val_style), qr_draw],
        [Paragraph("Étudiant :", label_style), Paragraph(f"{etudiant.get_nom_complet()} ({etudiant.matricule})", val_style), ""],
        [Paragraph("Filière & Niveau :", label_style), Paragraph(f"{etudiant.filiere.code if etudiant.filiere else 'N/A'} - Niveau {etudiant.niveau.numero if etudiant.niveau else 'N/A'}", val_style), ""],
        [Paragraph("Tranche Concernée :", label_style), Paragraph(tranche_str, val_style), ""],
        [Paragraph("Montant Validé :", label_style), Paragraph(f"<b>{recu.montant_mentionne:,.0f} FCFA</b>", val_style), ""],
        [Paragraph("Date de Paiement :", label_style), Paragraph(str(recu.date_paiement or (recu.date_televersement.date() if recu.date_televersement else 'N/A')), val_style), ""],
        [Paragraph("Statut sur la Plateforme :", label_style), Paragraph(f"<font color='#059669'><b>{recu.get_statut_display().upper()}</b></font>", val_style), ""],
        [Paragraph("Empreinte Sécurité (Hash) :", label_style), Paragraph(f"<code>{hash_doc}</code>", val_style), ""],
    ]

    t = Table(tableau_info, colWidths=[45 * mm, 85 * mm, 45 * mm])
    t.setStyle(TableStyle([
        ('SPAN', (2,0), (2,6)),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))

    elements.append(t)
    elements.append(Spacer(1, 10 * mm))

    note_p = Paragraph(
        "<i>Ce reçu est généré numériquement par le système IAI-Gestion. Le QR Code ci-dessus permet à tout tiers d'authentifier la validité de ce document en direct sur les serveurs de l'IAI-Cameroun.</i>",
        ParagraphStyle('Note', fontName='Helvetica-Oblique', fontSize=8, leading=10, textColor=colors.HexColor('#6B7280'), alignment=1)
    )
    elements.append(note_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generer_fiche_renseignement_pdf(etudiant, fiche=None, domain_url="http://localhost:8000"):
    """
    Génère la Fiche de Renseignement officielle IAI-Cameroun au format PDF.
    Design exécutif, élégant, haute qualité avec QR Code et mise en page moderne.
    """
    buffer = io.BytesIO()
    
    # Configuration des marges et du document A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    styles = getSampleStyleSheet()
    
    # Palette de couleurs officielles IAI
    COLOR_PRIMARY = colors.HexColor('#047857')     # Emerald Green
    COLOR_SECONDARY = colors.HexColor('#064E3B')   # Dark Forest
    COLOR_ACCENT = colors.HexColor('#D97706')      # Amber / Gold
    COLOR_TEXT_MAIN = colors.HexColor('#0F172A')   # Slate 900
    COLOR_TEXT_MUTED = colors.HexColor('#475569')  # Slate 600
    COLOR_BG_ALT = colors.HexColor('#F8FAFC')      # Slate 50
    COLOR_BORDER = colors.HexColor('#E2E8F0')      # Slate 200

    # Styles typographiques personnalisés
    title_main = ParagraphStyle(
        'FicheTitleMain', 
        fontName='Helvetica-Bold', 
        fontSize=15, 
        leading=18, 
        alignment=1, 
        textColor=COLOR_PRIMARY
    )
    
    h_small_bold = ParagraphStyle(
        'HSmallBold', 
        fontName='Helvetica-Bold', 
        fontSize=8.5, 
        leading=11, 
        alignment=1, 
        textColor=COLOR_SECONDARY
    )
    
    h_small_sub = ParagraphStyle(
        'HSmallSub', 
        fontName='Helvetica', 
        fontSize=7.5, 
        leading=9.5, 
        alignment=1, 
        textColor=COLOR_TEXT_MUTED
    )
    
    label_style = ParagraphStyle(
        'FicheLabel', 
        fontName='Helvetica-Bold', 
        fontSize=8.5, 
        leading=11.5, 
        textColor=COLOR_PRIMARY
    )
    
    val_style = ParagraphStyle(
        'FicheVal', 
        fontName='Helvetica', 
        fontSize=8.5, 
        leading=11.5, 
        textColor=COLOR_TEXT_MAIN
    )
    
    val_bold = ParagraphStyle(
        'FicheValBold', 
        fontName='Helvetica-Bold', 
        fontSize=8.5, 
        leading=11.5, 
        textColor=COLOR_TEXT_MAIN
    )
    
    nb_style = ParagraphStyle(
        'FicheNB', 
        fontName='Helvetica-Oblique', 
        fontSize=7.5, 
        leading=10, 
        textColor=colors.HexColor('#92400E')
    )

    elements = []

    # 1. En-tête Institutionnel + Photo d'Identité
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo_iai.png')
    logo_header = Image(logo_path, width=18 * mm, height=18 * mm) if os.path.exists(logo_path) else Paragraph("", label_style)

    header_text_data = [
        [logo_header],
        [Paragraph("<b>INSTITUT AFRICAIN D'INFORMATIQUE</b>", h_small_bold)],
        [Paragraph("Établissement Inter – États d'Enseignement Supérieur", h_small_sub)],
        [Paragraph("Représentation du Cameroun", h_small_sub)],
        [Paragraph("<b>CENTRE D'EXCELLENCE TECHNOLOGIQUE PAUL BIYA</b>", h_small_bold)],
        [Paragraph("BP 13719 Yaoundé (Cameroun) Tél. 22 72 99 58 / 22 72 99 57", h_small_sub)],
        [Paragraph("Site web: www.iaicameroun.com — E-mail: iaicameroun@yahoo.fr", h_small_sub)],
    ]
    header_table = Table(header_text_data, colWidths=[120 * mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 0.5),
    ]))

    # Photo de l'étudiant
    photo_element = None
    if etudiant.photo and hasattr(etudiant.photo, 'path') and os.path.exists(etudiant.photo.path):
        try:
            photo_element = Image(etudiant.photo.path, width=32 * mm, height=40 * mm)
        except Exception:
            photo_element = Paragraph("<font color='#94A3B8'>[PHOTO]</font>", label_style)
    else:
        photo_element = Paragraph("<br/><br/><b>PHOTO</b><br/>d'Identité", ParagraphStyle('PBox', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=1, textColor=colors.HexColor('#94A3B8')))

    photo_box_table = Table([[photo_element]], colWidths=[34 * mm], rowHeights=[41 * mm])
    photo_box_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, COLOR_PRIMARY),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    top_row_table = Table([[header_table, photo_box_table]], colWidths=[140 * mm, 46 * mm])
    top_row_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))

    elements.append(top_row_table)
    elements.append(Spacer(1, 3 * mm))

    # 2. Titre Officiel du Document avec Ligne Dorée
    annee_code = etudiant.annee_academique.code if etudiant.annee_academique else "2025-2026"
    title_table = Table([
        [Paragraph(f"<b>FICHE DE RENSEIGNEMENT {annee_code}</b>", title_main)]
    ], colWidths=[186 * mm])
    title_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ECFDF5')),
        ('BOX', (0,0), (-1,-1), 1, COLOR_PRIMARY),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(title_table)
    elements.append(Spacer(1, 4 * mm))

    # 3. Grille des 16 Données Renseignées
    def make_row(label, value_content, bg=colors.white):
        return [
            Paragraph(f"<b>{label}</b>", label_style),
            value_content
        ]

    nom_val = Paragraph(f"<b>{(etudiant.nom or '').upper()}</b>", val_bold)
    prenom_val = Paragraph(etudiant.prenom or "...", val_style)
    
    date_lieu_str = f"{etudiant.date_naissance.strftime('%d/%m/%Y') if etudiant.date_naissance else '...'} à {etudiant.lieu_naissance or '...'}"
    pays_str = etudiant.pays_naissance or 'Cameroun'
    date_lieu_val = Paragraph(f"{date_lieu_str} &nbsp;&nbsp;&nbsp;&nbsp;<b>Pays :</b> {pays_str}", val_style)
    
    matrimoniale_val = Paragraph(etudiant.situation_matrimoniale or "Célibataire", val_style)
    nationalite_val = Paragraph(etudiant.get_nationalite_display() if hasattr(etudiant, 'get_nationalite_display') else (etudiant.nationalite or "Camerounaise"), val_style)
    region_val = Paragraph(etudiant.region_origine or "...", val_style)
    
    adresse_tel_val = Paragraph(f"{etudiant.adresse or '...'} &nbsp;&nbsp;&nbsp;&nbsp;<b>Votre N° Téléphone :</b> {etudiant.telephone or '...'}", val_style)
    residence_val = Paragraph(etudiant.lieu_residence or (etudiant.adresse or "..."), val_style)
    email_val = Paragraph(f"<font color='#0369A1'><b>{etudiant.email or '...'}</b></font>", val_style)
    
    contact_nom_val = Paragraph(f"<b>{etudiant.personne_contact_nom_prenom or etudiant.nom_tuteur or '...'}</b>", val_style)
    contact_tel_res_val = Paragraph(f"{etudiant.personne_contact_telephone or etudiant.telephone_tuteur or '...'} &nbsp;&nbsp;&nbsp;&nbsp;<b>Lieu de Résidence :</b> {etudiant.personne_contact_residence or '...'}", val_style)
    
    filiere_code = etudiant.filiere.code if etudiant.filiere else ''
    filiere_nom = etudiant.filiere.nom if etudiant.filiere else '...'
    filiere_val = Paragraph(f"<b>{filiere_nom} ({filiere_code})</b> &nbsp;&nbsp;&nbsp;&nbsp;<b>BACC :</b> {etudiant.serie_bacc or '...'}", val_style)
    
    niveau_num = etudiant.niveau.numero if etudiant.niveau else '1'
    date_rentree_str = etudiant.date_premiere_rentree.strftime('%d/%m/%Y') if etudiant.date_premiere_rentree else '...'
    niveau_val = Paragraph(f"<b>Niveau {niveau_num}</b> &nbsp;&nbsp;&nbsp;&nbsp;<b>Date de première rentrée :</b> {date_rentree_str}", val_style)
    
    statut_val = Paragraph(etudiant.statut_etudiant_fiche or "Nouvelle admission", val_style)
    date_concours_val = Paragraph(etudiant.date_concours.strftime('%d/%m/%Y') if etudiant.date_concours else "...", val_style)
    matricule_val = Paragraph(f"<font color='#047857'><b>{etudiant.matricule or '...'}</b></font>", val_bold)

    grid_data = [
        make_row("Noms (MAJUSCULE)", nom_val),
        make_row("Prénoms", prenom_val),
        make_row("Date et lieu de naissance", date_lieu_val),
        make_row("Situation matrimoniale", matrimoniale_val),
        make_row("Nationalité", nationalite_val),
        make_row("Région d'origine", region_val),
        make_row("Adresse permanente", adresse_tel_val),
        make_row("Lieu de Résidence", residence_val),
        make_row("Email", email_val),
        make_row("Personnes à contacter Obligatoire (NOM et Prénom)", contact_nom_val),
        make_row("Téléphone / Lieu de Résidence", contact_tel_res_val),
        make_row("Filière & BACC", filiere_val),
        make_row("Niveau & Première rentrée", niveau_val),
        make_row("Statut étudiant", statut_val),
        make_row("Date du concours", date_concours_val),
        make_row("Matricule IAI", matricule_val),
    ]

    form_table = Table(grid_data, colWidths=[66 * mm, 120 * mm])
    form_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, COLOR_BG_ALT]),
        ('PADDING', (0,0), (-1,-1), 2.8),
    ]))

    elements.append(form_table)
    elements.append(Spacer(1, 6 * mm))

    # 4. Zone de signatures & Tampons (sans QR Code)
    sig_header_style = ParagraphStyle('SigH', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=1, textColor=COLOR_PRIMARY)
    sig_sub_style = ParagraphStyle('SigS', fontName='Helvetica-Oblique', fontSize=7, leading=9, alignment=1, textColor=COLOR_TEXT_MUTED)

    sig_data = [
        [
            Paragraph("<b>L'Étudiant(e)</b>", sig_header_style), 
            Paragraph("<b>Scolarité</b>", sig_header_style), 
            Paragraph("<b>Le Représentant Résident</b>", sig_header_style)
        ],
        [
            Paragraph("<br/><br/><i>Lu et approuvé</i>", sig_sub_style), 
            Paragraph("<br/><b>CACHET & SIGNATURE</b>", sig_sub_style), 
            Paragraph("<br/><br/><i>Visé de la Direction</i>", sig_sub_style)
        ],
    ]
    sig_table = Table(sig_data, colWidths=[62 * mm, 62 * mm, 62 * mm], rowHeights=[7 * mm, 23 * mm])
    sig_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, COLOR_PRIMARY),
        ('INNERGRID', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_ALT),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))

    elements.append(sig_table)

    # Canvas Callback pour Ajouter les bandes décoratives haut/bas
    def add_decorations(canvas, doc):
        canvas.saveState()
        # Bande supérieure verte
        canvas.setFillColor(COLOR_PRIMARY)
        canvas.rect(0, 290 * mm, 210 * mm, 7 * mm, fill=True, stroke=False)
        # Ligne fine dorée
        canvas.setFillColor(COLOR_ACCENT)
        canvas.rect(0, 289 * mm, 210 * mm, 1 * mm, fill=True, stroke=False)
        
        # Bas de page
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(COLOR_TEXT_MUTED)
        canvas.drawString(12 * mm, 5 * mm, "IAI-Cameroun — Système Officiel de Gestion Établissement (IAI-Gestion)")
        canvas.drawRightString(198 * mm, 5 * mm, f"Matricule : {etudiant.matricule or etudiant.id} | Page 1/1")
        canvas.restoreState()

    doc.build(elements, onFirstPage=add_decorations)
    buffer.seek(0)
    return buffer.getvalue()

