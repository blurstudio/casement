import os

from setuptools import setup, find_packages
import casement

name = 'casement'
dirname = os.path.dirname(os.path.abspath(__file__))

# Get the long description from the README file.
with open(os.path.join(dirname, 'README.md')) as fle:
    long_description = fle.read()

setup(
    name=name,
    version=casement.__version__,
    description=r'Useful functionality for managing Microsoft Windows.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/blurstudio/{}'.format(name),
    download_url='https://github.com/blurstudio/{}/archive/master.zip'.format(name),
    license='GNU LGPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Operating System :: Microsoft',
        'Operating System :: Microsoft :: Windows :: Windows 7',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
    ],
    packages=[name],
    include_package_data=True,
    author='Blur Studio',
    install_requires=[
      'pywin32',
    ],
    author_email='pipeline@blur.com',
    entry_points={
        'console_scripts': [
            'casement = casement:_cli',
        ],
    },
)
