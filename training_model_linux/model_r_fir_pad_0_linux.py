import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from torch import nn, optim, cuda
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
import natsort
import wandb
import os
import glob
import re
import warnings
import argparse
from torch.autograd import Variable

warnings.filterwarnings("ignore")
signal_dir = '/data/data_signal_MTI/project_util/signal_all_w_mti_cutoff_12/'
label_dir = '/data/data_signal_MTI/project_util/label_all/'

model_path = '/home/nakorn/weight_bias/wandb/run-20200818_161847-3tv89mst/fir_6cov_1.pt'
save_predict_path = '/home/nakorn/weight_bias/test_data/'
all_trajectory = 117

parser = argparse.ArgumentParser()
parser.add_argument('-epochs', type=int, default=500)
parser.add_argument('-batch_size', type=int, default=4000)
parser.add_argument('-learning_rate', type=float, default= 0.001)
parser.add_argument('-zero_padding', type=int, default=0)
parser.add_argument('-test_batch_size', type=int, default = 9860)
parser.add_argument('-loss_weight', type=int, default=3)
parser.add_argument('-save_to_wandb', type=bool, default=False)
parser.add_argument('-test_only', type=bool, default=False)
parser.add_argument('-range_resolution', type=float, default=54.90)
parser.add_argument('-wmodel', default='cnn+fc+reg')
args = parser.parse_args()

train_all = []
test_all = []
train_label_all = []
test_label_all = []
device = 'cuda:0' if cuda.is_available() else 'cpu'

if args.save_to_wandb:
    wandb.init(project="cnn-fc-117", dir='/home/nakorn/weight_bias')

def L2_loss(output, label, wmodel):
    
    if 'cnn+fc' == wmodel: 
        m_r = meshgrid()
        expect = torch.matmul(output, m_r)
        mse = mse_loss(expect, label)
    
    elif 'cnn+fc+reg' == wmodel:
        expect = output.view(-1)
        mse = mse_loss(expect, label)

    # print(expect.size(), label.size())

    return mse, expect

def cartesian_to_spherical(label):
    y_offset = 105
    r = np.sqrt(label[:,0,0]**2 + (label[:,0,1] - y_offset)**2 + label[:,0,2]**2)
    return r

def meshgrid():
    m_r = torch.arange(0, args.range_resolution*16, args.range_resolution).to(device)
    # print("m_r", m_r.shape)
    return m_r

def data_preparation(data_iq, label):
    
    data_fft = np.fft.fft(data_iq, axis=2) / data_iq.shape[2]
    data_fft_modulus = abs(data_fft)
    data_fft_modulus = np.mean(data_fft_modulus, axis=1)
    
    data_fft_modulus = np.swapaxes(data_fft_modulus, 1,2)
    data_fft_modulus = data_fft_modulus[:,:,:int(data_fft_modulus.shape[2]/4)]
    data_fft_modulus = np.float64(data_fft_modulus)

    label = cartesian_to_spherical(label)
    label = np.float64(label)

    return data_fft_modulus, label

# def plot_function():



class Model(nn.Module):
    def __init__(self):
        super(Model, self).__init__()
        # 2D-CNN Layer
        self.encode_conv1 = nn.Conv1d(in_channels=4, out_channels=8, kernel_size=3, stride = 1, padding=1)
        self.encode_conv2 = nn.Conv1d(in_channels=8, out_channels=8, kernel_size=3, stride = 2, padding=1)
        self.encode_conv3 = nn.Conv1d(in_channels=8, out_channels=16, kernel_size=3, stride = 1, padding=1)
        self.encode_conv4 = nn.Conv1d(in_channels=16, out_channels=16, kernel_size=3, stride = 2, padding=1)
        # self.encode_conv5 = nn.Conv1d(in_channels=8, out_channels=16, kernel_size=3, stride = 1, padding=1)
        # self.encode_conv6 = nn.Conv1d(in_channels=16, out_channels=16, kernel_size=3, stride = 2, padding=1)

        self.fc1 = nn.Linear(in_features=16*16, out_features=256)
        
        self.fc2 = nn.Linear(in_features=256, out_features=256)

        self.lstm = nn.LSTM(input_size=128, hidden_size=128, num_layers=2, batch_first = True)
        
        self.fc3 = nn.Linear(in_features=128, out_features=16)

        self.fc4 = nn.Linear(in_features=256, out_features=1)

    def forward(self, x, wmodel):

        if 'cnn+fc' == wmodel:
            x = F.relu(self.encode_conv1(x))
            x = F.relu(self.encode_conv2(x))
            x = F.relu(self.encode_conv3(x))
            x = F.relu(self.encode_conv4(x))
            # x = F.leaky_relu(self.encode_conv5(x))
            # x = F.leaky_relu(self.encode_conv6(x))

            x = x.view(x.size(0), -1)
            x = F.relu(self.fc1(x))
            x = F.relu(self.fc2(x))
            x = F.softmax(self.fc3(x), dim=1)

        elif 'cnn+fc+reg' == wmodel:
            
            x = F.relu(self.encode_conv1(x))
            x = F.relu(self.encode_conv2(x))
            x = F.relu(self.encode_conv3(x))
            x = F.relu(self.encode_conv4(x))
            # x = F.leaky_relu(self.encode_conv5(x))
            # x = F.leaky_relu(self.encode_conv6(x))

            x = x.view(x.size(0), -1)
            x = F.relu(self.fc1(x))
            x = F.relu(self.fc2(x))
            # x = F.relu(self.fc3(x))
            x = self.fc4(x)

        elif 'cnn+fc+lstm' == wmodel:
            x = F.relu(self.encode_conv1(x))
            x = F.relu(self.encode_conv2(x))
            x = F.relu(self.encode_conv3(x))
            x = F.relu(self.encode_conv4(x))
            # x = F.leaky_relu(self.encode_conv5(x))
            # x = F.leaky_relu(self.encode_conv6(x))

            x = x.view(x.size(0), -1)
            x = F.relu(self.fc1(x))
            x = x.view(x.size(0), 1, -1)
            h0 = Variable(torch.zeros(1*2, x.size(0), 128).to(device))
            c0 = Variable(torch.zeros(1*2, x.size(0), 128).to(device))
            out, (hn, cn) = self.lstm(x, (h0, c0))
            x = F.softmax(self.fc3(out[:, -1, :]), dim=1)            


        return x

