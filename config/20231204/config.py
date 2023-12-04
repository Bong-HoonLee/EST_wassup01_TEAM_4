import torch.nn.functional as F
import torch
import torchmetrics

from torchmetrics.classification import BinaryAccuracy, BinaryPrecision, BinaryRecall, BinaryF1Score, BinaryAUROC
from models.ann import ANN

config = {
    "name": "OverfittingConfig01",
    "model": {
        "class": ANN,
        "params": {
            "perceptron": (158, 128, 1),
            "dropout": 0.1,
            "activation": F.relu,
        },
    },
    "data": {
        "train_X": {
            "path": "data/HN_train_X.csv",
            "index_col": None,
        },
        "train_y": {
            "path": "data/HN_train_y.csv",
            "index_col": None,
        },
        "test_X": {
            "path": "data/HN_test_X.csv",
            "index_col": None,
        },
        "test_y": {
            "path": "data/HN_test_y.csv",
            "index_col": None,
        },
        "output_dir": "output/",
    },
    "hyper_params": {
        "data_loader_params": {
            "batch_size": 32,
            "shuffle": True,
        },
        "loss": F.mse_loss,
        "optim": torch.optim.Adam,
        "optim_params": {
            "lr": 0.01,
        },
        "metrics": {
            'accuracy': BinaryAccuracy(),
            'precision' : BinaryPrecision(),
            'recall' : BinaryRecall(),
            'f1score' : BinaryF1Score(),
            'auroc' : BinaryAUROC(),
            'trn_loss': torchmetrics.MeanSquaredError(squared=False)
        },
        "device": "cuda"
        if torch.cuda.is_available()
        else "cpu",
        "epochs": 300,
        'cv_params':{
            'n_split': 5,
        },
    },
}