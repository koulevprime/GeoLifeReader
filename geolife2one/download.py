#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Download the GeoLife dataset to the provided directory.
# Available here: https://www.microsoft.com/en-us/download/details.aspx?id=52367

import logging
logger = logging.getLogger(__name__)

import os
import requests
import urllib.parse
import subprocess
import zipfile

GEOLIFE_DOWNLOAD_URL = 'https://download.microsoft.com/download/F/4/8/F4894AA5-FDBC-481E-9285-D5F8C4C4F039/Geolife%20Trajectories%201.3.zip'
DOWNLOAD_CHUNK_SIZE = (1024*1024)


def download_with_progress(path):
    """
    Download the GeoLife file with a progress bar. Deprecated: nice 
    functionality, but might not auto-scale to a user's bandwidth.
    :param path: the path to which the GeoLife dataset ZIP archive is to be 
                 downloaded
    :return: Nothing
    """
    import humanfriendly
    from tqdm import tqdm
    r = requests.get(GEOLIFE_DOWNLOAD_URL, stream=True)
    size = int(r.headers.get('content-length', 0))

    logger.debug('Download file size: {}'.format(
        humanfriendly.format_size(size)
    ))

    with open(path, 'wb') as f:
        for data in tqdm(r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE),
                         total=size / DOWNLOAD_CHUNK_SIZE, unit='MB',
                         unit_scale=True):
            f.write(data)


def main(args):
    logger.info('Downloading the GeoLife dataset from {0} '
                'into {1.output_directory}'.format(
        GEOLIFE_DOWNLOAD_URL, args
    ))

    # Check to see if the file has already been downloaded; if so, abort
    download_file_name = os.path.basename(
        urllib.parse.unquote(
            urllib.parse.urlsplit(GEOLIFE_DOWNLOAD_URL).path
        )
    )
    download_to_path = os.path.join(args.output_directory, download_file_name)


    if os.path.isfile(download_to_path):
        import sys
        logger.warning('GeoLife archive already exists at "{}"! '
                       'Aborting download.'.format(download_to_path))

    else:
        # Download the GeoLife dataset file and create a progress bar to plot the
        #  download's progress.
        logger.debug('Output file will be located at "{}"'.format(
            download_to_path
        ))

        try:
            subprocess.call([
                'wget',
                '--directory-prefix={}'.format(args.output_directory),
                GEOLIFE_DOWNLOAD_URL
            ])
        except FileNotFoundError:
            # User might be on Windows.
            download_with_progress(path=download_to_path)

        logger.debug('Download complete!')

    # Unzip the archive in the given directory.
    if os.path.isdir(os.path.join(args.output_directory,
                                  'Geolife Trajectories 1.3')):
        # ZIP archive has already been unzipped.
        # Skip unzipping.
        logger.warning('ZIP archive has already been unzipped. Skip unzipping.')

    else:
        logger.debug('Unzipping GeoLife ZIP archive into {}'.format(
            args.output_directory
        ))
        unzip(download_to_path)


def unzip(path):
    try:
        subprocess.Popen(['unzip', path], cwd=os.path.dirname(path))
    except:
        # Use the pure Python method of unzipping. No progress / feedback
        # though.
        logger.debug('This may take some time. Go get some coffee.')
        zip_ref = zipfile.ZipFile(path, 'r')
        zip_ref.extractall('/tmp/geolife/') #os.path.dirname(path))
        zip_ref.close()


if __name__ == '__main__':
    import sys

    class DummyArgs(object):
        output_directory = sys.argv[-1]

    main(DummyArgs())