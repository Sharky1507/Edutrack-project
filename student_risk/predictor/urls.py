from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('predict/', views.predict, name='predict'),
    path('generate-study-plan/', views.generate_study_plan, name='generate_study_plan'),
    path('chat/', views.chat, name='chat'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),  # Add this
    #path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'), 
    path('signup/', views.signup, name='signup'),  # Add this to your urlpatterns # Add this
    path('logout/', views.logout_view, name='logout'),  # Use the custom logout view
    path('subject-tutors/', views.subject_tutors, name='subject_tutors'),
    path('subject-chat/', views.subject_chat, name='subject_chat'),
    # Add these patterns to your urlpatterns list
    path('resources/', views.resource_library, name='resource_library'),
    path('resources/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    path('resources/save/<int:resource_id>/', views.save_resource, name='save_resource'),
    path('resources/rate/<int:resource_id>/', views.rate_resource, name='rate_resource'),
    path('resources/upload/', views.upload_resource, name='upload_resource'),
    path('my-resources/', views.my_resources, name='my_resources'),
    # ... existing patterns
    path('learning-progress/', views.learning_progress, name='learning_progress'),
    path('update-resource-progress/', views.update_resource_progress, name='update_resource_progress'),
    path('analytics-dashboard/', views.analytics_dashboard, name='analytics_dashboard'),
    path('set-weekly-goals/', views.set_weekly_goals, name='set_weekly_goals'),
]
