import os
import sys
import json

from .pivot_utils import chronics_to_kpi, renewableninja_to_kpi, eco2mix_to_kpi_regional, nrel_to_kpi


def pivot_format(chronics_folder, kpi_input_folder, year, prods_charac, loads_charac, wind_solar_only, params, case):
    """
        This functions contains pivot formatting of reference and synthetic chronics, in a usable format by KPI computation.

        Parameters
        ----------
        chronics_folder (str): path to folder which contains generated chronics
        kpi_input_folder (str): path to folder of kpi inputs, which contains paramsKPI.json and benchmark folders. paramsKPI.json tells which benchmark to read as reference
        year (int): year in which results are written
        scenario_name (int): name of the scenario to study (KPIs are computed for each scenario separately)
        prods_charac (pandas.DataFrame): characteristics of generators such as Pmax, carrier and region
        loads_charac (pandas.DataFrame): characteristics of loads node such as Pmax, type of demand and region
        wind_solar_only (boolean): True if the generated chronics contain only wind, solar and load chronics, False otherwise
        params (dict): configuration params computed from params.json, such as timestep or mesh characteristics
        case (str): identify the studied case for chronics generation, such as l2rpn_118

        Returns
        -------
        pandas.DataFrame: reference productions per generator
        pandas.DataFrame: reference consumption per load node
        pandas.DataFrame: synthetic productions per generator
        pandas.DataFrame: synthetic consumption per load node
        dict: monthly patterns for seasons in KPI computation, read in paramsKPI.json
        dict: night hours per season to use in KPI computation, read in paramsKPI.json
        pandas.DataFrame: (only if wind_solar_only is False) reference prices per timestep
        pandas.DataFrame: (only if wind_solar_only is False) synthetic prices per timestep
        """

    # Read json parameters for KPI configuration
    kpi_case_input_folder = os.path.join(kpi_input_folder, case)
    json_filepath = os.path.join(kpi_case_input_folder, 'paramsKPI.json')
    with open(json_filepath, 'r') as json_file:
        paramsKPI = json.load(json_file)
    comparison = paramsKPI['comparison']
    timestep = paramsKPI['timestep']

    ## Format chosen benchmark chronics calling designed pivot functions
    if comparison == 'France':
        corresp_regions = {'R1':"Hauts-de-France", "R2": "Nouvelle-Aquitaine", "R3": "PACA"}
        if wind_solar_only:
            ref_prod, ref_load = renewableninja_to_kpi(kpi_case_input_folder, timestep, loads_charac, prods_charac, year,
                                                       params, corresp_regions, case)
        else:
            ref_prod, ref_load, ref_prices = eco2mix_to_kpi_regional(kpi_case_input_folder, timestep, prods_charac, loads_charac, year, params,
                                                         corresp_regions)
    elif comparison == 'Texas':

        if wind_solar_only:
            ref_prod, ref_load  = nrel_to_kpi(kpi_case_input_folder, timestep, prods_charac, loads_charac, params,year)
        else:
            print("Computation stopped: Texas Benchmark not implemented for a whole energy mix. Launch KPI computation in mode wind solar and load only.")
            sys.exit()
    else:
        print("Please chose one available benchmark in paramsKPI.json/comparison. Given comparison is: "+comparison)
        sys.exit()

    # Format generated chronics
    if wind_solar_only:
        syn_prod, syn_load = chronics_to_kpi(chronics_folder, timestep, params,
                                             thermal=not wind_solar_only)
        return ref_prod, ref_load, syn_prod, syn_load, paramsKPI
    else:
        syn_prod, syn_load, prices = chronics_to_kpi(
            chronics_folder, timestep, params, thermal=not wind_solar_only)
        return ref_prod, ref_load, syn_prod, syn_load, ref_prices, prices, paramsKPI


