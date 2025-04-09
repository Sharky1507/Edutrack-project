from django.shortcuts import render
from django.http import JsonResponse
import joblib
import pandas as pd
import google.generativeai as genai
import os
import re
from django.contrib.auth.decorators import login_required, user_passes_test  # Add user_passes_test here
from .models import StudentAssessment, ChatInteraction, ResourceCategory, Resource, UserResourceInteraction,Subject,ResourceProgress, LearningSession, UserLearningMetrics  # Also add new models
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q  # Add Q for complex queries
from django.contrib.auth import views as auth_views
from django.shortcuts import render, redirect, get_object_or_404  # Update this importfrom django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login
import json
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Avg, Case, When, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDate, ExtractWeekDay
from datetime import datetime, timedelta

class CustomLoginView(auth_views.LoginView):
    template_name = 'login.html'
    
    def form_valid(self, form):
        remember_me = form.cleaned_data.get('remember_me')
        if not remember_me:
            # Session expires when user closes browser
            self.request.session.set_expiry(0)
        return super().form_valid(form)

# Configure Gemini API
genai.configure(api_key="AIzaSyCvhHTnUry-WUB6C3gTBZpJSHcP5qN7P04")
chat_model = genai.GenerativeModel('gemini-2.0-flash')

# Load Model
model = joblib.load('/Users/kafeel/Downloads/django-datathon-2/student_risk_model.pkl')
feature_columns = joblib.load('/Users/kafeel/Downloads/django-datathon-2/feature_columns.pkl')

def home(request):
    return render(request, 'index.html')

def predict(request):
    if request.method == 'POST':
        try:
            # Extract form data
            input_data = {
                'Age': float(request.POST['age']),
                'Gender': request.POST['gender'],
                'ParentalEducation': request.POST['parental_edu'],
                'StudyTimeWeekly': float(request.POST['study_time']),
                'Absences': float(request.POST['absences']),
                'Tutoring': request.POST['tutoring'],
                'ParentalSupport': request.POST['parental_support'],
                'Sports': 1 if 'sports' in request.POST else 0,
                'Music': 1 if 'music' in request.POST else 0,
                'Volunteering': 1 if 'volunteer' in request.POST else 0,
                'Ethnicity': request.POST.get('ethnicity', '')
            }

            # Get prediction
            input_df = pd.DataFrame([input_data], columns=feature_columns)
            prediction = model.predict(input_df)[0]
            risk_status = 'At Risk' if prediction == 1 else 'Not At Risk'

            # Base recommendations
            recommendations = []
            if prediction == 1:
                if input_data['StudyTimeWeekly'] < 10:
                    recommendations.append("Increase weekly study time to at least 10 hours")
                if input_data['Absences'] > 5:
                    recommendations.append("Reduce absences through better attendance planning")
                if input_data['Tutoring'] == 'No':
                    recommendations.append("Enroll in tutoring program")
                if input_data['ParentalSupport'] == 'Low':
                    recommendations.append("Schedule regular parent-teacher meetings")

            # Personalize recommendations
            personalized_recommendations = []
            try:
                profile = request.user.userprofile
                learning_style = profile.learning_style
                wake_time = profile.wakeup_time.strftime("%I:%M %p")
                sleep_time = profile.bedtime.strftime("%I:%M %p")
            except:
                learning_style = 'visual'
                wake_time = '7:00 AM'
                sleep_time = '10:00 PM'

            for rec in recommendations:
                personalized_rec = rec
                
                # Learning style adaptations
                if 'study time' in rec.lower():
                    if learning_style == 'visual':
                        personalized_rec += ". Try using visual aids like diagrams and color-coded notes"
                    elif learning_style == 'auditory':
                        personalized_rec += ". Consider recording lectures or using text-to-speech apps"
                    else:
                        personalized_rec += ". Incorporate hands-on activities and movement breaks"
                
                # Time management suggestions
                if 'time' in rec.lower() or 'schedule' in rec.lower():
                    personalized_rec += f" (Your active hours: {wake_time} - {sleep_time})"
                
                personalized_recommendations.append(personalized_rec)

            # Save assessment
            assessment = StudentAssessment.objects.create(
                user=request.user if request.user.is_authenticated else None,
                risk_status=risk_status,
                age=input_data['Age'],
                study_time=input_data['StudyTimeWeekly'],
                absences=input_data['Absences'],
                recommendations=personalized_recommendations,
                data=input_data,
                learning_style=learning_style,
                timestamp=timezone.now(),
            )

            messages.success(request, 'Assessment completed with personalized recommendations!')
            
            return render(request, 'result.html', {
                'prediction': risk_status,
                'recommendations': personalized_recommendations,
                'form_data': request.POST,
                'assessment_id': assessment.id,
                'learning_style': learning_style,
                'wake_time': wake_time,
                'sleep_time': sleep_time
            })

        except Exception as e:
            print(f"Error during prediction: {e}")

            messages.error(request, f'Error processing assessment: {str(e)}')
            return render(request, 'result.html', {
                'prediction': "Error",
                'recommendations': ["Unable to process your request"],
                'form_data': request.POST
            })
