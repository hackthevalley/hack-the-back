import pytest
from faker import Faker

from .models import User

fake = Faker()


@pytest.mark.django_db
def test_create_user():
    email = fake.email()
    password = fake.password()

    user = User.objects.create_user(email=email, password=password)
    assert not user.is_staff
    assert not user.is_superuser
    assert user.email == email
    assert user.check_password(password)


@pytest.mark.django_db
def test_create_user_with_no_email_raises_ValueError():
    with pytest.raises(ValueError):
        User.objects.create_user(email=None, password=fake.password())


@pytest.mark.django_db
def test_create_superuser():
    email = fake.email()
    password = fake.password()

    user = User.objects.create_superuser(email=email, password=password)
    assert user.is_staff
    assert user.is_superuser
    assert user.email == email
    assert user.check_password(password)


@pytest.mark.django_db
def test_create_superuser_with_no_email_raises_ValueError():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email=None, password=fake.password())


@pytest.mark.django_db
def test_create_superuser_with_is_staff_set_False_raises_ValueError():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email=fake.email(), password=fake.password(), is_staff=False
        )


@pytest.mark.django_db
def test_create_superuser_with_is_superuser_set_False_raises_ValueError():
    with pytest.raises(ValueError):
        User.objects.create_superuser(
            email=fake.email(), password=fake.password(), is_superuser=False
        )
