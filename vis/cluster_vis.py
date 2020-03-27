"""
Visualization script

Written by Jatin Mathur and Ed Oughton.

January 2020

"""
import os
import configparser
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import geopandas as gpd
import matplotlib.colors
import geoio
import math
import warnings
warnings.filterwarnings('ignore')

CONFIG_DATA = configparser.ConfigParser()
CONFIG_DATA.read(os.path.join(os.path.dirname(__file__), '..', 'scripts','script_config.ini'))

CONFIG_COUNTRY = configparser.ConfigParser()
CONFIG_COUNTRY.read('script_config.ini')
COUNTRY = CONFIG_COUNTRY['DEFAULT']['COUNTRY']
SHAPEFILE_DIR = f'countries/{COUNTRY}/shapefile'
GRID_DIR = f'countries/{COUNTRY}/grid'
RESULTS_DIR = f'countries/{COUNTRY}/results'
WORLDPOP = 'data/world_population'
CLUSTER_DATA_DIR = f'data/LSMS/{COUNTRY}/processed/cluster_data.csv'
CLUSTER_FIGURES_DIR = f'data/LSMS/{COUNTRY}/figures'
CLUSTER_PREDICTIONS_DIR = f'data/LSMS/{COUNTRY}/output/cluster_predictions.csv'

# Purchasing Power Adjustment
PPP = float(CONFIG_COUNTRY['DEFAULT']['PPP'])

def create_folders():
    os.makedirs(CLUSTER_FIGURES_DIR, exist_ok=False)

def prepare_data():
    """
    Preprocessing function.

    """

    print("Preprocessing...")

    df_clusters = pd.read_csv(CLUSTER_PREDICTIONS_DIR)

    filename = 'ppp_2020_1km_Aggregated.tif'
    img = geoio.GeoImage(os.path.join(WORLDPOP, filename))
    im_array = np.squeeze(img.get_data())

    cluster_population = []
    for _, r in df_clusters.iterrows():
        min_lat, min_lon, max_lat, max_lon = create_space(r.cluster_lat, r.cluster_lon)
        xminPixel, yminPixel = img.proj_to_raster(min_lon, min_lat)
        xmaxPixel, ymaxPixel = img.proj_to_raster(max_lon, max_lat)

        xminPixel, xmaxPixel = min(xminPixel, xmaxPixel), max(xminPixel, xmaxPixel)
        yminPixel, ymaxPixel = min(yminPixel, ymaxPixel), max(yminPixel, ymaxPixel)

        xminPixel, yminPixel, xmaxPixel, ymaxPixel = (
            int(xminPixel), int(yminPixel), int(xmaxPixel), int(ymaxPixel)
        )
        cluster_population.append(
            round(im_array[yminPixel:ymaxPixel,xminPixel:xmaxPixel].mean()))

    df_clusters['cluster_population_density_1km2'] = cluster_population

    return df_clusters


def create_space(lat, lon):
    """
    Creates a 100km^2 area bounding box.

    Parameters
    ----------
    lat : float
        Latitude
    lon : float
        Longitude

    """
    v = (180 / math.pi) * (5000 / 6378137) # approximately 0.045
    min_lat = lat - v
    min_lon = lon - v
    max_lat = lat + v
    max_lon = lon + v

    return min_lat, min_lon, max_lat, max_lon


def r2(x, y):

    coef = round(np.corrcoef(x, y)[0, 1]**2, 3)

    return coef


