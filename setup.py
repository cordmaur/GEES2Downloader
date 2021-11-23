from setuptools import find_packages, setup

setup(
    name='geeS2Downloader',
    extras_require=dict(tests=['pytest']),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'setuptools~=58.0.4',
        'rasterio~=1.2.10',
        'earthengine-api~=0.1.290',
        'numpy~=1.21.3',
        'matplotlib~=3.4.3',
        'requests~=2.26.0',
        'geojson~=2.5.0',
        'tqdm~=4.62.3',
    ]
)

