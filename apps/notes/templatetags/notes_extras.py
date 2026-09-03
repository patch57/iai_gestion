from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Accès dynamique aux dictionnaires en template Django."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}
