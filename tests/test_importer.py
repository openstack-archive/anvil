
from devstack import importer
from devstack import distro


def test_function():
    f = importer.import_entry_point('devstack.importer:import_entry_point')
    assert f == importer.import_entry_point


def test_class():
    c = importer.import_entry_point('devstack.distro:Distro')
    assert c == distro.Distro
