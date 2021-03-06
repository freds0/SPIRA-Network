import os
import torch
from torch.utils.data import Dataset, DataLoader
from torch import stack
import numpy as np
import pandas as pd
import random
import torch.nn.functional as F
from torch.nn.utils.rnn import pad_sequence
import torchaudio
class Dataset(Dataset):
    """
    Class for load a train and test from dataset generate by import_librispeech.py and others
    """
    def __init__(self, c, ap, train=True, max_seq_len=None, test=False):
        # set random seed
        random.seed(c['seed'])
        torch.manual_seed(c['seed'])
        torch.cuda.manual_seed(c['seed'])
        np.random.seed(c['seed'])
        self.c = c
        self.ap = ap
        self.train = train
        self.dataset_csv = c.dataset['train_csv'] if train else c.dataset['eval_csv']
        self.dataset_root = c.dataset['train_data_root_path'] if train else c.dataset['eval_data_root_path']
        if test:
            self.dataset_csv = c.dataset['test_csv']
            self.dataset_root = c.dataset['test_data_root_path']
        assert os.path.isfile(self.dataset_csv),"Test or Train CSV file don't exists! Fix it in config.json"


        # read csvs
        self.dataset_list = pd.read_csv(self.dataset_csv, sep=',').values

        # get max seq lenght for padding
        if self.c.dataset['padding_with_max_lenght'] and train and not self.c.dataset['max_seq_len']:
            self.max_seq_len = 0
            for idx in range(len(self.dataset_list)):
                wav = self.ap.load_wav(os.path.join(self.dataset_root, self.dataset_list[idx][0]))
                # calculate time step dim using hop lenght
                seq_len = int((wav.shape[1]/c.audio['hop_length'])+1)
                if seq_len > self.max_seq_len:
                    self.max_seq_len = seq_len
            print("The Max Time dim Lenght is: ", self.max_seq_len)
        else: # for eval set max_seq_len in train mode
            if self.c.dataset['max_seq_len']:
                self.max_seq_len = self.c.dataset['max_seq_len']
            else:
                self.max_seq_len = max_seq_len

    def get_max_seq_lenght(self):
        return self.max_seq_len

    def __getitem__(self, idx):
        wav = self.ap.load_wav(os.path.join(self.dataset_root, self.dataset_list[idx][0]))
        class_name = self.dataset_list[idx][1]

        # feature shape (Batch_size, n_features, timestamp)
        feature = self.ap.get_feature_from_audio(wav)
        # transpose for (Batch_size, timestamp, n_features)
        feature = feature.transpose(1,2)
        # remove batch dim = (timestamp, n_features)
        feature = feature.reshape(feature.shape[1:])
        if not self.c.dataset['padding_with_max_lenght']:
            # generate tensor with zeros for each timestep
            target = torch.zeros(feature.shape[0],1)+class_name
        else:
            # padding for max sequence
            zeros = torch.zeros(self.max_seq_len - feature.size(0),feature.size(1))
            # append zeros before features
            feature = torch.cat([feature, zeros], 0)
            target = torch.FloatTensor([class_name])
        return feature, target

    def __len__(self):
        return len(self.dataset_list)

def train_dataloader(c, ap):
    return DataLoader(dataset=Dataset(c, ap, train=True),
                          batch_size=c.train_config['batch_size'],
                          shuffle=True,
                          num_workers=c.train_config['num_workers'],
                          collate_fn=own_collate_fn,
                          pin_memory=True,
                          drop_last=True,
                          sampler=None)

def eval_dataloader(c, ap, max_seq_len=None):
    return DataLoader(dataset=Dataset(c, ap, train=False, max_seq_len=max_seq_len),
                          collate_fn=own_collate_fn, batch_size=c.test_config['batch_size'],
                          shuffle=False, num_workers=c.test_config['num_workers'])


def test_dataloader(c, ap, max_seq_len=None):
    return DataLoader(dataset=Dataset(c, ap, train=False, test=True, max_seq_len=max_seq_len),
                          collate_fn=own_collate_fn, batch_size=c.test_config['batch_size'],
                          shuffle=False, num_workers=c.test_config['num_workers'])

def own_collate_fn(batch):
    features = []
    targets = []
    for feature, target in batch:
        features.append(feature)
        #print(target.shape)
        targets.append(target)
    # padding with zeros timestamp dim
    features = pad_sequence(features, batch_first=True, padding_value=0)

    # its padding with zeros but mybe its a problem because
    targets = pad_sequence(targets, batch_first=True, padding_value=0)

    # list to tensor
    #targets = stack(targets, dim=0)
    #features = stack(features, dim=0)
    return features, targets
