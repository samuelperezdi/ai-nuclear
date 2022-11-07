from sklearn.decomposition import PCA
import numpy as np
from data import get_data
import torch
from torch import nn
from copy import deepcopy


def numpy_old_effective_dim(model, all_protons, all_neutrons):
  #calculate entropy of the embeddings
  protons = model.emb_proton(all_protons)
  neutrons = model.emb_neutron(all_neutrons)
  pca = PCA(n_components=32)
  protons = pca.fit(protons.detach().cpu().numpy()).explained_variance_ratio_
  neutrons = pca.fit(neutrons.detach().cpu().numpy()).explained_variance_ratio_
  entropy_protons = -(protons * np.log(protons)).sum()
  entropy_neutrons = -(neutrons * np.log(neutrons)).sum()
  pr_e = np.exp(entropy_protons)
  ne_e = np.exp(entropy_neutrons)
  return pr_e, ne_e


def effective_dim(model, all_protons, all_neutrons):
  #calculate entropy of the embeddings
  protons = model.emb_proton(all_protons)
  neutrons = model.emb_neutron(all_neutrons)

  protons_S = (torch.square(torch.svd(protons)[1]) / (all_protons.shape[0] - 1))
  neutrons_S = (torch.square(torch.svd(neutrons)[1]) / (neutrons.shape[0] - 1))
  
  proton_prob = protons_S/protons_S.sum()
  neutron_prob = neutrons_S/neutrons_S.sum()
  
  entropy_protons = -(proton_prob * torch.log(proton_prob)).sum()
  entropy_neutrons = -(neutron_prob * torch.log(neutron_prob)).sum()

  pr_e = torch.exp(entropy_protons)
  ne_e = torch.exp(entropy_neutrons)

  return pr_e, ne_e

def regularize_effective_dim(model, all_protons, all_neutrons, alpha = 0.02):
  pr_e, ne_e = effective_dim(model, all_protons, all_neutrons)
  regularization = alpha * (pr_e+ne_e)
  return regularization


def test_model(model, state_dict, X_test, y_test):
    starting = deepcopy(model.state_dict())
    model.load_state_dict(state_dict)

    loss_fn = nn.MSELoss()
    y_pred = model(X_test)
    loss = loss_fn(y_pred, y_test)
    model.load_state_dict(starting)
    return loss

def nd_loss(model, all_protons, all_neutrons, X_test, y_test, n = 2):
  #calculate entropy of the embeddings
  protons = model.emb_proton(all_protons)
  neutrons = model.emb_neutron(all_neutrons)
  U_p, S_p, Vh_p = torch.linalg.svd(protons, False)
  U_n, S_n, Vh_n = torch.linalg.svd(neutrons, False)

  S_p[n:] = 0
  S_n[n:] = 0

  nd_state = model.state_dict().copy()
  nd_state['emb_proton.weight'] =  U_p @ torch.diag(S_p) @ Vh_p
  nd_state['emb_neutron.weight'] =  U_n @ torch.diag(S_n) @ Vh_n

  nd_loss = test_model(model, nd_state, X_test, y_test)
  return nd_loss