class Radar_train_Dataset(Dataset):
    def __init__(self, real_part, label_file):
 
        data_iq = np.load(real_part)
        label = np.load(label_file)

        data_fft_modulus, label = data_preparation(data_iq, label)
        
        train_all.extend(data_fft_modulus)
        train_label_all.extend(label)
                
        self.train_data = torch.tensor(np.array(train_all))
        self.train_label = torch.tensor(np.array(train_label_all))
        self.len = np.array(train_all).shape[0]

        print("train_function", self.train_data.size(), self.train_label.size())

    def __len__(self):
        return self.len

    def __getitem__(self, idx):
        return self.train_data[idx], self.train_label[idx]

class Radar_test_Dataset(Dataset):

    def __init__(self, real_part, label_file):
        
        data_iq = np.load(real_part)
        label = np.load(label_file)
        
        data_fft_modulus, label = data_preparation(data_iq, label)
        
        test_all.extend(data_fft_modulus)
        test_label_all.extend(label)
                
        self.test_data = torch.tensor(np.array(test_all))
        self.test_label = torch.tensor(np.array(test_label_all))
        self.len = np.array(test_all).shape[0]

        print("test_function", self.test_data.size(), self.test_label.size())

    def __len__(self):
        return self.len

    def __getitem__(self, idx):
        return self.test_data[idx], self.test_label[idx]


model = Model()
# wandb.watch(model)
if args.test_only:
    model.load_state_dict(torch.load(model_path))
model.to(device)

mse_loss = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

def train_function(train_loader):
    model.train()
    avg_mini_train_loss = []
    for i, (train_data, train_labels) in enumerate(train_loader, 0):
        train_data, train_labels = train_data.to(device), train_labels.to(device)
        train_data = train_data.float()
        train_labels = train_labels.float()

        optimizer.zero_grad()
        output = model(train_data, args.wmodel)
        loss, expect_r = L2_loss(output, train_labels, args.wmodel)
        loss.backward()
        optimizer.step()
        avg_mini_train_loss.append(loss.item())

    return np.mean(np.array(avg_mini_train_loss)) 
        
def test_function(test_loader):
    model.eval()
    avg_mini_test_loss = []
    for i, (test_data, test_labels) in enumerate(test_loader,0):
        test_data, test_labels = test_data.to(device), test_labels.to(device)
        test_data = test_data.float()
        test_labels = test_labels.float()
        output = model(test_data, args.wmodel)
        loss, expect_r = L2_loss(output, test_labels, args.wmodel)
        
        test_labels = test_labels.cpu().detach().numpy()
        expect_r = expect_r.cpu().detach().numpy()
        avg_mini_test_loss.append(loss.item())

    return np.mean(np.array(avg_mini_test_loss)), test_labels, expect_r 
    
if __name__ == '__main__':
    
    count = 0
    for f_name in range(all_trajectory):
        count += 1
        real_name = signal_dir + 'raw_iq_w_mti_' + str(count) + '.npy' 
        label_name = label_dir + 'label_' + str(count) + '.npy'

      
        if count%4 == 0:
            test_data = Radar_test_Dataset(real_part= real_name,  label_file=label_name)
        else:
            train_data = Radar_train_Dataset(real_part= real_name, label_file=label_name)
            
    train_loader = DataLoader(dataset=train_data, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(dataset=test_data, batch_size=args.test_batch_size)

    if args.test_only:
        test_loss, label, expect_r = test_function(test_loader)
        print(expect_r.shape)
        np.save(save_predict_path + 'label_r_%4', label)
        np.save(save_predict_path + 'expect_r_%4', expect_r)

    else:
        for epoch in range(args.epochs):
            # print("======> epoch =", epoch)
            train_loss = train_function(train_loader)
            
            if args.save_to_wandb:
                wandb.log({'Train_loss': train_loss}, step=epoch)
            
            # print(">>>>>> train_loss <<<<<<", train_loss)
            if epoch%10 == 0:
                test_loss, label, expect_r = test_function(test_loader)
                print(">>>>>> test_loss <<<<<< epoch", epoch , test_loss)
                
                if args.save_to_wandb:
                    plt.plot(label[:])
                    plt.plot(expect_r[:])
                    plt.ylabel('r distance')
                    plt.xlabel('number of test point')
                    wandb.log({'distance': plt}, step=epoch)
                    wandb.log({'Test_loss': test_loss}, step=epoch)
    
    if args.save_to_wandb:
        torch.save(model.state_dict(), os.path.join(wandb.run.dir, 'fir_6cov_1.pt'))


    
