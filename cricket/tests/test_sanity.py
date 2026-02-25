import pytest


@pytest.mark.django_db
def test_sanity():
    assert 1 + 1 == 2