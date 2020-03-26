import os
import argparse

import numpy as np
import pandas as pd
import seaborn as sns
from itertools import product
from pathlib import Path
from matplotlib import pyplot as plt
#from entropy import spectral_entropy

import plotly.graph_objects as go
import plotly.offline as pltly
import cufflinks as cf
from plotly.subplots import make_subplots


class EconomicDispatchValidator:

    def __init__(self, consumption, ref_dispatch, synthetic_dispatch, year, num_scenario, images_repo, prods_charac=None, loads_charac=None, prices=None):

        # Create Class variables

        self.consumption = consumption
        self.ref_dispatch = ref_dispatch
        self.syn_dispatch = synthetic_dispatch
        self.num_scenario = 'Scenario_'+str(num_scenario)
        self.year = year

        # Create repo if necessary for plot saving
        self.image_repo = images_repo+'/'+str(self.year)
        if not os.path.exists(self.image_repo):
            os.mkdir(self.image_repo)

        self.image_repo += '/' + self.num_scenario
        if not os.path.exists(self.image_repo):
            os.mkdir(self.image_repo)
            os.mkdir(os.path.join(self.image_repo,'dispatch_view'))
            os.mkdir(os.path.join(self.image_repo, 'wind_kpi'))
            os.mkdir(os.path.join(self.image_repo, 'wind_load_kpi'))
            os.mkdir(os.path.join(self.image_repo, 'solar_kpi'))
            os.mkdir(os.path.join(self.image_repo, 'nuclear_kpi'))
            os.mkdir(os.path.join(self.image_repo, 'hydro_kpi'))
        
        # Reindex to avoid problems
        # self.consumption.index.rename('Time', inplace=True)
        # self.ref_dispatch.index.rename('Time', inplace=True)
        # self.syn_dispatch.index.rename('Time', inplace=True)

        # Aggregate variables
        self.agg_conso = consumption.sum(axis=1)
        self.agg_ref_dispatch = ref_dispatch.sum(axis=1)
        self.agg_syn_dispatch = synthetic_dispatch.sum(axis=1)
        
        # Read grid characteristics (csv generated by notebook...)
        self.prod_charac = prods_charac
        self.load_charac = loads_charac
        self.prices = prices

        # # Check consisten information
        # try:
        #     if self.consumption.index.equals(self.ref_dispatch.index) \
        #         and self.ref_dispatch.index.equals(self.syn_dispatch.index) \
        #         and self.syn_dispatch.index.equals(self.consumption.index):
        #         pass
        # except:
        #     print ('Input data should have same time frame')

        # Months are used in multiple KPI's
        self.months = self.ref_dispatch.index.month.to_frame()
        self.months.index = self.ref_dispatch.index
        self.months.columns = ['month']
        
        # Set precision for percentage 
        # output values
        self.precision = 1

        # Json to save all KPIs
        self.output = {}

    def _plot_heatmap(self, corr, title, path_png=None, save_png=True):
        
        ax = sns.heatmap(corr, 
                        fmt='.1f',
                        annot = False,
                        vmin=-1, vmax=1, center=0,
                        cmap=sns.diverging_palette(20, 220, n=200),
                        cbar_kws={"orientation": "horizontal", 
                                  "shrink": 0.35,
                                  },
                        square=True,
                        linewidths = 0.5,
        )
        ax.set_xticklabels(ax.get_xticklabels(),
                          rotation=45,
                          horizontalalignment='right'
        )

        ax.set_title(title, fontsize=15)

        if save_png:
            figure = ax.get_figure()    
            figure.savefig(path_png)

    def plot_barcharts(self, df_ref, df_syn, save_plots = True, path_name = '', title_component = ''):
        # Plot results
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        sns.barplot(df_ref.index, df_ref, ax=axes[0])
        sns.barplot(df_syn.index, df_syn, ax=axes[1])
        axes[0].set_title('Reference '+title_component, size = 9)
        axes[1].set_title('Synthetic '+title_component, size = 9)

        if save_plots:
            fig.savefig(path_name)
            # Save separately ref and syn plots
            # extent0 = axes[0].get_window_extent().transformed(fig.dpi_scale_trans.inverted())
            # extent1 = axes[1].get_window_extent().transformed(fig.dpi_scale_trans.inverted())
            # fig.savefig(path_name_ref, bbox_inches=extent0.expanded(1.3, 1.3))
            # fig.savefig(path_name_syn, bbox_inches=extent1.expanded(1.3, 1.3))

    def energy_mix(self, save_plots = True):


        # Sum of production per generator type
        ref_prod_per_gen = self.ref_dispatch.sum(axis = 0)
        ref_prod_per_gen = pd.DataFrame({"Prod": ref_prod_per_gen.values, "name":ref_prod_per_gen.index})
        ref_prod_per_gen = ref_prod_per_gen.merge(self.prod_charac[["name","type"]], how = 'left',
                                                  on = 'name')
        ref_prod_per_gen = ref_prod_per_gen.groupby('type').sum()
        ref_prod_per_gen = ref_prod_per_gen.sort_index()

        syn_prod_per_gen = self.syn_dispatch.sum(axis=0)
        syn_prod_per_gen = pd.DataFrame({"Prod": syn_prod_per_gen.values, "name": syn_prod_per_gen.index})
        syn_prod_per_gen = syn_prod_per_gen.merge(self.prod_charac[["name", "type"]], how='left',
                                                  on='name')
        syn_prod_per_gen = syn_prod_per_gen.groupby('type').sum()
        syn_prod_per_gen = syn_prod_per_gen.sort_index()

        # Carrier values for label
        labels = ref_prod_per_gen.index.unique()

        # Distribution of prod
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        axes[0].pie(ref_prod_per_gen, labels=labels, autopct='%1.1f%%')
        axes[1].pie(syn_prod_per_gen, labels=labels, autopct='%1.1f%%')
        axes[0].set_title('Reference Energy Mix')
        axes[1].set_title('Synthetic Energy Mix')
        if save_plots:
            # Save plot as png
            fig.savefig(os.path.join(self.image_repo, 'dispatch_view', 'energy_mix.png'))

    def _pairwise_corr_different_dfs(self, df1, df2):

        n_col_df1 = df1.shape[1]
        n_col_df2 = df2.shape[1]

        tmp_corr = np.zeros((n_col_df1, n_col_df2))
        for i, j in product(range(n_col_df1), range(n_col_df2)):
            tmp_corr[i, j] = df1.iloc[:, i].corr(df2.iloc[:, j])

        corr_wind = pd.DataFrame(tmp_corr, index=df1.columns, columns=df2.columns)

        return corr_wind.round(self.precision)

    def add_trace_in_subplot(self, fig, x=None, y=None,
                             in_row=1, in_col=1, stacked=None, name = None):
        """
        Add invididual time series to the subplot
        """
        fig.add_trace(go.Scatter(x=x, y=y, stackgroup=stacked, name = name),
                      row=in_row, col=in_col)

    def plot_carriers_pw(self, curve = 'synthetic' ,stacked=True, max_col_splot=2, save_html = True, wind_solar_only = False):
        if curve == 'synthetic':
            prod_p = self.syn_dispatch.copy()
        elif curve == 'reference':
            prod_p = self.ref_dispatch.copy()
        # Initialize full gen dataframe
        df_mw = pd.DataFrame()

        # Num unique carriers
        if wind_solar_only:
            unique_carriers = ['solar','wind']
        else:
            unique_carriers = self.prod_charac['type'].unique().tolist()

        # Initialize the plot
        rows = int(np.ceil(len(unique_carriers) / max_col_splot))
        fig = make_subplots(rows=rows,
                            cols=max_col_splot,
                            subplot_titles=unique_carriers)

        # Visualize stacked plots?
        if stacked:
            stacked_method = 'one'
        else:
            stacked_method = None

        x = prod_p.index
        row = col = 1
        for carrier in unique_carriers:
            # Get the gen names per carrier
            carrier_filter = self.prod_charac['type'].isin([carrier])
            gen_names = self.prod_charac.loc[carrier_filter]['name'].tolist()

            # Agregate me per carrier in dt
            tmp_df_mw = prod_p[gen_names].sum(axis=1)
            df_mw = pd.concat([df_mw, tmp_df_mw], axis=1)

            for gen in gen_names:
                # Add trace per carrier in same axes
                self.add_trace_in_subplot(fig, x=x, y=prod_p[gen],
                                     in_row=row, in_col=col, stacked=stacked_method, name = gen)

                # Once all ts have been added, create a new subplot
            col += 1
            if col > max_col_splot:
                col = 1
                row += 1

        # Rename df_mw columns
        df_mw.columns = unique_carriers

        if save_html:
            fig.write_html(os.path.join(self.image_repo,'dispatch_view',str(curve)+'_prod_per_carrier.html'))
        return fig, df_mw


    def __hydro_in_prices(self,
                          norm_mw, 
                          upper_quantile, 
                          lower_quantile,
                          above_norm_cap,
                          below_norm_cap):
        
        '''
        '''
        
        # Get number of gen units
        n_units = norm_mw.shape[1]
        
        # Get the price at upper/lower quantile
        eu_upper_quantile = self.prices.quantile(upper_quantile)
        eu_lower_quantile = self.prices.quantile(lower_quantile)
        
        # Test if units are above/below normalized capacity
        is_gens_above_cap =  norm_mw.ge(eu_upper_quantile, axis=1)
        is_gens_below_cap =  norm_mw.le(eu_lower_quantile, axis=1)
        
        # Test if prices are greater/lower than defined quantiles
        is_price_above_q = self.prices > eu_upper_quantile
        is_price_below_q = self.prices < eu_lower_quantile
        
        # Stacking price bool condition for all hydro units along
        # the columns and rename them as units names
        is_price_above_q_gens = is_price_above_q[['price'] * n_units]
        is_price_above_q_gens.columns = norm_mw.columns
        
        is_price_below_q_gens = is_price_below_q[['price'] * n_units]
        is_price_below_q_gens.columns = norm_mw.columns
        
        # Match occurence of price high and full gen disaptch
        high_price_kpi = 100 * (is_price_above_q_gens & is_gens_above_cap).sum(axis=0) \
                        / is_price_above_q_gens.sum(axis=0)
                        
        # Match occurence when price is lower and almost no dispatch
        low_price_kpi = 100 * (is_price_below_q_gens & is_gens_below_cap).sum(axis=0) \
                        / is_price_below_q_gens.sum(axis=0)
        
        return high_price_kpi.round(self.precision), low_price_kpi.round(self.precision)
               
    def __hydro_seasonal(self, hydro_mw):
        
        '''
        '''
        
        # We aggregate hydro per month if a user want to deliver less MW in some
        # months rather than others. 
        #
        # E.g. Typical configuration:
        # 6 month full capacity and 
        # other months with 0 MW)
        hydro_mw_month = hydro_mw.copy()
        hydro_mw_month['month'] = self.months
        mw_per_month = hydro_mw_month.groupby('month').mean().round(self.precision)
        
        return mw_per_month

        
    def hydro_kpi(self, 
                  upper_quantile = 0.95, 
                  lower_quantile = 0.05,
                  above_norm_cap = 0.9,
                  below_norm_cap = 0.1):

        '''
        Get 4 different Hydro KPI's based on the assumption the total costs
        of the system follow same curve as the consumption.

        Parameters:
        ----------

        upper_quantile (float): Quantile that define high prices.
                                (Prices are considered high whether
                                price(t) is greater than upper_quantile)
        lower_quantile (float): Quantile that define lower prices
                                (Prices are considered low whether
                                price(t) is less than lower_quantile)

        above_cap (float): Per unit (<1) criteria to establish high hydro dispatch
        below_cap (float): Per unit (<1) criteria to establish low hydro dispatch

        Returns:
        --------
        
        highPrice_kpi (dataframe): Percentage of time a generator is keeping 
                                   operating above its predefined capacity

        lowPrice_kpi (dataframe): Percentage of time a generator is keeping 
                                   operating below its predefined capacity

        mw_per_month (dataframe): Aggregated sum per month. Used to design
                                  seasonal pattern in hydro plants.
        '''  

        # Get Hydro names
        hydro_filter = self.prod_charac.type.isin(['hydro'])
        hydro_names = self.prod_charac.name.loc[hydro_filter].values

        # Normalize MW according to the max value for
        # the reference data and synthetic one
        hydro_ref = self.ref_dispatch[hydro_names]
        hydro_syn = self.syn_dispatch[hydro_names]
        
        max_mw_ref = hydro_ref.max(axis=0)
        max_mw_syn = hydro_syn.max(axis=0)
        
        norm_mw_ref = hydro_ref / max_mw_ref
        norm_mw_syn = hydro_syn / max_mw_syn
        
        # Stats for reference data
        stat_ref_high_price, stat_ref_low_price = self.__hydro_in_prices(norm_mw_ref, 
                                                                         upper_quantile, 
                                                                         lower_quantile,
                                                                         above_norm_cap,
                                                                         below_norm_cap)
        
        # Stats for synthetic data
        stat_syn_high_price, stat_syn_low_price = self.__hydro_in_prices(norm_mw_syn, 
                                                                         upper_quantile, 
                                                                         lower_quantile,
                                                                         above_norm_cap,
                                                                         below_norm_cap)

        self.plot_barcharts(stat_ref_high_price, stat_syn_high_price, save_plots=True,
                            path_name=os.path.join(self.image_repo,'hydro_kpi','high_price.png'),
                       title_component='% of time production exceed '+str(above_norm_cap)+
                                       '*Pmax when prices are high (above quantile '+str(upper_quantile*100)+')')

        self.plot_barcharts(stat_ref_low_price, stat_syn_low_price, save_plots=True,
                            path_name=os.path.join(self.image_repo,'hydro_kpi','low_price.png'),
                            title_component='% of time production is below ' + str(below_norm_cap) +
                                            '*Pmax when prices are low (under quantile ' + str(
                                lower_quantile * 100) + ')')

        # Write results
        # -- + -- + --
        self.output['Hydro'] = {'high_price_for_ref': stat_ref_high_price.to_dict(),
                                'low_price_for_ref': stat_ref_low_price.to_dict(),
                                'high_price_for_syn': stat_syn_high_price.to_dict(),
                                'low_price_for_syn': stat_syn_low_price.to_dict()
                               }
        
        # Seasonal for reference data
        ref_agg_mw_per_month = self.__hydro_seasonal(hydro_ref)
        
        # Seasonal for synthetic data
        syn_agg_mw_per_month = self.__hydro_seasonal(hydro_syn)

        self.plot_barcharts(ref_agg_mw_per_month.sum(axis = 1), syn_agg_mw_per_month.sum(axis = 1), save_plots=True,
                            path_name=os.path.join(self.image_repo,'hydro_kpi','hydro_per_month.png'),
                            title_component='hydro mean production per month for all units')

        # Write results
        # -- + -- + --
        self.output['Hydro'] = {'seasonal_month_for_ref': ref_agg_mw_per_month.to_dict(),
                                'seasonal_month_for_syn': syn_agg_mw_per_month.to_dict()
                               }

        return stat_ref_high_price, stat_ref_low_price, ref_agg_mw_per_month, \
               stat_syn_high_price, stat_syn_low_price, syn_agg_mw_per_month
    
    # def __wind_entropy(self, wind_df):
    #
    #     '''
    #     Return:
    #     -------
    #     A measure of chaoticness given a wind time series
    #     '''
    #
    #     # Add month as column for wind dataframe
    #     copied_wind_df = wind_df.copy()
    #
    #     def entropy_per_gen(df):
    #         return df.apply(lambda x: spectral_entropy(x, 100, method='welch', normalize=True), axis=0)
    #
    #     # Get spectral entropy
    #     entropy_per_month = copied_wind_df.groupby(pd.Grouper(freq='M')).apply(entropy_per_gen).round(2)
    #
    #     # Set index as month value
    #     entropy_per_month.index = entropy_per_month.index.month
    #     entropy_per_month.index.rename('month', inplace=True)
    #
    #     return entropy_per_month
        
    def __wind_metric_distrib(self, wind_df, save_plots = True):
        
        '''
        Return:
        -------
        Skewness: measures simmetry
        Kurtosis: measures tailedness
        '''
        
        # Add month as column to compute stats
        copied_wind_df = wind_df.copy()
        # wind_df_month['month'] = self.months
        
        # Get Skewness agg per month
        skewness_per_month = copied_wind_df.groupby(pd.Grouper(freq='M')).apply(lambda x: x.skew()).round(2)      
        # Set index as month value
        skewness_per_month.index = skewness_per_month.index.month
        skewness_per_month.index.rename('month', inplace=True)
        
        # Get Kurtosis agg per month                      
        kurtosis_per_month = copied_wind_df.groupby(pd.Grouper(freq='M')).apply(lambda x: x.kurtosis()).round(2)
        # Set index as month value
        kurtosis_per_month.index = kurtosis_per_month.index.month
        kurtosis_per_month.index.rename('month', inplace=True)

                                         
        return skewness_per_month, kurtosis_per_month
        
    def wind_kpi(self, save_plots=True):

        '''
        Return:
        -------

        fig (plot): Subplot (1x2) containing the aggregated wind production

        corr_wind (pd.dataFrame): Correlation matrix (10x10) between ref data
                                  and synthethic one
        '''

        # First KPI
        # Correlation between wind time series
        
        # Get the wind gen names
        wind_filter = self.prod_charac.type.isin(['wind'])
        wind_names = self.prod_charac.name[wind_filter]

        # From dispatch, get only wind units
        wind_ref = self.ref_dispatch[wind_names]
        wind_syn = self.syn_dispatch[wind_names]
    
        # Compute correlation for all elements between both dataframes
        ref_corr_wind = self._pairwise_corr_different_dfs(wind_ref, wind_ref)
        syn_corr_wind = self._pairwise_corr_different_dfs(wind_syn, wind_syn)
        
        # Write results json output
        # -- + -- + -- + -- + -- + 
        self.output['wind_kpi'] = {'corr_wind': syn_corr_wind.to_dict()}
        
        # Second KPI
        # Measure non linearity of time series
        # chaoticness_ref = self.__wind_entropy(wind_ref)
        # chaoticness_syn = self.__wind_entropy(wind_syn)
        #
        # # Write results
        # # -- + -- + --
        # self.output['wind_kpi'] = {'non_linearity_reference': chaoticness_ref.to_dict(),
        #                            'non_linearity_synthetic': chaoticness_syn.to_dict(),
        #                            }
        
        # Third KPI
        # Meaure the simmetry of wind distribution
        skewness_ref, kurtosis_ref = self.__wind_metric_distrib(wind_ref)
        skewness_syn, kurtosis_syn = self.__wind_metric_distrib(wind_syn)

        self.plot_barcharts(skewness_ref.sum(axis=1), skewness_syn.sum(axis=1), save_plots=True,
                            path_name=os.path.join(self.image_repo,'wind_kpi','skewness.png'),
                            title_component='skewness per month')
        self.plot_barcharts(kurtosis_ref.sum(axis=1), kurtosis_syn.sum(axis=1), save_plots=True,
                            path_name=os.path.join(self.image_repo, 'wind_kpi', 'kurtosis.png'),
                            title_component='kurtosis per month')

        # Write results 
        # -- + -- + --
        self.output['wind_kpi'] = {'skewness_reference': skewness_ref.to_dict(),
                                   'skewness_synthetic': skewness_syn.to_dict(),
                                   'kurtosis_reference': kurtosis_ref.to_dict(),
                                   'kurtosis_synthetic': kurtosis_syn.to_dict(),
                                   }
        
        # Four KPI
        # Plot distributions

        # Aggregate time series
        agg_ref_wind = wind_ref.sum(axis=1)
        agg_syn_wind = wind_syn.sum(axis=1)

        # Plot results
        # Correlation heatmaps
        fig, axes = plt.subplots(1, 2, figsize=(17,5))
        sns.heatmap(ref_corr_wind, annot=True, linewidths=.5, ax=axes[0])
        sns.heatmap(syn_corr_wind, annot = True, linewidths=.5, ax=axes[1])
        if save_plots:
            fig.savefig(os.path.join(self.image_repo, 'wind_kpi', 'wind_corr_heatmap.png'))

        # Distribution of prod
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        sns.distplot(agg_ref_wind, ax=axes[0])
        sns.distplot(agg_syn_wind, ax=axes[1])
        axes[0].set_title('Reference Distribution of agregate wind production')
        axes[1].set_title('Synthetic Distribution of agregate wind production')
        if save_plots:
            # Save plot as png
            fig.savefig(os.path.join(self.image_repo,'wind_kpi','histogram.png'))

        return syn_corr_wind, \
               skewness_ref, skewness_syn, \
               kurtosis_ref, kurtosis_syn

    def __solar_at_night(self,
                         solar_df,
                         params,
                         aggregated=False
                         ):
        
        '''
        '''
        
        if aggregated:
            solar_df = solar_df.sum(axis=1)
            
        # Extract parameters
        monthly_pattern = params['monthly_pattern']
        hours = params['hours']
        
        # Add month variable solar df
        solar_df_month = pd.concat([solar_df, self.months], axis=1)
        
        # Iterate over all season per month to check if solar is 
        # present during night hours defined by a deterministic 
        # criteria per season.
        season_at_night = {}
        for season, month in monthly_pattern.items():

            # Filter by season (including all possible months avaible in season)
            month_filter = solar_df_month.month.isin(month)
            season_solar = solar_df_month.loc[month_filter, solar_df_month.columns != 'month']
                    
            if not season_solar.empty:
                # Filter by season and hours
                sum_over_season = season_solar.drop(season_solar.between_time(hours[season][0], hours[season][1]).index).sum(axis=0)
                percen_over_season = 100 * sum_over_season / season_solar.sum(axis=0)
                percen_over_season = percen_over_season.round(self.precision)

                # Save results in a dictionary
                season_at_night.update({season : percen_over_season})
                
        return season_at_night
        
    def __solar_cloudiness(self,
                           solar_df,
                           cloud_quantile,
                           factor_cloud):
        
        '''
        '''
        
        # Using all data, we get a unique x quantile
        # in order to grab a long term value
        solar_q = solar_df.quantile(cloud_quantile)
        
        # Per day, we are interested to get x quantile only when
        # generators are producing energy
        solar_q_perday = solar_df.replace(0, np.nan).resample('D').quantile(cloud_quantile)

        # Measure cloudiness: we compare the quantile values per
        # day with a long them x quantile truncated it a factor
        # cloudiness = solar_q_perday <= (solar_q * factor_cloud)
        thresholds = solar_q * factor_cloud
        cloudiness = pd.DataFrame({col: solar_q_perday[col]<=thresholds[col] for col in solar_q_perday.columns})

        # # Add month column to get some particular stats
        # # Add months to solar cloudiness measure df
        # month = cloudiness.index.month.to_frame()
        # month.index = cloudiness.index
        # cloudiness['month'] = month
        
        # Get in percentage the number of days solar
        # generators have been producing below the factor
        # (We considerer as a cloudiness's day)
        # percen_cloud = 100 * cloudiness.groupby('month').drop('month', axis=1).sum() \
        #                    / cloudiness.groupby('month').drop('month', axis=1).count()
        # percen_cloud = percen_cloud.round(self.precision)
        
        percen_cloud = 100 * cloudiness.groupby(pd.Grouper(freq='M')).sum() \
                             / cloudiness.groupby(pd.Grouper(freq='M')).count()
                             
        percen_cloud.index = percen_cloud.index.month
        percen_cloud.index.rename('month', inplace=True)
        
        return percen_cloud.round(self.precision)
        
    def solar_kpi(self, 
                  cloud_quantile=0.95,
                  cond_below_cloud=0.57, save_plots = True,
                  **kwargs):

        '''

        Parameters:
        ----------

        moderate_cloud_quantile: Quantile applied to the consequitive
                                 difference solar hisrogram to determine
                                 large spiked due to cloudness.
        severe_cloud_quantile:   Quantile applied to the consequitive
                                 difference solar hisrogram to determine
                                 large spiked due to cloudness.

        **kwargs:

            monthly_pattern: Contains a dictionary to define the month
                                a solar time series shoud follow (e.g summer
                                months should have more production rather than
                                sping).

                        monthly_pattern = {'summer': [6,7,8], 
                                           'fall': [9,10,11],
                                           'winter': [12,1,2], 
                                           'spring': [2,3,4,5]}

            hours: Defines the hours solar is producing energy to the system
                        per season.

                        hours = {'summer': ('07:00', '20:00'),
                                 'fall': ('08:00', '18:00'),
                                 'winter': ('09:30', '16:30')}

        Returns:
        --------

        corr_solar (pd.DataFrame):  Correlation matrix between reference and synthetic data

        season_night_percen (dict): Dictionary containing season percentage solar units has been
                                    producing energy out of hours.
        
        percen_moderate (dict):     Dictionary per solar unit that contains the number of times in
                                    percentage and per month a specific solar unit has overcome a pre-defined
                                    moderate quantile given the ref dispatch.

        percen_severe (dict):       Dictionary per solar unit that contains the number of times in
                                    percentage and per month a specific solar unit has overcome a pre-defined
                                    severe qunantile given the ref dispatch.
        
        '''

        # Get the solar gen names
        solar_filter = self.prod_charac.type.isin(['solar'])
        solar_names = self.prod_charac.name.loc[solar_filter].values

        # From data, extract only solar time series
        solar_ref = self.ref_dispatch[solar_names]
        solar_syn = self.syn_dispatch[solar_names]

        agg_ref_solar = solar_ref.sum(axis = 1)
        agg_syn_solar = solar_syn.sum(axis = 1)

        # First KPI
        # -- + -- +
        # Get correlation matrix (10 x 10)
        ref_corr_solar = self._pairwise_corr_different_dfs(solar_ref, solar_ref)
        syn_corr_solar = self._pairwise_corr_different_dfs(solar_syn, solar_syn)

        # Plot results
        # Correlation heatmaps
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        sns.heatmap(ref_corr_solar, annot=True, linewidths=.5, ax=axes[0])
        sns.heatmap(syn_corr_solar, annot=True, linewidths=.5, ax=axes[1])
        if save_plots:
            fig.savefig(os.path.join(self.image_repo, 'solar_kpi', 'solar_corr_heatmap.png'))

        # Distribution of prod
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        sns.distplot(agg_ref_solar, ax=axes[0])
        sns.distplot(agg_syn_solar, ax=axes[1])
        axes[0].set_title('Reference Distribution of agregate solar production')
        axes[1].set_title('Synthetic Distribution of agregate solar production')
        if save_plots:
            # Save plot as png
            fig.savefig(os.path.join(self.image_repo, 'solar_kpi', 'histogram.png'))


        # Write its value
        # -- + -- + -- +
        self.output['solar_kpi'] = {'solar_corr': syn_corr_solar.to_dict()}
        
        # Second KPI
        # -- + -- +
        # Get percentage solar at night
        
        if not kwargs:

            monthly_pattern = {'summer': [6,7,8], 'fall': [9,10,11],
                               'winter': [12,1,2], 'spring': [2,3,4,5]}

            hours = {'summer': ('07:00', '20:00'),
                     'fall': ('08:00', '18:00'),
                     'winter': ('09:30', '16:30'),
                     'spring': ('08:00', '18:00')}
            params = {'monthly_pattern': monthly_pattern, 'hours': hours}

        else:
            params = kwargs

        # Get percentage solar productions for reference data
        solar_night_ref = self.__solar_at_night(solar_ref, params=params)

        # Get percentage solar productions for synthetic data
        solar_night_syn = self.__solar_at_night(solar_syn, params=params)

        # Compute mean of generators
        solar_night_syn_mean = pd.DataFrame({key: [solar_night_syn[key].mean()] for key in solar_night_syn.keys()})
        solar_night_syn_mean = solar_night_syn_mean.sum(axis = 0)

        solar_night_ref_mean = pd.DataFrame({key: [solar_night_ref[key].mean()] for key in solar_night_ref.keys()})
        solar_night_ref_mean = solar_night_ref_mean.sum(axis=0)

        # Plot and save it average per season
        self.plot_barcharts(solar_night_ref_mean, solar_night_syn_mean, save_plots=True,
                            path_name=os.path.join(self.image_repo,'solar_kpi','solar_at_night.png'),
                            title_component='Mean % of production at night per season')


        # Write output
        # -- + -- + --
        self.output['solar_kpi'] = {'season_solar_at_night_reference': solar_night_ref,
                                    'season_solar_at_night_synthetic': solar_night_syn,
                                    }

        # Third KPI
        # -- + -- +
        # Measure Cloudiness as counting the number of days 
        # per month when the x quantile is below a factor
        # specified by the method.
        
        cloudiness_ref = self.__solar_cloudiness(solar_ref,
                                                 cloud_quantile=cloud_quantile,
                                                 factor_cloud=cond_below_cloud)
        
        cloudiness_syn = self.__solar_cloudiness(solar_syn,
                                                 cloud_quantile=cloud_quantile,
                                                 factor_cloud=cond_below_cloud)

        self.plot_barcharts(cloudiness_ref.sum(axis=1), cloudiness_syn.sum(axis=1), save_plots=True,
                            path_name=os.path.join(self.image_repo,'solar_kpi','cloudiness.png'),
                            title_component='Cloudiness per month (number of daily quantile '+str(cloud_quantile)+' below '+str(round(cond_below_cloud*100))+
                                            ' % of general quantile '+str(cloud_quantile)+')')
        # # Write its value
        # # -- + -- + -- +
        self.output['solar_kpi'] = {'cloudiness_reference': cloudiness_ref.to_dict(),
                                    'cloudiness_synthetic': cloudiness_syn.to_dict()
                                    }

        return syn_corr_solar, solar_night_ref, solar_night_syn, cloudiness_ref, cloudiness_syn


    def wind_load_kpi(self):

        '''
        Return:
        ------

        corr(win, load) Region R1 (pd.DataFrame)
        corr(win, load) Region R2 (pd.DataFrame)
        corr(win, load) Region R3 (pd.DataFrame)
        '''

        # Get the solar gen names
        wind_filter = self.prod_charac.type.isin(['wind'])

        regions = ['R1', 'R2', 'R3']
        corr_rel = []
        for region in regions:

            # Create zone filter for wind and loads
            wind_region_filter = self.prod_charac.zone.isin([region])
            wind_names = self.prod_charac.loc[wind_filter & wind_region_filter]['name']
            loads_names_filter = self.load_charac[self.load_charac.zone == region]['name']

            # Extract only wind units per region
            wind_gens_in_region = self.syn_dispatch[wind_names]
            loads_in_region = self.consumption[loads_names_filter]

            # Compute correlation matrix
            tmp_corr = self._pairwise_corr_different_dfs(wind_gens_in_region, loads_in_region)
            corr_rel.append(tmp_corr)

        # Plot results
        plt.figure(figsize=(18,4))
        self._plot_heatmap(corr_rel[0], 
                           'Correlation Wind Load Region R1',
                           path_png=os.path.join(self.image_repo,'wind_load_kpi','syn_corr_wind_load_R1.png'),
                           save_png=True)
        
        plt.figure(figsize=(18,4))
        self._plot_heatmap(corr_rel[1], 
                           'Correlation Wind Load Region R2',
                           path_png=os.path.join(self.image_repo,'wind_load_kpi','syn_corr_wind_load_R2.png'),
                           save_png=True)

        plt.figure(figsize=(12,3))
        self._plot_heatmap(corr_rel[2], 
                           'Correlation Wind Load Region R3',
                            path_png=os.path.join(self.image_repo,'wind_load_kpi','syn_corr_wind_load_R3.png'),
                            save_png=True)


        return corr_rel[0], corr_rel[1], corr_rel[2]

    def nuclear_kpi(self, save_plots=True):

        """
        Return:
        ------

        None
        """

        # Get the nuclear gen names
        nuclear_filter = self.prod_charac.type.isin(['nuclear'])
        nuclear_names = self.prod_charac.name.loc[nuclear_filter].values

        # Extract only nuclear power plants
        nuclear_ref = self.ref_dispatch[nuclear_names]
        nuclear_syn = self.syn_dispatch[nuclear_names]

        agg_nuclear_ref = nuclear_ref.sum(axis = 1)
        agg_nuclear_syn = nuclear_syn.sum(axis = 1)


        # Distribution of prod
        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        axes[0].hist(agg_nuclear_ref, bins = 100, alpha = 1)
        axes[1].hist(agg_nuclear_syn, bins = 100, alpha = 1)
        axes[0].set_title('Reference Distribution of agregate nuclear production')
        axes[1].set_title('Synthetic Distribution of agregate nuclear production')
        if save_plots:
            # Save plot as png
            fig.savefig(os.path.join(self.image_repo, 'nuclear_kpi', 'production_distribution.png'))

        ## Nuclear lag distribution
        nuclear_lag_ref = agg_nuclear_ref.diff()
        nuclear_lag_syn = agg_nuclear_syn.diff()

        fig, axes = plt.subplots(1, 2, figsize=(17, 5))
        axes[0].hist(nuclear_lag_ref.values, bins=100, alpha=1)
        axes[1].hist(nuclear_lag_syn.values, bins=100, alpha=1)
        axes[0].set_title('Reference Distribution of agregate nuclear production')
        axes[1].set_title('Synthetic Distribution of agregate nuclear production')
        if save_plots:
            # Save plot as png
            fig.savefig(os.path.join(self.image_repo, 'nuclear_kpi', 'lag_distribution.png'))


        ## Monthly maintenance percentage time
        maintenance_ref = agg_nuclear_ref.resample('1M').agg(lambda x: x[x==0.].count()/x.count())
        maintenance_syn = agg_nuclear_syn.resample('1M').agg(lambda x: x[x==0.].count()/x.count())

        maintenance_ref.index = maintenance_ref.index.month
        maintenance_syn.index = maintenance_syn.index.month


        self.plot_barcharts(maintenance_ref, maintenance_syn, save_plots=save_plots,
                            path_name=os.path.join(self.image_repo, 'nuclear_kpi', 'maintenance_percentage_of_time_per_month.png'),
                            title_component='% of time in maintenance at night per month')

        return None
