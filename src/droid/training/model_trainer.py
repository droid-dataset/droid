import csv
import json
import os
import shutil
import time
from collections import OrderedDict, defaultdict

import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.optim as optim
from tqdm import trange

from droid.data_loading.data_loader import create_train_test_data_loader
from droid.training.models.policy_network import ImagePolicy


def exp_launcher(variant, run_id, exp_id):
    variant["exp_name"] = os.path.join(variant["exp_name"], "run{0}/id{1}/".format(run_id, exp_id))

    # Set Random Seeds #
    torch.manual_seed(variant["seed"])
    np.random.seed(variant["seed"])

    # Set Compute Mode #
    use_gpu = variant.get("use_gpu", False)
    torch.device("cuda:0" if use_gpu else "cpu")

    # Prepare Dataset Generators #
    data_loader_kwargs = variant.get("data_loader_kwargs", {})
    data_processing_kwargs = variant.get("data_processing_kwargs", {})
    camera_kwargs = variant.get("camera_kwargs", {})
    train_dataloader, test_dataloader = create_train_test_data_loader(
        data_loader_kwargs=data_loader_kwargs, data_processing_kwargs=data_processing_kwargs, camera_kwargs=camera_kwargs
    )

    # Create Model #
    model = ImagePolicy(**variant.get("model_kwargs", {}))
    if use_gpu:
        model.cuda()

    # Create Trainer #
    trainer = ModelTrainer(
        model=model,
        train_dataloader=train_dataloader,
        test_dataloader=test_dataloader,
        exp_name=variant["exp_name"],
        variant=variant,
        **variant.get("training_kwargs", {}),
    )

    # Launch Experiment #
    trainer.train()


class ModelTrainer:
    def __init__(
        self,
        model,
        train_dataloader,
        test_dataloader,
        exp_name,
        variant,
        num_epochs=25,
        weight_decay=0.0,
        lr=1e-3,
        grad_steps_per_epoch=1000,
    ):
        self.model = model
        self.train_dataloader = iter(train_dataloader)
        self.test_dataloader = iter(test_dataloader)
        self.optimizer = None
        self.grad_steps_per_epoch = grad_steps_per_epoch
        self.weight_decay = weight_decay
        self.num_epochs = num_epochs
        self.lr = lr

        self.persistent_statistics = defaultdict(list)
        self.eval_statistics = defaultdict(list)
        self.variant = variant

        dir_path = os.path.dirname(os.path.realpath(__file__))
        self.log_dir = os.path.join(dir_path, "../../training_logs", exp_name)

    def compute_loss(self, batch, test=False):
        prefix = "test-" if test else "train-"
        loss = self.model.compute_loss(batch)
        self.eval_statistics[prefix + "Loss"].append(loss.item())
        return loss

    def save_policy(self, epoch):
        path = os.path.join(self.log_dir, "models", str(epoch) + ".pt")
        torch.save(self.model, path)

    def train_batch(self, batch):
        if self.optimizer is None:
            self.compute_loss(batch)
            params = list(self.model.parameters())
            self.optimizer = optim.Adam(params, lr=self.lr, weight_decay=self.weight_decay)

        self.optimizer.zero_grad()
        loss = self.compute_loss(batch)

        loss.backward()
        self.optimizer.step()

    def test_batch(self, batch):
        self.compute_loss(batch, test=True)

    def train_epoch(self, epoch):
        start_time = time.time()
        self.model.train()

        # Train On Batches #
        training_procedure = trange(self.grad_steps_per_epoch)
        training_procedure.set_description("Epoch {0}: Training".format(epoch))

        for _i in training_procedure:
            batch = next(self.train_dataloader)
            self.train_batch(batch)

        self.eval_statistics["train-epoch_duration"].append(time.time() - start_time)

    def test_epoch(self, epoch, test_batches=100):
        start_time = time.time()
        self.model.eval()

        # Test On Batches #
        testing_procedure = trange(test_batches)
        testing_procedure.set_description("Epoch {0}: Testing".format(epoch))

        for _i in testing_procedure:
            batch = next(self.test_dataloader)
            self.test_batch(batch)

        self.eval_statistics["test-epoch_duration"].append(time.time() - start_time)

    def prepare_logdir(self):
        if os.path.exists(self.log_dir):
            response = input("Directory Exists - Enter 'overwrite' to continue\n")
            if response == "overwrite":
                shutil.rmtree(self.log_dir)
            else:
                raise RuntimeError

        os.makedirs(self.log_dir)
        os.makedirs(self.log_dir + "graphs/")
        os.makedirs(self.log_dir + "models/")

        with open(self.log_dir + "variant.json", "w") as outfile:
            json.dump(self.variant, outfile)

    def output_diagnostics(self, epoch):
        stats = OrderedDict()
        for k in sorted(self.eval_statistics.keys()):
            stats[k] = np.mean(self.eval_statistics[k])
            self.persistent_statistics[k + "/mean"].append(stats[k])
            self.persistent_statistics[k + "/std"].append(np.std(self.eval_statistics[k]))

        self.update_plots(epoch)

        if epoch == 0:
            with open(self.log_dir + "progress.csv", "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=stats.keys())
                writer.writeheader()

        with open(self.log_dir + "progress.csv", "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=stats.keys())
            writer.writerow(stats)

        self.eval_statistics = defaultdict(list)
        np.save(self.log_dir + "logs.npy", self.persistent_statistics)

        print("\nEPOCH: ", epoch)
        for k, v in stats.items():
            spacing = ":" + " " * (30 - len(k))
            print(k + spacing + str(round(v, 5)))

    def update_plots(self, epoch):
        x_axis = np.arange(epoch + 1)
        for k in sorted(self.eval_statistics.keys()):
            plt.clf()
            mean = np.array(self.persistent_statistics[k + "/mean"])
            std = np.array(self.persistent_statistics[k + "/std"])
            plt.plot(x_axis, mean, color="blue")
            plt.fill_between(x_axis, mean - std, mean + std, facecolor="blue", alpha=0.5)
            plt.title(k)
            plt.savefig(self.log_dir + "graphs/{0}.png".format(k))

    def train(self):
        self.prepare_logdir()

        for epoch in range(self.num_epochs):
            self.test_epoch(epoch)
            self.train_epoch(epoch)
            self.save_policy(epoch)
            self.output_diagnostics(epoch)
