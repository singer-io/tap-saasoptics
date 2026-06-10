#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='tap-saasoptics',
      version='1.1.2',
      description='Singer.io tap for extracting data from the SaaSOptics v1.0 API',
      author='jeff.huth@bytecode.io',
      classifiers=['Programming Language :: Python :: 3 :: Only'],
      py_modules=['tap_saasoptics'],
      install_requires=[
          'backoff==2.2.1',
          'requests==2.32.4',
          'singer-python==6.8.0'
      ],
      entry_points='''
          [console_scripts]
          tap-saasoptics=tap_saasoptics:main
      ''',
      extras_require={
          'dev': [
              'pylint',
              'pytest'
          ]
      },
      packages=find_packages(),
      package_data={
          'tap_saasoptics': [
              'schemas/*.json'
          ]
      })
