"""
Define Exposures reader function from an Excel file.
"""

__all__ = ['DEF_VAR_EXCEL',
           'DEF_VAR_MAT',
           'read']

import os
import logging
from xlrd import XLRDError
import numpy as np
import pandas

from climada.entity.tag import Tag
import climada.util.hdf5_handler as hdf5
from climada.util.config import CONFIG
from climada.util.coordinates import IrregularGrid

DEF_VAR_EXCEL = {'sheet_name': {'exp': 'assets',
                                'name': 'names'
                               },
                 'col_name': {'lat' : 'Latitude',
                              'lon' : 'Longitude',
                              'val' : 'Value',
                              'ded' : 'Deductible',
                              'cov' : 'Cover',
                              'imp' : 'DamageFunID',
                              'cat' : 'Category_ID',
                              'reg' : 'Region_ID',
                              'uni' : 'Value unit',
                              'ass' : 'centroid_index',
                              'ref': 'reference_year',
                              'item' : 'Item'
                             }
                }

DEF_VAR_MAT = {'sup_field_name': 'entity',
               'field_name': 'assets',
               'var_name': {'lat' : 'lat',
                            'lon' : 'lon',
                            'val' : 'Value',
                            'ded' : 'Deductible',
                            'cov' : 'Cover',
                            'imp' : 'DamageFunID',
                            'cat' : 'Category_ID',
                            'reg' : 'Region_ID',
                            'uni' : 'Value_unit',
                            'ass' : 'centroid_index',
                            'ref' : 'reference_year'
                           }
              }

LOGGER = logging.getLogger(__name__)

def read(exposures, file_name, description, var_names):
    '''Test reader functionality of the CentroidsExcel class'''    
    exposures.tag = Tag(file_name, description)
    
    extension = os.path.splitext(file_name)[1]
    if extension == '.mat':
        try:
            read_mat(exposures, file_name, description, var_names)
        except KeyError as var_err:
            LOGGER.error("Not existing variable. " + str(var_err))
            raise var_err
    elif (extension == '.xlsx') or (extension == '.xls'):
        try:
            read_excel(exposures, file_name, var_names)
        except KeyError as var_err:
            LOGGER.error("Not existing variable. " + str(var_err))
            raise var_err
    else:
        LOGGER.error('Input file extension not supported: %s.', extension)
        raise ValueError

def read_mat(exposures, file_name, description='', var_names=None):
    """Read MATLAB file and store variables in exposures. """
    # set variable names in source file
    if var_names is None:
        var_names = DEF_VAR_MAT
        
   # append the file name and description into the instance class
    exposures.tag = Tag(file_name, description)

    # Load mat data
    data = hdf5.read(file_name)
    try:
        data = data[var_names['sup_field_name']]
    except KeyError:
        pass
    data = data[var_names['field_name']]

    # Fill variables
    _read_mat_obligatory(exposures, data, var_names)
    _read_mat_default(exposures, data, var_names)
    _read_mat_optional(exposures, data, file_name, var_names)

def read_excel(exposures, file_name, var_names):
    """Read excel file and store variables in exposures. """
    if var_names is None:
        var_names = DEF_VAR_EXCEL

    dfr = pandas.read_excel(file_name, var_names['sheet_name']['exp'])
    # get variables
    _read_xls_obligatory(exposures, dfr, var_names)
    _read_xls_default(exposures, dfr, var_names)
    _read_xls_optional(exposures, dfr, file_name, var_names)

def _read_xls_obligatory(exposures, dfr, var_names):
    """Fill obligatory variables."""
    exposures.value = dfr[var_names['col_name']['val']].values

    coord_cols = [var_names['col_name']['lat'], var_names['col_name']['lon']]
    exposures.coord = IrregularGrid(np.array(dfr[coord_cols]))

    exposures.impact_id = dfr[var_names['col_name']['imp']].values

    # set exposures id according to appearance order
    num_exp = len(dfr.index)
    exposures.id = np.linspace(exposures.id.size, exposures.id.size + \
                          num_exp - 1, num_exp, dtype=int)

def _read_xls_default(exposures, dfr, var_names):
    """Fill optional variables. Set default values."""
    # get the exposures deductibles as np.array float 64
    # if not provided set default zero values
    num_exp = len(dfr.index)
    exposures.deductible = _parse_xls_default(dfr, \
                            var_names['col_name']['ded'], np.zeros(num_exp))
    # get the exposures coverages as np.array float 64
    # if not provided set default exposure values
    exposures.cover = _parse_xls_default(dfr, var_names['col_name']['cov'], \
                                     exposures.value)

