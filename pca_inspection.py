import torch
from data import get_data
import pickle
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from BasicModel import BasicModel, BasicModelSmall, BasicModelSmaller, BasicModelReallySmall, BasicModelSmallest, BasicLinear
from NormalizeModel import NormalizeReallySmall
from pca import test_model, effective_dim
import pandas as pd
from torch import nn
import numpy as np
from inspect_pca import twodim_pca, compare_onedim_pca
from test_empirical import test_empirical, Empirical

import matplotlib.colors as mcolors




def effective_dim_analysis(model, all_protons, all_neutrons, heavy_elem = 0):
  #calculate entropy of the embeddings
  protons = model.emb_proton(all_protons)
  neutrons = model.emb_neutron(all_neutrons)
  U_p, S_p, Vh_p = torch.linalg.svd(protons, False)
  U_n, S_n, Vh_n = torch.linalg.svd(neutrons, False)

  

  loss_nd = [0 for i in range(len(S_p))]
  _, X_test, _, y_test, vocab_size = get_data()

  test_heavy_mask = X_test[:,0]>heavy_elem
  X_test = X_test[test_heavy_mask]
  y_test = y_test[test_heavy_mask]


  original = model.state_dict().copy()
  actual_loss = test_model(model, original, X_test, y_test)

  for i in range(len(S_p)):
    index = len(S_p)-i
    S_p[index:] = 0
    S_n[index:] = 0
    nd_state = model.state_dict()
    nd_state['emb_proton.weight'] =  U_p @ torch.diag(S_p) @ Vh_p
    nd_state['emb_neutron.weight'] =  U_n @ torch.diag(S_n) @ Vh_n
    loss_nd[index-1] = test_model(model, nd_state, X_test, y_test)
    model.load_state_dict(original)

  return actual_loss, loss_nd

def plot_effective_dim_losses(models, titles, all_protons, all_neutrons, heavy_elem = 15):
    colors = plt.cm.get_cmap('viridis', len(models))
        
    for i in range(len(models)):
        model = models[i]
        title = titles[i]
        actual_loss, loss_nd = effective_dim_analysis(model, all_protons, all_neutrons, heavy_elem=heavy_elem)
        print(f'{title}\n {actual_loss:.4f}, {loss_nd[2]:.4f} \n')
        plt.axhline(y = actual_loss, linestyle = '--', c = colors(i))
        plt.plot(range(1, 1+len(loss_nd)), loss_nd, label = title+f' loss = {actual_loss:.4f}', c = colors(i))

    #plt.axhline(y = test_empirical(heavy_elem = 15), c = 'k', linewidth = 2, label = 'SEMI EMPIRICAL MASS FORMULA')
    xlow, xhigh = 1, 5
    plt.xlim((xlow,xhigh))
    for i in range(xlow, xhigh):
        plt.axvline(x = i, linewidth = 0.2, c = 'k')
    
    plt.yscale('log')
    plt.legend()
    plt.ylabel('Test Loss (log scale)')
    plt.xlabel('Dimensions in PCA of embeddings to compute test loss')
    plt.title('Models Embeddings N-dimensional PCA Performance')
    plt.show()


def get_models(titles):
    models = []
    for i in range(len(titles)):
        title = titles[i]
        directory = 'Basic'
        sd = torch.load(f"models/{directory}/{title}/best.pt")
        models.append(torch.load(f"models/{directory}/{title}/model.pt"))
        models[i].load_state_dict(sd)
    return models

if __name__ == '__main__':
    '''
    title = 'BasicModelSmallest_reg2e_2'
    sd = torch.load(f"models/Basic/{title}/best.pt")
    model = torch.load(f"models/{title}/model.pt")
    model.load_state_dict(sd)
    x = model.state_dict()
    print(x['nonlinear.1.weight'].shape)
    '''
    #show_loss_diff()

    _, _, _, _, vocab_size = get_data()

    all_protons = torch.tensor(list(range(vocab_size[0])))
    all_neutrons = torch.tensor(list(range(vocab_size[1])))
    vals = ['1', '1e_1', '2e_2', '2e_3']#, '2e_4', '2e_5']
    
    bases = ['BasicModel_reg', 'BasicModelSmall_reg',  'BasicModelSmaller_reg', 'BasicModelSmallest_reg', 'BasicModelReallySmall_reg']
    titles = []
    for base in bases:
        for val in vals:
            titles.append(base+val)
    start = [f'BasicModelReallySmall_reg{val}_reg10wd' for val in vals]
    for s in start:
        titles.append(s)

    titles.append("BasicModelSmallest_noreg")
    titles.append("BasicModelReallySmall_noreg")
    titles.append('BasicModel_noreg')
    #models = get_models(titles)

    title = 'BasicModelSmall_reg2e_2'
    model = get_models([title])[0]
    title+='\nloss = 0.0099, effective_dim = 2'
    #print(effective_dim_analysis(model, all_protons, all_neutrons))
    #twodim_pca(model, all_protons, all_neutrons, title = title)
    
    titles.append('BasicModelSmall_reg2e_2_heavy')
    '''
    titles = []
    regs = [2e-3, 2e-2, 1e-1, 1]
    vals = ['2e_3', '2e_2', '1e_1', '1']
    heavy = 15
    for i in range(len(regs)):
        reg = regs[i]
        val = vals[i]
        title = f'BasicLinear_reg{val}_heavy{heavy}'
        titles.append(title)
    titles = titles[0:2]
    '''
    models = get_models(titles)


    #compare_onedim_pca(models, all_protons, all_neutrons, titles)
    '''
    for model in models:
        actual_loss, list_loss = effective_dim_analysis(model, all_protons, all_neutrons)
        print(actual_loss, list_loss[1])
    '''

    plot_effective_dim_losses(models, titles, all_protons, all_neutrons)
    #actual_loss, loss_list = effective_dim_analysis(models[-1], all_protons, all_neutrons, heavy_elem = 15)
   # print(actual_loss, loss_list)
    #print(models[-1].state_dict()['emb_proton.weight'].shape)


