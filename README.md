# Introduction
- - -

This is a Django project made for my thesis where I developed a portal for educational institutions.

The project includes instructors, students, courses, exams and more.

# Instructions #
- - -

## Installation ##
- - -

1.Download and install Python from [here](https://www.python.org/downloads/).

2.Download and install PyCharm from [here](https://www.jetbrains.com/pycharm/download/?section=windows) or any other IDE of your choice.

3.Clone the repository.

4.Create a virtual environment using ```py -m venv env```

5.Activate the virtual environment env using ```.\env\Scripts\activate```.

6.Navigate to the project folder with the command ```cd .\educa```.

7.Install the requirements using the command ```pip install -r requirements.txt```.

_**Notes**_:

If you want to start from scratch, then:

1. Delete the db.sqlite3 file and run the command ```py .\manage.py migrate```. This will automatically create a new clean database.

2. Clear the files from the media folder and subfolders. Keep the default.jpg file.

## Configuration ##
- - -

Rename ```.env.sample```  file to ```.env``` and change the variables:

### Django Secret Key
- - -

Open the Python Console and run the following commands:
```
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
 ```
Then replace _DJANGO_SECRET_KEY_ with the output.

### Email (Optional)
- - -
To enable email functionality,  
Replace _EMAIL_HOST_USER_ and _EMAIL_HOST_PASSWORD_ with your credentials.

### Stripe
- - -

It is strongly recommended to enable Stripe for the enrollments to work as intended.

You can create a sandbox stripe account.

1.Login to the Stripe Dashboard.

2.Replace _STRIPE_SECRET_KEY_ and _STRIPE_PUBLISHABLE_KEY_ with your credentials.

3.Download stripe CLI from the official [GitHub](https://github.com/stripe/stripe-cli/releases).

4.Unzip the file.

5.Open the cmd inside the unzipped folder.

6.Run the command ```.\stripe login```.

7.Run the command ```.\stripe listen --forward-to http://localhost:8000/students/webhook/stripe/```.

### Ngrok (Optional)
- - -

Ngrok is used to make the project accessible from the internet.

You can create a free account on [NGROK](https://dashboard.ngrok.com/signup).

1.Login to NGROK.

2.Download ngrok.

3.Unzip the file.

4.Open the cmd inside the unzipped folder.

5.If it is your first time running ngrok on your machine, add the auth token.

6.Deploy the ngrok server using the command ```ngrok http --url=Your URL Your Port```.

## Running the project ##
- - - 

If it is your first time running this project then create a superuser using the command ```py .\manage.py createsuperuser``` and follow the instructions.

Run the command ```py .\manage.py runserver```.

The project will be available at ```http://127.0.0.1:8000/```.

The admin panel will be available at ```http://127.0.0.1:8000/admin/```.

Login using the superuser credentials you created.

## First Time Setup
- - -
In case you have started the project from scratch, then you will need:
1. To create a User Group named 'Instructors'
2. To create an Academic Year and set it as active.

To designate a user as an Instructor, go to the user profile and add the user to the 'Instructors' User Group.

To assign a course to an Instructor, go to the course page and add the Instructor to the owner field.

# Final Notes
- - - 

## Database
- - -

The project includes an SQLite database filled with sample data and files.

Feel free to create your own database and populate it with your own data.

## Browser
- - -

I suggest using a browser that allows for multiple different identities (e.g. Ghost Browser) to avoid excessive login and logouts between different accounts.

_**Example**_:

* Identity #1 - Admin
* Identity #2 - Instructor
* Identity #3 - Student

Thanks for reading!