@csrf_exempt
def chat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            # Store the user message
            user_interaction = None
            if request.user.is_authenticated:
                user_interaction = ChatInteraction.objects.create(
                    user=request.user,
                    message=user_message,
                    is_user=True
                )
            
            # Create context for the AI (use student profile info if available)
            context = ""
            try:
                if request.user.is_authenticated:
                    profile = request.user.userprofile
                    context = f"""
                    Student context:
                    - Learning style: {profile.learning_style}
                    - Academic goals: {profile.academic_goals}
                    - Strengths: {profile.strengths}
                    - Weaknesses: {profile.weaknesses}
                    - Daily schedule: {profile.wakeup_time.strftime('%I:%M %p')} to {profile.bedtime.strftime('%I:%M %p')}
                    """
            except Exception:
                # If profile doesn't exist, proceed without context
                pass
                
            # Create prompt for Gemini
            prompt = f"""
            You are an AI educational assistant helping a student.
            
            {context}
            
            Respond to the following question in a helpful, encouraging, and educational manner.
            If the student asks about study techniques, tailor your response to their learning style if available.
            Keep responses concise (under 150 words) but informative.
            
            Student: {user_message}
            """
            
            # Generate response with Gemini
            gemini_response = chat_model.generate_content(prompt)
            response = gemini_response.text
            
            # Store the AI response
            if request.user.is_authenticated:
                ChatInteraction.objects.create(
                    user=request.user,
                    message=response,
                    is_user=False
                )
            
            return JsonResponse({
                'status': 'success',
                'response': response
            })
        except Exception as e:
            print(f"Chat error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'response': f"Sorry, I couldn't process that request. Error: {str(e)}"
            })
    
    return JsonResponse({
        'status': 'error',
        'response': "Method not allowed"
    })
@csrf_exempt
def generate_study_plan(request):
    if request.method == 'POST':
        try:
            # Get assessment data
            assessment_id = request.POST.get('assessment_id')
            assessment = StudentAssessment.objects.get(id=assessment_id)
            
            # Get user profile if available
            try:
                profile = request.user.userprofile
                learning_style = profile.learning_style
                strengths = profile.strengths
                weaknesses = profile.weaknesses
                goals = profile.academic_goals
                wake_time = profile.wakeup_time.strftime("%I:%M %p")
                sleep_time = profile.bedtime.strftime("%I:%M %p")
            except:
                learning_style = 'visual'
                strengths = 'Not specified'
                weaknesses = 'Not specified'
                goals = 'Not specified'
                wake_time = '7:00 AM'
                sleep_time = '10:00 PM'

            # Build personalized prompt
            prompt = f"""
            Create a detailed, personalized study plan for a {assessment.age}-year-old student who is:
            - Learning style: {learning_style}
            - Current risk status: {assessment.risk_status}
            - Strengths: {strengths}
            - Weaknesses: {weaknesses}
            - Goals: {goals}
            - Daily schedule: {wake_time} to {sleep_time}
            
            Key recommendations to address:
            {', '.join(assessment.recommendations)}
            
            Additional student data:
            - Weekly study hours: {assessment.study_time}
            - Recent absences: {assessment.absences}
            - Extracurriculars: {', '.join([k for k,v in assessment.data.items() if v == 1 and k in ['Sports', 'Music', 'Volunteering']])}
            
            Please structure the plan with:
            1. Weekly schedule with time blocks
            2. Subject-specific strategies
            3. Recommended resources based on learning style
            4. Progress tracking suggestions
            5. Personalized motivational tips
            
            Format in Markdown with clear headings and bullet points.
            """

            # Generate with Gemini
            response = chat_model.generate_content(prompt)
            
            # Save and return
            assessment.study_plan = response.text
            assessment.save()
            
            return JsonResponse({
                "status": "success",
                "study_plan": response.text,
                "learning_style": learning_style,
                "schedule": f"{wake_time} - {sleep_time}"
            })
            
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "study_plan": f"Failed to generate plan: {str(e)}"
            })
