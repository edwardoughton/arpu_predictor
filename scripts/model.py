import configparser
import torch
import torch.nn as nn
from torchvision import transforms
import pandas as pd
import numpy as np
import os
from PIL import Image
import matplotlib.pyplot as plt
from tqdm import tqdm
import joblib
import logging
import warnings
warnings.filterwarnings('ignore')

CONFIG = configparser.ConfigParser()
CONFIG.read('script_config.ini')

GRID_DIR = CONFIG['DEFAULT']['GRID_DIR']
IMAGE_DIR = CONFIG['DEFAULT']['IMAGE_DIR']
CNN_DIR = CONFIG['MODELS']['CNN_DIR']
RIDGE_PHONE_DENSITY_DIR = CONFIG['MODELS']['RIDGE_PHONE_DENSITY_DIR']
RIDGE_PHONE_CONSUMPTION_DIR = CONFIG['MODELS']['RIDGE_PHONE_CONSUMPTION_DIR']
RIDGE_CONSUMPTION_DIR = CONFIG['MODELS']['RIDGE_CONSUMPTION_DIR']

CNN_FEATURE_SAVE_DIR = CONFIG['RESULTS']['CNN_FEATURE_SAVE_DIR']
RIDGE_PHONE_DENSITY_SAVE_DIR = CONFIG['RESULTS']['RIDGE_PHONE_DENSITY_SAVE_DIR']
RIDGE_PHONE_CONSUMPTION_SAVE_DIR = CONFIG['RESULTS']['RIDGE_PHONE_CONSUMPTION_SAVE_DIR']
RIDGE_CONSUMPTION_SAVE_DIR = CONFIG['RESULTS']['RIDGE_CONSUMPTION_SAVE_DIR']

DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

def filename_to_im_tensor(file):
    transformer = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    im = plt.imread(file)[:,:,:3]
    im = transformer(im)
    return im[None].to(DEVICE)

