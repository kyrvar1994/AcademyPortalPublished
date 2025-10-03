from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View
from django.views.generic.edit import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic.edit import FormView
from .forms import CourseEnrollForm, UserRegistrationForm, StudentProfileUpdateForm, ProfileImageUpdateForm
from django.views.generic.list import ListView
from courses.models import *
from django.views.generic.detail import DetailView
from courses.forms import *
from django.db.models import Count, Avg, Sum, Case, When, FloatField, F
from django.conf import settings
import stripe
import logging
from django.http import HttpResponse


class StudentRegistrationView(CreateView):
    template_name = 'students/student/registration.html'
    form_class = UserRegistrationForm
    success_url = reverse_lazy('student_course_list')

    def form_valid(self, form):
        # Save the user object without committing to the database
        user = form.save(commit=False)

        # Set the password for the user
        user.set_password(form.cleaned_data['password1'])
        user.save()

        Profile.objects.get_or_create(user=user)

        # Authenticate the user with the provided username and password
        cd = form.cleaned_data
        user = authenticate(username=cd['username'], password=cd['password1'])

        # Check if the user is successfully authenticated
        if user is not None:
            # Log in the user
            login(self.request, user)
            return super().form_valid(form)
        else:
            # If authentication fails, return an error (optional handling)
            form.add_error(None, "Authentication failed. Please try again.")
            return self.form_invalid(form)


class StudentEnrollCourseView(LoginRequiredMixin, FormView):
    course = None
    form_class = CourseEnrollForm

    def get(self, request, *args, **kwargs):
        return redirect('student_enrollment')

    def form_valid(self, form):
        courses = form.cleaned_data['courses']
        academic_year = form.cleaned_data['academic_year']

        for course in courses:
            StudentCourseEnrollment.objects.get_or_create(student=self.request.user,
                                                          course=course,
                                                          academic_year=academic_year)
        self.course = courses[0] if courses else None
        return super().form_valid(form)

    def get_success_url(self):
        if self.course:
            return reverse_lazy(
                'student_course_detail', args=[self.course.id]
            )
        return reverse_lazy('student_course_list')


class StudentEnrollmentView(LoginRequiredMixin, FormView):
    form_class = CourseEnrollForm
    template_name = 'students/course/enroll.html'
    success_url = reverse_lazy('course_payment')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_year = AcademicYear.objects.filter(is_current=True).first()
        context['current_academic_year'] = current_year

        form = context['form']

        subjects_with_courses = {}
        for course in form.all_courses:
            if course.subject not in subjects_with_courses:
                subjects_with_courses[course.subject] = []
            subjects_with_courses[course.subject].append({
                'course': course,
                'unavailable': course.id in form.unavailable_courses,
                'price': course.price,
            })
        context['subjects_with_courses'] = subjects_with_courses

        all_courses = []
        for subject_courses in subjects_with_courses.values():
            all_courses.extend(subject_courses)

        context['courses'] = all_courses
        return context

    def form_valid(self, form):
        courses = form.cleaned_data['courses']
        academic_year = form.cleaned_data['academic_year']

        self.request.session['selected_courses'] = [course.id for course in courses]
        self.request.session['selected_academic_year'] = academic_year.id

        return super().form_valid(form)


class StudentCourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = 'students/course/list.html'

    def get_queryset(self):
        enrollments = StudentCourseEnrollment.objects.filter(student=self.request.user)
        return Course.objects.filter(id__in=enrollments.values_list('course_id', flat=True))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollments = StudentCourseEnrollment.objects.filter(student=self.request.user
                                                             ).select_related('course', 'academic_year')
        enrollments_with_completion = []
        for enrollment in enrollments:
            completion = StudentCourseCompletion.objects.filter(enrollment=enrollment).first()
            enrollment.completion_status = completion
            enrollments_with_completion.append(enrollment)
        context['enrollments'] = enrollments_with_completion
        return context


class StudentCourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = 'students/course/detail.html'

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return Course.objects.all()

        enrollments = StudentCourseEnrollment.objects.filter(student=user)
        enrolled_courses = Course.objects.filter(id__in=enrollments.values_list('course_id', flat=True))

        owned_courses = Course.objects.filter(owners=user)

        return (enrolled_courses | owned_courses).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()

        context['enrollments'] = StudentCourseEnrollment.objects.filter(student=self.request.user,
                                                                        course=course
                                                                        ).select_related('academic_year')
        if 'module_id' in self.kwargs:
            context['module'] = course.modules.get(
                id=self.kwargs['module_id']
            )
            # print(context)
        else:
            modules = course.modules.all()
            if modules.exists():
                context['module'] = modules[0]
            else:
                context['module'] = None

        if context['module']:
            context['available_exercises'] = Exercise.objects.filter(course=course, module=context['module'],
                                                                     visible=True)
        else:
            context['available_exercises'] = []
        return context


class StudentProfile(LoginRequiredMixin, TemplateView):
    template_name = 'students/student/student_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, created = Profile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        return context


class StudentProfileUpdateView(LoginRequiredMixin, UpdateView, SuccessMessageMixin):
    model = User
    form_class = StudentProfileUpdateForm
    template_name = 'students/student/update_profile.html'
    success_url = reverse_lazy('student_profile')
    success_message = "Your profile has been updated successfully."

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        # print("Form was valid - adding success message and redirecting...")
        messages.success(self.request, self.success_message)
        # print(f"Success message: {self.success_message}")
        return super().form_valid(form)


class ProfileImageUpdateView(LoginRequiredMixin, UpdateView):
    model = Profile
    form_class = ProfileImageUpdateForm
    success_url = reverse_lazy('student_profile')

    def get_object(self, queryset=None):
        return self.request.user.profile

    def form_valid(self, form):
        profile = self.get_object()

        #        old_image_path = None
        #        if form.instance.image and form.instance.image.url != '/media/images/profile_pics/default.jpg':
        #            old_image_path = form.instance.image.path
        #        print(f"Old image path: {old_image_path}")

        self.object = form.save()

        #        print('before second if')
        #        print(f"File exists: {os.path.exists(old_image_path)}")
        #        if old_image_path and os.path.exists(old_image_path):
        #            try:
        #
        #                print("Inside second if try")
        #                os.remove(old_image_path)
        #            except Exception as e:
        #                pdb.set_trace()
        #               print(f"Error removing old image: {e}")
        #        pdb.set_trace()
        #        print('after second if')
        messages.success(self.request, "Your profile image has been updated successfully.")
        return super().form_valid(form)


