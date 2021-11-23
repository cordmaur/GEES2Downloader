from geojson import Point, Polygon
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from io import BytesIO
import zipfile
from tqdm.notebook import tqdm
from rasterio import MemoryFile
import matplotlib.pyplot as plt


def open_url(url: str, session, pbar):
    # get the session
    session = session if session is not None else requests

    mem_file = BytesIO()

    r = session.get(url, stream=True)
    for chunk in r.iter_content(chunk_size=1024):
        if chunk:
            mem_file.write(chunk)
            mem_file.flush()
            if pbar is not None:
                pbar.update(1024)

    if pbar.n < pbar.total:
        pbar.update(pbar.total - pbar.n)

    return mem_file


def open_zip_url(url: str, session=None, pbar=None):
    # get the contents from the url
    content = open_url(url, session, pbar)

    # create a zipfile with the url content
    z = zipfile.ZipFile(content)

    # extract the content of the zipfile
    extracted = BytesIO(z.read(z.filelist[0]))

    return extracted


def open_url_dataset(url: str, session, pbar: tqdm):
    # get the extracted file at url
    extracted = open_zip_url(url, session, pbar)

    # open the file in memory with rasterio
    ds = MemoryFile(extracted).open()

    # read the bytes
    ds.read()

    # return the dataset
    return ds


def plot_url(url: str):
    plt.figure(figsize=(10, 10))
    ds = open_url_dataset(url)
    img = ds.read().squeeze()

    plt.imshow(img)


def create_geometry(pts, logger=None):
    if isinstance(pts, tuple):
        geometry = Point(coordinates=pts)

    elif isinstance(pts, (Point, Polygon)):
        geometry = pts

    else:
        # check if the polygon is correctly closed. If it is not, close it.
        if pts[0] != pts[-1]:
            pts.append(pts[0])

        geometry = Polygon(coordinates=[pts])

    # if the geometry is not valid, return None
    if geometry.is_valid:
        return geometry
    else:
        # get the context logger
        msg = 'Informed points do not correspond to a valid polygon.'

        if logger is not None:
            logger.error(msg)
        else:
            print(msg)


# remove the folder
def rm_tree(pth):
    pth = Path(pth)
    for child in pth.glob('*'):
        if child.is_file():
            child.unlink()
        else:
            rm_tree(child)
    pth.rmdir()


# create a session that retries connecting automatically
def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
