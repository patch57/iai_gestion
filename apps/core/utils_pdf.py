"""
Module utilitaire centralisé pour le rendu et l'impression de documents PDF officiels.
IAI-Cameroun - Centre de Douala
"""
from django.template.loader import render_to_string
from django.http import HttpResponse


def rendre_document_imprimable(template_src, context_dict, filename="document.pdf"):
    """
    Rend un template HTML configuré avec un CSS d'impression optimisé (A4 portrait/paysage,
    en-tête officiel IAI, filigrane et mise en page haute résolution).
    """
    html_content = render_to_string(template_src, context_dict)
    response = HttpResponse(html_content, content_type='text/html; charset=utf-8')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