class StudentExamListView(LoginRequiredMixin, ListView):
    template_name = 'students/exam/exam_list.html'
    model = Exam

    def dispatch(self, request, *args, **kwargs):
        self.course = Course.objects.get(id=self.kwargs['course_id'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        enrollment = StudentCourseEnrollment.objects.filter(student=self.request.user,
                                                            course=self.course).first()
        if enrollment:
            return qs.filter(course=self.course,
                             is_active=True,
                             academic_year=enrollment.academic_year)
        return Exam.objects.none()

    def _exam_status_for_student(self, exam, user):
        now = timezone.localtime(timezone.now())
        start = timezone.localtime(exam.start_time)
        end = timezone.localtime(exam.end_time)

        enrollment = StudentCourseEnrollment.objects.filter(student=user,
                                                            course=exam.course,
                                                            ).first()
        attempt = StudentExamAttempt.objects.filter(exam=exam,
                                                    enrollment=enrollment
                                                    ).first()

        is_active_window = start <= now <= end
        has_taken_exam = bool(attempt and attempt.is_finalized)
        in_progress = bool(attempt and not attempt.is_finalized and is_active_window)
        results_available = bool(has_taken_exam and exam.is_graded and attempt and attempt.is_graded)

        if now < start:
            return {
                'label': 'Not Available Yet',
                'style': 'gray',
                'action': None,
            }

        if is_active_window:
            if in_progress:
                return {
                    'label': 'In Progress',
                    'style': 'warning',
                    'action': {
                        'text': 'Resume',
                        'url': reverse_lazy('student_take_exam', kwargs={'course_id': exam.course.id,
                                                                         'exam_id': exam.id})
                    }
                }

            if not has_taken_exam:
                return {
                    'label': 'Active',
                    'style': 'green',
                    'action': None,
                }

            if results_available:
                return {
                    'label': 'Results Available',
                    'style': 'blue',
                    'action': {
                        'text': 'View',
                        'url': reverse_lazy('student_exam_result', kwargs={'course_id': exam.course.id,
                                                                           'exam_id': exam.id,
                                                                           'exam_attempt_id': attempt.id,
                                                                           })
                    }
                }
            return {
                'label': 'Pending Results',
                'style': 'warning',
                'action': {
                    'text': 'Details',
                    'url': reverse_lazy('student_exam_detail', kwargs={'course_id': exam.course.id,
                                                                       'exam_id': exam.id})
                }
            }

        if has_taken_exam:
            if results_available:
                return {
                    'label':'Results Available',
                    'style': 'blue',
                    'action': {
                        'text': 'View',
                        'url': reverse_lazy('student_exam_result', kwargs={
                            'course_id': exam.course.id,
                            'exam_id': exam.id,
                            'exam_attempt_id': attempt.id
                        })
                    }
                }
            return {
                'label': 'Pending Results',
                'style': 'warning',
                'action': {
                    'text': 'Details',
                    'url': reverse_lazy('student_exam_detail', kwargs={
                        'course_id': exam.course.id,
                        'exam_id': exam.id
                    })
                }
            }

        return {
            'label': 'Expired',
            'style': 'red',
            'action': None,
        }


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exams = context['object_list']
        user = self.request.user

        items = []
        for exam in exams:
            status = self._exam_status_for_student(exam,user)
            items.append({
                'exam': exam,
                'status': status['label'],
                'status_style': status['style'],
                'action': status.get('action'),
            })
        context['course'] = self.course
        context['exam_items'] = items
        # pprint(f"StudentExamListView context: {context}")
        return context


class StudentExamDetailView(LoginRequiredMixin, DetailView):
    model = Exam
    template_name = 'students/exam/exam_details.html'

    def get_object(self, queryset=None):
        return Exam.objects.get(id=self.kwargs['exam_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = self.get_object()
        user = self.request.user

        now_utc = timezone.now()
        now_user_tz = timezone.localtime(now_utc)
        exam_start_user_tz = timezone.localtime(exam.start_time)
        exam_end_user_tz = timezone.localtime(exam.end_time)

        is_exam_active = exam_start_user_tz <= now_user_tz <= exam_end_user_tz

        # print(f'is_exam_active: {is_exam_active}')
        # print(f'exam_start_user_tz: {exam_start_user_tz}')
        # print(f'now_utc: {now_utc}')
        # print(f'now_user_tz: {now_user_tz}')
        # print(f'exam_end_user_tz: {exam_end_user_tz}')

        enrollment = StudentCourseEnrollment.objects.filter(student=user,
                                                            course=exam.course).first()
        attempt = StudentExamAttempt.objects.filter(exam=exam, enrollment=enrollment).first()
        has_taken_exam = attempt is not None and attempt.is_finalized
        in_progress = attempt is not None and not attempt.is_finalized and is_exam_active

        results_available = has_taken_exam and exam.is_graded and attempt.is_graded

        context['course_id'] = self.kwargs['course_id']
        context['exam_id'] = self.kwargs['exam_id']
        context['is_exam_active'] = is_exam_active
        context['has_taken_exam'] = has_taken_exam
        context['in_progress_attempt'] = in_progress
        context['can_take_exam'] = is_exam_active and not has_taken_exam
        context['results_available'] = results_available

        if has_taken_exam:
            context['attempt'] = attempt
        # print(f"StudentExamDetailView context: {context}")
        return context


class StudentTakeExamView(LoginRequiredMixin, FormView):
    template_name = 'students/exam/exam.html'
    form_class = ExamAnswerForm

    def dispatch(self, request, *args, **kwargs):
        # print('StudentTakeExamView')
        # print('Entering dispatch function')
        # pdb.set_trace()
        self.exam = Exam.objects.get(id=self.kwargs['exam_id'])
        self.course = Course.objects.get(id=self.kwargs['course_id'])

        now = timezone.localtime(timezone.now())
        exam_start = timezone.localtime(self.exam.start_time)
        exam_end = timezone.localtime(self.exam.end_time)

        if not (exam_start <= now <= exam_end):
            # messages.error(request, "The exam is not currently active.")
            print('The exam is not currently active.')
            return redirect('student_exam_detail', course_id=self.course.id, exam_id=self.exam.id)

        enrollment = StudentCourseEnrollment.objects.filter(student=self.request.user,
                                                            course=self.course).first()
        existing_attempt = StudentExamAttempt.objects.filter(exam=self.exam, enrollment=enrollment).first()
        if existing_attempt:
            if existing_attempt.is_finalized:
                messages.error(request, "You have already completed this exam.")
                print('You have already completed this exam.')
                return redirect('student_exam_detail', course_id=self.course.id, exam_id=self.exam.id)
            else:
                self.attempt = existing_attempt
        else:

            self.attempt = StudentExamAttempt.objects.create(exam=self.exam,
                                                             enrollment=enrollment,
                                                             is_finalized=False)
            request.session['current_question_index'] = 1

        if 'action' in request.POST:
            action = request.POST.get('action')
            current_index = request.session.get('current_question_index', 1)

            # Before changing page save answer
            questions = list(self.exam.questions.all())
            if questions and current_index <= len(questions):
                current_question = questions[current_index - 1]
                self.save_answer(current_question, None)

            if action == 'next' and current_index < self.exam.questions.count():
                request.session['current_question_index'] = current_index + 1
            elif action == 'prev' and current_index > 1:
                request.session['current_question_index'] = current_index - 1

        if 'current_question_index' not in request.session:
            request.session['current_question_index'] = 1

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # print('Entering get_context_data function')
        # pdb.set_trace()
        context = super().get_context_data(**kwargs)
        context['exam'] = self.exam
        context['course'] = self.course
        context['attempt'] = self.attempt
        questions = list(self.exam.questions.all())
        context['total_questions'] = len(questions)

        current_index = self.request.session.get('current_question_index', 1)
        if current_index > len(questions):
            current_index = len(questions)
        if questions:
            context['current_question'] = questions[current_index - 1]
            context['current_question_index'] = current_index
            context['current_progress'] = (current_index / len(questions)) * 100
        else:
            context['current_question'] = None
            context['current_question_index'] = 0
            context['current_progress'] = 0

        context['answers'] = {}
        for question in questions:
            answer = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                      question=question).first()
            if answer:
                context['answers'][question.id] = answer

        return context

    def get_form_kwargs(self):
        # print('Entering get_form_kwargs function')
        # pdb.set_trace()
        kwargs = super().get_form_kwargs()

        current_index = self.request.session.get('current_question_index', 1)
        questions = list(self.exam.questions.all())

        if questions and current_index > len(questions):
            current_index = len(questions)

        if questions and current_index <= len(questions):
            current_question = questions[current_index - 1]
            kwargs['questions'] = [current_question]
        else:
            kwargs['questions'] = []

        initial_data = {}
        if questions and current_index <= len(questions):
            current_question = questions[current_index - 1]
            answer = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                      question=current_question).first()

            if answer:
                if current_question.question_type == "MCQ" and answer.selected_answer:
                    initial_data[f"question_{current_question.id}"] = answer.selected_answer.id
                elif current_question.question_type == "TF":
                    initial_data[f"question_{current_question.id}"] = answer.is_correct
                elif current_question.question_type == "ESSAY":
                    initial_data[f"question_{current_question.id}"] = answer.essay_answer

        if 'initial' in kwargs:
            kwargs['initial'].update(initial_data)
        else:
            kwargs['initial'] = initial_data
        return kwargs

    def form_valid(self, form):
        # print('Entering form_valid function')
        # pdb.set_trace()
        action = self.request.POST.get('action', '')
        current_index = self.request.session.get('current_question_index', 1)
        questions = list(self.exam.questions.all())

        # print(f"DEBUG - questions: {questions}")
        # print(f"DEBUG - current_index: {current_index}")
        # print(f"DEBUG - len(questions): {len(questions)}")

        # Save the current question's answer
        if current_index > len(questions):
            current_index = len(questions)
        if questions:
            current_question = questions[current_index - 1]
            # print(f"DEBUG - Adjusted current_index: {current_index}")
            # try:
            self.save_answer(current_question, form)
            # except Exception as e:
            # print(f"Error saving answer: {e}")

        # Update total score
        auto_graded_score = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                             awarded_score__isnull=False
                                                             ).aggregate(Sum('awarded_score'))[
                                'awarded_score__sum'] or 0
        self.attempt.score = auto_graded_score
        self.attempt.save()

        # print(f"DEBUG - request.FILES: {self.request.FILES}")
        # Redirects depending on action
        if action == "submit":
            self.attempt.completed_at = timezone.now()
            self.attempt.is_finalized = True
            self.attempt.save()
            messages.success(self.request, "Your exam has been submitted successfully.")
            return redirect('student_exam_detail', course_id=self.course.id, exam_id=self.exam.id)
        elif action == 'save':
            messages.success(self.request,
                             "Your exam has been saved but NOT submitted. You must click 'Submit Exam' to complete your exam.")
            return redirect('student_exam_detail', course_id=self.course.id, exam_id=self.exam.id)
        elif action in ['next', 'prev']:
            return redirect('student_take_exam', course_id=self.course.id, exam_id=self.exam.id)
        else:
            return redirect('student_take_exam', course_id=self.course.id, exam_id=self.exam.id)

    def save_answer(self, question, form):
        # print('Entering save_answer function')
        # pdb.set_trace()
        if question.question_type == "MCQ":
            answer_id = self.request.POST.get(f"question_{question.id}")
            if not answer_id:
                return
            selected_answer = Answer.objects.get(id=answer_id) if answer_id else None
            is_correct = selected_answer.is_correct if selected_answer else False

            student_answer = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                              question=question).first()
            if student_answer:
                student_answer.selected_answer = selected_answer
                student_answer.boolean_answer = None
                student_answer.essay_answer = None
                student_answer.is_correct = is_correct
                student_answer.awarded_score = question.score if is_correct else 0
                student_answer.save()
            else:
                StudentExamAnswer.objects.create(attempt=self.attempt,
                                                 question=question,
                                                 selected_answer=selected_answer,
                                                 boolean_answer=None,
                                                 essay_answer=None,
                                                 is_correct=is_correct,
                                                 awarded_score=question.score if is_correct else 0,
                                                 )
        elif question.question_type == "TF":
            answer_value = self.request.POST.get(f"question_{question.id}")
            if not answer_value:
                return
            if answer_value == "True":
                boolean_value = True
            else:
                boolean_value = False
            is_correct = (boolean_value == question.is_true)

            student_answer = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                              question=question).first()
            if student_answer:
                student_answer.selected_answer = None
                student_answer.boolean_answer = boolean_value
                student_answer.essay_answer = None
                student_answer.is_correct = is_correct
                student_answer.awarded_score = question.score if is_correct else 0
                student_answer.save()
            else:
                StudentExamAnswer.objects.create(attempt=self.attempt,
                                                 question=question,
                                                 selected_answer=None,
                                                 boolean_answer=boolean_value,
                                                 essay_answer=None,
                                                 is_correct=is_correct,
                                                 awarded_score=question.score if is_correct else 0,
                                                 )

        elif question.question_type == "ESSAY":
            # print(f"ESSAY DEBUG - Question ID: {question.id}")

            essay_answer = self.request.POST.get(f"question_{question.id}", "")
            # print(f"ESSAY DEBUG - Raw essay answer: '{essay_answer}'")
            # print(f"ESSAY DEBUG - Raw essay answer length: {len(essay_answer)}")
            # print(f"ESSAY DEBUG - Raw essay answer type: {type(essay_answer)}")

            essay_answer = essay_answer.strip()
            # print(f"ESSAY DEBUG - Stripped essay answer: '{essay_answer}'")
            # print(f"ESSAY DEBUG - Stripped essay answer length: {len(essay_answer)}")

            uploaded_file = self.request.FILES.get(f'file_question_{question.id}')
            # if uploaded_file:
            # print(f"DEBUG - File name: {uploaded_file.name}, size: {uploaded_file.size}")

            student_answer = StudentExamAnswer.objects.filter(attempt=self.attempt,
                                                              question=question).first()
            # print(f"ESSAY DEBUG - Existing student answer: {student_answer}")

            if student_answer:
                # print(f"ESSAY DEBUG - Updating existing answer")
                student_answer.selected_answer = None
                student_answer.boolean_answer = None
                student_answer.essay_answer = essay_answer
                if uploaded_file:
                    student_answer.uploaded_file = uploaded_file
                student_answer.is_correct = False
                student_answer.awarded_score = None
                student_answer.save()
                # print(f"ESSAY DEBUG - Updated answer saved: '{student_answer.essay_answer}'")
            else:
                # print(f"ESSAY DEBUG - Creating new answer")
                new_answer = StudentExamAnswer.objects.create(attempt=self.attempt,
                                                              question=question,
                                                              selected_answer=None,
                                                              boolean_answer=None,
                                                              essay_answer=essay_answer,
                                                              uploaded_file=uploaded_file,
                                                              is_correct=False,
                                                              awarded_score=None,
                                                              )
                # print(f"ESSAY DEBUG - New answer created: '{new_answer.essay_answer}'")