def create_regplot(data):
    print("Creating regplot")

    data = data[data['cluster_annual_consumption_pc'] <= 10000]

    data['cluster_monthly_consumption_pc'] = data['cluster_annual_consumption_pc'] / 12
    data['cluster_monthly_phone_consumption_pc'] = data['cluster_annual_phone_consumption_pc'] / 12
    data['cluster_monthly_phone_cost_pc'] = data['cluster_estimated_annual_phone_cost_pc'] / 12

    bins = [0, 400, 800, 1200, 4020]
    labels = [5, 15, 25, 60]
    data['pop_density_binned'] = pd.cut(data['cluster_population_density_1km2'], bins=bins, labels=labels)

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(10,8))

    coef1 = r2(data['cluster_nightlights'], data['cluster_monthly_consumption_pc'])
    g = sns.regplot(y="cluster_nightlights", x="cluster_monthly_consumption_pc",
        data=data, ax=ax1, scatter_kws={'alpha': 0.2, 'color':'blue'},
        line_kws={'alpha': 0.5, 'color':'black'})
    g.set(ylabel='Luminosity (DN)', xlabel='Consumption per capita ($ per month)',
        title='Luminosity vs\nConsumption (R$^2$={})'.format(str(coef1)),
        ylim=(0, 50))

    coef2 = r2(data['cluster_nightlights'], data['cluster_monthly_phone_consumption_pc'])
    g = sns.regplot(y="cluster_nightlights", x="cluster_monthly_phone_consumption_pc",
        data=data, ax=ax2, scatter_kws={'alpha': 0.2, 'color':'blue'},
        line_kws={'alpha': 0.5, 'color':'black'})
    g.set(ylabel='Luminosity (DN)', xlabel='Total Cost ($ per month)',
        title='Luminosity vs\nTotal Cost of Phone Services (R$^2$={})'.format(str(coef2)),
        ylim=(0, 50))

    #'hh_f34': 'cellphones_pc',
    coef3 = r2(data['cluster_nightlights'], data['cluster_cellphones_pc'])
    g = sns.regplot(y="cluster_nightlights", x="cluster_cellphones_pc",
        data=data, ax=ax3, scatter_kws={'alpha': 0.2, 'color':'blue'},
        line_kws={'alpha': 0.5, 'color':'black'})
    g.set(ylabel='Luminosity (DN)', xlabel='Number of Cell Phones',
        title='Luminosity vs Total Cell \nPhones per HH (R$^2$={})'.format(str(coef3)),
        ylim=(0, 50))

    #'hh_f35': 'estimated_annual_phone_cost_pc'
    data = data.dropna(subset=['cluster_nightlights', 'cluster_monthly_phone_cost_pc'])
    coef4 = r2(data['cluster_nightlights'].dropna(), data['cluster_monthly_phone_cost_pc'].dropna())
    g = sns.regplot(y="cluster_nightlights", x="cluster_monthly_phone_cost_pc",
        data=data, ax=ax4, scatter_kws={'alpha': 0.2, 'color':'blue'},
        line_kws={'alpha': 0.5, 'color':'black'})
    g.set(ylabel='Luminosity (DN)', xlabel='Annual consumption ($)',
        title='Luminosity vs Annual Consumption\nof Phone and Fax Services (R$^2$={})'.format(str(coef4)),
        ylim=(0, 50))

    fig.tight_layout()
    save_dir = os.path.join(CLUSTER_FIGURES_DIR, 'regplot.png')
    print(f'Saving figure to {save_dir}')
    fig.savefig(save_dir)

    print("Plotting completed")


def results(data):

    fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8)) = plt.subplots(
        4, 2, figsize=(10,10))

    g = sns.regplot(x="cons_pred_10km", y="cons", data=data, ax=ax1)
    g.set(xlabel='Predicted Consumption ($)', ylabel='Consumption ($)',
        title='Consumption vs \n Predicted Consumption (cluster_nightlights)')

    g = sns.regplot(x="predicted_cons", y="cons", data=data, ax=ax2)
    g.set(xlabel='Predicted Consumption ($ per month)',
        ylabel='Consumption ($ per month)',
        title='Consumption vs \n Luminosity (CNN)')

    g = sns.regplot(x="predicted_phone_cons", y="cluster_phone_cons",
        data=data, ax=ax4)
    g.set(xlabel='Annual Spending ($)',
        ylabel='Predicted Annual Spending ($)',
        title='Predicted Spending on Phone Services (rexp_cat083) (CNN)')

    g = sns.regplot(x="predicted_cluster_hh_f35", y="cluster_hh_f35",
        data=data, ax=ax6)
    g.set(xlabel='Annual Cost ($)',
        ylabel='Annual Predicted Cost ($)',
        title='Predicted Annual Cost of Cell Phone Services (hh_f35) (CNN)')

    g = sns.regplot(x="predicted_cluster_hh_f34", y="cluster_hh_f34",
        data=data, ax=ax8)
    g.set(xlabel='Cell Phones per Household',
        ylabel='Predicted Cell Phones per Household',
        title='Predicted Cell Phones (hh_f34) (CNN)')

    fig.tight_layout()
    fig.savefig(os.path.join(CLUSTER_FIGURES_DIR, 'regplot.png'))

    return print('Completed regplot')


if __name__ == '__main__':

    create_folders()

    data = prepare_data()

    create_regplot(data)