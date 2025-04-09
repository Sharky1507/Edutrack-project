# Create a middleware to auto-create profiles
from predictor.models import UserProfile
class AutoCreateProfileMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and not hasattr(request.user, 'userprofile'):
            UserProfile.objects.create(user=request.user)
        return self.get_response(request)