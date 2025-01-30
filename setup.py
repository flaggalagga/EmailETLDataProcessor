from setuptools import setup, find_packages

setup(
    name="etl_processor",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'python-dotenv>=1.0.0',
        'mysql-connector-python>=8.2.0',
        'sqlalchemy>=1.4.0',
        'asyncio>=3.4.3',
        'dnspython>=2.4.0',
        'python-magic>=0.4.27',
        'defusedxml>=0.7.1',
        'clamd>=1.0.2',
        'dkimpy>=1.1.4',
        'imap-tools>=1.0.0',
        'colorama>=0.4.6',
        'tabulate>=0.9.0',
    ],
    entry_points={
        'console_scripts': [
            'bsm-import=etl_processor.run_import:main',
        ],
    },
    python_requires='>=3.8',
    author="ENSM",
    description="BSM Import Processing System",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
