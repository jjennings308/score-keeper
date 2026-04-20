from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Allow dictionary lookup by variable key in templates.
    Usage: {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
