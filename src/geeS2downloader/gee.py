import rasterio as rio
import ee
import math
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from .common import *
import logging
import matplotlib.pyplot as plt


class Tile:
    """
    The tile represents a square area inside a raster matrix.
    It can be used to easily slice an array.
    """
    def __init__(self, slice_y, slice_x, band_info):
        self.slice_y, self.slice_x = slice_y, slice_x
        self.band_info = band_info

    @property
    def shape(self):
        return self.slice_y.stop - self.slice_y.start, self.slice_x.stop - self.slice_x.start

    @property
    def slices(self):
        return self.slice_y, self.slice_x

    @property
    def size(self):
        return int(self.shape[0] * self.shape[1] * 1.3)

    @property
    def nominal_scale(self):
        return self.band_info['nominal_scale']

    @property
    def bounding_box(self):
        """
        Return the bounding box [(x1, y1), (x2, y2)] of the tile, according to a CRS affine transformation
        :return: the bounding box in coordinates
        """
        transform = self.band_info['crs_transform']
        affine = rio.Affine(*transform)

        bbox = [affine * (self.slice_x.start, self.slice_y.start),
                affine * (self.slice_x.stop, self.slice_y.stop)]

        return bbox

    def download(self, img: ee.Image, band: str = None, session=None):
        # get the session
        session = session if session is not None else requests

        # Get the polygon in lat lon
        region_latlon = self.polygon('EPSG:4326')

        # get a url for the tile
        url = img.select(band).getDownloadUrl(dict(scale=self.nominal_scale, region=self.polygon('EPSG:4326')))

        # create a progress bar with the tile size
        with tqdm(total=self.size, unit_scale=True, desc=str(self), unit='b', smoothing=0) as pbar:
            ds = open_url_dataset(url, session, pbar)

        return ds.read(out_shape=self.shape)

    def polygon(self, to_crs: str = None):
        """
        Return the closed polygon of the tile.
        If a projection is passed, then the Polygon is transformed to the new projection.
        :param to_crs: The coordinate reference system to project the Polygon
        :return: GeoJson polygon
        """

        top_left, bottom_right = self.bounding_box
        polygon = create_geometry([top_left,
                                   (bottom_right[0], top_left[1]),
                                   bottom_right,
                                   (top_left[0], bottom_right[1])])

        if to_crs is not None:
            polygon = rio.warp.transform_geom(self.band_info['crs'], to_crs, polygon)

        return polygon

    def __repr__(self):
        s = f'Tile[{self.slice_y.start}:{self.slice_y.stop},'
        s += f'{self.slice_x.start}:{self.slice_x.stop}]'
        return s


class GEES2Downloader:
    def __init__(self, max_workers=5, logger_level=logging.INFO):
        self.img = None
        self.band = None
        self.band_info = None
        self.array = None

        self.max_workers = max_workers

        # create a logger
        logging.basicConfig(format='%(asctime)s %(levelname)s:%(message)s',
                            level=logging.ERROR, datefmt='%I:%M:%S')
        self.logger = logging.getLogger('GEES2Downloader')
        self.logger.setLevel(logger_level)

        # set all loggers to ERROR
        for logger in [logging.getLogger(name) for name in logging.root.manager.loggerDict]:
            logger.setLevel(logging.ERROR)

    def _estimate_band_size(self, excess_factor=2):
        if self.band_info is None:
            self.logger.warning(f'GEES2Downloader not initialized')
            return

        values_range = self.band_info['data_type']['max'] - self.band_info['data_type']['min'] + 1
        bits = math.log2(values_range)
        bts = bits/8

        dimensions = self.band_info['dimensions']
        return dimensions[0] * dimensions[1] * 2 * excess_factor

    def _create_tiles(self, max_size=33554432):
        # check if it is initialized
        if self.band_info is None:
            self.logger.warning(f'GEES2Downloader not initialized')
            return

        # calculate the estimated size of the band, to evaluate the number of pieces to slice
        size = self._estimate_band_size()

        # as we will rescale on x and y, we can use the double of the factor
        rescale_factor = math.sqrt(max_size / size)

        # get the band dimension
        dimension = self.band_info['dimensions']

        if rescale_factor > 1:
            return [Tile(slice(0, dimension[0]), slice(0, dimension[1]), self.band_info)]

        step_y = int(rescale_factor * dimension[0])
        step_x = int(rescale_factor * dimension[1])

        i, j = 0, 0
        tiles = []
        while i < dimension[0]:
            while j < dimension[1]:

                slice_y = slice(*[i, i + step_y if i + step_y < dimension[0] else dimension[0]])
                slice_x = slice(*[j, j + step_x if j + step_x < dimension[1] else dimension[1]])
                tiles.append(Tile(slice_y, slice_x, self.band_info))
                j += step_x
            i += step_y
            j = 0

        return tiles

    @staticmethod
    def _workers_done(workers):
        running = 0
        for w in workers:
            running += int(w.done())
        return running

    def _download_band(self):
        # create the empty matrix
        img_array = np.zeros(self.band_info['dimensions']).astype('int16')

        # get the tiles
        self.tiles = self._create_tiles()
        print(f'Dividing band in {len(self.tiles)} tiles')

        # for each tile, download it in memory and copy to the img matrix
        executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # open a session that will handle the retries
        session = requests_retry_session(5, status_forcelist=[500, 502, 503, 504])

        # create a list for the workers and launch one work for each tile
        workers = []
        for tile in self.tiles:
            workers.append(executor.submit(Tile.download, tile, self.img, self.band, session))

        # wait for the workers to complete the requests
        total_done = 0
        with tqdm(total=len(workers), desc='Tiles', unit='tile') as pbar:
            done = GEES2Downloader._workers_done(workers)
            while done < len(workers):
                done = GEES2Downloader._workers_done(workers)
                sleep(0.1)
                if done > total_done:
                    finished = done - total_done
                    pbar.update(finished)
                    total_done += finished

        pbar.close()

        # recreate the scene
        for tile, worker in zip(self.tiles, workers):
            img_array[tile.slices] = worker.result()

        return img_array

    def download(self, img: ee.Image, band: str, scale: int = None):
        # todo: REESCREVER COM TRY E EXCEPT, PARA EVITAR UM GETINFO
        print('Retrieving band info')
        if img.bandNames().contains(band).getInfo():
            self.img = img.select(band)
            self.band = band
            self.band_info = self.img.get('system:bands').getInfo()[band]

            # Get the nominal (original) scale of the band
            proj = self.img.projection()
            self.band_info['nominal_scale'] = proj.nominalScale().getInfo()

            self.array = self._download_band()

            print('Finished. The result can be accessed at obj.array')

        else:
            self.logger.error(f'Image does not contain band {band}')
            return

    def plot_tiling(self, figsize=(5, 5)):
        arr = np.zeros(self.band_info['dimensions']).astype('uint8')
        plt.figure(figsize=figsize)
        for i, tile in enumerate(self.tiles):
            arr[tile.slices] = i

        plt.imshow(arr)

    def plot(self, figsize=(10, 10)):
        plt.figure(figsize=figsize)
        plt.imshow(self.array)