class ModelPipeline:
    def __init__(self):
        print('loading CNN...')
        self.cnn = torch.load(CNN_DIR, map_location=DEVICE).eval()
        print('loading Ridge Regression models...')
        self.ridge_phone_density = joblib.load(RIDGE_PHONE_DENSITY_DIR)
        self.ridge_phone_consumption = joblib.load(RIDGE_PHONE_CONSUMPTION_DIR)
        self.ridge_consumption = joblib.load(RIDGE_CONSUMPTION_DIR)

    def run_pipeline(self, metric):
        assert metric in ['phone_density', 'phone_consumption', 'consumption']
        print('Reading reference dataframe...')
        try:
            df = pd.read_csv(os.path.join(GRID_DIR, 'image_download_locs.csv'))
        except Exception as e:
            logging.error('Make sure there is a file called image_download_locs.csv in ' + GRID_DIR, exc_info=True)
            exit(1)
        
        print('Extracting features using ' + IMAGE_DIR + ' as the image directory')
        images, features = self.extract_features()

        print('Clustering the extracted features using the reference dataframe')
        clusters, clustered_features = self.cluster_features(df, images, features, cluster_keys=['centroid_lat', 'centroid_lon'], image_key='image_name')

        print('Generating predictions usign Ridge Regression model for given metric')
        predictions = None
        SAVE_DIR = None
        if metric == 'phone_density':
            predictions = self.predict_phone_density(clustered_features)
            predictions = np.squeeze(predictions)
            SAVE_DIR = RIDGE_PHONE_DENSITY_SAVE_DIR

        elif metric == 'phone_consumption':
            predictions = self.predict_phone_consumption(clustered_features)
            predictions = np.squeeze(predictions)
            SAVE_DIR = PHONE_CONSUMPTION_SAVE_DIR

        elif metric == 'consumption':
            predictions = self.predict_consumption(clustered_features)
            predictions = np.squeeze(predictions)
            SAVE_DIR = RIDGE_CONSUMPTION_SAVE_DIR

        assert predictions is not None and SAVE_DIR is not None

        print('Saving predictions to ' + os.path.join(SAVE_DIR, 'predictions.csv'))
        predictions = np.squeeze(predictions)
        with open(os.path.join(SAVE_DIR, 'predictions.csv'), 'w') as f:
                for (centroid_lat, centroid_lon), pred in zip(clusters, predictions):
                    to_write = [str(centroid_lat), str(centroid_lon), str(pred)]
                    f.write(','.join(to_write) + '\n')


    def predict_nightlights(self):
        """
            Obtains nightlight predictions for all the images.
            
            Return: two items of equal length, one being the list of images and the other an array of shape (len(images), NUM_CLASSES)
        """
        SAVE_NAME = 'forward_classifications.npy'
        if SAVE_NAME in os.listdir(CNN_FEATURE_SAVE_DIR):
            return np.load(os.path.join(CNN_FEATURE_SAVE_DIR, SAVE_NAME))

        ims = os.listdir(IMAGE_DIR)
        path = os.path.join(IMAGE_DIR, '{}')

        i = 0
        batch_size = 4
        predictions = np.zeros((len(ims), 3))
        pbar = tqdm(total=len(ims))

        # this approach uses batching and should offer a speed-up over passing one image at a time by nearly 10x
        # runtime should be 5-7 minutes vs 45+ for a full forward pass
        while i + batch_size < len(ims):
            ims_as_tensors = torch.cat([filename_to_im_tensor(path.format(ims[i+j])) for j in range(batch_size)], 0)
            predictions[i:i+batch_size,:] = self.cnn(ims_as_tensors).cpu().detach().numpy()
            i += batch_size
            pbar.update(batch_size)

        # does the final batch of remaining images
        if len(ims) - i != 0:
            rem = len(ims) - i
            ims_as_tensors = torch.cat([filename_to_im_tensor(path.format(ims[i+j])) for j in range(rem)], 0)
            predictions[i:i+rem,:] = self.cnn(ims_as_tensors).cpu().detach().numpy()
            i += rem
            pbar.update(rem)

        np.save(os.path.join(CNN_FEATURE_SAVE_DIR, SAVE_NAME), predictions)
        return ims, predictions

    def extract_features(self):
        """
            Obtains feature vectors for all the images.
            
            Return: two items of equal length, one being the list of images and the other an array of shape (len(images), 4096)
        """
        SAVE_NAME = 'forward_features.npy'
        if SAVE_NAME in os.listdir(CNN_FEATURE_SAVE_DIR):
            return np.load(os.path.join(CNN_FEATURE_SAVE_DIR, SAVE_NAME))

        # we "rip" off the final layers so we can extract the 4096-size feature vector
        # this layer is the 4th on the classifier half of the CNN
        original = self.cnn.classifier
        ripped = self.cnn.classifier[:4]
        self.cnn.classifier = ripped

        ims = os.listdir(IMAGE_DIR)
        path = os.path.join(IMAGE_DIR, '{}')

        i = 0
        batch_size = 4
        features = np.zeros((len(ims), 4096))
        pbar = tqdm(total=len(ims))

        # this approach uses batching and should offer a speed-up over passing one image at a time by nearly 10x
        # runtime should be 5-7 minutes vs 45+ for a full forward pass
        while i + batch_size < len(ims):
            ims_as_tensors = torch.cat([filename_to_im_tensor(path.format(ims[i+j])) for j in range(batch_size)], 0)
            features[i:i+batch_size,:] = self.cnn(ims_as_tensors).cpu().detach().numpy()
            i += batch_size
            pbar.update(batch_size)

        # does the final batch of remaining images
        if len(ims) - i != 0:
            rem = len(ims) - i
            ims_as_tensors = torch.cat([filename_to_im_tensor(path.format(ims[i+j])) for j in range(rem)], 0)
            features[i:i+rem,:] = self.cnn(ims_as_tensors).cpu().detach().numpy()
            i += rem
            pbar.update(rem)

        self.cnn.classifier = original
        np.save(os.path.join(CNN_FEATURE_SAVE_DIR, SAVE_NAME), features)
        return ims, features

    def cluster_features(self, df, images, features, cluster_keys, image_key):
        """
            Aggregates the features based on a key(s) in the dataframe (specified by cluster_keys) against the image column in the dataframe (specified by image_key)
            - df: the dataframe
            - images: list of images that should have been outputted by extract_features
            - features: array of features created by extract_features
            - cluster_keys: key(s) to cluster on
            - image_key: key which has image names

            df[image_key] should not contain any images that are not in the list of image names

            Returns: two items of equal length, the first being a list of clusters and the second being a cluster-aggregated feature array of shape (NUM_CLUSTERS, 4096)
        """
        assert len(images) == len(features)
        if type(cluster_keys) is not list:
            cluster_keys = [cluster_keys]

        df_lookup = pd.Dataframe.from_dict({image_key: images, 'feature_index': [i for i in range(len(images))]})
        prev_shape = len(df)
        df = pd.merge(df, df_lookup, on=image_key, how='left')
        assert prev_shape == len(df)

        num_unique = len(pd.unique(df[cluster_keys]))
        clustered_feats = np.zeros((num_unique, 4096))
        clusters = []

        groups = df.groupby(cluster_keys)
        for i, (cluster, data) in enumerate(groups):
            cluster_feats = np.zeros((len(data), 4096))
            for j, d in data.iterrows():
                cluster_feats[j,:] = features[d.feature_index]
            # averages the features across all images in the cluster
            cluster_feats = cluster_feats.mean(axis=0)
            clustered_feats[i,:] = cluster_feats
            clusters.append(cluster)
        
        return clusters, clustered_feats

    def predict_phone_density(self, clustered_feats):
        return self.ridge_phone_density.predict(clustered_feats)

    def prediction_phone_consumption(self, clustered_feats):
        return self.ridge_phone_consumption.predict(clustered_feats)

    def predict_consumption(self, clustered_feats):
        return self.ridge_consumption.predict(clustered_feats)



if __name__ == '__main__':
    mp = ModelPipeline()
    mp.run_pipeline(metric='phone_consumption')
