from django import forms
from courses.models import *
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User



class CourseEnrollForm(forms.Form):
    courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.none(),
        label='Courses',
        widget=forms.CheckboxSelectMultiple
    )
    academic_year = forms.ModelChoiceField(
        queryset= AcademicYear.objects.all(),
        widget=forms.HiddenInput
    )

    def __init__(self,*args,**kwargs):
        user = kwargs.pop('user',None)
        super(CourseEnrollForm,self).__init__(*args,**kwargs)
        current_year = AcademicYear.objects.filter(is_current=True).first()
        if current_year:
            self.fields['academic_year'].initial = current_year

        self.all_courses = Course.objects.all().order_by('subject__title','title')

        self.unavailable_courses = []
        if user and user.is_authenticated:
            self.unavailable_courses = StudentCourseEnrollment.objects.filter(student=user,
                                                                              ).values_list('course_id',flat=True)
            self.fields['courses'].queryset = Course.objects.exclude(id__in=self.unavailable_courses)
        else:
            self.fields['courses'].queryset = Course.objects.none()

class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password',widget=forms.PasswordInput)
    password2 = forms.CharField(label='Repeat password',widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ('username','first_name','last_name','email')

    def clean_password2(self):
        cd = self.cleaned_data
        if cd['password1'] != cd['password2']:
            raise forms.ValidationError('Passwords don\'t match.')
        return cd['password2']

class StudentProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name','last_name','email')

    def unique_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError('Email already exists.')
        return email

class ProfileImageUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image']