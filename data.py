import numpy as np
import pandas as pd
import urllib.request
import os
from sklearn.preprocessing import (
    QuantileTransformer,
    MinMaxScaler,
    RobustScaler,
    StandardScaler,
)
import torch
import argparse
from collections import namedtuple, OrderedDict
import math

Data = namedtuple(
    "Data",
    [
        "X",
        "y",
        "vocab_size",
        "output_map",
        "regression_transformer",
        "train_mask",
        "val_mask",
        "hold_out_mask",
    ],
)


def delta(Z, N):
    A = Z + N
    aP = 11.18
    delta = aP * A ** (-1 / 2)
    delta[(Z % 2 == 1) & (N % 2 == 1)] *= -1
    delta[(Z % 2 == 0) & (N % 2 == 1)] = 0
    delta[(Z % 2 == 1) & (N % 2 == 0)] = 0
    return delta


def semi_empirical_mass_formula(Z, N):
    A = N + Z
    aV = 15.75
    aS = 17.8
    aC = 0.711
    aA = 23.7
    Eb = (
        aV * A
        - aS * A ** (2 / 3)
        - aC * Z * (Z - 1) / (A ** (1 / 3))
        - aA * (N - Z) ** 2 / A
        + delta(Z, N)
    )
    Eb[Eb < 0] = 0
    return Eb / A * 1000  # keV


def apply_to_df_col(column):
    def wrapper(fn):
        return lambda df: df[column].astype(str).apply(fn)

    return wrapper


@apply_to_df_col(column="jp")
def get_spin_from(string):
    string = (
        string.replace("(", "")
        .replace(")", "")
        .replace("+", "")
        .replace("-", "")
        .replace("]", "")
        .replace("[", "")
        .replace("GE", "")
        .replace("HIGH J", "")
        .replace(">", "")
        .replace("<", "")
        .strip()
        .split(" ")[0]
    )
    if string == "":
        return float("nan")
    else:
        return float(eval(string))  # eval for 1/2 and such


@apply_to_df_col("jp")
def get_parity_from(string):
    # find the first + or -
    found_plus = string.find("+")
    found_minus = string.find("-")

    if found_plus == -1 and found_minus == -1:
        return float("nan")
    elif found_plus == -1:
        return 0  # -
    elif found_minus == -1:
        return 1  # +
    elif found_plus < found_minus:
        return 1  # +
    elif found_plus > found_minus:
        return 0  # -
    else:
        raise ValueError("something went wrong")


def get_half_life_from(df):
    # selection excludes unknown lifetimes and ones where lifetimes are given as bounds
    series = df.half_life_sec.copy()
    series[(df.half_life_sec == " ") | (df.operator_hl != " ")] = float("nan")
    series = series.astype(float)
    series = series.apply(np.log10)
    return series


@apply_to_df_col("qa")
def get_qa_from(string):
    # ~df.qa.isna() & (df.qa != " ")
    if string == " ":
        return float("nan")
    else:
        return float(string)


@apply_to_df_col("qbm")
def get_qbm_from(string):
    return float(string.replace(" ", "nan"))


@apply_to_df_col("qbm_n")
def get_qbm_n_from(string):
    return float(string.replace(" ", "nan"))


@apply_to_df_col("qec")
def get_qec_from(string):
    return float(string.replace(" ", "nan"))


@apply_to_df_col("sn")
def get_sn_from(string):
    return float(string.replace(" ", "nan"))


@apply_to_df_col("sp")
def get_sp_from(string):
    return float(string.replace(" ", "nan"))


def get_abundance_from(df):
    # abundance:
    # assumes that " " means 0
    return df.abundance.replace(" ", "0").astype(float)


@apply_to_df_col("half_life")
def get_stability_from(string):
    if string == "STABLE":
        return 1.0
    elif string == " ":
        return float("nan")
    else:
        return 0.0


@apply_to_df_col("isospin")
def get_isospin_from(string):
    return float(eval(string.replace(" ", "float('nan')")))


def get_binding_energy_from(df):
    binding = df.binding.replace(" ", "nan").astype(float)
    return binding


