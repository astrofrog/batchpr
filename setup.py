from setuptools import setup

from batchpr import __version__

with open('README.rst') as infile:
    long_description = infile.read()

setup(
    version=__version__,
    url="https://github.com/astrofrog/batchpr",
    name="batchpr",
    description='Easy automated pull requests to GitHub repositories',
    long_description=long_description,
    packages=['batchpr'],
    package_data={'pytest_mpl': ['classic.mplstyle']},
    install_requires=['requests'],
    license='BSD',
    author='Thomas Robitaille',
    author_email='thomas.robitaille@gmail.com',
    classifiers=['Development Status :: 4 - Beta',
                 'Intended Audience :: Developers',
                 'Programming Language :: Python',
                 'Programming Language :: Python :: 2',
                 'Programming Language :: Python :: 3',
                 'Operating System :: OS Independent',
                 'License :: OSI Approved :: BSD License'])
