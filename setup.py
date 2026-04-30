from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="ficsy",
    version="1.1.0",
    author="FICSY Team",
    description="Financial Literacy CLI untuk Pelajar SMA",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "rich>=13.7.0",
        "google-generativeai>=0.7.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ficsy=ficsy.ficsy:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