#


class StudentExamResultsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = StudentExamAttempt
    template_name = 'students/exam/exam_results.html'

    def dispatch(self, request, *args, **kwargs):
        self.course_id = kwargs.get('course_id')
        self.exam_id = kwargs.get('exam_id')
        self.attempt_id = kwargs.get('exam_attempt_id')
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        user = self.request.user
        attempt = self.get_object()
        course = Course.objects.get(id=self.course_id)

        if user.is_superuser or user.is_staff or user in course.owners.all():
            return True

        return attempt.enrollment.student == user

    def get_object(self, queryset=None):
        return get_object_or_404(
            StudentExamAttempt,
            id=self.attempt_id,
            exam_id=self.exam_id,
            exam__course_id=self.course_id,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.get_object()
        exam = attempt.exam

        context['course_id'] = self.course_id
        context['exam_id'] = self.exam_id
        context['attempt'] = attempt
        context['total_score'] = attempt.score if attempt else 0
        context['max_score'] = exam.total_score
        context['percentage'] = (attempt.score / exam.total_score * 100) if attempt and exam.total_score > 0 else 0
        context['answers'] = attempt.answers.all() if attempt else []

        return context


class StudentAnalyticsDashboard(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'students/student/student_analytics.html'

    def test_func(self):
        return self.request.user.is_authenticated

    def dispatch(self, request, *args, **kwargs):
        self.user = self.request.user
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Academic Year
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

        context['user'] = self.user

        all_enrollments = StudentCourseEnrollment.objects.filter(student=self.user)
        enrollments_by_year = {}
        for year in all_academic_years:
            year_enrollments = all_enrollments.filter(academic_year=year)
            if year_enrollments.exists():
                enrollments_by_year[year] = year_enrollments
        context['enrollments_by_year'] = enrollments_by_year

        if selected_year:
            enrollments = all_enrollments.filter(academic_year=selected_year)
        else:
            enrollments = all_enrollments
        context['enrollments'] = enrollments

        courses = Course.objects.filter(id__in=enrollments.values_list('course', flat=True))
        context['courses'] = courses

        exams = Exam.objects.filter(course__in=courses)
        context['exams'] = exams

        exam_attempts = StudentExamAttempt.objects.filter(enrollment__in=all_enrollments,
                                                          is_finalized=True,
                                                          is_graded=True)
        context['attempts'] = exam_attempts

        attempts_by_year_course = {}
        for year in all_academic_years:
            attempts_by_year_course[year] = {}
            year_enrollments = all_enrollments.filter(academic_year=year)
            for enrollment in year_enrollments:
                course = enrollment.course
                if course not in attempts_by_year_course[year]:
                    attempts_by_year_course[year][course] = []

                course_attempts = exam_attempts.filter(enrollment=enrollment)
                attempts_by_year_course[year][course].extend(course_attempts)
        context['attempts_by_year_course'] = attempts_by_year_course

        stats_by_year = {}
        for year, year_enrollments in enrollments_by_year.items():
            year_attempts = StudentExamAttempt.objects.filter(enrollment__in=year_enrollments,
                                                              is_finalized=True,
                                                              is_graded=True)

            year_stats = {
                'total_enrollments': year_enrollments.count(),
                'total_exams': year_attempts.count(),
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
            stats_by_year[year] = year_stats
        context['stats_by_year'] = stats_by_year

        context['overall_stats'] = {
            'total_enrollments': enrollments.count(),
            'total_exams_taken': StudentExamAttempt.objects.filter(enrollment__in=enrollments,
                                                                   is_finalized=True).count(),
            'average_score': StudentExamAttempt.objects.filter(enrollment__in=enrollments,
                                                               is_finalized=True,
                                                               is_graded=True).aggregate(
                avg_score=Avg(
                    Case(
                        When(exam__total_score__gt=0,
                             then=F('score') * 100 / F('exam__total_score')),
                        default=0,
                        output_field=FloatField()
                    )
                )
            )['avg_score'] or 0,
            'completed_courses': StudentCourseCompletion.objects.filter(enrollment__in=enrollments).count()
        }

        if selected_year:
            context['selected_year_stats'] = stats_by_year.get(selected_year, {})

        # pprint(f"Student Analytics Dashboard Context: {str(context)}")
        return context


# Payments
stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger('students')


class CoursePaymentView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        # Get course and academic year
        courses_ids = request.session.get('selected_courses', [])
        academic_year_id = request.session.get('selected_academic_year')

        logger.debug({
            "Selected courses ids": courses_ids,
            "Selected academic year": academic_year_id,
        })

        if not courses_ids or not academic_year_id:
            return redirect('student_enrollment')

        courses = Course.objects.filter(id__in=courses_ids)
        academic_year = get_object_or_404(AcademicYear, id=academic_year_id)

        # Υπολογισμός συνόλου
        total_amount = sum(course.price for course in courses)

        # Δημιουργία line items
        line_items = []
        for course in courses:
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'unit_amount': int(course.price * 100),
                    'product_data': {
                        'name': course.title,
                        'description': course.overview[:255],  # Περιορισμός μήκους
                    },
                },
                'quantity': 1,
            })

        # Δημιουργία συνεδρίας πληρωμών Stripe
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                success_url=request.build_absolute_uri(reverse('payment_success')),
                cancel_url=request.build_absolute_uri(reverse('payment_cancel')),
                client_reference_id=f"{request.user.id}_{academic_year_id}_{','.join(map(str, courses_ids))}",
            )
            return redirect(checkout_session.url)
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            messages.error(request, "An error occurred while processing your payment. Please try again later.")
            return redirect('student_enrollment')

    def get(self, request, *args, **kwargs):
        courses_ids = request.session.get('selected_courses', [])
        academic_year_id = request.session.get('selected_academic_year')

        if courses_ids and academic_year_id:
            return self.post(request, *args, **kwargs)
        else:
            messages.warning(request, "Please select courses before proceeding to payment.")
            return redirect('student_enrollment')


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'students/payment/success.html'

    # Κατά την επιτυχία της συναλλαγής, καθαρίζουμε ό,τι έχει απομείνει για ασφάλεια
    def get(self, request, *args, **kwargs):
        if 'selected_courses' in request.session:
            del request.session['selected_courses']
        if 'selected_academic_year' in request.session:
            del request.session['selected_academic_year']
        return super().get(request, *args, **kwargs)


