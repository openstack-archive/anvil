
from devstack import passwords


def test_generate_random():
    def check_one(i):
        p = passwords.generate_random(i)
        assert len(p) == i
    for i in range(1, 9):
        yield check_one, i
