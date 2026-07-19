from django.test import TestCase
from django.contrib.auth import authenticate, get_user_model

User = get_user_model()


class AuthenticationTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='johndoe',
            email='john.doe@iai.cm',
            password='SecretPassword123',
            matricule='GL.CMR.D014.2425A',
            type_utilisateur='ETUDIANT',
            first_name='John',
            last_name='Doe'
        )

    def test_authenticate_by_username(self):
        user = authenticate(username='johndoe', password='SecretPassword123')
        self.assertIsNotNone(user)
        self.assertEqual(user, self.user)

    def test_authenticate_by_email(self):
        user = authenticate(username='john.doe@iai.cm', password='SecretPassword123')
        self.assertIsNotNone(user)
        self.assertEqual(user, self.user)

    def test_authenticate_by_matricule(self):
        user = authenticate(username='GL.CMR.D014.2425A', password='SecretPassword123')
        self.assertIsNotNone(user)
        self.assertEqual(user, self.user)

    def test_authenticate_invalid_password(self):
        user = authenticate(username='GL.CMR.D014.2425A', password='WrongPassword')
        self.assertIsNone(user)

    def test_authenticate_nonexistent_user(self):
        user = authenticate(username='nonexistent', password='SecretPassword123')
        self.assertIsNone(user)
