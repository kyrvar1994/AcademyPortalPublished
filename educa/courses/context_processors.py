def is_instructor_processor(request):
    if request.user.is_authenticated:
        is_instructor = request.user.groups.filter(name="Instructors").exists()
    else:
        is_instructor = False
    return {"is_instructor": is_instructor}