@login_required
def dashboard(request):
    # Get student assessments ordered by date (newest first)
    assessments = StudentAssessment.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'dashboard.html', {
        'assessments': assessments
    })

@login_required
def profile(request):
    # Get or create profile
    try:
        profile = request.user.userprofile
    except:
        profile = UserProfile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # Update profile fields
        profile.learning_style = request.POST.get('learning_style', profile.learning_style)
        profile.academic_goals = request.POST.get('academic_goals', '')
        profile.strengths = request.POST.get('strengths', '')
        profile.weaknesses = request.POST.get('weaknesses', '')
        
        try:
            # Handle time fields
            wakeup_time = request.POST.get('wakeup_time')
            if wakeup_time:
                profile.wakeup_time = wakeup_time
                
            bedtime = request.POST.get('bedtime')
            if bedtime:
                profile.bedtime = bedtime
                
            profile.save()
            messages.success(request, 'Profile updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
    
    return render(request, 'profile.html', {
        'profile': profile
    })

def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if password1 != password2:
            messages.error(request, "Passwords don't match")
            return render(request, 'signup.html')
            
        try:
            user = User.objects.create_user(username=username, email=email, password=password1)
            login(request, user)
            return redirect('dashboard')
        except:
            messages.error(request, "Error creating user")
            
    return render(request, 'signup.html')
from django.contrib.auth import logout

def logout_view(request):
    logout(request)
    return redirect('/') 
def subject_tutors(request):
    """View for the subject tutors selection page"""
    return render(request, 'subject_chat.html')
@csrf_exempt
def subject_chat(request):
    """Handle subject-specific chat interactions"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            subject = data.get('subject', '')
            
            # Store the interaction
            if request.user.is_authenticated:
                interaction = ChatInteraction.objects.create(
                    user=request.user,
                    message=user_message,
                    is_user=True
                )
            
            # Get user profile for context if available
            context = ""
            try:
                if request.user.is_authenticated:
                    profile = request.user.userprofile
                    context = f"""
                    Student profile:
                    - Learning style: {profile.learning_style}
                    - Academic goals: {profile.academic_goals}
                    - Strengths: {profile.strengths}
                    - Areas for improvement: {profile.weaknesses}
                    """
            except:
                pass
                
            # Create subject-specific prompts
            subjects = {
                'math': {
                    'expertise': 'mathematics including algebra, calculus, geometry, statistics, and number theory',
                    'approach': 'Use step-by-step explanations and visual representations when possible.',
                    'resources': 'Khan Academy, Wolfram Alpha, Desmos, and Paul\'s Online Math Notes'
                },
                'science': {
                    'expertise': 'sciences including biology, chemistry, physics, and earth sciences',
                    'approach': 'Explain concepts using analogies and real-world examples.',
                    'resources': 'NASA resources, Khan Academy, and PhET Interactive Simulations'
                },
                'english': {
                    'expertise': 'English language arts including literature analysis, writing, grammar, and rhetoric',
                    'approach': 'Provide constructive feedback on writing and help with structural analysis of texts.',
                    'resources': 'Purdue OWL, Grammarly, and Project Gutenberg'
                },
                'history': {
                    'expertise': 'history and social studies including world history, geography, economics, and political science',
                    'approach': 'Present multiple perspectives and contextual factors for historical events.',
                    'resources': 'BBC History, National Geographic, and primary source archives'
                },
                'languages': {
                    'expertise': 'language learning including grammar, vocabulary, pronunciation, and conversational practice',
                    'approach': 'Use spaced repetition techniques and conversational examples.',
                    'resources': 'Duolingo, Memrise, and language-specific dictionaries'
                },
                'computer': {
                    'expertise': 'computer science including programming, algorithms, data structures, and web development',
                    'approach': 'Provide code examples and pseudocode to illustrate concepts.',
                    'resources': 'Stack Overflow, GitHub, W3Schools, and language documentation'
                }
            }
            
            # Get the subject info or default to general tutoring
            subject_info = subjects.get(subject, {
                'expertise': 'general academic topics',
                'approach': 'Provide clear, concise explanations tailored to the student\'s learning style.',
                'resources': 'educational websites and academic journals'
            })
            
            # Create specialized prompt
            prompt = f"""
            You are an expert tutor specializing in {subject_info['expertise']}.
            
            {context}
            
            When helping this student:
            1. {subject_info['approach']}
            2. Adapt explanations to their learning style if mentioned.
            3. Be encouraging and positive while maintaining academic rigor.
            4. For complex problems, break them down into smaller steps.
            5. When appropriate, recommend specific resources like {subject_info['resources']}.
            
            Student question: {user_message}
            
            Provide a helpful, educational response that demonstrates expertise in {subject or 'this subject'}.
            """
            
            # Generate response with Gemini
            gemini_response = chat_model.generate_content(prompt)
            response = gemini_response.text
            
            # Store AI response
            if request.user.is_authenticated:
                ChatInteraction.objects.create(
                    user=request.user,
                    message=response,
                    is_user=False
                )
            
            return JsonResponse({
                'status': 'success',
                'response': response
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'response': f"Error: {str(e)}"
            })
            
    return JsonResponse({
        'status': 'error',
        'response': "Method not allowed"
    })
# views.py
@login_required
def generate_quiz(request):
    """Generate a personalized quiz based on user's weak areas"""
    if request.method == 'POST':
        subject = request.POST.get('subject')
        difficulty = request.POST.get('difficulty', 'medium')
        
        # Get user profile and past assessments
        weak_areas = []
        try:
            profile = request.user.userprofile
            weak_areas = profile.weaknesses.split(',')
        except:
            pass
            
        # Create prompt for quiz generation
        prompt = f"""
        Create a 5-question quiz on {subject} at {difficulty} difficulty level.
        
        Focus areas to emphasize: {', '.join(weak_areas)}
        
        For each question provide:
        1. The question text
        2. Four possible answers (A, B, C, D)
        3. The correct answer letter
        4. A brief explanation of why that answer is correct
        
        Format as a valid JSON array with this structure:
        [
            {{
                "question": "Question text here",
                "options": {{
                    "A": "First option",
                    "B": "Second option",
                    "C": "Third option",
                    "D": "Fourth option"
                }},
                "correct": "B",
                "explanation": "Explanation here"
            }},
            // more questions...
        ]
        """
        
        # Generate with Gemini API
        response = chat_model.generate_content(prompt)
        
        try:
            # Parse the JSON response
            quiz_data = json.loads(response.text)
            return JsonResponse({"status": "success", "quiz": quiz_data})
        except:
            return JsonResponse({"status": "error", "message": "Failed to generate quiz"})
            
    # If not POST, show the quiz generation form
    return render(request, 'generate_quiz.html')
# views.py
@csrf_exempt
def summarize_content(request):
    """Summarize academic content with AI"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
            subject = data.get('subject', '')
            
            # Create prompt for summarization
            prompt = f"""
            Summarize the following {subject} content concisely and effectively.
            
            Focus on key concepts, main ideas, and important details.
            Format the summary with:
            - A title
            - 3-5 bullet points for main takeaways
            - A brief paragraph explaining the significance
            - Key terms and definitions where relevant
            
            Content to summarize:
            {content}
            """
            
            # Generate with Gemini API
            response = chat_model.generate_content(prompt)
            
            return JsonResponse({
                'status': 'success',
                'summary': response.text
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    # If not POST, show the summarization form
    return render(request, 'summarize.html')
@login_required
def resource_library(request):
    """Main view for the resource library"""
    categories = ResourceCategory.objects.all()
    subjects = Subject.objects.all()
    
    # Get filter parameters
    category_id = request.GET.get('category')
    subject_id = request.GET.get('subject')
    difficulty = request.GET.get('difficulty')
    resource_type = request.GET.get('type')
    query = request.GET.get('q')
    
    # Start with all resources
    resources = Resource.objects.filter(is_approved=True)
    
    # Apply filters
    if category_id:
        resources = resources.filter(category_id=category_id)
    if subject_id:
        resources = resources.filter(subjects__id=subject_id)
    if difficulty:
        resources = resources.filter(difficulty=difficulty)
    if resource_type:
        resources = resources.filter(resource_type=resource_type)
    if query:
        resources = resources.filter(Q(title__icontains=query) | Q(description__icontains=query))
        
    # Get user's recommended resources
    recommended_resources = []
    if request.user.is_authenticated:
        recommended_resources = get_recommended_resources(request.user)[:4]
    
    # Track user's recently viewed resources
    recent_resources = []
    if request.user.is_authenticated:
        recent_interactions = UserResourceInteraction.objects.filter(
            user=request.user,
            viewed=True
        ).order_by('-last_viewed')[:4]
        recent_resources = [interaction.resource for interaction in recent_interactions]
    # Pagination
    paginator = Paginator(resources, 12)  # Show 12 resources per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'resource_library.html', {
        'categories': categories,
        'subjects': subjects,
        'resources': resources,
        'recommended_resources': recommended_resources,
        'recent_resources': recent_resources,
        'filters': {
            'category': category_id,
            'subject': subject_id,
            'difficulty': difficulty,
            'type': resource_type,
            'query': query
        }
    })

@login_required
def resource_detail(request, resource_id):
    """View for a single resource"""
    resource = get_object_or_404(Resource, id=resource_id, is_approved=True)
    
    # Track user interaction with this resource
    interaction, created = UserResourceInteraction.objects.get_or_create(
        user=request.user,
        resource=resource
    )
    
    # Update interaction data
    interaction.viewed = True
    interaction.view_count += 1
    interaction.save()
    
    # Get related resources
    related_resources = Resource.objects.filter(
        subjects__in=resource.subjects.all()
    ).exclude(id=resource.id).distinct()[:3]
    
    return render(request, 'resource_detail.html', {
        'resource': resource,
        'related_resources': related_resources,
        'interaction': interaction
    })

@login_required
def save_resource(request, resource_id):
    """Toggle save/unsave a resource"""
    if request.method == 'POST':
        resource = get_object_or_404(Resource, id=resource_id)
        
        interaction, created = UserResourceInteraction.objects.get_or_create(
            user=request.user,
            resource=resource
        )
        
        # Toggle saved status
        interaction.saved = not interaction.saved
        interaction.save()
        
        return JsonResponse({
            'status': 'success',
            'saved': interaction.saved
        })
        
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

@login_required
def rate_resource(request, resource_id):
    """Rate a resource"""
    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 0))
            if 1 <= rating <= 5:
                resource = get_object_or_404(Resource, id=resource_id)
                
                interaction, created = UserResourceInteraction.objects.get_or_create(
                    user=request.user,
                    resource=resource
                )
                
                interaction.rated = rating
                interaction.save()
                
                return JsonResponse({
                    'status': 'success',
                    'rating': rating
                })
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid rating'
                })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
            
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

@login_required
@user_passes_test(lambda u: u.is_staff)
def upload_resource(request):
    """Form for staff to upload new resources"""
    if request.method == 'POST':
        # Process form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        url = request.POST.get('url')
        thumbnail = request.POST.get('thumbnail', '')
        category_id = request.POST.get('category')
        difficulty = request.POST.get('difficulty')
        resource_type = request.POST.get('resource_type')
        learning_styles = request.POST.getlist('learning_styles')
        subjects = request.POST.getlist('subjects')
        keywords = request.POST.get('keywords', '').split(',')
        keywords = [k.strip() for k in keywords if k.strip()]
        
        # Validate required fields
        if not all([title, description, url, category_id, difficulty, resource_type]):
            messages.error(request, "Please fill all required fields")
            return redirect('upload_resource')
            
        try:
            # Create new resource
            resource = Resource.objects.create(
                title=title,
                description=description,
                url=url,
                thumbnail=thumbnail,
                category_id=category_id,
                difficulty=difficulty,
                resource_type=resource_type,
                learning_styles=learning_styles,
                keywords=keywords,
                uploaded_by=request.user,
                is_approved=True  # Auto-approve for staff
            )
            
            # Add subjects
            for subject_id in subjects:
                resource.subjects.add(subject_id)
            
            messages.success(request, f"Resource '{title}' has been created")
            return redirect('resource_detail', resource_id=resource.id)
        except Exception as e:
            messages.error(request, f"Error creating resource: {str(e)}")
            
    # GET request - show form
    categories = ResourceCategory.objects.all()
    subjects = Subject.objects.all()
    
    return render(request, 'upload_resource.html', {
        'categories': categories,
        'subjects': subjects,
        'difficulty_choices': Resource.DIFFICULTY_CHOICES,
        'type_choices': Resource.TYPE_CHOICES,
        'learning_style_choices': [('visual', 'Visual'), ('auditory', 'Auditory'), ('kinesthetic', 'Hands-on')]
    })

@login_required
def my_resources(request):
    """View for user's saved resources"""
    saved_interactions = UserResourceInteraction.objects.filter(
        user=request.user,
        saved=True
    ).select_related('resource')
    
    saved_resources = [interaction.resource for interaction in saved_interactions]
    
    return render(request, 'my_resources.html', {
        'saved_resources': saved_resources
    })

def get_recommended_resources(user, limit=4):
    """Get AI-powered resource recommendations for a user"""
    try:
        # Get user profile data for personalization
        profile = user.userprofile
        learning_style = profile.learning_style
        strengths = profile.strengths
        weaknesses = profile.weaknesses
        
        # Get user's interaction history
        viewed_resources = UserResourceInteraction.objects.filter(
            user=user, 
            viewed=True
        ).values_list('resource_id', flat=True)
        
        # Query resources the user hasn't viewed yet
        available_resources = Resource.objects.filter(
            is_approved=True
        ).exclude(
            id__in=viewed_resources
        )
        
        # If we have learning style info, prioritize matching resources
        if learning_style:
            style_resources = available_resources.filter(
                learning_styles__contains=[learning_style]
            )
            if style_resources.exists():
                available_resources = style_resources
        
        # If user specified weaknesses, find resources that might help
        if weaknesses:
            # Convert weaknesses to keywords for matching
            weakness_keywords = [w.strip().lower() for w in weaknesses.split(',')]
            
            matching_resources = []
            for resource in available_resources:
                # Check if any resource keyword matches weakness keywords
                if any(k.lower() in weakness_keywords for k in resource.keywords):
                    matching_resources.append(resource.id)
                    
            if matching_resources:
                priority_resources = available_resources.filter(id__in=matching_resources)
                return list(priority_resources[:limit])
        
        # If all else fails, return top resources
        return list(available_resources.order_by('?')[:limit])
    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        return Resource.objects.filter(is_approved=True).order_by('?')[:limit]
    
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Case, When, F, ExpressionWrapper, fields
from django.db.models.functions import TruncDate, ExtractWeekDay
import json
from datetime import datetime, timedelta

# Add these new views for progress tracking and analytics

@login_required
def learning_progress(request):
    """View for a user's learning progress dashboard"""
    user = request.user
    
    # Get user's metrics or create if it doesn't exist
    metrics, created = UserLearningMetrics.objects.get_or_create(user=user)
    
    # Get recent progress entries
    progress_entries = ResourceProgress.objects.filter(
        user=user
    ).select_related('resource').order_by('-last_accessed')[:10]
    
    # Get completed resources
    completed_resources = ResourceProgress.objects.filter(
        user=user, 
        status='completed'
    ).select_related('resource').order_by('-completion_date')
    
    # Get in-progress resources
    in_progress_resources = ResourceProgress.objects.filter(
        user=user, 
        status='in_progress'
    ).select_related('resource').order_by('-last_accessed')
    
    # Calculate progress by category
    from django.db.models import Avg
    progress_by_category = ResourceProgress.objects.filter(
        user=user
    ).values('resource__category__name').annotate(
        avg_progress=Avg('progress_percent')
    ).order_by('-avg_progress')
    
    # Get weekly study time
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    
    daily_study_time = LearningSession.objects.filter(
        user=user,
        start_time__date__gte=start_of_week
    ).annotate(
        date=TruncDate('start_time')
    ).values('date').annotate(
        total_minutes=Sum('duration') / 60
    ).order_by('date')
    
    # Build weekly data
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_data = {day: 0 for day in days_of_week}
    
    for entry in daily_study_time:
        day_index = entry['date'].weekday()
        weekly_data[days_of_week[day_index]] = round(entry['total_minutes'], 1)
    
    # Update streak
    metrics.update_streak()
    
    # Recommendations based on progress
    # Get uncompleted resources in categories the user has engaged with
    completed_resource_ids = ResourceProgress.objects.filter(
        user=user, status='completed'
    ).values_list('resource_id', flat=True)
    
    engaged_categories = UserResourceInteraction.objects.filter(
        user=user
    ).values_list('resource__category_id', flat=True).distinct()
    
    recommended_resources = Resource.objects.filter(
        category_id__in=engaged_categories,
        is_approved=True
    ).exclude(
        id__in=completed_resource_ids
    ).order_by('?')[:3]
    
    return render(request, 'learning_progress.html', {
        'metrics': metrics,
        'progress_entries': progress_entries,
        'completed_resources': completed_resources,
        'in_progress_resources': in_progress_resources,
        'progress_by_category': progress_by_category,
        'weekly_data': weekly_data,
        'recommended_resources': recommended_resources,
        'progress_percent': round((metrics.resources_completed / max(metrics.resources_viewed, 1)) * 100, 1) if metrics.resources_viewed > 0 else 0
    })

@login_required
def update_resource_progress(request):
    """AJAX endpoint for updating resource progress"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            resource_id = data.get('resource_id')
            progress_percent = data.get('progress_percent', 0)
            time_spent = data.get('time_spent', 0)  # Time spent in seconds
            status = data.get('status')
            notes = data.get('notes', '')
            
            resource = Resource.objects.get(id=resource_id)
            
            # Update resource progress
            progress, created = ResourceProgress.objects.get_or_create(
                user=request.user,
                resource=resource,
                defaults={
                    'status': 'not_started',
                    'progress_percent': 0
                }
            )
            
            # Update progress data
            progress.progress_percent = progress_percent
            progress.time_spent += time_spent  # Add to existing time
            
            if status:
                progress.status = status
                
            if status == 'completed' and progress.completion_date is None:
                progress.completion_date = timezone.now()
                
            if notes:
                progress.notes = notes
                
            progress.save()
            
            # Update metrics
            metrics, created = UserLearningMetrics.objects.get_or_create(user=request.user)
            metrics.total_time_spent += time_spent
            
            if created and progress.status == 'completed':
                metrics.resources_completed += 1
                
            if created:
                metrics.resources_viewed += 1
                
            metrics.update_streak()
            metrics.save()
            
            # Create or update learning session
            if 'session_id' in data:
                session_id = data.get('session_id')
                session = LearningSession.objects.get(id=session_id)
                session.end_time = timezone.now()
                session.duration += time_spent
                session.completed = (status == 'completed')
                session.save()
            else:
                session = LearningSession.objects.create(
                    user=request.user,
                    resource=resource,
                    end_time=timezone.now(),
                    duration=time_spent,
                    completed=(status == 'completed')
                )
            
            return JsonResponse({
                'status': 'success', 
                'session_id': session.id,
                'progress_percent': progress.progress_percent
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'})

@login_required
def analytics_dashboard(request):
    """View for advanced learning analytics"""
    user = request.user
    
    # Get user's metrics
    metrics, created = UserLearningMetrics.objects.get_or_create(user=user)
    
    # Update metrics
    metrics.update_favorite_categories()
    metrics.update_study_time_distribution()
    
    # Get top categories
    top_categories = []
    for cat_id, count in metrics.favorite_categories.items():
        try:
            category = ResourceCategory.objects.get(id=cat_id)
            top_categories.append({
                'name': category.name,
                'count': count
            })
        except ResourceCategory.DoesNotExist:
            continue
    
    # Sort by count, descending
    top_categories = sorted(top_categories, key=lambda x: x['count'], reverse=True)[:5]
    
    # Get time distribution by hour
    time_distribution = {}
    for hour, minutes in metrics.study_time_distribution.items():
        # Convert hour (0-23) to formatted time (12am, 1am, ..., 11pm)
        hour_int = int(hour)
        formatted_hour = f"{hour_int if hour_int < 12 else hour_int - 12}{' am' if hour_int < 12 or hour_int == 24 else ' pm'}"
        if hour_int == 0:
            formatted_hour = "12 am"
        elif hour_int == 12:
            formatted_hour = "12 pm"
        
        time_distribution[formatted_hour] = minutes
    
    # Get resource completion by difficulty
    completion_by_difficulty = ResourceProgress.objects.filter(
        user=user,
        status='completed'
    ).values('resource__difficulty').annotate(
        count=Count('id')
    ).order_by('resource__difficulty')
    
    difficulty_data = {
        'beginner': 0,
        'intermediate': 0,
        'advanced': 0
    }
    
    for item in completion_by_difficulty:
        difficulty = item['resource__difficulty']
        if difficulty in difficulty_data:
            difficulty_data[difficulty] = item['count']
    
    # Get weekly averages
    four_weeks_ago = timezone.now().date() - timedelta(days=28)
    weekly_sessions = LearningSession.objects.filter(
        user=user,
        start_time__date__gte=four_weeks_ago
    ).annotate(
        week=TruncDate('start_time', output_field=fields.DateField()),
        weekday=ExtractWeekDay('start_time')
    ).values('week').annotate(
        total_minutes=Sum('duration') / 60,
        count=Count('id')
    ).order_by('week')
    
    weekly_averages = []
    for week in weekly_sessions:
        start_date = week['week']
        end_date = start_date + timedelta(days=6)
        weekly_averages.append({
            'week': f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}",
            'minutes': round(week['total_minutes'], 1),
            'sessions': week['count']
        })
    
    # Get subject distribution
    subject_distribution = ResourceProgress.objects.filter(
        user=user
    ).values('resource__subjects__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    return render(request, 'analytics_dashboard.html', {
        'metrics': metrics,
        'top_categories': top_categories,
        'time_distribution': time_distribution,
        'difficulty_data': difficulty_data,
        'weekly_averages': weekly_averages,
        'subject_distribution': subject_distribution,
    })

@login_required
def set_weekly_goals(request):
    """Set weekly learning goals"""
    if request.method == 'POST':
        try:
            minutes_goal = int(request.POST.get('minutes_goal', 0))
            resources_goal = int(request.POST.get('resources_goal', 0))
            
            metrics, created = UserLearningMetrics.objects.get_or_create(user=request.user)
            
            # Update weekly goals
            metrics.weekly_goals = {
                'minutes': minutes_goal,
                'resources': resources_goal,
                'start_date': timezone.now().date().isoformat()
            }
            metrics.save()
            
            messages.success(request, "Weekly goals have been updated!")
            return redirect('learning_progress')
        
        except Exception as e:
            messages.error(request, f"Error setting goals: {str(e)}")
            return redirect('learning_progress')
    
    return render(request, 'set_goals.html')