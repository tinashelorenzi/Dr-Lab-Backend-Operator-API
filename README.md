# Dr Lab LIMS (Laboratory Information Management System)

A Django-based Laboratory Information Management System for Dr Lab.

## Features

- Laboratory sample management
- Test result tracking
- User authentication and authorization
- API endpoints for integration
- Modern web interface

## Technology Stack

- **Backend**: Django 5.2+
- **API**: Django REST Framework
- **Database**: PostgreSQL (recommended)
- **Authentication**: Django's built-in auth system
- **Frontend**: Django templates (can be extended with React/Vue.js)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Dr-Lab-Backend-Operator-API
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Run database migrations:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

## Project Structure

```
dr_lab_lims/
├── dr_lab_lims/          # Main project settings
│   ├── settings.py       # Django settings
│   ├── urls.py          # Main URL configuration
│   ├── wsgi.py          # WSGI configuration
│   └── asgi.py          # ASGI configuration
├── manage.py            # Django management script
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Development

### Running Tests
```bash
python manage.py test
```

### Making Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Creating Apps
```bash
python manage.py startapp <app_name>
```

## API Documentation

The API documentation will be available at `/api/docs/` once the project is running.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Add your license information here]

## Contact

[Add contact information here] 