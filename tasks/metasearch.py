# coding=utf-8

from __future__ import absolute_import

import shutil
import os
import tempfile
import io
import urllib
import urlparse

from zipfile import ZipFile

import subprocess
from celery.app import shared_task
from owslib.wfs import WebFeatureService

from geonode.layers.utils import file_upload
from geosafe.tasks.analysis import download_file

__author__ = 'Rizky Maulana Nugraha <lana.pcfre@gmail.com>'
__date__ = '7/29/16'


@shared_task(
    name='geosafe.tasks.metasearch.add_wcs_layer',
    queue='geosafe')
def add_wcs_layer(
        endpoint,
        version,
        coverage_id,
        metadata_string=None,
        title=None,
        bbox=None,
        user=None, password=None):
    # build url
    endpoint_parsed = urlparse.urlparse(endpoint)
    q_dict = {
        'version': version,
        'coverageid': coverage_id,
        'format': 'image/tiff',
        'request': 'GetCoverage',
        'service': 'WCS',
        'crs': 'EPSG:4326',
    }
    if bbox:
        q_dict['bbox'] = ','.join(bbox)
    parsed_url = urlparse.ParseResult(
        scheme=endpoint_parsed.scheme,
        netloc=endpoint_parsed.netloc,
        path=endpoint_parsed.path,
        params=None,
        query=urllib.urlencode(q_dict),
        fragment=None
    )
    tmpfile = download_file(parsed_url.geturl(), user=user, password=password)
    shutil.move(tmpfile, tmpfile + '.tif')
    tmpfile += '.tif'

    # get metadata file
    if metadata_string:
        metadata_file = '%s.xml' % tmpfile
        with io.open(metadata_file, mode='w', encoding='utf-8') as f:
            f.write(metadata_string)

    saved_layer = None
    with open(tmpfile) as f:
        saved_layer = file_upload(tmpfile, overwrite=True)
        saved_layer.set_default_permissions()
        saved_layer.title = title or coverage_id
        saved_layer.save()
    try:
        os.remove(tmpfile)
    except:
        pass
    return saved_layer

@shared_task(
    name='geosafe.tasks.metasearch.add_wfs_layer',
    queue='geosafe')
def add_wfs_layer(
        endpoint,
        version,
        typename,
        metadata_string=None,
        title=None,
        bbox=None,
        user=None,
        password=None):
    # wfs = WebFeatureService(url=endpoint, version=version)
    # response = wfs.getfeature(
    #     typename=typename,
    #     bbox=bbox,
    #     outputFormat='shape-zip')
    endpoint_parsed = urlparse.urlparse(endpoint)
    q_dict = {
        'version': version,
        'typename': typename,
        'outputFormat': 'json',
        'request': 'GetFeature',
        'service': 'WFS',
        'srsName': 'EPSG:4326',
    }
    if bbox:
        q_dict['bbox'] = ','.join(bbox)
    parsed_url = urlparse.ParseResult(
        scheme=endpoint_parsed.scheme,
        netloc=endpoint_parsed.netloc,
        path=endpoint_parsed.path,
        params=None,
        query=urllib.urlencode(q_dict),
        fragment=None
    )
    tmpfile = download_file(parsed_url.geturl(), user=user, password=password)

    args = [
        'ogr2ogr',
        '-nlt POLYGON',
        '-skipfailures',
        '%s.shp' % tmpfile,
        tmpfile,
        'OGRGeoJSON'
    ]

    retval = subprocess.call(args)

    # get metadata file
    if metadata_string:
        metadata_file = '%s.xml' % tmpfile
        with io.open(metadata_file, mode='w', encoding='utf-8') as f:
            f.write(metadata_string)

    saved_layer = None
    if retval == 0:
        saved_layer = file_upload(
            '%s.shp' % tmpfile,
            overwrite=True)
        saved_layer.set_default_permissions()
        saved_layer.title = title or typename
        saved_layer.save()

    # cleanup
    dir_name = os.path.dirname(tmpfile)
    for root, dirs, files in os.walk(dir_name):
        for f in files:
            if tmpfile in f:
                try:
                    os.remove(os.path.join(root, f))
                except:
                    pass

    # dir_name = os.path.dirname(tmpfile)
    # saved_layer = None
    #
    # with ZipFile(tmpfile) as zf:
    #     zf.extractall(path=dir_name)
    #     for name in zf.namelist():
    #         basename, ext = os.path.splitext(name)
    #         if '.shp' in ext:
    #             # process shapefile layer
    #             saved_layer = file_upload(
    #                 os.path.join(dir_name, name),
    #                 overwrite=True)
    #             saved_layer.set_default_permissions()
    #             saved_layer.title = title or typename
    #             saved_layer.save()
    #
    #     # cleanup
    #     for name in zf.namelist():
    #         filepath = os.path.join(dir_name, name)
    #         try:
    #             os.remove(filepath)
    #         except:
    #             pass
    #
    # # cleanup
    # try:
    #     os.remove(tmpfile)
    # except:
    #     pass
    return saved_layer