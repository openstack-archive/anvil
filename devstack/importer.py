

def import_entry_point(fullname):
    """Given a name import the class and return it.

    The name should be in dotted.path:ClassName syntax.
    """
    if ':' not in fullname:
        raise ValueError('Invalid entry point specifier %r' % fullname)
    module_name, ignore, classname = fullname.partition(':')
    try:
        module = __import__(module_name)
        for submodule in module_name.split('.')[1:]:
            module = getattr(module, submodule)
        cls = getattr(module, classname)
    except (ImportError, AttributeError) as err:
        raise RuntimeError('Could not load entry point %s: %s' %
                           (fullname, err))
    return cls
