from django.conf import settings
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.utils.html import format_html

from .models import *
from django.contrib.auth.models import User


# Register your models here.
@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug','order']
    prepopulated_fields = {'slug':('title',)}
    list_editable = ['order']

class ModuleInline(admin.StackedInline):
    model = Module

class EnrolledStudentInline(admin.TabularInline):
    model = StudentCourseEnrollment
    extra = 0
    fk_name = 'course'

class OwnerFilter(admin.SimpleListFilter):
    title = 'Instructor'
    parameter_name = 'owner'

    def lookups(self, request, model_admin):
        instructors = User.objects.filter(groups__name='Instructors')
        return [(instructor.id, instructor.get_full_name()) for instructor in instructors]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(owners__id=self.value())
        return queryset

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'subject', 'instructors','created','slug','student_count']
    list_filter = ['created', 'subject', OwnerFilter]
    search_fields = ['title', 'overview']
    prepopulated_fields = {'slug':('title',)}
    inlines = [ModuleInline, EnrolledStudentInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.distinct()


    def student_count(self, obj):
        return obj.course_enrollment.count()

    student_count.short_description = 'Enrolled Students'
    student_count.admin_order_field ='course_enrollment'

    def instructors(self, obj):
        return ", ".join([owner.get_full_name() for owner in obj.owners.all()])

    instructors.short_description = 'Instructors'
    instructors.admin_order_field ='owners'

# @admin.register(Profile)
# class ProfileAdmin(admin.ModelAdmin):
#     list_display = ['user', 'image']
#
#     def profile_image(self, obj):
#         if obj.image and obj.image.url:
#             return format_html('<img src="{}" style="width: 50px; height: 50px;" />', obj.image.url)
#         else:
#             default_url = f"{settings.MEDIA_URL}images/profile_pics/default.png"
#             return format_html('<img src="{}" style="width: 50px; height: 50px;" />', default_url)
#
#     profile_image.short_description = 'Profile Picture'


class StudentExamAttemptInline(admin.TabularInline):
    model = StudentExamAttempt
    extra = 0
    readonly_fields = ['student', 'started_at', 'completed_at', 'score', 'is_finalized']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'start_time', 'end_time', 'attempt_count']
    inlines = [StudentExamAttemptInline]

    def attempt_count(self, obj):
        return obj.studentexamattempt_set.count()

    attempt_count.short_description = 'Attempts'



# @admin.register(Question)
# class QuestionAdmin(admin.ModelAdmin):
#     list_display = ['text']

# @admin.register(Answer)
# class AnswerAdmin(admin.ModelAdmin):
#     list_display = ['text']

# @admin.register(Exercise)
# class ExerciseAdmin(admin.ModelAdmin):
#     list_display = ['title','course','module','visible']
#     list_editable = ['visible']

# @admin.register(ExerciseQuestion)
# class ExerciseQuestionAdmin(admin.ModelAdmin):
#     list_display = ['exercise','question','order']


@admin.register(StudentExamAttempt)
class StudentExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam', 'started_at', 'completed_at', 'score', 'is_finalized']
    list_filter = ['is_finalized', 'exam', 'started_at']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'exam__title']
    date_hierarchy = 'started_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('enrollment__student', 'exam')


class StudentExamAnswerInline(admin.TabularInline):
    model = StudentExamAnswer
    extra = 0
    readonly_fields = ['question', 'selected_answer', 'boolean_answer', 'essay_answer', 'uploaded_file', 'is_correct']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# @admin.register(StudentExamAnswer)
