from django import template
register=template.Library()
@register.filter
def model_name(obj):
    try:
        return obj._meta.model_name
    except AttributeError:
        return None

@register.filter
def index(List, i):
    try:
        idx = int(i)
        return List[idx]
    except (IndexError, ValueError,TypeError):
        return None


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def div(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0
