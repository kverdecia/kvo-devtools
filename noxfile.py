import nox


@nox.session(python='3.13')
def lint(session):
    session.install('ruff')
    session.run('ruff', 'check', '--preview')


@nox.session(python='3.13')
def mypy(session):
    session.install('.[typing]')
    session.run('mypy', 'src/kvo')


@nox.session(python='3.13')
def test(session):
    session.install('.', 'pytest')
    session.run('pytest')