# class StudentExamAnswerAdmin(admin.ModelAdmin):
#     list_display = ['student_name', 'exam_title', 'question_text', 'answer_display', 'is_correct', 'awarded_score']
#     list_filter = ['is_correct', 'attempt__exam', 'question__question_type']
#     search_fields = ['attempt__enrollment__student__username', 'attempt__enrollment__student__first_name', 'attempt__enrollment__student__last_name',
#                      'attempt__exam__title', 'question__text']
#     readonly_fields = ['attempt', 'question', 'selected_answer', 'boolean_answer', 'essay_answer', 'uploaded_file',
#                        'is_correct']
#     fields = ['attempt', 'question', 'selected_answer', 'boolean_answer', 'essay_answer', 'uploaded_file', 'is_correct',
#               'awarded_score', 'feedback']
#
#     def student_name(self, obj):
#         return f"{obj.attempt.student.first_name} {obj.attempt.student.last_name}" if obj.attempt.student.first_name else obj.attempt.student.username
#
#     student_name.short_description = 'Student'
#     student_name.admin_order_field = 'attempt__enrollment__student__username'
#
#     def exam_title(self, obj):
#         return obj.attempt.exam.title
#
#     exam_title.short_description = 'Exam'
#     exam_title.admin_order_field = 'attempt__exam__title'
#
#     def question_text(self, obj):
#         return obj.question.text[:50] + '...' if len(obj.question.text) > 50 else obj.question.text
#
#     question_text.short_description = 'Question'
#
#     def answer_display(self, obj):
#         if obj.question.question_type == 'MCQ' and obj.selected_answer:
#             return obj.selected_answer.text
#         elif obj.question.question_type == 'TF' and obj.boolean_answer is not None:
#             return 'True' if obj.boolean_answer else 'False'
#         elif obj.question.question_type == 'ESSAY':
#             essay_text = obj.essay_answer[:50] + '...' if obj.essay_answer and len(
#                 obj.essay_answer) > 50 else obj.essay_answer
#             file_info = f" [File: {obj.uploaded_file.name.split('/')[-1]}]" if obj.uploaded_file else ""
#             return f"{essay_text or 'No text'}{file_info}"
#         return 'No answer'
#
#     answer_display.short_description = 'Answer'
#
#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'attempt', 'attempt__enrollment__student', 'attempt__exam', 'question', 'selected_answer'
#         )


@admin.register(StudentCourseEnrollment)
class StudentCourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'academic_year', 'enrollment_date']
    list_filter = ['academic_year', 'enrollment_date']
    search_fields = ['student__username', 'course__title']
    raw_id_fields = ['student', 'course']

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date']
    search_fields = ['name']
    list_filter = ['start_date', 'end_date']


@admin.register(StudentCourseCompletion)
class StudentCourseCompletionAdmin(admin.ModelAdmin):
    list_display = ['get_student', 'get_course', 'get_academic_year', 'completed_date', 'certificate_issued']
    list_filter = ['certificate_issued', 'completed_date']
    search_fields = ['enrollment__student__username', 'enrollment__course__title']

    def get_student(self, obj):
        return obj.enrollment.student.username

    get_student.short_description = 'Student'

    def get_course(self, obj):
        return obj.enrollment.course.title

    get_course.short_description = 'Course'

    def get_academic_year(self, obj):
        return obj.enrollment.academic_year.name

    get_academic_year.short_description = 'Academic Year'

@admin.register(CoursePayment)
class CoursePaymentAdmin(admin.ModelAdmin):
    list_display = ['enrollment','amount','get_payment_date','get_status','get_transaction_id']
    list_filter = ['transaction__status','transaction__payment_date']
    search_fields = ['enrollment__student__username', 'enrollment__course__title','transaction__transaction_id']
    change_list_template = 'admin/courses/coursepayment/change_list.html'


    def get_payment_date(self,obj):
        return obj.transaction.payment_date if obj.transaction else None
    get_payment_date.short_description = 'Payment Date'
    get_payment_date.admin_order_field = 'transaction__payment_date'

    def get_status(self,obj):
        return obj.transaction.status if obj.transaction else None
    get_status.short_description = 'Status'
    get_status.admin_order_field = 'transaction__status'

    def get_transaction_id(self,obj):
        return obj.transaction.transaction_id if obj.transaction else None
    get_transaction_id.short_description = 'Transaction ID'
    get_transaction_id.admin_order_field = 'transaction__transaction_id'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('enrollment__student', 'enrollment__course', 'transaction')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['student','transaction_id','payment_date','status','total_amount','receipt_number']
    list_filter = ['status','payment_date']
    search_fields = ['student__username','transaction_id','receipt_number']

