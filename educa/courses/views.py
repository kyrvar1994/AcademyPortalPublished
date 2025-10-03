import os
from pprint import pprint
import django
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, Http404, HttpResponseRedirect


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AcademyPortal6.educa.educa.settings')
django.setup()
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy, reverse
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView
from django.contrib.auth.mixins import (LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin)
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic.base import TemplateResponseMixin, View
from .forms import *
from django.apps import apps
from django.forms.models import modelform_factory, inlineformset_factory
from braces.views import CsrfExemptMixin, JSONRequestResponseMixin
from django.db.models import Count, Exists, Q, Avg, Case, When, F, FloatField
from django.views.generic.detail import DetailView
from students.forms import CourseEnrollForm
from .models import *
from django.contrib import messages as django_messages
from decimal import Decimal


# Create your views here.
class OwnerMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(Q(owners=self.request.user))


class OwnerEditMixin:
    def form_valid(self, form):
        response = super().form_valid(form)
        self.object.owners.set([self.request.user])
        return response


class OwnerCourseMixin(OwnerMixin, LoginRequiredMixin, PermissionRequiredMixin):
    model = Course
    fields = ['subject', 'title', 'overview', 'duration']
    success_url = reverse_lazy('manage_course_list')


class OwnerCourseEditMixin(OwnerCourseMixin, OwnerEditMixin):
    template_name = 'courses/manage/course/form.html'


