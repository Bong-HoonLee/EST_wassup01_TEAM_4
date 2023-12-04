import os
import importlib
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torchmetrics

from datetime import datetime
from tqdm.auto import trange
from sklearn.model_selection import KFold
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader

class Trainer():
    def __init__(self, data_dir: str, config_dir: str) -> None:
        self.data_dir = data_dir
        self.config_dir = config_dir
        
        self.config_modules = []
        self.load_module_from_path()

        self.configs = [module.config for module in self.config_modules]


    def load_module_from_path(self):
        config_files = os.listdir(self.config_dir)
        for config_file in config_files:
            config_file = os.path.join(self.config_dir, config_file)
            module_name = os.path.splitext(os.path.basename(config_file))[0]
            spec = importlib.util.spec_from_file_location(module_name, config_file)
            if spec is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.config_modules.append(module)
        


    def fit(self):
        for config in self.configs:
            model = config['model']
            model_class = model['class']
            model_params = model['params']

            data = config['data']
            train_X = torch.tensor(pd.read_csv(data['train_X']['path'], index_col=data['train_X']['index_col']).to_numpy(dtype=np.float32))
            train_y = torch.tensor(pd.read_csv(data['train_y']['path'], index_col=data['train_y']['index_col']).to_numpy(dtype=np.float32))
            output_dir = data['output_dir']

            hyperparameters = config['hyper_params']
            device = hyperparameters['device']
            epochs = hyperparameters['epochs']
            optim = hyperparameters['optim']
            optim_params = hyperparameters['optim_params']
            metrics = hyperparameters['metrics']
            metrics = {key: metric for key, metric in metrics.items() if key == 'trn_loss'} #trn_loss만 사용
            metrics = {key: metric.to(device) for key, metric in metrics.items()}

            data_loader_params = hyperparameters['data_loader_params']
            dataset = TensorDataset(train_X, train_y)
            dataloader = DataLoader(dataset, **data_loader_params)

            model = model_class(**model_params).to(device)
            loss = hyperparameters['loss']
            optimizer = optim(model.parameters(), **optim_params)

            values = {}
            pbar = trange(epochs)
            for _ in pbar:
                self.training_step(model=model, dataloader=dataloader, loss_function=loss, optimizer=optimizer, device=device, metrics=metrics)
                for key, metric in metrics.items():
                    if key not in values:
                        values[key] = []
                    values[key].append(metric.compute().item())
                    metric.reset()
                postfix_values = {key: value[-1] for key, value in values.items()}
                pbar.set_postfix(postfix_values)

            file_name = config["name"] + "_" + datetime.now().strftime("%Y%m%d%H%M") + ".pth"
            torch.save(model.state_dict(), f"{output_dir}/{file_name}")


    def validate(self):
        for config in self.configs:
            model = config['model']
            model_class = model['class']
            model_params = model['params']

            data = config['data']
            train_X = torch.tensor(pd.read_csv(data['train_X']['path'], index_col=data['train_X']['index_col']).to_numpy(dtype=np.float32))
            train_y = torch.tensor(pd.read_csv(data['train_y']['path'], index_col=data['train_y']['index_col']).to_numpy(dtype=np.float32))
            output_dir = data['output_dir']

            hyperparameters = config['hyper_params']
            device = hyperparameters['device']
            epochs = hyperparameters['epochs']
            optim = hyperparameters['optim']
            optim_params = hyperparameters['optim_params']
            metrics = hyperparameters['metrics']
            metrics = {key: metric.to(device) for key, metric in metrics.items()}

            n_split = hyperparameters['cv_params']['n_split']
            data_loader_params = hyperparameters['data_loader_params']

            model = model_class(**model_params).to(device)
            models = [model_class(**model_params).to(device) for _ in range(n_split)]
            for i, _ in enumerate(models):
                models[i].load_state_dict(model.state_dict())

            kfold = KFold(n_splits=n_split, shuffle=False)
            trn_values = {}
            val_values = {}
            history = []

            for i, (trn_idx, val_idx) in enumerate(kfold.split(train_X)):
                X_trn, y_trn = train_X[trn_idx], train_y[trn_idx]
                X_val, y_val = train_X[val_idx], train_y[val_idx]

                ds_trn = TensorDataset(X_trn, y_trn)
                ds_val = TensorDataset(X_val, y_val)

                dl_trn = DataLoader(ds_trn, **data_loader_params)
                dl_val = DataLoader(ds_val, **data_loader_params)

                loss = hyperparameters['loss']
                optimizer = optim(models[i].parameters(), **optim_params)

                pbar = trange(epochs)
                for _ in pbar:
                    self.training_step(model=models[i], dataloader=dl_trn ,loss_function=loss, optimizer=optimizer, device=device, metrics=metrics)
                    for key, metric in metrics.items():
                        if key not in trn_values:
                            trn_values[key] = []
                        trn_values[key].append(metric.compute().item())
                        metric.reset()
                    postfix_values1 = {f"trn_{key}": value[-1] for key, value in trn_values.items()}
                    
                    self.validation_step(model=models[i], dataloader=dl_val, metrics=metrics, device=device)
                    for key, metric in metrics.items():
                        if key not in val_values:
                            val_values[key] = []
                        val_values[key].append(metric.compute().item())
                        metric.reset()
                    postfix_values2 = {f"val_{key}": value[-1] for key, value in val_values.items()}

                    pbar.set_postfix({**postfix_values1, **postfix_values2})
                history.append({**postfix_values1, **postfix_values2})

            df_metrics = pd.DataFrame(history)
            df_metrics = pd.concat([df_metrics, df_metrics.apply(['mean', 'std'])])
            print(df_metrics)

            file_name = config["name"] + "_validation_" + datetime.now().strftime("%Y%m%d%H%M") + ".csv"
            df_metrics.to_csv(f"{output_dir}/{file_name}", index=False)

    def test(self):
        # self.model.test()

        #TODO testset
        #TODO testset 고르게 추출. 나이 분포, 성별 분포 고려해서 분리. PHQ 점수 분포도 잘 맞추는지 테스트 필요(고르게 추출).

        
        pass


    def training_step(self, model: nn.Module, dataloader: DataLoader, loss_function, optimizer: torch.optim.Optimizer, device, metrics: dict[str, torchmetrics.metric.Metric]) -> float:
        model.train()
        for X, y in dataloader:
            X, y = X.to(device), y.to(device)
            y_hat = model.forward(X)
            loss = loss_function(y_hat, y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            for metric in metrics.values():
                metric.update(y_hat, y)

    def validation_step(self, model: nn.Module, dataloader: DataLoader, device, metrics: dict[str, torchmetrics.metric.Metric]):
        model.eval()
        with torch.inference_mode():
            for X, y in dataloader:
                X, y = X.to(device), y.to(device)
                y_hat = model.forward(X)
                for metric in metrics.values():
                    metric.update(y_hat, y)

    def test_step(self, model: nn.Module, dataloader: DataLoader):
        pass