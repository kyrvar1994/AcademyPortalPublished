from time import timezone
from django.utils import timezone
from django import forms
from django.forms.models import inlineformset_factory
from .models import *

ModuleFormSet = inlineformset_factory(Course,
                                      Module,
                                      fields=['title', 'description'],
                                      extra=2,
                                      can_delete=True)


class ExerciseForm(forms.ModelForm):
    duration = forms.CharField(
        label='Duration',
        widget=forms.TextInput(attrs={'placeholder': 'HH:MM'})
    )

    # question_files = forms.FileField(
    #     label='Question Files',
    #     widget=forms.ClearableFileInput(attrs={'multiple':True}),
    #     required=False
    # )
    # question_images = forms.ImageField(
    #     label='Question Images',
    #     widget=forms.ClearableFileInput(attrs={'multiple':True}),
    #     required=False
    # )
    # answer_files = forms.FileField(
    #     label='Answer Files',
    #     widget=forms.ClearableFileInput(attrs={'multiple':True}),
    #     required=False
    # )
    # answer_images = forms.ImageField(
    #     label='Answer Images',
    #     widget=forms.ClearableFileInput(attrs={'multiple':True}),
    #     required=False
    # )

    class Meta:
        model = Exercise
        fields = ['title', 'question_description', 'question_file', 'duration', 'answer', 'answer_file', 'visible']

    def save(self, commit=True):
        exercise = super(ExerciseForm, self).save(commit=commit)
        return exercise

    # def clean_duration(self):
    #     data = self.cleaned_data['duration']
    #     pattern = r'^(\d+):([0-5][0-9])$'
    #     # match = re.match(pattern,data)
    #     # if not match:
    #     #     raise forms.ValidationError('Invalid duration format. Use HH:MM.')
    #     hours, minutes = int(match.group(1)), int(match.group(2))
    #     if hours == 0 and minutes == 0:
    #         raise forms.ValidationError('Duration must be greater than 0.')
    #     return timedelta(hours=hours,minutes=minutes)


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'score']
        labels = {
            'text': 'Question',
            'score': 'Question Score'
        }


ExerciseFormSet = inlineformset_factory(Exercise,
                                        Question,
                                        fields=['text', ],
                                        extra=1,
                                        can_delete=True)

AnswerFormSet = inlineformset_factory(Question,
                                      Answer,
                                      fields=['text', ],
                                      extra=1,
                                      can_delete=True,
                                      max_num=1)


class ExamForm(forms.ModelForm):
    start_time = forms.DateTimeField(
        input_formats=['%d-%m-%Y %H:%M'],
        widget=forms.DateTimeInput(format='%d-%m-%Y %H:%M',
                                   attrs={'class': 'datetimepicker', })

    )

    end_time = forms.DateTimeField(
        input_formats=['%d-%m-%Y %H:%M'],
        widget=forms.DateTimeInput(format='%d-%m-%Y %H:%M',
                                   attrs={'class': 'datetimepicker', }),

    )

    class Meta:
        model = Exam
        fields = "__all__"
        exclude = ['course']

    def clean_start_time(self):
        start_time = self.cleaned_data['start_time']
        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time, timezone.get_current_timezone())
        return start_time

    def clean_end_time(self):
        end_time = self.cleaned_data['end_time']
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time, timezone.get_current_timezone())
        return end_time


class EssayQuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'score']
        labels = {
            'text': 'Question',
            'score': 'Question Score'
        }


MultipleChoiceQuestionFormSet = inlineformset_factory(Question,
                                                      Answer,
                                                      fields=['id','text', 'is_correct'],
                                                      extra=4,
                                                      can_delete=True,
                                                      max_num=4)

TrueFalseQuestionFormSet = inlineformset_factory(Question,
                                                 Answer,
                                                 fields=['is_correct'],
                                                 extra=0)


class TrueFalseQuestionForm(forms.ModelForm):
    is_true = forms.BooleanField(required=False,
                                 widget=forms.CheckboxInput(),
                                 label='Is this statement true?')

    score = forms.DecimalField(widget=forms.TextInput())

    class Meta:
        model = Question
        fields = ['text', 'is_true', 'score']
        labels = {
            'text': 'Question',
            'is_true': 'Is this statement true?',
            'score': 'Question Score'
        }


class ExamAnswerForm(forms.Form):
    def __init__(self, questions, *args, **kwargs):
        super().__init__(*args, **kwargs)

        action = None
        if 'data' in kwargs and kwargs['data']:
            action = kwargs['data'].get('action')

        for question in questions:
            required = action != 'save'

            if question.question_type == 'MCQ':
                choices = [(answer.id, answer.text) for answer in question.answers.all()]
                self.fields[f'question_{question.id}'] = forms.ChoiceField(choices=choices,
                                                                           widget=forms.RadioSelect,
                                                                           label=question.text,
                                                                           required=required)
            elif question.question_type == 'TF':
                self.fields[f'question_{question.id}'] = forms.ChoiceField(choices=[(True, 'True'), (False, 'False')],
                                                                           widget=forms.RadioSelect,
                                                                           label=question.text,
                                                                           required=required)
            elif question.question_type == 'ESSAY':
                self.fields[f'question_{question.id}'] = forms.CharField(widget=forms.Textarea,
                                                                         label=question.text,
                                                                         required=required
                                                                         )
                self.fields[f'file_question_{question.id}'] = forms.FileField(label='Upload File',
                                                                              required=False,
                                                                              widget=forms.ClearableFileInput(
                                                                                  attrs={'accept': '.pdf,.doc,.docx'}))

class GradeEssayAnswerForm(forms.ModelForm):
    class Meta:
        model = StudentExamAnswer
        fields = ['awarded_score','feedback']
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 3}),
        }

class ResetStudentExamAttemptForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea,
                             required=False,
                             help_text='Enter the reason for resetting the exam attempt.')