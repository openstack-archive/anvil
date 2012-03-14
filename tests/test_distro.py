
from devstack import distro


def test_component_dependencies():
    d = distro.Distro('fake', 'ignore', 'apt', {},
                      {'a': {'dependencies': ['b'],
                              },
                       'b': {},
                       })
    actual = d.resolve_component_dependencies(['a'])
    assert actual == {'a': set(['b']),
                      'b': set(),
                      }