class ManageCourseListView(OwnerCourseMixin, ListView):
    model = Course
    template_name = 'courses/manage/course/list.html'
    permission_required = 'courses.view_course'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_superuser:
            return qs
        return qs.filter(owners=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_superuser:
            context['subjects'] = Subject.objects.prefetch_related(
                models.Prefetch(
                    'courses',
                    queryset=Course.objects.all()
                )
            )
        else:
            context['subjects'] = Subject.objects.filter(
                Exists(
                    Course.objects.filter(
                        owners=self.request.user,
                        subject=models.OuterRef('pk')
                    )
                )
            ).prefetch_related(
                models.Prefetch(
                    'courses',
                    queryset=Course.objects.filter(
                        owners=self.request.user
                    )
                )
            )
        return context


class CourseCreateView(OwnerCourseEditMixin, CreateView):
    permission_required = 'courses.add_course'


class CourseUpdateView(OwnerCourseEditMixin, UpdateView):
    permission_required = 'courses.change_course'


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    template_name = 'courses/manage/course/delete.html'
    permission_required = 'courses.delete_course'


class CourseModuleUpdateView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/formset.html'
    course = None

    def get_formset(self, data=None):
        return ModuleFormSet(instance=self.course, data=data)

    def dispatch(self, request, pk):
        self.course = get_object_or_404(Course,
                                        id=pk)

        if not request.user.is_superuser and not self.course.owners.filter(id=request.user.id).exists():
            return self.handle_no_permission()
        return super().dispatch(request, pk)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response(
            {'course': self.course, 'formset': formset}
        )

    def post(self, request, *args, **kwargs):
        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            formset.save()
            return redirect('manage_course_list')
        return self.render_to_response(
            {'course': self.course, 'formset': formset}
        )

    def handle_no_permission(self):
        return HttpResponseForbidden("You don't have permission to view this course.")


class CourseReorderView(View):
    def post(self, request, *args, **kwargs):
        course_order = request.POST.getlist('order[]')
        for index, course_id in enumerate(course_order):
            course = get_object_or_404(Course, id=course_id)
            course.order = index
            course.save()
        return JsonResponse({'success': 'True'})


class ContentCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = 'courses/manage/content/form.html'

    def get_model(self, model_name):
        if model_name in ['text', 'video', 'image', 'file', 'exercise']:
            return apps.get_model(app_label='courses', model_name=model_name)
        return None

    def get_form(self, model, *args, **kwargs):
        Form = modelform_factory(model, exclude=['owner', 'order', 'created', 'updated'])
        return Form(*args, **kwargs)

    def dispatch(self, request, course_id, module_id, model_name, id=None):
        if request.user.is_staff or request.user.is_superuser:
            self.module = get_object_or_404(Module, id=module_id, course__id=course_id)
        else:
            self.module = get_object_or_404(Module, id=module_id, course__owners=request.user, course_id=course_id)

        self.model = self.get_model(model_name)
        if id:
            if request.user.is_staff or request.user.is_superuser:
                self.obj = get_object_or_404(self.model, id=id)
            else:
                self.obj = get_object_or_404(self.model, id=id, owner=request.user)
        return super().dispatch(request, course_id, module_id, model_name, id)

    def get(self, request, course_id, module_id, model_name, id=None):
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({'form': form, 'object': self.obj})

    def post(self, request, course_id, module_id, model_name, id=None):
        form = self.get_form(self.model,
                             instance=self.obj,
                             data=request.POST,
                             files=request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            if not id:
                Content.objects.create(module=self.module, item=obj)
            return redirect('module_content_list', course_id, self.module.id)
        return self.render_to_response(
            {'form': form, 'object': self.obj}
        )


class ContentDeleteView(View):
    def post(self, request, id):
        content = get_object_or_404(Content, id=id, module__course__owners=request.user)
        module = content.module
        content.item.delete()
        content.delete()
        return redirect('module_content_list', module.course.id, module.id)


class ModuleContentListView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/content_list.html'

    def get(self, request, course_id, module_id):
        course = get_object_or_404(Course, id=course_id)
        module = get_object_or_404(Module, id=module_id, course__id=course_id)
        if not module.course.owners.filter(id=request.user.id).exists() and not request.user.is_superuser:
            return self.handle_no_permission()

        exercises = Exercise.objects.filter(module=module)
        for exercise in exercises:
            print(f"ID: {exercise.id} - Title: {exercise.title}")

        fields = [field.name for field in Exercise._meta.fields]
        pprint(fields)
        return self.render_to_response({'course': course,'module': module, 'exercises': exercises})

    def post(self, request, exercise_id, *args, **kwargs):
        return self.toggle_exercise_visibility(request, exercise_id)

    def handle_no_permission(self):
        return HttpResponseForbidden("You don't have permission to view this course.")

    def toggle_exercise_visibility(self, request, exercise_id):
        exercise = get_object_or_404(Exercise, id=exercise_id)
        exercise.visible = not exercise.visible
        exercise.save()
        return redirect(request.META.get('HTTP_REFERER', '/'))


class ModuleOrderView(CsrfExemptMixin, JSONRequestResponseMixin, View):
    def post(self, request):
        for id, order in self.request_json.items():
            Module.objects.filter(
                id=id, course__owner=request.user
            ).update(order=order)
        return self.render_json_response({'saved': 'OK'})


class ContentOrderView(CsrfExemptMixin, JSONRequestResponseMixin, View):
    def post(self, request):
        for id, order in self.request_json.items():
            Content.objects.filter(
                id=id, module__course__owner=request.user
            ).update(order=order)
        return self.render_json_response({'saved': 'OK'})


class CourseListView(TemplateResponseMixin, View):
    model = Course
    template_name = 'courses/course/list.html'

    def get(self, request, subject=None):
        subjects = Subject.objects.annotate(
            total_courses=Count('courses')
        ).order_by('order')

        courses = Course.objects.annotate(
            total_modules=Count('modules')
        ).prefetch_related('owners')

        if subject:
            subject = get_object_or_404(Subject, slug=subject)
            courses = courses.filter(subject=subject)

        return self.render_to_response({
            'subjects': subjects,
            'subject': subject,
            'courses': courses,

        })


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        owners_list = self.get_owners_list()
        context['enroll_form'] = CourseEnrollForm(
            initial={'course': self.object}
        )
        context['is_instructor'] = self.is_instructor()
        context['is_enrolled'] = self.is_enrolled()
        context['should_enroll'] = self.should_enroll()
        context['owners_list'] = ", ".join(owners_list)
        return context

    def is_instructor(self):
        return self.request.user.groups.filter(name='Instructors').exists()

    def is_enrolled(self):
        if not self.request.user.is_authenticated:
            return False

        is_student_enrolled = StudentCourseEnrollment.objects.filter(
            student=self.request.user,
            course=self.object
        ).exists()

        is_course_owner = self.object.owners.filter(id=self.request.user.id).exists()

        return is_student_enrolled or is_course_owner

    def should_enroll(self):
        is_authenticated = self.request.user.is_authenticated
        is_instructor = self.is_instructor()
        is_enrolled = self.is_enrolled()
        if is_authenticated and not is_instructor and not is_enrolled:
            return True
        else:
            return False

    def get_owners_list(self):
        owners_list = []
        for owner in self.object.owners.all():
            owners_list.append(owner.get_full_name())
        return owners_list


class CustomLoginView(LoginView):
    def get_success_url(self):
        user = self.request.user
        if user.groups.filter(name='Instructors').exists():
            return reverse('manage_course_list')
        if user.is_superuser:
            return reverse('admin:index')
        else:
            return reverse('student_course_list')


class ExerciseCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = 'exercises/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.course = get_object_or_404(Course, id=kwargs['course_id'])
        self.module = get_object_or_404(Module, id=kwargs['module_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        valid = form.is_valid()
        if valid:
            self.object = form.save(commit=False)
            self.object.course = self.course
            self.object.module = self.module
            self.object.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):
        return reverse('module_content_list',
                       kwargs={'course_id': self.object.course.id, 'module_id': self.object.module.id})

    def test_func(self):
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)
        course_owners = course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExerciseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Exercise
    template_name = "exercises/exercise_confirm_delete.html"
    success_url = reverse_lazy('module_content_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        exercise_id = self.object.id
        if not exercise_id:
            raise Http404("Exercise ID is required.")
        exercise = get_object_or_404(Exercise, id=exercise_id)
        context['exercise_id'] = exercise.id
        context['course_id'] = exercise.course.id
        context['module_id'] = exercise.module.id
        return context

    def get_success_url(self):
        module_id = self.kwargs.get('module_id')
        if not module_id:
            raise ValueError("Module ID is required.")
        exercise = self.get_object()
        return reverse('module_content_list', kwargs={'course_id': exercise.course.id, 'module_id': module_id})

    def test_func(self):
        exercise = self.get_object()
        course_owners = exercise.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExerciseUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Exercise
    form_class = ExerciseForm
    template_name = 'exercises/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.exercise = self.get_object()
        self.course = self.exercise.course
        self.module = self.exercise.module
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_id'] = self.course.id
        exercise = self.get_object()
        return context

    def form_valid(self, form):
        valid = form.is_valid()
        if valid:
            self.object = form.save(commit=False)
            self.object.course = self.course
            self.object.module = self.module
            self.object.save()
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def get_success_url(self):

        return reverse('module_content_list', args=[self.course.id, self.module.id])

    def test_func(self):
        exercise = self.get_object()
        course_owners = exercise.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExerciseDetailView(LoginRequiredMixin, DetailView):
    model = Exercise
    template_name = 'exercises/exercise_details.html'
    context_object_name = 'exercise'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_id'] = self.object.course.id
        context['module_id'] = self.object.module.id
        context['available_exercises'] = Exercise.objects.filter(module_id=self.object.module.id, visible=True)
        return context


class ExamsCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Exam
    form_class = ExamForm
    template_name = 'exams/exam_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.course = get_object_or_404(Course, id=kwargs['course_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_id'] = self.course.id
        return context

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        current_year = AcademicYear.objects.filter(is_current=True).first()
        form.fields['academic_year'] = forms.ModelChoiceField(
            queryset=AcademicYear.objects.all().order_by('-start_date'),
            initial=current_year,
            widget=forms.HiddenInput()
        )
        return form

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.course = self.course
        self.object.academic_year = form.cleaned_data['academic_year']
        self.object.save()

        if 'save' in self.request.POST:
            self.button_clicked = 'save'
        else:
            self.button_clicked = 'next'

        return redirect(self.get_success_url())

    def test_func(self):
        course = get_object_or_404(Course, id=self.course.id)
        course_owners = course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner

    def get_success_url(self):
        if hasattr(self, 'button_clicked') and self.button_clicked == 'next':
            return reverse('exam_add_questions', kwargs={'course_id': self.course.id, 'exam_id': self.object.id})
        else:
            return reverse('exam_manage', kwargs={'course_id': self.course.id})


class ExamsListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Exam
    context_object_name = 'exams'
    template_name = 'exams/exam_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course_id = self.kwargs.get('course_id')
        context['course_id'] = course_id
        context['course_title'] = Course.objects.get(id=context['course_id']).title

        all_exams = Exam.objects.filter(course_id=course_id)

        current_year = AcademicYear.objects.filter(is_current=True).first()

        current_year_exams = all_exams.filter(academic_year=current_year) if current_year else []

        previous_years_exams = {}
        if current_year:
            previous_years = AcademicYear.objects.filter(~Q(id=current_year.id)).order_by('-start_date')
            for year in previous_years:
                year_exams = all_exams.filter(academic_year=year)
                if year_exams.exists():
                    previous_years_exams[year] = year_exams

        context['current_year'] = current_year
        context['current_year_exams'] = current_year_exams
        context['previous_years_exams'] = previous_years_exams

        return context

    def test_func(self):
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)
        course_owners = course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExamUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Exam
    form_class = ExamForm
    template_name = 'exams/exam_form.html'
    context_object_name = 'exam'

    def dispatch(self, request, *args, **kwargs):
        self.exam = self.get_object()
        self.course = self.exam.course
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam'] = Exam.objects.get(pk=self.object.pk)
        context['course_id'] = self.course.id
        return context

    def get_form(self,form_class=None):
        form = super().get_form(form_class)
        form.fields['academic_year'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        valid = form.is_valid()
        if valid:
            self.object = form.save(commit=False)
            self.object.course = self.course
            self.object.save()

            if 'save' in self.request.POST:
                self.button_clicked = 'save'
            else:
                self.button_clicked = 'next'

            return redirect(self.get_success_url())
        else:
            return self.render_to_response(self.get_context_data(form=form))

    def test_func(self):
        exam = self.get_object()
        course_owners = exam.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner

    def get_success_url(self):
        if hasattr(self, 'button_clicked') and self.button_clicked == 'next':
            return reverse('exam_add_questions', kwargs={'course_id': self.course.id, 'exam_id': self.object.id})
        else:
            return reverse('exam_manage', kwargs={'course_id': self.course.id})


class ExamDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Exam
    template_name = "exams/exam_confirm_delete.html"
    success_url = reverse_lazy('exam_manage')

    def dispatch(self, request, *args, **kwargs):
        self.exam = self.get_object()
        self.course = self.exam.course
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam_id = self.exam.id
        context['exam_id'] = exam_id
        context['course_id'] = self.course.id
        return context

    def get_success_url(self):
        return reverse('exam_manage', kwargs={'course_id': self.course.id})

    def test_func(self):
        exam = self.get_object()
        course_owners = exam.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExamAddQuestionsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Question
    template_name = 'exams/exam_form_2.html'

    def dispatch(self, request, *args, **kwargs):
        self.exam = get_object_or_404(Exam, id=kwargs['exam_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Question.objects.filter(exam__id=self.exam.id).prefetch_related('answers')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['questions'] = self.object_list
        context['exam_id'] = self.exam.id
        context['exam_title'] = self.exam.title
        context['course_id'] = self.exam.course.id
        # context['test'] =
        # print(context)
        return context

    def test_func(self):
        course_owners = self.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners

    def get_success_url(self):
        return reverse('exam_manage', kwargs={'course_id': self.exam.course.id})


class ExamAddEssayView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Question
    form_class = EssayQuestionForm
    template_name = 'exams/exam_question_essay.html'

    def dispatch(self, request, *args, **kwargs):
        self.exam_id = self.kwargs.get('exam_id')
        self.course_id = self.kwargs.get('course_id')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_id'] = self.exam_id
        context['course_id'] = self.course_id
        # print(context)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        exam_instance = Exam.objects.get(pk=self.kwargs.get('exam_id'))
        self.object.exam.add(exam_instance)
        return response

    def test_func(self):
        exam = Exam.objects.get(pk=self.kwargs.get('exam_id'))
        course_owners = exam.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner

    def get_success_url(self):
        return reverse('exam_add_questions', kwargs={'course_id': self.course_id, 'exam_id': self.exam_id})


class ExamEditEssayView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Question
    form_class = EssayQuestionForm
    template_name = 'exams/exam_question_essay.html'

    def get_object(self, queryset=None):
        return get_object_or_404(Question, pk=self.kwargs.get('pk'))

    def get_success_url(self):
        return reverse('exam_add_questions',
                       kwargs={'course_id': self.kwargs.get('course_id'), 'exam_id': self.kwargs.get('exam_id')})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_id'] = self.kwargs.get('exam_id')
        context['course_id'] = self.kwargs.get('course_id')
        return context

    def test_func(self):
        exam = Exam.objects.get(pk=self.kwargs.get('exam_id'))
        course_owners = exam.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExamDeleteEssayView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Question
    template_name = "exams/exam_question_essay_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_id'] = self.kwargs.get('exam_id')
        context['course_id'] = self.kwargs.get('course_id')
        return context

    def get_success_url(self):
        return reverse('exam_add_questions', kwargs={
            'course_id': self.kwargs.get('course_id'),
            'exam_id': self.kwargs.get('exam_id')
        })

    def test_func(self):
        question = self.get_object()
        exam = question.exam.first()
        course_owners = exam.course.owners.all()
        is_superuser = self.request.user.is_superuser
        is_owner = self.request.user in course_owners
        return is_superuser or is_owner


class ExamAddMultipleChoiceView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Question
    form_class = QuestionForm
    template_name = 'exams/exam_question_multiple_choice.html'

    def dispatch(self, request, *args, **kwargs):
        self.exam_id = kwargs.get('exam_id')
        self.course_id = kwargs.get('course_id')
        self.exam_instance = get_object_or_404(Exam, id=self.exam_id, course_id=self.course_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = MultipleChoiceQuestionFormSet(self.request.POST)
        else:
            context['formset'] = MultipleChoiceQuestionFormSet()

        context['exam_id'] = self.exam_id
        context['course_id'] = self.course_id
        # print(context)
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.question_type = 'MCQ'
        self.object.save()

        self.object.exam.add(self.exam_instance)

        formset = MultipleChoiceQuestionFormSet(self.request.POST, instance=self.object)

        if formset.is_valid():
            forms_to_save = [f for f in formset.forms if not f.cleaned_data.get('DELETE', False)]

            if not forms_to_save:
                form.add_error(None, 'At least one correct answer is required.')
                self.object.delete()
                return self.form_invalid(form)

            empty_answers = [f for f in forms_to_save if not f.cleaned_data.get('text', '').strip()]
            if empty_answers:
                form.add_error(None, 'Answer text cannot be empty.')
                self.object.delete()
                return self.form_invalid(form)

            correct_answers = [f for f in forms_to_save if f.cleaned_data.get('is_correct', False)]
            if len(correct_answers) != 1:
                form.add_error(None, 'Only one correct answer is allowed.')
                self.object.delete()
                return self.form_invalid(form)

            instances = formset.save(commit=False)

            for instance in instances:
                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            formset.save_m2m()

            return super().form_valid(form)
        else:
            self.object.delete()
            return self.form_invalid(form)

    def test_func(self):
        user = self.request.user
        return user.is_superuser or self.exam_instance.course.owners.filter(pk=user.pk).exists()

    def get_success_url(self):
        return reverse('exam_add_questions', kwargs={'course_id': self.course_id, 'exam_id': self.exam_id})


class ExamUpdateMultipleChoiceView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Question
    form_class = QuestionForm
    template_name = 'exams/exam_question_multiple_choice.html'

    def dispatch(self, request, *args, **kwargs):
        self.question = self.get_object()
        self.course_id = self.kwargs.get('course_id')
        self.exam_id = self.kwargs.get('exam_id')
        self.exam_instance = get_object_or_404(Exam, id=self.exam_id, course_id=self.course_id)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = MultipleChoiceQuestionFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = MultipleChoiceQuestionFormSet(instance=self.object)

        context['exam_id'] = self.exam_id
        context['course_id'] = self.course_id
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.save()

        self.object.exam.add(self.exam_instance)

        formset = MultipleChoiceQuestionFormSet(self.request.POST, instance=self.object)

        print(f'Formset valid: {formset.is_valid()}')
        if not formset.is_valid():
            print(f'Forsmet errors: {formset.errors}')
            return self.form_invalid(form)

        formset.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context['formset'] = MultipleChoiceQuestionFormSet(self.request.POST, instance=self.object)
        return self.render_to_response(context)

    def get_success_url(self):
        url = reverse('exam_add_questions', kwargs={'course_id': self.course_id, 'exam_id': self.exam_id})
        print(f'Generated success URL: {url}')
        return url

    def test_func(self):
        user = self.request.user
        return user.is_superuser or self.question.exam.first().course.owners.filter(pk=user.pk).exists()


class ExamCreateTrueFalseQuestion(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Question
    form_class = TrueFalseQuestionForm
    template_name = 'exams/exam_question_true_false.html'

    def dispatch(self, request, *args, **kwargs):
        self.course_id = kwargs.get('course_id')
        self.exam_id = kwargs.get('exam_id')
        self.exam = get_object_or_404(Exam, id=kwargs['exam_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = TrueFalseQuestionFormSet(self.request.POST)
        else:
            context['formset'] = TrueFalseQuestionFormSet()

        context['course_id'] = self.course_id
        context['exam_id'] = self.exam_id
        return context

    def form_valid(self, form):
        print("Entering form_valid")
        self.object = form.save(commit=False)
        self.object.question_type = 'TF'
        self.object.save()
        self.object.exam.add(self.exam)

        is_true = form.cleaned_data.get('is_true', False)

        Answer.objects.create(question=self.object, is_correct=is_true, text="True/False Answer")

        return super().form_valid(form)

    def form_invalid(self, form):
        print('Entering form_invalid')
        context = self.get_context_data(form=form)
        context['formset'] = TrueFalseQuestionFormSet(self.request.POST)
        return self.render_to_response(context)

    def test_func(self):
        course_owners = self.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners

    def get_success_url(self):
        return reverse('exam_add_questions', kwargs={'course_id': self.course_id, 'exam_id': self.exam_id})


class ExamUpdateTrueFalseQuestion(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Question
    form_class = TrueFalseQuestionForm
    template_name = 'exams/exam_question_true_false.html'

    def dispatch(self, request, *args, **kwargs):
        self.question = self.get_object()
        self.course_id = kwargs.get('course_id')
        self.exam_id = kwargs.get('exam_id')
        self.exam = get_object_or_404(Exam, id=kwargs['exam_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['formset'] = TrueFalseQuestionFormSet(self.request.POST, instance=self.object)
        else:
            context['formset'] = TrueFalseQuestionFormSet(instance=self.object)
        context['course_id'] = self.course_id
        context['exam_id'] = self.exam_id
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.question_type = 'TF'
        self.object.save()

        self.object.exam.add(self.exam)

        return super().form_valid(form)

    def test_func(self):
        course_owners = self.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners

    def get_success_url(self):
        return reverse('exam_add_questions', kwargs={'course_id': self.course_id, 'exam_id': self.exam_id})


class GradeExamConsoleView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = StudentExamAttempt
    template_name = "exams/grade_exam_console.html"
    context_object_name = 'attempts'

    def dispatch(self, request, *args, **kwargs):
        # print('Entering dispatch')
        self.course_id = kwargs.get('course_id')
        self.exam_id = kwargs.get('exam_id')
        self.exam = get_object_or_404(Exam, id=kwargs['exam_id'])
        self.filter_status = request.GET.get('status', 'all')

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # print('Entering get_queryset')
        queryset = StudentExamAttempt.objects.filter(exam=self.exam)

        if self.filter_status == 'graded':
            queryset = queryset.filter(exam__is_graded=True)
        elif self.filter_status == 'ungraded':
            queryset = queryset.filter(exam__is_graded=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam'] = self.exam
        context['course_id'] = self.course_id
        context['all_attempts_graded'] = self.exam.all_attempts_graded()
        context['filter_status'] = self.filter_status
        return context

    def test_func(self):
        # print('Entering test_func')
        course_owners = self.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners


class GradeStudentExamView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = StudentExamAttempt
    template_name = 'exams/grade_student_exam.html'

    def dispatch(self, request, *args, **kwargs):
        self.attempt = self.get_object()
        self.course_id = kwargs.get('course_id')
        self.exam = self.attempt.exam
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attempt'] = self.attempt
        context['exam'] = self.exam
        context['course_id'] = self.course_id
        return context

    def post(self, request, *args, **kwargs):
        attempt = self.get_object()
        self.object = attempt
        validation_messages = []

        for answer in attempt.answers.all():
            score_key = f'score_{answer.id}'
            feedback_key = f'feedback_{answer.id}'
            score = request.POST.get(score_key, 0)
            feedback = request.POST.get(feedback_key, '')

            max_score = answer.question.score
            try:
                score_value = float(score)
                if score_value > max_score:
                    validation_messages.append(
                        f'Score for question {answer.question.id} is greater than maximum score of {max_score}.')
                    score_value = max_score
            except (ValueError, TypeError):
                score_value = 0

            answer.awarded_score = score_value
            answer.feedback = feedback
            answer.save()

        try:
            total_score = float(request.POST.get('total_score', 0))
            max_total_score = attempt.exam.total_score
            if total_score > max_total_score:
                validation_messages.append(f'Total score is greater than maximum total score of {max_total_score}.')
                total_score = attempt.exam.total_score
        except(ValueError, TypeError):
            total_score = 0

        instructor_feedback = request.POST.get('instructor_feedback', '')

        attempt.score = total_score
        attempt.instructor_feedback = instructor_feedback

        if 'finalize' in request.POST:
            attempt.is_graded = True
            attempt.save()
        else:
            attempt.save()

        if validation_messages:
            storage = django_messages.get_messages(request)
            storage.used = True

            for message in validation_messages:
                django_messages.warning(request, message)

            context = self.get_context_data()
            return render(request, self.template_name, context)

        return redirect('grade_management_console', course_id=self.course_id, exam_id=self.exam.id)

    def test_func(self):
        attempt = self.get_object()
        course_owners = attempt.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners


class AllNotificationsView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/all_notifications.html'
    context_object_name = 'notifications'
    paginate_by = 10

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')


def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()

    if notification.link:
        if '/course/' in notification.link and '/exam/' in notification.link and '/results/' in notification.link:
            parts = notification.link.split('/')
            try:
                exam_index = parts.index('exam')
                if exam_index + 1 < len(parts):
                    exam_id = int(parts[exam_index + 1])

                    try:
                        Exam.objects.get(id=exam_id)
                    except Exam.DoesNotExist:
                        django_messages.warning(request, 'The exam no longer exists.')
                        return HttpResponseRedirect(reverse('student_course_list'))
            except (ValueError, IndexError):
                pass
        return HttpResponseRedirect(notification.link)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('all_notifications')))


def mark_all_notifications_read(request):
    if request.user.is_authenticated:
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('all_notifications')))


class ExamAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Exam
    template_name = 'exams/exam_analytics.html'
    context_object_name = 'exam'

    def dispatch(self, request, *args, **kwargs):
        self.exam = self.get_object()
        self.course_id = kwargs.get('course_id')
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        exam_id = self.kwargs.get('exam_id')
        return get_object_or_404(queryset, id=exam_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['course_id'] = self.course_id
        context['exam_id'] = self.exam.id
        graded_student_attempts = StudentExamAttempt.objects.filter(exam=self.exam, is_graded=True)
        context['student_attempts'] = graded_student_attempts

        if graded_student_attempts.exists():
            scores_list = [attempt.score for attempt in graded_student_attempts]
            context['avg_score'] = sum(scores_list) / len(scores_list)
            context['max_score'] = max(scores_list) if scores_list else 0
            context['min_score'] = min(scores_list) if scores_list else 0
            context['passing_score'] = self.exam.passing_score

            passed_count = sum(1 for score in scores_list if score >= self.exam.passing_score)
            context['pass_rate'] = (passed_count / len(
                graded_student_attempts)) * 100 if graded_student_attempts.exists() else 0

            total_score = self.exam.total_score
            context['score_ranges'] = {
                '90-100%': sum(1 for s in scores_list if s >= Decimal(0.9) * total_score),
                '80-89%': sum(1 for s in scores_list if Decimal(0.8) * total_score <= s < Decimal(0.9) * total_score),
                '70-79%': sum(1 for s in scores_list if Decimal(0.7) * total_score <= s < Decimal(0.8) * total_score),
                '60-69%': sum(1 for s in scores_list if Decimal(0.6) * total_score <= s < Decimal(0.7) * total_score),
                'Below 60%': sum(1 for s in scores_list if s < Decimal(0.6) * total_score)
            }

        #     Question analysis
        questions = self.exam.questions.all()
        question_stats = []
        for question in questions:
            answers = StudentExamAnswer.objects.filter(
                attempt__in=graded_student_attempts,
                question=question
            )
            if answers.exists():
                avg_score = sum(answer.awarded_score for answer in answers) / answers.count()
                max_possible = question.score
                question_stats.append({
                    'question': question,
                    'avg_score': avg_score,
                    'max_possible': max_possible,
                    'percent': (avg_score / max_possible) * 100 if max_possible else 0
                })

        question_stats.sort(key=lambda x: x['percent'])
        context['question_stats'] = question_stats

        total_enrolled = self.exam.course.course_enrollment.count()

        return context

    def test_func(self):
        course_owners = self.exam.course.owners.all()
        return self.request.user.is_superuser or self.request.user in course_owners


class CourseAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Course
    template_name = 'courses/course_analytics.html'
    context_object_name = 'course'

    def dispatch(self, request, *args, **kwargs):
        self.course = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        course_id = self.kwargs.get('course_id')
        return get_object_or_404(queryset, id=course_id)

    def _attempt_passed(self,attempt):
        if attempt.exam.passing_score is not None:
            return (attempt.score or 0) >= attempt.exam.passing_score
        if attempt.exam.total_score:
            return ((attempt.score or 0) / attempt.exam.total_score) * 100 >= 50
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get All Academic Years
        selected_year_id = self.request.GET.get('academic_year')
        all_academic_years = AcademicYear.objects.all().order_by('-start_date')
        context['academic_years'] = all_academic_years

        if selected_year_id == '':
            selected_year = None
        elif selected_year_id:
            selected_year = AcademicYear.objects.filter(id=selected_year_id).first()
        else:
            selected_year = AcademicYear.objects.filter(is_current=True).first()
            if not selected_year and all_academic_years.exists():
                selected_year = all_academic_years.first()
        context['selected_year'] = selected_year

        # How many students enrolled in this course?
        # How many students have completed this course?
        enrollments = StudentCourseEnrollment.objects.filter(course=self.course)
        if selected_year:
            enrollments = enrollments.filter(academic_year=selected_year)

        # Add student data
        student_data = []
        for enrollment in enrollments.select_related('student', 'academic_year'):
            # Add student's completion status
            completion = StudentCourseCompletion.objects.filter(enrollment=enrollment).first()

            # Get the student's related valid exam attempts
            student_attempts = StudentExamAttempt.objects.filter(enrollment=enrollment,
                                                                 is_finalized=True,
                                                                 is_graded=True
                                                                 ).select_related('exam')

            # Calculate metrics
            exams_taken = student_attempts.count()
            avg_score = 0

            if exams_taken > 0:
                avg_score = student_attempts.aggregate(
                    avg_score=Avg(Case(
                        When(exam__total_score__gt=0,
                             then=F('score') * 100 / F('exam__total_score')),
                        default=0,
                        output_field=FloatField()
                    ))
                )['avg_score'] or 0

            # Prepare exam details
            exam_details = []
            has_failed_final_exam = False
            is_avg_below_50 = False
            status = 'in_progress'
            for attempt in student_attempts:
                percentage_score = 0
                if attempt.exam.total_score > 0:
                    percentage_score = (attempt.score / attempt.exam.total_score) * 100

                exam_details.append({
                    'attempt_id': attempt.id,
                    'exam_id': attempt.exam.id,
                    'exam_title': attempt.exam.title,
                    'attempt_date': attempt.completed_at,
                    'raw_score': attempt.score,
                    'percentage_score': percentage_score,
                    'passing_score': attempt.exam.passing_score,
                    'total_score': attempt.exam.total_score,
                    'has_passed': self._attempt_passed(attempt),
                    'feedback': attempt.instructor_feedback
                })

                final_attempts = [a for a in student_attempts if getattr(a.exam, 'is_final', False)]
                if final_attempts:
                    has_failed_final_exam = any(not self._attempt_passed(a) for a in final_attempts)

                is_avg_below_50 = exams_taken > 0 and (avg_score or 0) < 50

                if completion is not None:
                    status = 'completed'
                elif exams_taken == 0:
                    status = 'in_progress'
                elif has_failed_final_exam or is_avg_below_50:
                    status = 'failed'
                else:
                    status = 'in_progress'

            student_data.append({
                'enrollment': enrollment,
                'student': enrollment.student,
                'exams_taken': exams_taken,
                'avg_score': avg_score,
                'completion': completion,
                'is_completed': completion is not None,
                'completion_date': completion.completed_date if completion else None,
                'exam_details': exam_details,
                'has_failed_final_exam': has_failed_final_exam,
                'is_avg_below_50': is_avg_below_50,
                'status': status
            })

        context['student_data'] = student_data

        context['total_enrollments'] = enrollments.count()
        context['completion_count'] = StudentCourseCompletion.objects.filter(enrollment__in=enrollments).count()

        # What percentage of the enrolled students completed this course?
        if context['total_enrollments'] > 0:
            context['completion_rate'] = (context['completion_count'] / context['total_enrollments']) * 100
        else:
            context['completion_rate'] = 0

        # Get exam statistics
        course_exams = Exam.objects.filter(course=self.course)

        if selected_year:
            exams_year = StudentExamAttempt.objects.filter(enrollment__academic_year=selected_year,
                                                           exam__course=self.course
                                                           ).values_list('exam', flat=True).distinct()
            course_exams = course_exams.filter(Q(academic_year=selected_year) |
                                               Q(id__in=exams_year))

        exam_attempts = StudentExamAttempt.objects.filter(exam__in=course_exams,
                                                          enrollment__in=enrollments,
                                                          is_finalized=True,
                                                          is_graded=True)

        context['exam_attempts_count'] = exam_attempts.count()

        # What is the average score of the exam attempts?
        if exam_attempts.exists():
            context['average_score'] = exam_attempts.aggregate(
                avg_score=Avg(
                    Case(
                        When(exam__total_score__gt=0,
                             then=F('score') * 100 / F('exam__total_score')),
                        default=0,
                        output_field=FloatField()
                    )
                )
            )['avg_score'] or 0
        else:
            context['average_score'] = 0

        # What is the performance in specific year?
        stats_by_year = {}
        for year in all_academic_years:
            year_enrollments = enrollments.filter(academic_year=year)
            if year_enrollments.exists():
                year_attempts = StudentExamAttempt.objects.filter(enrollment__in=year_enrollments,
                                                                  is_finalized=True,
                                                                  is_graded=True)

                year_stats = {
                    'total_enrollments': year_enrollments.count(),
                    'total_exams_taken': year_attempts.values('exam').distinct().count(),
                    'average_score': year_attempts.aggregate(
                        avg_score=Avg(
                            Case(
                                When(exam__total_score__gt=0,
                                     then=F('score') * 100 / F('exam__total_score')),
                                default=0,
                                output_field=FloatField()
                            )
                        )
                    )['avg_score'] or 0,
                    'completed_courses': StudentCourseCompletion.objects.filter(enrollment__in=year_enrollments).count()
                }
                if year_stats['total_enrollments'] > 0:
                    year_stats['completion_rate'] = (year_stats['completed_courses'] / year_stats[
                        'total_enrollments']) * 100
                else:
                    year_stats['completion_rate'] = 0
                stats_by_year[year] = year_stats
        context['stats_by_year'] = stats_by_year

        exam_stats = {}
        context['course_exams'] = course_exams
        for exam in course_exams:
            exam_attempts_for_this = exam_attempts.filter(exam=exam)
            if exam_attempts_for_this.exists():
                scores_list = list(exam_attempts_for_this.values_list('score', flat=True))
                passing_count = sum(1 for score in scores_list if score >= exam.passing_score)

                exam_stats[exam.id] = {
                    'title': exam.title,
                    'attempts': exam_attempts_for_this.count(),
                    'avg_score': sum(scores_list) / len(scores_list) if scores_list else 0,
                    'avg_percent': (sum(scores_list) / len(scores_list)) / exam.total_score * 100 if scores_list and exam.total_score else 0,
                    'pass_rate': (passing_count / exam_attempts_for_this.count()) * 100 if exam_attempts_for_this.count() > 0 else 0,
                    'max_score': max(scores_list) if scores_list else 0,
                    'min_score': min(scores_list) if scores_list else 0,
                }
        context['exam_stats'] = exam_stats

        if not selected_year:
            context['exams_count'] = StudentExamAttempt.objects.filter(
                exam__course=self.course,
                is_finalized=True,
                is_graded=True
            ).values('exam').distinct().count()
        else:
            context['exams_count'] = len(exam_stats)

        # Student Score Distribution
        if exam_attempts.exists():
            normalized_scores = []
            for attempt in exam_attempts:
                if attempt.exam.total_score > 0:
                    normalized_scores.append((attempt.score / attempt.exam.total_score) * 100)

            context['score_distribution'] = {
                '90-100%': sum(1 for s in normalized_scores if s >= 90),
                '80-89%': sum(1 for s in normalized_scores if 80 <= s < 90),
                '70-79%': sum(1 for s in normalized_scores if 70 <= s < 80),
                '60-69%': sum(1 for s in normalized_scores if 60 <= s < 70),
                '50-59%': sum(1 for s in normalized_scores if 50 <= s < 60),
                'Below 50%': sum(1 for s in normalized_scores if s < 50)
            }

        pprint(context)
        return context

    def test_func(self):
        course = self.get_object()
        return self.request.user.is_superuser or self.request.user in course.owners.all()

class PaymentManagementView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = StudentCourseEnrollment
    template_name = 'admin/courses/payment_management.html'
    context_object_name = 'enrollments'
    paginate_by = 20

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = StudentCourseEnrollment.objects.select_related('student', 'course', 'academic_year','payment').order_by('-enrollment_date')

        # For filters
        student = self.request.GET.get('student')
        course = self.request.GET.get('course')
        academic_year = self.request.GET.get('academic_year')
        payment_status = self.request.GET.get('payment_status')

        if student:
            queryset = queryset.filter(student__username__icontains=student)
        if course:
            queryset = queryset.filter(course__title__icontains=course)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if payment_status:
            queryset = queryset.filter(payment__transaction__status=payment_status)

        return queryset

    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        context['academic_years'] = AcademicYear.objects.all()
        context['payment_statuses'] =Transaction._meta.get_field('status').choices
        return context

class ManageCourseCompletionsView(LoginRequiredMixin,UserPassesTestMixin,ListView):
    model = StudentCourseCompletion
    template_name = 'courses/manage/completions.html'
    context_object_name = 'enrollments'
    paginate_by = 20

    def get_queryset(self):
        queryset = StudentCourseEnrollment.objects.select_related('student',
                                                                  'course',
                                                                  'academic_year',
                                                                  'completion'
                                                                  ).order_by('-enrollment_date')

        student = self.request.GET.get('student')
        course = self.request.GET.get('course')
        academic_year = self.request.GET.get('academic_year')
        completion_status = self.request.GET.get('completion_status')

        if student:
            queryset = queryset.filter(student__username__icontains=student)
        if course:
            queryset = queryset.filter(course__title__icontains=course)
        if academic_year:
            queryset = queryset.filter(academic_year_id=academic_year)
        if completion_status:
            if completion_status == 'completed':
                queryset = queryset.filter(completion__isnull=False)
            elif completion_status == 'not_completed':
                queryset = queryset.filter(completion__isnull=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['academic_years'] = AcademicYear.objects.all()
        context['completion_statuses'] = [('completed', 'Completed'),
                                          ('not_completed', 'Not Completed')]

        return context

    def test_func(self):
        return self.request.user.is_staff

@login_required
def mark_course_completed(request, course_id, enrollment_id):
    enrollment = get_object_or_404(StudentCourseEnrollment, id=enrollment_id)
    course = enrollment.course

    if not request.user.is_staff:
        return HttpResponseForbidden("You don't have permission to perform this action.")

    completion, created = StudentCourseCompletion.objects.get_or_create(enrollment=enrollment)

    if created or not completion.certificate_issued:
        completion.certificate_issued = True
        completion.save()

    if created:
        create_notification(user=enrollment.student,
                            message=f'You have successfully completed the course "{course.title}" and your certificate is now available',
                            link=reverse('student_certificate', args=[course_id, completion.id]))

        django_messages.success(request, f"{enrollment.student.username} has been marked as having completed the course.")
    else:
        django_messages.info(request, f"{enrollment.student.username} has already completed the course.")
    return redirect('manage_course_completions')

@login_required
def revoke_course_completion(request, course_id, completion_id):
    completion = get_object_or_404(StudentCourseCompletion, id=completion_id)
    student = completion.enrollment.student
    course = completion.enrollment.course

    if not request.user.is_staff:
        return HttpResponseForbidden("You don't have permission to perform this action.")

    completion.delete()

    create_notification(user=student,
                        message=f'Your completion of the course "{course.title}" has been revoked. Please contact your instructor.',
                        link=reverse('student_course_detail', args=[course.id]))

    django_messages.success(request,
                            f"Completion status for {student.username} has been revoked.")

    return redirect('manage_course_completions')

