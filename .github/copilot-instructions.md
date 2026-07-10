# IAI-Gestion Copilot Instructions
## MODE ÉCONOMIQUE ÉTUDIANT (RÈGLES STRICTES)

### Concision obligatoire
- Réponses < 1500 tokens maximum
- Pas de "bien sûr", "voici", "certainement", "tout d'abord"
- Pas d'explications si non demandées
- Code sans commentaires superflus
- Vas droit au but

### Exemples de bons vs mauvais comportements
❌ "Bien sûr ! Voici comment vous pourriez implémenter une vue Django..."
✅ "`def ma_vue(request): return render(...)`"

❌ "Tout d'abord, il faut comprendre que le matricule suit le format..."
✅ "Format matricule : `XX.CMR.D014.XXXXA`"

### Gestion des tokens
- Une seule idée par réponse
- Si la tâche est longue, propose de la découper
- Priorité aux extraits de code courts (< 20 lignes)
## Project Overview
IAI-Gestion is a Django-based university management system for IAI-Cameroun (Institut Africain d'Informatique) in Douala, Cameroon. It manages students, professors, courses, grades, enrollments, and payments with a French interface using Tailwind CSS.

## Architecture
- **Framework**: Django 5.0 with modular app structure
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Frontend**: HTML5, Tailwind CSS, Font Awesome icons
- **Authentication**: Custom user model with matricule-based login
- **Language**: French (fr-fr), timezone Africa/Douala

## Key Components
- `apps/authentification`: Custom user model with roles (ETUDIANT, PROFESSEUR, ADMIN_*)
- `apps/etudiants`: Student management with documents and academic tracking
- `apps/cours`: Course scheduling, attendance, resources
- `apps/notes`: Grade management with evaluation types and bulletins
- `apps/inscriptions`: Enrollment and payment processing
- `apps/tableau_bord`: Dashboard with statistics and notifications

## Authentication Patterns
- **Custom Backend**: `MatriculeAuthBackend` allows login with matricule, email, or username
- **Matricule Format**: `XX.CMR.D014.XXXXA` (e.g., `GL.CMR.D014.2425A`)
- **User Types**: Defined in `Utilisateur.TYPE_UTILISATEUR` with role-based permissions

## Development Workflow
```bash
# Setup environment
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Load fixtures (optional)
python manage.py loaddata fixtures/initial_data.json

# Run development server
python manage.py runserver
```

## Coding Conventions
- **Models**: Use verbose French field names with `verbose_name` and `help_text`
- **Forms**: Extend `forms.ModelForm` with Crispy Forms and Tailwind styling
- **Views**: Class-based views with role-based access control
- **Templates**: Extend `base.html`, use Tailwind classes, include Font Awesome icons
- **URLs**: App-specific URL patterns in each app's `urls.py`

## Configuration Patterns
- **Settings**: Extensive config in `IAI_CONFIG`, `PAIEMENT_CONFIG`, etc.
- **Context Processors**: Site config, academic year, notifications in `tableau_bord.context_processors`
- **Logging**: File-based logging to `logs/iai_gestion.log`
- **Static/Media**: Served via Whitenoise in production

## Common Patterns
- **Status Fields**: Use choices with emoji prefixes (e.g., `'EN_ATTENTE': '⏳ En attente'`)
- **File Uploads**: Organize by date in `upload_to='path/%Y/%m/%d/'`
- **Validation**: Regex validators for matricules and phone numbers
- **Exports**: Use `django-import-export` for CSV/Excel/PDF generation
- **Notifications**: Email/console backend with configurable templates

## Database Relationships
- Students linked to Filiere and academic year
- Courses assigned to professors and enrolled students
- Grades tied to evaluations and bulletin generation
- Payments tracked with tranches and receipts

## Security Considerations
- CSRF protection enabled
- Role-based permissions via user types
- File upload validation and cleanup
- Session management with 1-hour timeout

## Testing & Deployment
- Use Django's test framework for unit tests
- Static files collected via `collectstatic`
- Gunicorn for production WSGI server
- Environment variables via `python-decouple`

## Key Files to Reference
- `iai_gestion/settings.py`: All configuration constants
- `apps/authentification/models.py`: User model and authentication logic
- `templates/base.html`: Base template with Tailwind setup
- `fixtures/initial_data.json`: Sample data for filieres and courses