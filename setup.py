"""
Webkitwindow
------------

An easy to use Python wrapper around QtWebkit, BSD Licenced.
"""

from setuptools import setup

setup(
    name='Webkitwindow',
    version='0.1-alpha',
    url='http://github.com/hoeck/webkitwindow/',
    license='BSD',
    author='Erik Soehnel',
    author_email='eriksoehnel@gmail.com',
    description='An easy to use Python wrapper around QtWebkit.',
    long_description=__doc__,
    py_modules=['webkitwindow'],
    include_package_data=True,
)
