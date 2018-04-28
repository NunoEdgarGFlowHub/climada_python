"""
Define Exposures class.
"""

__all__ = ['Exposures',
           'FILE_EXT']

import os
import copy
import logging
import numpy as np

from climada.entity.exposures.source import READ_SET
#from climada.entity.exposures.source import DEF_VAR_EXCEL, DEF_VAR_MAT
from climada.util.files_handler import to_list, get_file_names
import climada.util.checker as check
from climada.entity.tag import Tag
from climada.util.coordinates import Coordinates
from climada.util.interpolation import METHOD, DIST_DEF
from climada.util.config import CONFIG
import climada.util.plot as plot

LOGGER = logging.getLogger(__name__)

FILE_EXT = {'.mat':  'MAT',
            '.xls':  'XLS',
            '.xlsx': 'XLS'
           }
""" Supported files format to read from """

class Exposures(object):
    """Defines exposures attributes and basic methods. Loads from
    files with format defined in FILE_EXT.

    Attributes:
        tag (Tag): information about the source data
        ref_year (int): reference year
        value_unit (str): unit of the exposures values
        id (np.array): an id for each exposure
        coord (Coordinates): Coordinates instance (in degrees)
        value (np.array): a value for each exposure
        impact_id (np.array): impact function id corresponding to each
            exposure
        deductible (np.array, default): deductible value for each exposure
        cover (np.array, default): cover value for each exposure
        category_id (np.array, optional): category id for each exposure
            (when defined)
        region_id (np.array, optional): region id for each exposure
            (when defined)
        assigned (dict, optional): for a given hazard, id of the
            centroid(s) affecting each exposure. Filled in 'assign' method.
    """

    def __init__(self, file_name='', description=''):
        """Fill values from file, if provided.

        Parameters:
            file_name (str or list(str), optional): absolute file name(s) or
                folder name containing the files to read
            description (str or list(str), optional): one description of the
                data or a description of each data file

        Raises:
            ValueError

        Examples:
            Fill exposures with values and check consistency data:

            >>> exp_city = Exposures()
            >>> exp_city.coord = np.array([[40.1, 8], [40.2, 8], [40.3, 8]])
            >>> exp_city.value = np.array([5604, 123, 9005001])
            >>> exp_city.impact_id = np.array([1, 1, 1])
            >>> exp_city.id = np.array([11, 12, 13])
            >>> exp_city.check()

            Read exposures from Zurich.mat and checks consistency data.

            >>> exp_city = Exposures(ENT_TEST_XLS)
        """
        self.clear()
        if file_name != '':
            self.read(file_name, description)

    def clear(self):
        """Reinitialize attributes."""
        # Optional variables
        self.tag = Tag()
        self.ref_year = CONFIG["present_ref_year"]
        self.value_unit = 'NA'
        # Following values defined for each exposure
        # Obligatory variables
        self.coord = Coordinates()
        self.value = np.array([], float)
        self.impact_id = np.array([], int)
        self.id = np.array([], int)
        # Optional variables. Default values set in check if not filled.
        self.deductible = np.array([], float)
        self.cover = np.array([], float)
        # Optional variables. No default values set in check if not filled.
        self.category_id = np.array([], int)
        self.region_id = np.array([], int)
        self.assigned = dict()

    def assign(self, hazard, method=METHOD[0], dist=DIST_DEF[0]):
        """Compute the hazard centroids ids affecting to each exposure.

        Parameters:
            hazard (subclass Hazard): one hazard
            method (str, optional): interpolation method, neareast neighbor by
                default. The different options are provided by the class
                constant 'METHOD' of the interpolation module
            dist (str, optional): distance used, euclidian approximation by
                default. The different options are provided by the class
                constant 'DIST_DEF' of the interpolation module

        Raises:
            ValueError
        """
        self.assigned[hazard.tag.haz_type] = hazard.centroids.coord.resample(\
                     self.coord, method, dist)

    def check(self):
        """Check instance attributes.

        Raises:
            ValueError
        """
        num_exp = len(self.id)
        if np.unique(self.id).size != num_exp:
            LOGGER.error("There are exposures with the same identifier.")
            raise ValueError
        self._check_obligatories(num_exp)
        self._check_optionals(num_exp)
        self._check_defaults(num_exp)

    def plot(self, ignore_null=False, pop_name=True, **kwargs):
        """Plot exposures values sum binned over Earth's map.

        Parameters:
            ignore_null (bool, optional): flag to indicate if zero and
                negative values are ignored in plot. Default is False.
            pop_name (bool, optional): add names of the populated places.
            kwargs (optional): arguments for hexbin matplotlib function

         Returns:
            matplotlib.figure.Figure, cartopy.mpl.geoaxes.GeoAxesSubplot
        """
        if ignore_null:
            pos_vals = self.value > 0
        else:
            pos_vals = np.ones((self.value.size,), dtype=bool)
        title = self.tag.join_file_names()
        cbar_label = 'Value (%s)' % self.value_unit
        if 'reduce_C_function' not in kwargs:
            kwargs['reduce_C_function'] = np.sum
        return plot.geo_bin_from_array(self.value[pos_vals], \
            self.coord[pos_vals], cbar_label, title, pop_name, **kwargs)

    def read(self, files, descriptions='', var_names=None):
        """Read and check exposures.

        Parameters:
            files (str or list(str)): absolute file name(s) or folder name
                containing the files to read
            descriptions (str or list(str), optional): one description of the
                data or a description of each data file
            var_names (dict or list(dict), default): name of the variables in
                the file (default: check def_source_vars() function)

        Raises:
            ValueError
        """
        # Construct absolute path file names
        all_files = get_file_names(files)
        desc_list = to_list(len(all_files), descriptions, 'descriptions')
        var_list = to_list(len(all_files), var_names, 'var_names')
        self.clear()
        for file, desc, var in zip(all_files, desc_list, var_list):
            self.append(Exposures._read_one(file, desc, var))

    def append(self, exposures):
        """Check and append variables of input Exposures to current Exposures.

        Parameters:
            exposures (Exposures): Exposures instance to append to current

        Raises:
            ValueError
        """
        self._check_defaults(len(self.id))
        exposures.check()
        if self.id.size == 0:
            self.__dict__ = exposures.__dict__.copy()
            return

        self.tag.append(exposures.tag)
        if self.ref_year != exposures.ref_year:
            LOGGER.error("Append not possible. Different reference years.")
            raise ValueError
        if (self.value_unit == 'NA') and (exposures.value_unit != 'NA'):
            self.value_unit = exposures.value_unit
            LOGGER.warning("Exposures units set to %s.", self.value_unit)
        elif exposures.value_unit == 'NA':
            LOGGER.warning("Exposures units set to %s.", self.value_unit)
        elif self.value_unit != exposures.value_unit:
            LOGGER.error("Append not possible. Different units: %s != %s.", \
                             self.value_unit, exposures.value_unit)
            raise ValueError

        self.coord = np.append(self.coord, exposures.coord, axis=0)
        self.value = np.append(self.value, exposures.value)
        self.impact_id = np.append(self.impact_id, exposures.impact_id)
        self.id = np.append(self.id, exposures.id)
        self.deductible = np.append(self.deductible, exposures.deductible)
        self.cover = np.append(self.cover, exposures.cover)
        self.category_id = self._append_optional(self.category_id, \
                          exposures.category_id)
        self.region_id = self._append_optional(self.region_id, \
                        exposures.region_id)
        for (ass_haz, ass) in exposures.assigned.items():
            if ass_haz not in self.assigned:
                self.assigned[ass_haz] = ass
            else:
                self.assigned[ass_haz] = self._append_optional( \
                                         self.assigned[ass_haz], ass)

        # provide new ids to repeated ones
        _, indices = np.unique(self.id, return_index=True)
        new_id = np.max(self.id) + 1
        for dup_id in np.delete(np.arange(self.id.size), indices):
            self.id[dup_id] = new_id
            new_id += 1

    @staticmethod
    def get_sup_file_format():
        """ Get supported file extensions that can be read.

        Returns:
            list(str)
        """
        return list(FILE_EXT.keys())

    @staticmethod
    def get_def_file_var_names(src_format):
        """Get default variable names for given file format.

        Parameters:
            src_format (str): extension of the file, e.g. '.xls', '.mat'

        Returns:
            dict: dictionary with variable names
        """
        try:
            if '.' not in src_format:
                src_format = '.' + src_format
            return copy.deepcopy(READ_SET[FILE_EXT[src_format]][0])
        except KeyError:
            LOGGER.error('File extension not supported: %s.', src_format)
            raise ValueError

    @property
    def lat(self):
        """ Get latitude from coord array """
        return self.coord[:, 0]

    @property
    def lon(self):
        """ Get longitude from coord array """
        return self.coord[:, 1]

    @staticmethod
    def _read_one(file_name, description='', var_names=None):
        """Read one file and fill attributes.

        Parameters:
            file_name (str): name of the source file
            description (str, optional): description of the source data
            var_names (dict, optional): name of the variables in the file

        Raises:
            ValueError

        Returns:
            Exposures
        """
        LOGGER.info('Reading file: %s', file_name)
        new_exp = Exposures()
        new_exp.tag = Tag(file_name, description)

        extension = os.path.splitext(file_name)[1]
        try:
            reader = READ_SET[FILE_EXT[extension]][1]
        except KeyError:
            LOGGER.error('Input file extension not supported: %s.', extension)
            raise ValueError
        reader(new_exp, file_name, var_names)

        return new_exp

    @staticmethod
    def _append_optional(ini, to_add):
        """Append variable only if both are filled."""
        if (ini.size != 0) and (to_add.size != 0):
            ini = np.append(ini, to_add)
        else:
            ini = np.array([], float)
        return ini

    def _check_obligatories(self, num_exp):
        """Check coherence obligatory variables."""
        check.size(num_exp, self.value, 'Exposures.value')
        check.size(num_exp, self.impact_id, 'Exposures.impact_id')
        check.shape(num_exp, 2, self.coord, 'Exposures.coord')

    def _check_defaults(self, num_exp):
        """Check coherence optional variables. Warn and set default values \
        if empty."""
        self.deductible = check.array_default(num_exp, self.deductible, \
                                 'Exposures.deductible', np.zeros(num_exp))
        self.cover = check.array_default(num_exp, self.cover, \
                                 'Exposures.cover', self.value)

    def _check_optionals(self, num_exp):
        """Check coherence optional variables. Warn if empty."""
        check.array_optional(num_exp, self.category_id, \
                             'Exposures.category_id')
        check.array_optional(num_exp, self.region_id, \
                             'Exposures.region_id')
        check.empty_optional(self.assigned, "Exposures.assigned")
        for (ass_haz, ass) in self.assigned.items():
            if ass_haz == 'NA':
                LOGGER.warning('Exposures.assigned: assigned hazard type ' \
                               'not set.')
            check.array_optional(num_exp, ass, 'Exposures.assigned')

    def __str__(self):
        return self.tag.__str__()

    __repr__ = __str__
