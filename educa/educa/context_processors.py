from django.urls import resolve, reverse

from courses.models import *


def breadcrumbs(request):
    breadcrumbs = [{'name': 'Home', 'url': '/'}]

    try:
        resolver_match = resolve(request.path_info)
        url_name = resolve(request.path_info).url_name
        kwargs = resolver_match.kwargs

        if url_name == 'student_course_list':
            breadcrumbs.append({'name': 'My Courses', 'url': None})

        elif url_name == 'student_course_detail':
            course = Course.objects.get(id=kwargs.get('pk'))
            is_instructor = request.user.groups.filter(name="Instructors").exists()
            if not is_instructor:
                breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
            else:
                breadcrumbs.append({'name': 'Manage Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': course.title, 'url': None})

        elif url_name == 'student_course_detail_module':
            course = Course.objects.get(id=kwargs.get('pk'))
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
            breadcrumbs.append({'name': course.title, 'url': f'/students/course/{course.id}/'})
            if module_id:
                try:
                    module = Module.objects.get(id=module_id)
                    breadcrumbs.append({'name': module.title, 'url': None})
                except Module.DoesNotExist:
                    pass

        elif url_name == 'student_profile':
            breadcrumbs.append({'name': 'Profile', 'url': None})

        elif url_name == 'course_detail':
            course_slug = kwargs.get('slug')
            if course_slug:
                try:
                    course = Course.objects.get(slug=course_slug)
                    subject = Subject.objects.get(id=course.subject.id)
                    breadcrumbs.append({'name': subject.title, 'url': reverse('course_list_subject', args=(subject.slug,))})
                    breadcrumbs.append({'name': course.title, 'url': None})
                except Course.DoesNotExist:
                    pass

        elif url_name == 'course_delete':
            course_id = kwargs.get('pk')
            if course_id:
                try:
                    course = Course.objects.get(id=course_id)
                    breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
                    breadcrumbs.append({'name': 'Delete Course', 'url': None})
                except Course.DoesNotExist:
                    pass
        elif url_name == 'course_list_subject':
            subject_slug = kwargs.get('subject')
            if subject_slug:
                try:
                    subject = Subject.objects.get(slug=subject_slug)
                    breadcrumbs.append({'name': subject.title, 'url': None})
                except Subject.DoesNotExist:
                    pass
        elif url_name == 'student_exam_list':
            breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
            course_id = kwargs.get('course_id')
            if course_id:
                try:
                    course = Course.objects.get(id=course_id)
                    breadcrumbs.append({'name': course.title + ' Exams', 'url': f'/students/course/{course_id}/'})
                    # breadcrumbs.append({'name': 'Exams', 'url': None})
                except Course.DoesNotExist:
                    pass
        elif url_name == 'student_exam_detail':
            breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            if course_id and exam_id:
                try:
                    course = Course.objects.get(id=course_id)
                    exam = Exam.objects.get(id=exam_id)
                    breadcrumbs.append({'name': course.title + ' Exams', 'url': f'/students/course/{course_id}/exams/'})
                    # breadcrumbs.append({'name': 'Exams', 'url': f'/students/course/{course_id}/exams/'})
                    breadcrumbs.append({'name': exam.title, 'url': None})
                except (Course.DoesNotExist, Exam.DoesNotExist):
                    pass
        elif url_name == 'student_exam_result':
            breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            if course_id and exam_id:
                try:
                    course = Course.objects.get(id=course_id)
                    exam = Exam.objects.get(id=exam_id)
                    breadcrumbs.append({'name': course.title + ' Exams', 'url': f'/students/course/{course_id}/exams/'})
                    # breadcrumbs.append({'name': 'Exams', 'url': f'/students/course/{course_id}/exams/'})
                    breadcrumbs.append({'name': exam.title, 'url': f'/students/course/{course_id}/exams/{exam_id}/'})
                    breadcrumbs.append({'name': 'Results', 'url': None})
                except (Course.DoesNotExist, Exam.DoesNotExist):
                    pass
        elif url_name == 'manage_course_list':
            breadcrumbs.append({'name': 'My Courses', 'url': '/students/courses/'})
        elif url_name == 'course_edit':
            course_id = kwargs.get('pk')
            if course_id:
                try:
                    course = Course.objects.get(id=course_id)
                    breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
                    # breadcrumbs.append({'name': course.title, 'url': f'/students/course/{course_id}/edit/'})
                    breadcrumbs.append({'name': course.title + ' - Edit', 'url': None})
                except Course.DoesNotExist:
                    pass
        elif url_name == 'course_module_update':
            course_id = kwargs.get('pk')
            if course_id:
                try:
                    course = Course.objects.get(id=course_id)
                    breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
                    breadcrumbs.append({'name':  course.title + ' - Edit Modules', 'url': None})
                except Course.DoesNotExist:
                    pass
        elif url_name == 'module_content_list':
            course = Course.objects.get(id=kwargs.get('course_id'))
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': course.title + ' - Manage Content', 'url': None})

        elif url_name == 'module_content_update':
            course_id = kwargs.get('course_id')
            course = Course.objects.get(id=kwargs.get('course_id'))
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
            breadcrumbs.append({'name': 'Edit Content', 'url': None})

        elif url_name == 'exercise_detail':
            course_id = kwargs.get('course_id')
            module_id = kwargs.get('module_id')
            exercise_id = kwargs.get('pk')

            is_instructor = request.user.groups.filter(name="Instructors").exists()

            if is_instructor:
                breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
                breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
                breadcrumbs.append({'name': 'View Exercise', 'url': None})
            else:
                course = Course.objects.get(id=course_id)
                module = Module.objects.get(id=module_id)
                exercise = Exercise.objects.get(id=exercise_id)

                breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
                breadcrumbs.append({'name': course.title, 'url': reverse('student_course_detail', args=(course_id,))})
                breadcrumbs.append({'name': module.title, 'url': reverse('student_course_detail_module', args=(course_id, module_id,))})
                breadcrumbs.append({'name': exercise.title, 'url': None})

        elif url_name == 'exercise_update':
            course_id = kwargs.get('course_id')
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
            breadcrumbs.append({'name': 'Edit Exercise', 'url': None})

        elif url_name == 'exercise_delete':
            course_id = kwargs.get('course_id')
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
            breadcrumbs.append({'name': 'Delete Exercise', 'url': None})

        elif url_name == 'module_content_create':
            course_id = kwargs.get('course_id')
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
            breadcrumbs.append({'name': 'Add Content', 'url': None})

        elif url_name == 'exercise_create':
            course_id = kwargs.get('course_id')
            module_id = kwargs.get('module_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Content', 'url': reverse('module_content_list', args=(course_id, module_id,))})
            breadcrumbs.append({'name': 'Add Exercise', 'url': None})

        elif url_name == 'exam_manage':
            course_id = kwargs.get('course_id')
            course = Course.objects.get(id=course_id)
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': f'{course.title} - Manage Exams', 'url': None})

        elif url_name == 'exam_add_questions':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': 'Add Questions', 'url': None})

        elif url_name == 'exam_update':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': 'Edit Exam', 'url': None})

        elif url_name == 'exam_delete':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': 'Delete Exam', 'url': None})

        elif url_name == 'grade_management_console':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            exam_title = Exam.objects.get(id=exam_id).title
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': f"{exam_title} Grade Management", 'url': None})

        elif url_name == 'grade_student_exam':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            exam_title = Exam.objects.get(id=exam_id).title
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': f'{exam_title} Grade Management', 'url': reverse('grade_management_console', args=(course_id,exam_id,))})
            breadcrumbs.append({'name': 'Grade Student Exam', 'url': None})

        elif url_name == 'exam_create':
            course_id = kwargs.get('course_id')
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': 'Add Exam', 'url': None})

        elif url_name == 'course_create':
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Add Course', 'url': None})

        elif url_name == 'exam_analytics':
            course_id = kwargs.get('course_id')
            exam_id = kwargs.get('exam_id')
            exam_title = Exam.objects.get(id=exam_id).title
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': 'Manage Exams', 'url': reverse('exam_manage', args=(course_id,))})
            breadcrumbs.append({'name': f'{exam_title} Grade Management',
                                'url': reverse('grade_management_console', args=(course_id, exam_id,))})
            breadcrumbs.append({'name': 'Exam Analytics', 'url': None})

        elif url_name == 'student_analytics':
            breadcrumbs.append({'name': 'Profile', 'url': reverse('student_profile')})
            breadcrumbs.append({'name': 'My Analytics', 'url': None})

        elif url_name == 'student_enrollment':
            breadcrumbs.append({'name': 'Course Enrollments', 'url': None})

        elif url_name == 'course_analytics':
            course_id = kwargs.get('course_id')
            course = Course.objects.get(id=course_id)
            breadcrumbs.append({'name': 'My Courses', 'url': reverse('manage_course_list')})
            breadcrumbs.append({'name': f'{course.title} - Course Analytics', 'url': None})

        elif url_name == 'student_receipts':
            breadcrumbs.append({'name': 'Profile', 'url': reverse('student_profile')})
            breadcrumbs.append({'name': 'My Receipts', 'url': None})

        elif url_name == 'payment_receipt':
            if not request.user.is_staff:
                transaction_id = kwargs.get('pk')
                transaction = Transaction.objects.get(id=transaction_id)
                receipt_number = transaction.receipt_number
                breadcrumbs.append({'name': 'Profile', 'url': reverse('student_profile')})
                breadcrumbs.append({'name': 'My Receipts', 'url': reverse('student_receipts')})
                breadcrumbs.append({'name': f'Receipt # {receipt_number}', 'url': None})

        elif url_name == 'student_certificates':
            breadcrumbs.append({'name': 'Profile', 'url': reverse('student_profile')})
            breadcrumbs.append({'name': 'My Certificates', 'url': None})

        elif url_name == 'student_certificate':
            breadcrumbs.append({'name': 'Profile', 'url': reverse('student_profile')})
            breadcrumbs.append({'name': 'My Certificates', 'url': reverse('student_certificates')})
            completion_id = kwargs.get('completion_id')
            completion = StudentCourseCompletion.objects.get(id=completion_id)
            completion_id = completion.id
            breadcrumbs.append({'name': f'Certificate ID {completion_id}' , 'url': None})

        elif url_name == 'admin_certificate':
            breadcrumbs.append({'name': 'Dashboard', 'url': reverse('manage_course_completions')})
            completion_id = kwargs.get('completion_id')
            breadcrumbs.append({'name': f'Certificate ID {completion_id}' , 'url': None})

    except Exception:
        print(f'Error in breadcrumbs context processor: {Exception}')
        print(f'Resolver match: {resolver_match}')
        print(f'URL name: {url_name}')
        print(f'Kwargs: {kwargs}')

    return {'breadcrumbs': breadcrumbs}

def notifications_processor(request):
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(user=request.user,
                                                           is_read=False).order_by('-created_at')[:5]

        unread_count = Notification.objects.filter(user=request.user,
                                                   is_read=False).count()

        return {
            'unread_notifications': unread_notifications,
            'unread_count': unread_count,
        }

    return {
        'unread_notifications': [],
        'unread_count': 0,
    }
