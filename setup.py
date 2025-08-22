from setuptools import setup, find_packages

with open('requirements.txt', 'r') as f:
    requirements = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]

setup(
    name="worksheet-api",
    version="1.0.0",
    packages=find_packages(),
    install_requires=requirements,
    py_modules=['app', 'worksheet_generator'],
    include_package_data=True,
    package_data={
        '': ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.bmp'],
    },
)
