"""
Tests on Black marble.
"""

import unittest
import numpy as np
from cartopy.io import shapereader

from climada.entity.exposures.black_marble import BlackMarble
from climada.entity.exposures.nightlight import load_nightlight_nasa, load_nightlight_noaa, NOAA_BORDER
from climada.entity.exposures import nightlight as nl_utils

class Test2013(unittest.TestCase):
    """Test black marble of previous in 2013."""

    def test_spain_pass(self):
        country_name = ['Spain']
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 2013, res_km=1, sea_res=(200, 50))
        self.assertIn('GDP ESP 2013: 1.362e+12.', cm.output[0])
        self.assertIn('Income group ESP 2013: 4.', cm.output[1])
        self.assertIn("Nightlights from NOAA's earth observation group for year 2013.", cm.output[2])
        self.assertIn("Processing country Spain.", cm.output[3])
        self.assertIn("Generating resolution of approx 1 km.", cm.output[4])

    def test_sint_maarten_pass(self):
        country_name = ['Sint Maarten']
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 2013, res_km=0.2, sea_res=(200, 50))
        self.assertIn('GDP SXM 2014: 3.658e+08.', cm.output[0])
        self.assertIn('Income group SXM 2013: 4.', cm.output[1])
        self.assertIn("Nightlights from NOAA's earth observation group for year 2013.", cm.output[2])
        self.assertIn("Processing country Sint Maarten.", cm.output[3])
        self.assertIn("Generating resolution of approx 0.2 km.", cm.output[4])

    def test_anguilla_pass(self):
        country_name = ['Anguilla']
        ent = BlackMarble()
        ent.set_countries(country_name, 2013, res_km=0.2)
        self.assertEqual(ent.ref_year, 2013)
        self.assertIn("Anguilla 2013 GDP: 1.754e+08 income group: 3", ent.tag.description)

class Test1968(unittest.TestCase):
    """Test black marble of previous years to 1992."""
    def test_switzerland_pass(self):
        country_name = ['Switzerland']
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 1968, res_km=0.5)
        self.assertIn('GDP CHE 1968: 1.894e+10.', cm.output[0])
        self.assertIn('Income group CHE 1987: 4.', cm.output[1])
        self.assertIn("Nightlights from NOAA's earth observation group for year 1992.", cm.output[2])
        self.assertTrue("Processing country Switzerland." in cm.output[-2])
        self.assertTrue("Generating resolution of approx 0.5 km." in cm.output[-1])

class Test2012(unittest.TestCase):
    """Test year 2012 flags."""
    
    def test_from_hr_flag_pass(self):
        """Check from_hr flag in set_countries method."""
        country_name = ['Turkey']
        
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 2012, res_km=5.0)
        self.assertTrue('NOAA' in cm.output[-3])
        size1 = ent.value.size
    
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 2012, res_km=5.0, from_hr=True)
        self.assertTrue('NASA' in cm.output[-3])
        size2 = ent.value.size
    
        ent = BlackMarble()
        with self.assertLogs('climada.entity.exposures.black_marble', level='INFO') as cm:
            ent.set_countries(country_name, 2012, res_km=5.0, from_hr=False)
        self.assertTrue('NOAA' in cm.output[-3])
        size3 = ent.value.size
    
        self.assertEqual(size1, size3)
        self.assertTrue(size1 < size2)

class BMFuncs(unittest.TestCase):
    """Test plot functions."""
    def test_cut_nasa_esp_pass(self):
        """Test load_nightlight_nasa function."""
        shp_fn = shapereader.natural_earth(resolution='10m',
                                           category='cultural', 
                                           name='admin_0_countries')
        shp_file = shapereader.Reader(shp_fn)
        list_records = list(shp_file.records())
        for info_idx, info in enumerate(list_records):
            if info.attributes['ADM0_A3'] == 'AIA':
                bounds = info.bounds
        
        req_files = nl_utils.check_required_nl_files(bounds)
        files_exist, _ = nl_utils.check_nl_local_file_exists(req_files)
        nl_utils.download_nl_files(req_files, files_exist)
        
        nightlight, coord_nl = load_nightlight_nasa(bounds, req_files, 2016)
   
        self.assertTrue(coord_nl[0, 0] < bounds[1])
        self.assertTrue(coord_nl[1, 0] < bounds[0])
        self.assertTrue(coord_nl[0, 0]+(nightlight.shape[0]-1)*coord_nl[0,1] > bounds[3])
        self.assertTrue(coord_nl[1, 0]+(nightlight.shape[1]-1)*coord_nl[1,1] > bounds[2])

    def test_load_noaa_pass(self):
        """Test load_nightlight_noaa function."""
        nightlight, coord_nl, fn_nl = load_nightlight_noaa(2013)
           
        self.assertEqual(coord_nl[0, 0], NOAA_BORDER[1])
        self.assertEqual(coord_nl[1, 0], NOAA_BORDER[0])
        self.assertEqual(coord_nl[0, 0]+(nightlight.shape[0]-1)*coord_nl[0,1], NOAA_BORDER[3])
        self.assertEqual(coord_nl[1, 0]+(nightlight.shape[1]-1)*coord_nl[1,1], NOAA_BORDER[2])

    def test_set_country_pass(self):
        """Test exposures attributes after black marble."""
        country_name = ['Switzerland', 'Germany']
        ent = BlackMarble()
        ent.set_countries(country_name, 2013, res_km=5.0)
        ent.check()
                
        self.assertEqual(np.unique(ent.region_id).size, 2)
        self.assertEqual(np.unique(ent.impact_id).size, 1)
        self.assertEqual(ent.ref_year, 2013)
        self.assertIn('Switzerland 2013 GDP: ', ent.tag.description[0])
        self.assertIn('Germany 2013 GDP: ', ent.tag.description[1])
        self.assertIn('income group: 4', ent.tag.description[0])
        self.assertIn('income group: 4', ent.tag.description[1])
        self.assertIn('F182013.v4c_web.stable_lights.avg_vis.p', ent.tag.file_name[0])
        self.assertIn('F182013.v4c_web.stable_lights.avg_vis.p', ent.tag.file_name[1])

# Execute Tests
TESTS = unittest.TestLoader().loadTestsFromTestCase(Test2013)
TESTS.addTests(unittest.TestLoader().loadTestsFromTestCase(Test1968))
TESTS.addTests(unittest.TestLoader().loadTestsFromTestCase(Test2012))
TESTS.addTests(unittest.TestLoader().loadTestsFromTestCase(BMFuncs))
unittest.TextTestRunner(verbosity=2).run(TESTS)
