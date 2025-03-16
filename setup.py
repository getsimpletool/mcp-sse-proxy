from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mcp-sse-proxy",
    version="0.1.2",
    author="Artur Zdolinski",
    author_email="contact@nchekwa.com",
    description="A proxy for MCP SSE events",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/getsimpletool/mcp-sse-proxy",
    project_urls={
        "Bug Tracker": "https://github.com/getsimpletool/mcp-sse-proxy/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.7",
    install_requires=[
        "httpx>=0.24.0",
        "anyio>=4.7.0",
        "python-dotenv"
    ],
    entry_points={
        "console_scripts": [
            "mcp-sse-proxy=mcp_sse_proxy:main",
        ],
    },
)
