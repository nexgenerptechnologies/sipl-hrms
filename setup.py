from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="sipl_hrms",
    version="0.0.1",
    description="Custom HRMS Extension for SIPL",
    author="Nexgen ERP Technologies",
    author_email="contact@nexgenerptechnologies.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
