import os

import mdshare
import mdtraj as md
import numpy as np
import torch
from torch.utils import data
from torch_geometric.data import Data as GeometricData


class StochasticLaggedDataset(data.Dataset):
    def __init__(self, trajs, max_lag, fixed_lag=False):
        self.max_lag = max_lag
        trajs = [traj for traj in trajs if len(traj) > max_lag]
        self.data = np.concatenate(trajs)
        self.data0_idx = np.zeros(len(self.data) - max_lag * len(trajs), dtype=int)
        self.fixed_lag = fixed_lag

        l = 0
        l0 = 0
        for traj in trajs:
            dl = len(traj)
            dl0 = len(traj) - max_lag
            self.data0_idx[l0 : l0 + dl0] = range(l, l + dl0)
            l += dl
            l0 += dl0

    def __len__(self):
        return len(self.data0_idx)

    def __getitem__(self, idx):
        log_lag = np.random.uniform(0, np.log(self.max_lag))
        lag = int(np.floor(np.exp(log_lag)))

        if self.fixed_lag:
            lag = self.max_lag

        data0_idx = self.data0_idx[idx]
        data0 = self.data[data0_idx]
        datat = self.data[data0_idx + lag]

        return self.process(data0, datat, lag)

    def process(self, x0, xt, t):
        raise NotImplementedError


class ALA2Dataset(StochasticLaggedDataset):
    def __init__(
        self, max_lag, distinguish=False, scale=False, fixed_lag=False, path=None
    ):
        self.atom_numbers = get_ala2_atom_numbers(distinguish=distinguish)
        trajs = get_ala2_trajs(path, scale)

        super().__init__(trajs, max_lag, fixed_lag=fixed_lag)

    def get_geom_batch(self, x, t_phys):
        batch = GeometricData(
            x=x,
            t_phys=torch.ones_like(self.atom_number) * t_phys,
            atom_number=self.atom_numbers,
        )

        return batch

    def process(self, x0, xt, t):
        x0 = torch.Tensor(x0.squeeze())
        xt = torch.Tensor(xt.squeeze())

        batch_0 = self.get_geom_batch(x0, t)
        batch_t = self.get_geom_batch(xt, t)
        return {"batch_0": batch_0, "batch_t": batch_t}


def get_ala2_trajs(path=None, scale=False):
    if not path:
        path = "data/ala2/"
    if not os.path.exists(path):
        print(f"downloading alanine-dipeptide dataset to {path} ...")

    filenames = [
        os.path.join(f"alanine-dipeptide-{i}-250ns-nowater.xtc") for i in range(3)
    ]

    local_filenames = [
        mdshare.fetch(
            filename,
            working_directory=path,
        )
        for filename in filenames
    ]

    topology = mdshare.fetch("alanine-dipeptide-nowater.pdb", path)
    trajs = [md.load_xtc(fn, topology) for fn in local_filenames]

    trajs = [t.center_coordinates().xyz for t in trajs]

    if scale:
        std = 0.1661689
        trajs = [t / std for t in trajs]

    return trajs


def get_ala2_atomnumbers(distinguish=False):
    # fmt: off
    ALA2ATOMNUMBERS = [1, 6, 1, 1, 6, 8, 7, 1, 6, 1, 6, 1, 1, 1, 6, 8, 7, 1, 6, 1, 1, 1]
    # fmt: on
    atom_numbers = torch.tensor(  # pylint: disable=not-callable
        list(range(len(ALA2ATOMNUMBERS))) if distinguish else ALA2ATOMNUMBERS,
        dtype=torch.long,
    )
    return atom_numbers
