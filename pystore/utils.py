#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# PyStore: Flat-file datastore for timeseries data
# https://github.com/ranaroussi/pystore
#
# Copyright 2018-2020 Ran Aroussi
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from datetime import datetime
import json
import shutil
import pandas as pd
import numpy as np
from dask import dataframe as dd
from dask.distributed import Client


try:
    from pathlib import Path
    Path().expanduser()
except (ImportError, AttributeError):
    from pathlib2 import Path

from . import config


def read_csv(urlpath, *args, **kwargs):
    def rename_dask_index(df, name):
        df.index.name = name
        return df

    index_col = index_name = None

    if "index" in kwargs:
        del kwargs["index"]
    if "index_col" in kwargs:
        index_col = kwargs["index_col"]
        if isinstance(index_col, list):
            index_col = index_col[0]
        del kwargs["index_col"]
    if "index_name" in kwargs:
        index_name = kwargs["index_name"]
        del kwargs["index_name"]

    df = dd.read_csv(urlpath, *args, **kwargs)

    if index_col is not None:
        df = df.set_index(index_col)

    if index_name is not None:
        df = df.map_partitions(rename_dask_index, index_name)

    return df


def datetime_to_int64(df):
    """ convert datetime index to epoch int
    allows for cross language/platform portability
    """

    if isinstance(df.index, dd.Index) and (
            isinstance(df.index, pd.DatetimeIndex) and
            any(df.index.nanosecond) > 0):
        df.index = df.index.astype(np.int64)  # / 1e9

    return df


def subdirs(d):
    """ use this to construct paths for future storage support """
    return [o.parts[-1] for o in Path(d).iterdir()
            if o.is_dir() and o.parts[-1] != "_snapshots"]


def path_exists(path):
    """ use this to construct paths for future storage support """
    return path.exists()


def read_metadata(path):
    """ use this to construct paths for future storage support """
    dest = make_path(path, "metadata.json")
    if path_exists(dest):
        with dest.open() as f:
            return json.load(f)


def write_metadata(path, metadata={}):
    """ use this to construct paths for future storage support """
    now = datetime.now()
    metadata["_updated"] = now.strftime("%Y-%m-%d %H:%I:%S.%f")
    meta_file = make_path(path, "metadata.json")
    with meta_file.open("w") as f:
        json.dump(metadata, f, ensure_ascii=False)


def make_path(*args):
    """ use this to construct paths for future storage support """
    # return Path(os.path.join(*args))
    return Path(*args)


def get_path(*args):
    """ use this to construct paths for future storage support """
    # return Path(os.path.join(config.DEFAULT_PATH, *args))
    return Path(config.DEFAULT_PATH, *args)


def set_path(path):
    if path is None:
        path = get_path()

    else:
        path = path.rstrip("/").rstrip("\\").rstrip(" ")
        if "://" in path and "file://" not in path:
            raise ValueError(
                "PyStore currently only works with local file system")

    config.DEFAULT_PATH = path
    path = get_path()

    # if path does not exist - create it
    if not path_exists(get_path()):
        os.makedirs(get_path())

    return get_path()


def list_stores():
    if not path_exists(get_path()):
        os.makedirs(get_path())
    return subdirs(get_path())


def delete_store(store):
    shutil.rmtree(get_path(store))
    return True


def delete_stores():
    shutil.rmtree(get_path())
    return True


def set_client(scheduler=None):
    if scheduler != config._SCHEDULER and config._CLIENT is not None:
        try:
            config._CLIENT.shutdown()
            config._CLIENT = None
        except Exception:
            pass

    config._SCHEDULER = scheduler
    if scheduler is not None:
        config._CLIENT = Client(scheduler)

    return config._CLIENT


def get_client():
    return config._CLIENT


def set_partition_size(size=None):
    if size is None:
        size = config.DEFAULT_PARTITION_SIZE * 1
    config.PARTITION_SIZE = size
    return config.PARTITION_SIZE


def get_partition_size():
    return config.PARTITION_SIZE

def infer_str_to_float_or_int(s):
  if isinstance(s, (float, int)):
    return s
  
  try:
    return float(s) if '.' in s or 'e' in s.lower() else int(s)
  except ValueError:
    return s
  
def columns_to_multiindex(df, inplace=False):
  assert all(isinstance(c, str) for c in df.columns)
  assert all(c[0] == '(' and c[-1] == ')' for c in df.columns)
  if not inplace:
    df = df.copy() 
  df.columns = pd.MultiIndex.from_tuples(list(map(lambda x: tuple(x[1:-1].split(', ')), df.columns)))

  df.columns = pd.MultiIndex.from_tuples(list(map(lambda x: tuple(x), df.columns.to_frame().applymap(infer_str_to_float_or_int).values)))
  return df