def get_radius_from(df):
    return df.radius.replace(" ", "nan").astype(float)


def get_targets(df):
    # place all targets into targets an empty copy of df
    targets = df[["z", "n"]].copy()
    # binding energy per nucleon
    targets["binding"] = get_binding_energy_from(df)
    # binding energy per nucleon minus semi empirical mass formula
    targets["binding_semf"] = targets.binding - semi_empirical_mass_formula(df.z, df.n)
    # radius in fm
    targets["radius"] = get_radius_from(df)
    # half life in log10(sec)
    targets["half_life_sec"] = get_half_life_from(df)
    # stability in {0, 1, nan}
    targets["stability"] = get_stability_from(df)
    # spin as float
    targets["spin"] = get_spin_from(df)
    # parity as {0 (-),1 (+), nan}
    targets["parity"] = get_parity_from(df)
    # isotope abundance in %
    targets["abundance"] = get_abundance_from(df)
    # qa = alpha decay energy in keV
    targets["qa"] = get_qa_from(df)
    # qbm = beta minus decay energy in keV
    targets["qbm"] = get_qbm_from(df)
    # qbm_n = beta minus + neutron emission energy in keV
    targets["qbm_n"] = get_qbm_n_from(df)
    # qec = electron capture energy in keV
    targets["qec"] = get_qec_from(df)
    # sn = neutron separation energy in keV
    targets["sn"] = get_sn_from(df)
    # sp = proton separation energy in keV
    targets["sp"] = get_sp_from(df)
    # isospin as float
    targets["isospin"] = get_isospin_from(df)
    # These are semi-empirical mass formula terms
    targets["volume"] = targets.z + targets.n  # volume
    targets["surface"] = targets.volume ** (2 / 3)  # surface
    targets["symmetry"] = ((targets.z - targets.n) ** 2) / targets.volume  # symmetry
    targets["delta"] = delta(targets.z, targets.n)  # delta
    targets["coulomb"] = (targets.z**2 - targets.z) / targets.volume ** (
        1 / 3
    )  # coulomb

    return targets


def get_nuclear_data(recreate=False):
    def lc_read_csv(url):
        req = urllib.request.Request("https://nds.iaea.org/relnsd/v0/data?" + url)
        req.add_header(
            "User-Agent",
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:77.0) Gecko/20100101 Firefox/77.0",
        )
        return pd.read_csv(urllib.request.urlopen(req))

    if not os.path.exists("data"):
        os.mkdir("data")
    if recreate or not os.path.exists("data/ground_states.csv"):
        df = lc_read_csv("fields=ground_states&nuclides=all")
        df.to_csv("data/ground_states.csv", index=False)

    df2 = pd.read_csv("data/ame2020.csv").set_index(["z", "n"])
    df2 = df2[~df2.index.duplicated(keep="first")]
    df = pd.read_csv("data/ground_states.csv").set_index(["z", "n"])
    df["binding_unc"] = df2.binding_unc
    df["binding_sys"] = df2.binding_sys
    df.reset_index(inplace=True)
    # df = df[(df.z > 8) & (df.n > 8)]

    zn2016 = pd.read_csv("data/2016.csv").set_index(["z","n"])
    zn2020 = pd.read_csv("data/2020.csv").set_index(["z","n"])
    not_in_2016 = zn2020[~zn2020.index.isin(zn2016.index)].index
    test_idx = df.set_index(["z","n"]).index.isin(not_in_2016)

    return df, test_idx

