from django.db import models
from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class StudentAssessment(models.Model):
    RISK_CHOICES = [('At Risk', 'At Risk'), ('Not At Risk', 'Not At Risk')]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    risk_status = models.CharField(max_length=20, choices=RISK_CHOICES)
    age = models.PositiveSmallIntegerField()
    study_time = models.FloatField()
    absences = models.PositiveIntegerField()
    recommendations = models.JSONField()
    data = models.JSONField()  # Stores all input data
    study_plan = models.TextField(blank=True)
    learning_style = models.CharField(max_length=100, null=True, blank=True)
    wakeup_time = models.TimeField(null=True, blank=True)
    bedtime = models.TimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.timestamp} - {self.risk_status}"

    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    learning_style = models.CharField(max_length=20, choices=[
        ('visual', 'Visual'), 
        ('auditory', 'Auditory'), 
        ('kinesthetic', 'Hands-on')
    ], default='visual')
    academic_goals = models.TextField(blank=True)
    wakeup_time = models.TimeField(default='07:00')
    bedtime = models.TimeField(default='22:00')
    strengths = models.CharField(max_length=100, blank=True)
    weaknesses = models.CharField(max_length=100, blank=True)

class Subject(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class")
    
    def __str__(self):
        return self.name
class ChatInteraction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    message = models.TextField()
    response = models.TextField(blank=True, null=True)  # Make this optional
    assessment = models.ForeignKey(StudentAssessment, on_delete=models.CASCADE, null=True, blank=True)
    is_user = models.BooleanField(default=True)  # Add the field from the second definition
    subject = models.ForeignKey(Subject, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'}: {self.message[:50]}"
    
# models.py
class ResourceCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, help_text="Font Awesome icon class", default="fas fa-book")
    
    def __str__(self):
        return self.name
        
    class Meta:
        verbose_name_plural = "Resource categories"

class Resource(models.Model):
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ]
    
    TYPE_CHOICES = [
        ('video', 'Video'),
        ('article', 'Article'),
        ('book', 'Book'),
        ('exercise', 'Interactive Exercise'),
        ('quiz', 'Quiz'),
        ('tool', 'Tool'),
        ('other', 'Other')
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    url = models.URLField()
    thumbnail = models.URLField(blank=True, help_text="URL to thumbnail image")
    category = models.ForeignKey(ResourceCategory, on_delete=models.CASCADE, related_name='resources')
    subjects = models.ManyToManyField(Subject, related_name='resources')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate')
    resource_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='article')
    learning_styles = models.JSONField(default=list, help_text="List of learning styles this resource is good for")
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_resources')
    is_approved = models.BooleanField(default=False, help_text="Admin approval status")
    keywords = models.JSONField(default=list, help_text="List of keywords related to this resource")
    
    def __str__(self):
        return self.title
        
    class Meta:
        ordering = ['-upload_date']

class UserResourceInteraction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    saved = models.BooleanField(default=False)
    viewed = models.BooleanField(default=False)
    rated = models.IntegerField(null=True, blank=True, choices=[(i, i) for i in range(1, 6)])
    view_count = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'resource')
class ResourceProgress(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resource_progress')
    resource = models.ForeignKey('Resource', on_delete=models.CASCADE, related_name='progress_entries')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    progress_percent = models.IntegerField(default=0)  # For tracking partial completion
    time_spent = models.IntegerField(default=0)  # Time spent in seconds
    last_accessed = models.DateTimeField(auto_now=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('user', 'resource')
    
    def __str__(self):
        return f"{self.user.username}'s progress on {self.resource.title}"

class LearningSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learning_sessions')
    resource = models.ForeignKey('Resource', on_delete=models.CASCADE, related_name='learning_sessions')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0)  # Duration in seconds
    completed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s session on {self.resource.title} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"
    
class UserLearningMetrics(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='learning_metrics')
    resources_viewed = models.IntegerField(default=0)
    resources_completed = models.IntegerField(default=0)
    total_time_spent = models.IntegerField(default=0)  # In seconds
    average_completion_rate = models.FloatField(default=0)
    favorite_categories = models.JSONField(default=dict)  # Store category_id: count
    learning_streak = models.IntegerField(default=0)  # Days in a row with activity
    last_active_date = models.DateField(null=True, blank=True)
    study_time_distribution = models.JSONField(default=dict)  # Store hour: minutes
    weekly_goals = models.JSONField(default=dict)  # Store goal data
    weekly_goals_met = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Learning metrics for {self.user.username}"
    
    def update_favorite_categories(self):
        """Update favorite categories based on user's interactions"""
        from django.db.models import Count
        
        category_counts = UserResourceInteraction.objects.filter(
            user=self.user, 
            viewed=True
        ).values('resource__category').annotate(
            count=Count('resource__category')
        ).order_by('-count')
        
        categories = {}
        for item in category_counts:
            cat_id = item['resource__category']
            if cat_id:  # Ensure it's not None
                categories[str(cat_id)] = item['count']
        
        self.favorite_categories = categories
        self.save()
    
    def update_study_time_distribution(self):
        """Update study time distribution based on session data"""
        from django.db.models import Sum
        from django.db.models.functions import ExtractHour
        
        # Get total minutes spent by hour of day
        hour_data = LearningSession.objects.filter(
            user=self.user,
            completed=True
        ).annotate(
            hour=ExtractHour('start_time')
        ).values('hour').annotate(
            total_minutes=Sum('duration')
        ).order_by('hour')
        
        time_dist = {}
        for item in hour_data:
            hour = str(item['hour'])
            minutes = item['total_minutes'] // 60  # Convert seconds to minutes
            time_dist[hour] = minutes
        
        self.study_time_distribution = time_dist
        self.save()
    
    def update_streak(self):
        """Update the user's learning streak"""
        import datetime
        
        today = datetime.date.today()
        
        if not self.last_active_date:
            self.last_active_date = today
            self.learning_streak = 1
            self.save()
            return
        
        # If active today, nothing to update
        if self.last_active_date == today:
            return
            
        # If active yesterday, increase streak
        if (today - self.last_active_date).days == 1:
            self.learning_streak += 1
        # If more than 1 day has passed, reset streak
        elif (today - self.last_active_date).days > 1:
            self.learning_streak = 1
            
        self.last_active_date = today
        self.save()