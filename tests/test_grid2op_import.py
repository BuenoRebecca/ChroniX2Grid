import datetime as dt
import json
import os
import tempfile
import unittest

import pandas as pd
import pathlib
from tqdm import tqdm

import chronix2grid.constants as cst
import grid2op
from grid2op.Chronics import ChangeNothing
from grid2op.Chronics import Multifolder, GridStateFromFileWithForecasts
from grid2op.Parameters import Parameters
from grid2op.Backend import PandaPowerBackend
from grid2op.Runner import Runner
backend = PandaPowerBackend()
param = Parameters()
param.init_from_dict({"NO_OVERFLOW_DISCONNECTION": True})


class TestGrid2OpImport(unittest.TestCase):
    def setUp(self):
        self.input_folder = os.path.join(
            pathlib.Path(__file__).parent.absolute(),
            'data', 'input')
        self.CASE = 'case118_l2rpn_wcci'
        self.year = 2012
        self.start_date = '2012-01-01'
        self.grid_path = os.path.join(self.input_folder, cst.GENERATION_FOLDER_NAME,
                                      self.CASE, 'grid.json')
        self.generation_output_folder = os.path.join(
            pathlib.Path(__file__).parent.absolute(), 'data', 'output',
            'generation', self.CASE, self.start_date
        )
        self.env = grid2op.make(
            "rte_case118_example",
            test=True,
            grid_path=self.grid_path,
            chronics_class=Multifolder,
            data_feeding_kwargs={
               "path": os.path.abspath(self.generation_output_folder),
               "gridvalueClass": GridStateFromFileWithForecasts},
            param=param,
            backend=backend,
        )

    def test_grid2op_runner(self):

        path_data_saved = os.path.join(
            os.path.abspath(os.path.join(self.generation_output_folder, os.pardir)),
            'agent_results')  # , scenario_name)
        os.makedirs(path_data_saved, exist_ok=True)

        nb_episode = 1
        NB_CORE = 2
        runner = Runner(**self.env.get_params_for_runner())
        res = runner.run(nb_episode=nb_episode, nb_process=NB_CORE,
                         path_save=path_data_saved, pbar=tqdm)
