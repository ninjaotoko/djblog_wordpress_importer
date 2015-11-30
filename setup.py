# -*- coding:utf8 -*-
#
# Copyright (c) 2014 Xavier Lesa <xavierlesa@gmail.com>.
# All rights reserved.
# Distributed under the BSD license, see LICENSE
from setuptools import setup, find_packages
import sys, os

setup(name='djblog_wordpress_importer', 
        version='0.1', 
        description="Herramienta para migrar wordpress a djblog, a través de wordpress-json",
        packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
        include_package_data=True,
        install_requires=[
            'wordpress-json',
        ],
        dependency_links=[
            'git+https://github.com/ninjaotoko/djblog.git',
        ],
        zip_safe=False,
        author='Xavier Lesa',
        author_email='xavierlesa@gmail.com',
        url='http://github.com/ninjaotoko/djblog_wordpress_importer'
        )
