from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string using the specified separator."""
    if value is None:
        return []
    return value.split(arg)
from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """Split a string using the specified separator."""
    if value is None:
        return []
    return value.split(arg)

@register.filter
def youtube_embed_url(url):
    """Convert YouTube URL to embed URL"""
    if 'youtube.com/watch' in url:
        video_id = url.split('v=')[1].split('&')[0]
        return f"https://www.youtube.com/embed/{video_id}"
    elif 'youtu.be' in url:
        video_id = url.split('/')[-1]
        return f"https://www.youtube.com/embed/{video_id}"
    return url