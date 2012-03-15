
from ConfigParser import ConfigParser

import mox

from devstack.components import db
from devstack import passwords

def test_fetch_dbdsn_full():
    cfg = ConfigParser()
    cfg.add_section('db')
    cfg.set('db', 'sql_user', 'sql_user')
    cfg.set('db', 'sql_host', 'sql_host')
    cfg.set('db', 'port', '55')
    cfg.set('db', 'type', 'mysql')
    cfg.add_section('passwords')
    cfg.set('passwords', 'sql', 'password')

    dsn = db.fetch_dbdsn(cfg, passwords.PasswordGenerator(cfg, False))
    assert dsn == 'mysql://sql_user:password@sql_host:55/'


def test_fetch_dbdsn_no_user():
    cfg = ConfigParser()
    cfg.add_section('db')
    cfg.set('db', 'sql_user', '')
    cfg.set('db', 'sql_host', 'sql_host')
    cfg.set('db', 'port', '55')
    cfg.set('db', 'type', 'mysql')
    cfg.add_section('passwords')
    cfg.set('passwords', 'sql', 'password')

    dsn = db.fetch_dbdsn(cfg, passwords.PasswordGenerator(cfg, False))
    assert dsn == 'mysql://:password@sql_host:55/'


def test_fetch_dbdsn_dbname():
    cfg = ConfigParser()
    cfg.add_section('db')
    cfg.set('db', 'sql_user', 'sql_user')
    cfg.set('db', 'sql_host', 'sql_host')
    cfg.set('db', 'port', '55')
    cfg.set('db', 'type', 'mysql')
    cfg.add_section('passwords')
    cfg.set('passwords', 'sql', 'password')

    pw_gen = passwords.PasswordGenerator(cfg, False)
    dsn = db.fetch_dbdsn(cfg, pw_gen, 'dbname')
    assert dsn == 'mysql://sql_user:password@sql_host:55/dbname'
