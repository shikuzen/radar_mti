import numpy as np
import matplotlib.pyplot as plt
import scipy.linalg as LA
import scipy.signal as ss
import operator

MHz = 1e6
us = 1e-6
m = 1
k = 1000
c = 299792458 * m
fs = 13*MHz

pad_multi_range = 3
pad_multi_angle = 20

adc_range = 512
Rx = 8
antenna_array = np.linspace(0,((Rx+(pad_multi_angle*Rx))-1)/2, Rx+(pad_multi_angle*Rx))
aoa_search = np.linspace(-np.pi/2,np.pi/2,3600)

r_pad = (0, pad_multi_range*adc_range)
a_pad = ((0,pad_multi_range*adc_range),(0, pad_multi_angle*Rx))

all_trajectory = 120
range_res = 47.6 / (1+pad_multi_range)
angle_res = 3.1415 / (Rx*(pad_multi_angle+1)-1)

signal_dir = 'D:/data_signal_MTI/project_util_3/signal_all_w_mti_cutoff_12/'
fold_dir = 'D:/data_signal_MTI/project_util_3/10_fold_validation/100%_data/test_data/test_index_fold_'

all_trajectory = 120
M = 100
p = 2

def range_estimation(data_frame):
    data_frame = np.pad(data_frame, pad_width=r_pad, mode='constant', constant_values=0)
    data_frame = np.reshape(data_frame, (-1,1))
    f = np.arange(0, fs, (fs/(data_frame.shape[0])))
    se = np.arange(0,M)
    se = np.reshape(se, (-1,1))
    omega = 2*np.pi*(f/(fs))
    omega = np.reshape(omega, (-1,1))
    cov_matrix = np.zeros((M,M))
    for i in range((data_frame.shape[0])-M):
        cov_matrix = cov_matrix + data_frame[i:i+M]@data_frame[i:i+M].conj().transpose()
    lamb, V = np.linalg.eig(cov_matrix)
    idx = lamb.argsort()
    lamb = lamb[idx]
    V = V[:, idx]
    e = np.exp(1j*se*omega.T)
    den = np.zeros((omega.shape[0],1))
    for j in range(M-p):
        v = V[:, j]
        v = np.reshape(v, (-1,1))
        den = den + (abs((e.conj().transpose()@v)))**2
    psd_range = 1/den

    return psd_range

def angle_estimation(data_frame):
    data_frame = np.pad(data_frame, pad_width=a_pad, mode='constant', constant_values=0)
    data_frame = np.swapaxes(data_frame,0,1)
    cov_matrix = data_frame@data_frame.conj().transpose()
    lamb, V = np.linalg.eig(cov_matrix)
    idx = lamb.argsort()[::-1]
    V = V[:, idx]
    V = V[:, p:Rx]
    
    psd_aoa = np.zeros(aoa_search.size)
    for i in range(aoa_search.size):
        st_vec = np.exp(1j*2*np.pi*antenna_array*np.sin(aoa_search[i]))
        st_vec = np.reshape(st_vec, (-1, 1))
        psd_aoa[i] = 1/np.linalg.norm(V.conj().transpose()@st_vec)
    
    return psd_aoa

    

if __name__ == '__main__':
    count = 0
    expect_r = []
    expect_z = []
    for i in range(10):
        test_dir = fold_dir + str(i+1) +'.npy'
        print(test_dir)
        fold_num = np.load(test_dir)
        print(fold_num)
        for j in fold_num:
            print(j+1)  
            real_name = signal_dir + 'raw_iq_w_mti_' + str(j+1) + '.npy'
            test_data = np.load(real_name)
            for k in range(test_data.shape[0]):
                psd_range = range_estimation(test_data[k,0,:,0])
                psd_aoa = angle_estimation(test_data[k,0,:,:])
                range_max = np.argmax(psd_range[:,0])
                
                if range_max > (50+(pad_multi_range*50)):
                    expect_r.append(np.nan)
                    expect_z.append(np.nan)
                    print("outlier")
                else:
                    angle_max = np.argmax(psd_aoa)
                    actual_range = range_max*range_res
                    actual_doa =  -1*aoa_search[angle_max]
                    expect_r.append(actual_range)
                    expect_z.append(actual_doa)
            print("finish")
    expect_r = np.array(expect_r)
    expect_z = np.array(expect_z)
    np.save('D:/data_signal_MTI/project_util_3/prediction_result/expect_r_music_pad_100%_fold_cut', np.array(expect_r))
    np.save('D:/data_signal_MTI/project_util_3/prediction_result/expect_z_music_pad_100%_fold_cut', np.array(expect_z))