class PaymentCancelView(LoginRequiredMixin, TemplateView):
    template_name = 'students/payment/cancel.html'

    def get(self, request, *args, **kwargs):
        if 'selected_courses' in request.session:
            del request.session['selected_courses']
        if 'selected_academic_year' in request.session:
            del request.session['selected_academic_year']
        return super().get(request, *args, **kwargs)


@csrf_exempt
def stripe_webhook(request):
    # Get request and signature
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']

    # Authenticate
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # When payment completed
    if event['type'] == 'checkout.session.completed':
        # Get data
        session = event['data']['object']

        # From data get
        client_reference_id = session.get('client_reference_id')
        if client_reference_id:
            # split client_reference_id
            parts = client_reference_id.split('_')
            if len(parts) >= 3:
                user_id = parts[0]
                academic_year_id = parts[1]
                courses_ids = parts[2].split(',')

                try:
                    # Get
                    user = User.objects.get(id=user_id)
                    academic_year = AcademicYear.objects.get(id=academic_year_id)
                    courses = Course.objects.filter(id__in=courses_ids)

                    # Calculate Total Amount
                    total_amount = sum(course.price for course in courses)

                    # Create transaction for all courses
                    transaction = Transaction.objects.create(
                        student=user,
                        transaction_id=session.get('payment_intent'),
                        total_amount=total_amount,
                        status='completed',
                    )

                    transaction.generate_receipt_number()

                    # For every course the student enrolls in
                    for course in courses:
                        # Create the Enrollment
                        enrollment, created = StudentCourseEnrollment.objects.get_or_create(
                            student=user,
                            course=course,
                            academic_year=academic_year,
                        )

                        # Create the Payment
                        CoursePayment.objects.create(
                            transaction=transaction,
                            enrollment=enrollment,
                            amount=course.price,
                        )


                except (User.DoesNotExist, AcademicYear.DoesNotExist):
                    pass

    return HttpResponse(status=200)