def _read_xls_optional(exposures, dfr, file_name, var_names):
    """Fill optional parameters."""
    exposures.category_id = _parse_xls_optional(dfr, exposures.category_id, \
                                            var_names['col_name']['cat'])
    exposures.region_id = _parse_xls_optional(dfr, exposures.region_id, \
                                          var_names['col_name']['reg'])
    exposures.value_unit = _parse_xls_optional(dfr, exposures.value_unit, \
                                           var_names['col_name']['uni'])
    if not isinstance(exposures.value_unit, str):
        # Check all exposures have the same unit
        if len(np.unique(exposures.value_unit)) is not 1:
            LOGGER.error("Different value units provided for exposures.")
            raise ValueError
        exposures.value_unit = exposures.value_unit[0]
    assigned = _parse_xls_optional(dfr, np.array([]), \
                                   var_names['col_name']['ass'])
    if assigned.size > 0:
        exposures.assigned['NA'] = assigned

    # check if reference year given under "names" sheet
    # if not, set default present reference year
    exposures.ref_year = _parse_xls_ref_year(file_name, var_names)

def _parse_xls_ref_year(file_name, var_names):
    """Retrieve reference year provided in the other sheet, if given."""
    try:
        dfr = pandas.read_excel(file_name, var_names['sheet_name']['name'])
        dfr.index = dfr[var_names['col_name']['item']]
        ref_year = dfr.loc[var_names['col_name']['ref']]['name']
    except (XLRDError, KeyError):
        ref_year = CONFIG['present_ref_year']
    return ref_year

def _parse_xls_optional(dfr, var, var_name):
    """Retrieve optional variable, leave its original value if fail."""
    try:
        var = dfr[var_name].values
    except KeyError:
        pass
    return var

def _parse_xls_default(dfr, var_name, def_val):
    """Retrieve optional variable, set default value if fail."""
    try:
        res = dfr[var_name].values
    except KeyError:
        res = def_val
    return res

def _read_mat_obligatory(exposures, data, var_names):
    """Fill obligatory variables."""
    exposures.value = np.squeeze(data[var_names['var_name']['val']])

    coord_lat = data[var_names['var_name']['lat']]
    coord_lon = data[var_names['var_name']['lon']]
    exposures.coord = IrregularGrid(np.concatenate((coord_lat, coord_lon), \
                                                   axis=1))

    exposures.impact_id = np.squeeze(data[var_names['var_name']['imp']]). \
        astype(int)

    # set exposures id according to appearance order
    num_exp = len(exposures.value)
    exposures.id = np.linspace(exposures.id.size, exposures.id.size + \
                          num_exp - 1, num_exp, dtype=int)

def _read_mat_default(exposures, data, var_names):
    """Fill optional variables. Set default values."""
    num_exp = len(data[var_names['var_name']['val']])
    # get the exposures deductibles as np.array float 64
    # if not provided set default zero values
    exposures.deductible = _parse_mat_default(data, \
                                              var_names['var_name']['ded'], \
                                              np.zeros(num_exp))
    # get the exposures coverages as np.array float 64
    # if not provided set default exposure values
    exposures.cover = _parse_mat_default(data, var_names['var_name']['cov'], \
                                         exposures.value)

def _read_mat_optional(exposures, data, file_name, var_names):
    """Fill optional parameters."""
    exposures.ref_year = _parse_mat_optional(data, exposures.ref_year, \
                                             var_names['var_name']['ref'])
    if not isinstance(exposures.ref_year, int):
        exposures.ref_year = int(exposures.ref_year)

    exposures.category_id = _parse_mat_optional(data, exposures.category_id, \
                        var_names['var_name']['cat']).astype(int)
    exposures.region_id = _parse_mat_optional(data, exposures.region_id, \
                        var_names['var_name']['reg']).astype(int)
    assigned = _parse_mat_optional(data, np.array([]), \
                                   var_names['var_name']['ass']).astype(int)
    if assigned.size > 0:
        exposures.assigned['NA'] = assigned
    try:
        exposures.value_unit = hdf5.get_str_from_ref(file_name, \
            data[var_names['var_name']['uni']][0][0])
    except KeyError:
        pass

def _parse_mat_optional(hdf, var, var_name):
    """Retrieve optional variable, leave its original value if fail."""
    try:
        var = np.squeeze(hdf[var_name])
    except KeyError:
        pass
    return var

def _parse_mat_default(hdf, var_name, def_val):
    """Retrieve optional variable, set default value if fail."""
    try:
        res = np.squeeze(hdf[var_name])
    except KeyError:
        res = def_val
    return res