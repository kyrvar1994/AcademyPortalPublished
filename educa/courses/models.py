import uuid
from itertools import count
from os.path import abspath

from django.core.mail import send_mail
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import F, FloatField, Avg, Case, When
from django.db.models.fields import return_None
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify

from educa.utils import build_absolute_uri
from .fields import OrderField
from django.template.loader import render_to_string



# Create your models here.
#We are gonna have Subject, Course, Content
#For Example Subject = Mathematics, Courses = Math 1, Math 2 and Content = Text/Image/Video

class Subject(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    duration = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0,)
    class Meta:
        ordering = ['order']
    def __str__(self):
        return self.title


class Course(models.Model):
    #Who created the course
    owners = models.ManyToManyField(User,
                                    related_name='courses_created',
                                    blank=True)
    subject = models.ForeignKey(Subject,
                                related_name='courses',
                                on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200,
                            unique=True,
                            auto_created=True)
    overview = models.TextField()
    duration = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True) #set when new object is created
    price = models.DecimalField(max_digits=10,decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0,)

    class Meta:
        ordering = ['order'] # - means descending order
    def __str__(self):
        return self.title
    def save(self,*args,**kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args,**kwargs)

class Module(models.Model):
    course = models.ForeignKey(Course,
                               related_name='modules',
                               on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = OrderField(blank=True, for_fields=['course'])
    def __str__(self):
        #return self.title
        return f'{self.order}.{self.title}'
    class Meta:
        ordering = ['order']

class Content(models.Model):
    module = models.ForeignKey(Module,
                               related_name='contents',
                               on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType,
                                     on_delete= models.CASCADE,
                                     limit_choices_to={'model__in':('text','video','image','file','exercise')})
    object_id = models.PositiveIntegerField()
    item = GenericForeignKey('content_type', 'object_id')
    order = OrderField(blank=True, for_fields=['module'])
    class Meta:
        ordering = ['order']

class ItemBase(models.Model):
    owner = models.ForeignKey(User,
                              related_name='%(class)s_related',
                              on_delete=models.CASCADE)
    title = models.CharField(max_length=250)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True
    def __str__(self):
        return self.title

    def render(self):
        return render_to_string(
            f'courses/content/{self._meta.model_name}.html',
            {'item': self}
        )

class Text(ItemBase):
    content = models.TextField()

class File(ItemBase):
    file = models.FileField(upload_to='files')

class Image(ItemBase):
    file = models.FileField(upload_to='images')

class Video(ItemBase):
    url = models.URLField()

class Profile(models.Model):
    user = models.OneToOneField(User,on_delete=models.CASCADE)
    image=models.ImageField(default='images/profile_pics/default.jpg',upload_to='images/profile_pics',null=True,blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'


QuestionTypes = (
    ('MCQ','Multiple Choice'),
    ('TF','True or False'),
    ('ESSAY','Essay'),)


class Question(models.Model):
    text = models.TextField()
    exercise = models.ForeignKey('Exercise',blank=True,on_delete=models.CASCADE,null=True)
    exam = models.ManyToManyField('Exam',blank=True, related_name='questions')
    question_type = models.CharField(max_length=200,choices=QuestionTypes, default='ESSAY')
    is_true = models.BooleanField(default=False,null=True,blank=True)
    score = models.DecimalField(max_digits=5,decimal_places=2,default=0)


    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question,blank=True,on_delete=models.CASCADE,null=True, related_name='answers')
    text = models.TextField(blank=True,null=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class Exercise(models.Model):
    title = models.CharField(max_length=200)
    question_description = models.TextField(blank=True,null=True)
    answer = models.TextField(blank=True,null=True)
    duration = models.DurationField(blank=True,null=True)
    course = models.ForeignKey(Course,on_delete=models.CASCADE,blank=True,null=True)
    module = models.ForeignKey(Module,on_delete=models.CASCADE,blank=True,null=True,related_name='exercises')
    question_file = models.FileField(upload_to='files/exercise_files/question_files',blank=True,null=True)
    answer_file = models.FileField(upload_to='files/exercise_files/answer_files',blank=True,null=True)
    visible = models.BooleanField(default=False)


    def __str__(self):
        return self.title

    @property
    def duration_hm(self):
        total_minutes = int(self.duration.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f'{hours:02d}:{minutes:02d}'





class AcademicYear(models.Model):
    name = models.CharField(max_length=9, help_text="Academic year in format YYYY-YYYY (e.g. 2024-2025)")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).exclude(id=self.id).update(is_current=False)
        super().save(*args, **kwargs)


class Exam(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True,null=True)
    duration = models.DurationField(blank=True,null=True)
    start_time = models.DateTimeField(blank=True,null=True)
    end_time = models.DateTimeField(blank=True,null=True)
    passing_score = models.DecimalField(max_digits=5,decimal_places=2,blank=True,null=True)
    total_score = models.DecimalField(max_digits=5,decimal_places=2,blank=True,null=True)
    attempts_allowed = models.PositiveIntegerField(blank=True,null=True)
    is_active = models.BooleanField(default=False)
    is_graded = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False, help_text="Mark this exam as the final exam for the course.")
    guid = models.UUIDField(unique=True,default=uuid.uuid4,editable=False)
    course = models.ForeignKey(Course,
                                related_name='exams',
                                on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear,on_delete=models.CASCADE,related_name='exams')


    def __str__(self):
        return self.title

    def all_attempts_graded(self):
        finalized_attempts = StudentExamAttempt.objects.filter(exam = self, is_finalized=True)

        if not finalized_attempts.exists():
            return False

        return all(attempt.is_graded for attempt in finalized_attempts)

class StudentCourseEnrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_enrollment')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='course_enrollment')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='academic_year_enrollment')
    enrollment_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_year')

    def __str__(self):
        return f'{self.student.username} enrolled {self.course.title} in {self.academic_year.name} on {self.enrollment_date.strftime("%Y-%m-%d")}.'


class StudentCourseCompletion(models.Model):
    enrollment = models.OneToOneField(StudentCourseEnrollment, on_delete=models.CASCADE, related_name='completion')
    completed_date = models.DateTimeField(auto_now_add=True)
    certificate_issued = models.BooleanField(default=False)

    def __str__(self):
       return f'{self.enrollment.student.username} completed {self.enrollment.course.title} in {self.enrollment.academic_year.name} on {self.completed_date.strftime("%Y-%m-%d")}.'





class StudentExamAttempt(models.Model):
    # student = models.ForeignKey(User,on_delete=models.CASCADE)
    enrollment = models.ForeignKey(StudentCourseEnrollment,on_delete=models.CASCADE,related_name='exam_attempts')
    exam = models.ForeignKey(Exam,on_delete=models.CASCADE)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True,null=True)
    score = models.DecimalField(max_digits=5,decimal_places=2,blank=True,null=True)
    instructor_feedback = models.TextField(blank=True,null=True)
    is_finalized = models.BooleanField(default=False)
    is_graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('enrollment','exam')

    @property
    def student(self):
        return self.enrollment.student

    def is_in_progress(self):
        return self.completed_at is None and not self.is_finalized


