# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright (C) 2012 Yahoo! Inc. All Rights Reserved.
#    Copyright (C) 2012 Dreamhost Inc. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from devstack import utils


def partition(fullname):
    """
    The name should be in dotted.path:ClassName syntax.
    """
    if ':' not in fullname:
        raise ValueError('Invalid entry point specifier %r' % fullname)
    module_name, ignore, classname = fullname.partition(':')
    return (module_name, ignore, classname)


def import_entry_point(fullname):
    """
    Given a name import the class and return it.
    """
    (module_name, _, classname) = partition(fullname)
    try:
        module = utils.import_module(module_name, False)
        for submodule in module_name.split('.')[1:]:
            module = getattr(module, submodule)
        cls = getattr(module, classname)
    except (ImportError, AttributeError) as err:
        raise RuntimeError('Could not load entry point %s: %s' %
                           (fullname, err))
    return cls
