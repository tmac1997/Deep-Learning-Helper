import pandas as pd
import numpy as np

from collections import OrderedDict

import torch
import torch.nn.functional as F

from torch import nn
from torch.autograd import Variable

from torch import nn


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def get_optim_lr(optimizer):
    for param_group in optimizer.param_groups:
        lr = param_group['lr']
    return lr

def get_optim_gamma(optimizer):
    for param_group in optimizer.param_groups:
        lr = param_group['gamma']
    return lr