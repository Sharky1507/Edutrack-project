from django.shortcuts import render
from django.http import JsonResponse
import joblib
import pandas as pd
import google.generativeai as genai
import os
import re
from django.contrib.auth.decorators import login_required
from .models import StudentAssessment, ChatInteraction
from django.contrib import messages


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
                'Volunteering': 1 if 'volunteer' in request.POST else 0
            }

            input_df = pd.DataFrame([input_data], columns=feature_columns)
            prediction = model.predict(input_df)[0]
            risk_status = 'At Risk' if prediction == 1 else 'Not At Risk'

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

            return render(request, 'result.html', {
                'prediction': risk_status,
                'recommendations': recommendations,
                'form_data': request.POST
            })
        except Exception as e:
            return render(request, 'result.html', {
                'prediction': "Error",
                'recommendations': ["Unable to process your request"],
                'form_data': request.POST
            })

def chat(request):
    if request.method == 'POST':
        user_message = request.POST['message']
        try:
            response = chat_model.generate_content(user_message)
            return JsonResponse({"status": "success", "response": response.text})
        except Exception as e:
            return JsonResponse({"status": "error", "response": "Sorry, I'm having trouble responding."})
@csrf_exempt  # Only if you're having CSRF issues with AJAX
z
def generate_study_plan(request):
    if request.method == 'POST':
        try:
            
            student_data = {
                'risk_status': request.POST['prediction'],
                'study_hours': float(request.POST['study_time']),
                'absences': float(request.POST['absences']),
                'extracurriculars': [],
                'recommendations': request.POST.getlist('recommendations')
            }

            prompt = f"Generate a structured study plan for a student with {student_data['risk_status']} risk level, {student_data['study_hours']} weekly study hours, and recommendations: {', '.join(student_data['recommendations'])}"

            response = chat_model.generate_content(prompt)
            return JsonResponse({"status": "success", "study_plan": response.text})
        except Exception as e:
            return JsonResponse({"status": "error", "study_plan": "Failed to generate study plan. Please try again later."})