def prepare_nuclear_data(config: argparse.Namespace, recreate: bool = False):
    """Prepare data to be used for training. Transforms data to tensors, gets tokens X,targets y,
    vocab size and output map which is a dict of {target:output_shape}. Usually output_shape is 1 for regression
    and n_classes for classification.

    Args:
        columns (list, optional): List of columns to use as targets. Defaults to None.
        recreate (bool, optional): Force re-download of data and save to csv. Defaults to False.
    returns (Data): namedtuple of X, y, vocab_size, output_map, quantile_transformer
    """
    df, hold_out_idx = get_nuclear_data(recreate=recreate)
    hold_out_X = torch.tensor(df[hold_out_idx][["z","n"]].values)
    targets = get_targets(df)

    X = torch.tensor(targets[["z", "n"]].values)
    vocab_size = (
        targets.z.max() + 1,
        targets.n.max() + 1,
        len(config.TARGETS_CLASSIFICATION) + len(config.TARGETS_REGRESSION),
    )

    # classification targets increasing integers
    for col in config.TARGETS_CLASSIFICATION:
        targets[col] = targets[col].astype("category").cat.codes
        # put nans back
        targets[col] = targets[col].replace(-1, np.nan)

    output_map = OrderedDict()
    for target in config.TARGETS_CLASSIFICATION:
        output_map[target] = targets[target].nunique()

    for target in config.TARGETS_REGRESSION:
        output_map[target] = 1

    reg_columns = list(config.TARGETS_REGRESSION)
    # feature_transformer = QuantileTransformer(
    #     output_distribution="uniform", random_state=config.SEED
    # )
    feature_transformer = MinMaxScaler()
    if len(reg_columns) > 0:
        targets[reg_columns] = feature_transformer.fit_transform(
            targets[reg_columns].values
        )


    y = torch.tensor(targets[list(output_map.keys())].values).float()

    # Time to flatten everything
    X = torch.vstack(
        [torch.tensor([*x, task]) for x in X for task in torch.arange(len(output_map))]
    )
    y = y.flatten().view(-1, 1)
    train_mask, test_mask = _train_test_split(
        len(y), config.TRAIN_FRAC, seed=config.SEED
    )

    hold_out_mask = (X[:,:2].unsqueeze(1) == hold_out_X).all(-1).any(-1)
    train_mask = train_mask #& ~hold_out_mask
    test_mask = test_mask #& ~hold_out_mask

    # don't consider nuclei with high uncertainty in binding energy
    # but only for validation
    # assumes binding comes first
    if config.TMS == "remove":
        except_binding = (df.binding_unc * (df.z + df.n) > 100).values
        test_mask[::len(output_map)] = test_mask.view(-1)[::len(output_map)] & ~except_binding
    elif config.TMS != "keep":
        raise ValueError(f"Unknown TMS {config.TMS}")

    return Data(
        X.to(config.DEV),
        y.to(config.DEV),
        vocab_size,
        output_map,
        feature_transformer,
        train_mask.to(config.DEV),
        test_mask.to(config.DEV),
        hold_out_mask.to(config.DEV),
    )


def _train_test_split_sampled(X, train_frac, n_embedding_inputs, seed=1):
    """
    Samples are assigned to train by a bernoulli distribution with probability train_frac.
    """
    torch.manual_seed(seed)
    # assert that we have each X at least once in the training set
    while True:
        train_mask = torch.rand(X.shape[0]) < train_frac
        for i in range(n_embedding_inputs):
            if len(X[train_mask][:, i].unique()) != len(X[:, i].unique()):
                print("Resampling train mask")
                break
        else:
            break
    test_mask = ~train_mask
    return train_mask, test_mask


def _train_test_split(size, train_frac, seed=1):
    torch.manual_seed(seed)
    train_mask = torch.zeros(size, dtype=torch.bool)
    train_mask[: int(train_frac * size)] = True
    train_mask = train_mask[torch.randperm(size)]
    return train_mask, ~train_mask


class Loader:
    def __init__(self, X, y, batch_size=1024, shuffle=True):
        self.X = X
        self.y = y
        self.batch_size = batch_size
        if shuffle:
            self.randperm = torch.randperm(len(X), device=X.device)
        else:
            self.randperm = torch.arange(len(X), device=X.device)

    def __iter__(self):
        self.current_idx = 0
        return self

    def __next__(self):
        if self.current_idx >= len(self.X):
            raise StopIteration
        idx = self.randperm[self.current_idx : self.current_idx + self.batch_size]
        self.current_idx += self.batch_size
        return self.X[idx], self.y[idx]

    def __len__(self):
        return math.ceil(len(self.X) / self.batch_size)