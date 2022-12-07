import torch
from torch import nn

class Model(nn.Module):
  def __init__(self, n_inputs, hidden_dim):
    super().__init__()
    self.emb = nn.Embedding(n_inputs, hidden_dim) # [ batch_size, 2, hidden_dim ]
    self.nonlinear = nn.Sequential(
      nn.Flatten(),
      nn.Linear(2*hidden_dim, hidden_dim),
      nn.ReLU(),
      nn.Linear(hidden_dim, hidden_dim),
      nn.ReLU(),
      nn.Linear(hidden_dim, 1))
    #bigger init
    self.emb.weight.data.uniform_(-10,10)
    
  def forward(self, x): # x: [ batch_size, 2 ]
    x = self.emb(x) # [ batch_size, 2, hidden_dim ]
    x = self.nonlinear(x)
    return x

class Model2(nn.Module):
  def __init__(self, n_protons, n_neutrons, hidden_dim):
    super().__init__()
    self.emb_proton = nn.Embedding(n_protons, hidden_dim) # [ batch_size, hidden_dim ]
    self.emb_neutron = nn.Embedding(n_neutrons, hidden_dim) # [ batch_size, hidden_dim ]
    self.nonlinear = nn.Sequential(
      nn.Flatten(),
      nn.Linear(2*hidden_dim, hidden_dim),
      nn.ReLU(),
      nn.Dropout(p=0.001),
      nn.Linear(hidden_dim, hidden_dim),
      nn.ReLU(),
      #nn.Dropout(0.001),
      nn.Linear(hidden_dim, 1))
    #bigger init
    self.emb_proton.weight.data.uniform_(-1,1)
    self.emb_neutron.weight.data.uniform_(-1,1)
    
    self.emb_proton.weight = nn.Parameter(nn.functional.normalize(self.emb_proton.weight, p = 2, dim = 1))
    self.emb_neutron.weight = nn.Parameter(nn.functional.normalize(self.emb_neutron.weight, p = 2, dim = 1))
    
  def forward(self, x): # x: [ batch_size, 2 [n_protons, n_neutrons] ]
    proton = self.emb_proton(x[:,0]) # [ batch_size, hidden_dim ]
    neutron = self.emb_neutron(x[:,1]) # [ batch_size, hidden_dim ]
    
    proton = nn.functional.normalize(proton, p = 2, dim = 1)
    neutron = nn.functional.normalize(neutron, p = 2, dim = 1)
    
    x = self.nonlinear(torch.hstack((proton, neutron)))
    return x


class Model3(nn.Module):
  def __init__(self, n_protons, n_neutrons, hidden_dim):
    super().__init__()
    self.emb_proton = nn.Embedding(n_protons, hidden_dim) # [ batch_size, hidden_dim ]
    self.emb_neutron = nn.Embedding(n_neutrons, hidden_dim) # [ batch_size, hidden_dim ]
    self.nonlinear = nn.Sequential(
      nn.Flatten(),
      nn.Linear(2*hidden_dim, 16), # we need 2*hidden_dim to get proton and neutron embedding
      nn.ReLU(),
      nn.Dropout(p=0.001),
      nn.Linear(16, 1))
    #bigger init
    self.emb_proton.weight.data.uniform_(-1,1)
    self.emb_neutron.weight.data.uniform_(-1,1)

  def forward(self, x): # x: [ batch_size, 2 [n_protons, n_neutrons] ]
    proton = self.emb_proton(x[:,0]) # [ batch_size, hidden_dim ]
    neutron = self.emb_neutron(x[:,1]) # [ batch_size, hidden_dim ]
    
    x = self.nonlinear(torch.hstack((proton, neutron)))
    return x