class StudentExamAnswer(models.Model):
    attempt = models.ForeignKey(StudentExamAttempt,on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question,on_delete=models.CASCADE)
    # MCQ
    selected_answer = models.ForeignKey(Answer,on_delete=models.CASCADE,blank=True,null=True)
    #TFQ
    boolean_answer = models.BooleanField(blank=True,null=True)
    #Essay
    essay_answer = models.TextField(blank=True,null=True)
    uploaded_file = models.FileField(upload_to='files/exam_files/student_answers',blank=True,null=True)

    is_correct = models.BooleanField()
    awarded_score = models.DecimalField(max_digits=5, decimal_places=2, null=True,blank=True)
    feedback = models.TextField(blank=True,null=True)

    def __str__(self):
        return f"Answer for {self.question.text} in {self.attempt.exam.title} by {self.attempt.student.username}"


# class StudentExamAttemptsReset(models.Model):
#     enrollment = models.ForeignKey(StudentCourseEnrollment,on_delete=models.CASCADE,related_name='exam_attempts_resets',blank=True,null=True)
#     # student = models.ForeignKey(User,on_delete=models.CASCADE)
#     exam = models.ForeignKey(Exam,on_delete=models.CASCADE)
#     reset_by = models.ForeignKey(User,on_delete=models.CASCADE,related_name='exam_resets')
#     reset_at = models.DateTimeField(auto_now_add=True)
#     reason = models.TextField(blank=True,null=True)
#
#     def __str__(self):
#         return f"{self.enrollment.student.username}'s attempt for {self.exam.title} reset by {self.reset_by.username}."

class Notification(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255,blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message[:30]}...'

class CoursePayment(models.Model):
    transaction = models.ForeignKey('Transaction',on_delete=models.CASCADE,related_name='payments',null=True,blank=True)
    enrollment = models.OneToOneField(StudentCourseEnrollment,on_delete=models.CASCADE,related_name='payment')
    amount = models.DecimalField(max_digits=10,decimal_places=2)

    def __str__(self):
        return f'{self.enrollment.student} - {self.enrollment.course} - {self.amount}'

class Transaction(models.Model):
    student=models.ForeignKey(User,on_delete=models.CASCADE,related_name='transactions')
    transaction_id=models.CharField(max_length=100,unique=True)
    payment_date=models.DateTimeField(auto_now_add=True)
    receipt_number=models.CharField(max_length=100,blank=True,null=True)
    total_amount=models.DecimalField(max_digits=10,decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Σε εκκρεμότητα'),
        ('completed', 'Ολοκληρώθηκε'),
        ('failed', 'Απέτυχε'),
        ('refunded', 'Επιστροφή χρημάτων'),
    ], default='pending')

    def __str__(self):
        return f'Transaction {self.receipt_number} - {self.student.username} - {self.total_amount}'

    def generate_receipt_number(self):
        if not self.receipt_number and self.status == 'completed':
            year = self.payment_date.strftime('%Y')
            month = self.payment_date.strftime('%m')
            count = Transaction.objects.filter(payment_date__year=self.payment_date.year,
                                                 payment_date__month=self.payment_date.month,
                                                 receipt_number__isnull=False
                                                 ).count() + 1
            self.receipt_number = f'{year}{month}{count:04d}'
            self.save()
        return self.receipt_number


