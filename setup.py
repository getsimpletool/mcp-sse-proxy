from setuptools import setup

setup(
    name='mcp-sse-proxy',
    version='0.1.3',
    description='Proxy between MCP server using STDIO transport and client using SSE transport',
    author='Artur Zdolinski',
    author_email='artur@zdolinski.com',
    url='https://github.com/getsimpletool/mcp-sse-proxy',
    py_modules=['mcp_sse_proxy'],
    package_dir={'': 'src'},
    install_requires=[
        'httpx>=0.24.0',
        'anyio>=4.7.0',
        'python-dotenv',
    ],
    entry_points={
        'console_scripts': [
            'mcp-sse-proxy=mcp_sse_proxy:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)
