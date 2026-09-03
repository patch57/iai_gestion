from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Accès dynamique aux dictionnaires en template Django avec tolérance de types de clés."""
    if isinstance(dictionary, dict):
        if key in dictionary:
            return dictionary[key]
        str_k = str(key)
        if str_k in dictionary:
            return dictionary[str_k]
        try:
            int_k = int(key)
            if int_k in dictionary:
                return dictionary[int_k]
        except (ValueError, TypeError):
            pass
    return None