@receiver(post_save,sender=StudentExamAttempt)
def update_exam_graded_status(sender,instance,**kwargs):
    exam = instance.exam
    was_graded = exam.is_graded

    if exam.all_attempts_graded():
        exam.is_graded = True
        exam.save()

        if not was_graded and exam.is_graded:
            graded_exam_student_notification(exam)

def create_notification(user,message, link=None):
    Notification.objects.create(user=user,
                                message=message,
                                link=link)

def send_exam_graded_email(student, exam, course, attempt):
    subject = f"Your exam {exam.title} for {course.title} has been graded!"

    relative_url = reverse('student_exam_result', args=(course.id,exam.id,attempt.id,))
    absolute_url = build_absolute_uri(relative_url)

    context = {
        'student_name': student.get_full_name() or student.username,
        'exam_title': exam.title,
        'course_title': course.title,
        'results_url': absolute_url,
        'attempt': attempt,
        'exam': exam,
        'course': course,
    }

    html_message = render_to_string('students/exam/emails/graded_exam_notification.html', context)
    plain_message = render_to_string('students/exam/emails/graded_exam_notification.txt',context)

    send_mail(subject=subject,
              message=plain_message,
              from_email='kyrvarop+academy@hotmail.com',
              recipient_list=[student.email],
              html_message=html_message)


def graded_exam_student_notification(exam):
    course = exam.course
    student_attempts =StudentExamAttempt.objects.filter(exam=exam,is_finalized=True,is_graded=True)

    for attempt in student_attempts:
        student = attempt.student

        relative_url = reverse('student_exam_result', args=(course.id,exam.id,attempt.id,))
        absolute_url = build_absolute_uri(relative_url)

        create_notification(user=student,
                            message=f'Your exam {exam.title} for {course.title} has been graded!',
                            link= absolute_url)

        send_exam_graded_email(student,exam,course,attempt)

        # Check if this is a final exam
        if exam.is_final:
            enrollment = attempt.enrollment
            academic_year = enrollment.academic_year

            # Check if student has completed the course
            completed, enrollment = check_course_completion(student, course, academic_year)
            if completed:
                # Create Completion record
                completion, created = StudentCourseCompletion.objects.get_or_create(enrollment=enrollment)

                if not completion.certificate_issued:
                    completion.certificate_issued = True
                    completion.save()

                # Notify student
                relative_url = reverse('student_certificate', args=(course.id, completion.id,))
                absolute_url = build_absolute_uri(relative_url)

                create_notification(user=student,
                                    message=f'Congratulations! You have completed the course "{course.title}" ',
                                    link=absolute_url,)


def get_student_average_score(student, course, academic_year):
    # We want to calculate the average performance of the student for a course

    # Get the enrollment
    enrollment = StudentCourseEnrollment.objects.filter(student=student,
                                                        course=course,
                                                        academic_year=academic_year).first()
    if not enrollment:
        return 0

    # Get the valid attempts
    attempts = StudentExamAttempt.objects.filter(enrollment=enrollment,
                                                 is_finalized=True,
                                                 is_graded=True)

    if not attempts.exists():
        return 0

    avg_score = attempts.aggregate(
        avg_score=Avg(
            Case(
                When(exam__total_score__gt=0,
                     then=F('score') * 100 / F('exam__total_score')),
                default=0,
                output_field=FloatField()
            )
        )
    )['avg_score'] or 0

    return avg_score

def check_course_completion(student,course, academic_year):
    # We want to check if the student has completed the course

    # Get the student enrollment
    enrollment = StudentCourseEnrollment.objects.filter(student=student,
                                                        course=course,
                                                        academic_year=academic_year).first()

    if not enrollment:
        return False, enrollment

    # If enrolled, then get all the final exams of this course and academic year
    final_exams = Exam.objects.filter(course=course,
                                      academic_year=academic_year,
                                      is_final=True)

    # Calculate the average score of the student in all the exams
    avg_score = get_student_average_score(student, course, academic_year)

    # Default passing score
    course_passing_grade = 50

    #If the performance of the student is greater than the base
    if avg_score >= course_passing_grade:
        # We check if the student has also successfully passed a final exam

        # For each final exam
        for exam in final_exams:
            # From the final exams we keep only the finalized and graded attempts
            attempt = StudentExamAttempt.objects.filter(enrollment=enrollment,
                                                        exam=exam,
                                                        is_finalized=True,
                                                        is_graded=True).first()

            # Check if the attempt is successful
            if attempt:
                passed_final = False
                if exam.passing_score is not None:
                    # If the score of the attempt is greater than the passing score, then the student has passed
                    passed_final = attempt.score >= exam.passing_score
                else:
                    # If there is no passing score, default to greater than 50%
                    passed_final = (attempt.score / exam.total_score * 100) >= 50

                # If the Student has also passed the final exam
                if passed_final:
                    # The student has completed the course
                    return True, enrollment

    return False, enrollment