class PaymentReceiptView(LoginRequiredMixin, DetailView):
    model = Transaction
    template_name = 'students/payment/receipt.html'
    context_object_name = 'transaction'

    def get_queryset(self):
        return Transaction.objects.filter(student=self.request.user,
                                            status='completed')


class AdminPaymentReceiptView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Transaction
    template_name = 'students/payment/receipt.html'
    context_object_name = 'transaction'
    pk_url_kwarg = 'transaction_id'

    def test_func(self):
        return self.request.user.is_staff


class StudentReceiptsView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'students/payment/receipts_list.html'
    context_object_name = 'transactions'

    def get_queryset(self):
        return Transaction.objects.filter(student=self.request.user,
                                            status='completed').order_by('-payment_date')

class StudentCertificatesListView(LoginRequiredMixin,ListView):
    model = StudentCourseCompletion
    template_name = 'students/student/certificate_list.html'
    context_object_name = 'completions'

    def get_queryset(self):
        return StudentCourseCompletion.objects.filter(
            enrollment__student=self.request.user,
            certificate_issued=True
        ).select_related('enrollment__course', 'enrollment__academic_year')

class StudentCertificateView(LoginRequiredMixin,DetailView):
    model = StudentCourseCompletion
    template_name = 'courses/certificate.html'
    context_object_name = 'completion'
    pk_url_kwarg = 'completion_id'

    def get_queryset(self):
        return StudentCourseCompletion.objects.filter(
            enrollment__student=self.request.user,
            certificate_issued=True
        )

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)

        completion = self.get_object()
        if not completion.certificate_issued:
            completion.certificate_issued = True
            completion.save()

        return response

class AdminCertificateView(LoginRequiredMixin,UserPassesTestMixin,DetailView):
    model = StudentCourseCompletion
    template_name = 'courses/certificate.html'
    context_object_name = 'completion'
    pk_url_kwarg = 'completion_id'

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return StudentCourseCompletion.objects.filter(
            certificate_issued=True
        ).select_related('enrollment__course', 'enrollment__student', 'enrollment__academic_year')