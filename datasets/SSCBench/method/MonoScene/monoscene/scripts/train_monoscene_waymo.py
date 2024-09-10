from monoscene.data.waymo.waymo_dm import WaymoDataModule
from monoscene.data.waymo.params import (
    waymo_class_frequencies,
    waymo_class_names,
)
from torch.utils.data.dataloader import DataLoader
from monoscene.models.monoscene import MonoScene
from pytorch_lightning import Trainer
from pytorch_lightning.loggers import TensorBoardLogger
from pytorch_lightning.callbacks import ModelCheckpoint, LearningRateMonitor
import os
import hydra
from omegaconf import DictConfig
import numpy as np
import torch

hydra.output_subdir = None

CLASS_NUM = 15
@hydra.main(config_name="../config/monoscene.yaml")
def main(config: DictConfig):
    exp_name = config.exp_prefix
    exp_name += "_{}_{}".format(config.dataset, config.run)
    exp_name += "_FrusSize_{}".format(config.frustum_size)
    exp_name += "_nRelations{}".format(config.n_relations)
    exp_name += "_WD{}_lr{}".format(config.weight_decay, config.lr)

    if config.CE_ssc_loss:
        exp_name += "_CEssc"
    if config.geo_scal_loss:
        exp_name += "_geoScalLoss"
    if config.sem_scal_loss:
        exp_name += "_semScalLoss"
    if config.fp_loss:
        exp_name += "_fpLoss"

    if config.relation_loss:
        exp_name += "_CERel"
    if config.context_prior:
        exp_name += "_3DCRP"

    # Setup dataloaders
    class_names = waymo_class_names
    max_epochs = 30
    logdir = config.waymo_logdir
    full_scene_size = (256, 256, 32)
    project_scale = 2
    feature = 64
    n_classes = CLASS_NUM
    class_weights = torch.from_numpy(
        1 / np.log(waymo_class_frequencies + 0.001)
    )
    data_module = WaymoDataModule(
        root=config.waymo_root,
        preprocess_root=config.waymo_preprocess_root,
        frustum_size=config.frustum_size,
        project_scale=project_scale,
        batch_size=int(config.batch_size / config.n_gpus),
        num_workers=int(config.num_workers_per_gpu),
    )




    project_res = ["1"]
    if config.project_1_2:
        exp_name += "_Proj_2"
        project_res.append("2")
    if config.project_1_4:
        exp_name += "_4"
        project_res.append("4")
    if config.project_1_8:
        exp_name += "_8"
        project_res.append("8")

    print(exp_name)

    # Initialize MonoScene model
    model = MonoScene(
        dataset=config.dataset,
        frustum_size=config.frustum_size,
        project_scale=project_scale,
        n_relations=config.n_relations,
        fp_loss=config.fp_loss,
        feature=feature,
        full_scene_size=full_scene_size,
        project_res=project_res,
        n_classes=n_classes,
        class_names=class_names,
        context_prior=config.context_prior,
        relation_loss=config.relation_loss,
        CE_ssc_loss=config.CE_ssc_loss,
        sem_scal_loss=config.sem_scal_loss,
        geo_scal_loss=config.geo_scal_loss,
        lr=config.lr,
        weight_decay=config.weight_decay,
        class_weights=class_weights,
    )

    if config.enable_log:
        logger = TensorBoardLogger(save_dir=logdir, name=exp_name, version="")
        lr_monitor = LearningRateMonitor(logging_interval="step")
        checkpoint_callbacks = [
            ModelCheckpoint(
                save_last=True,
                monitor="val/mIoU",
                save_top_k=1,
                mode="max",
                filename="{epoch:03d}-{val/mIoU:.5f}",
            ),
            lr_monitor,
        ]
    else:
        logger = False
        checkpoint_callbacks = False

    model_path = os.path.join(logdir, exp_name, "checkpoints/last.ckpt")
    if os.path.isfile(model_path):
        # Continue training from last.ckpt
        trainer = Trainer(
            callbacks=checkpoint_callbacks,
            resume_from_checkpoint=model_path,
            sync_batchnorm=True,
            deterministic=False,
            max_epochs=max_epochs,
            gpus=config.n_gpus,
            logger=logger,
            check_val_every_n_epoch=1,
            log_every_n_steps=10,
            flush_logs_every_n_steps=100,
            accelerator="ddp",
        )
    else:
        # Train from scratch
        trainer = Trainer(
            callbacks=checkpoint_callbacks,
            sync_batchnorm=True,
            deterministic=False,
            max_epochs=max_epochs,
            gpus=config.n_gpus,
            logger=logger,
            check_val_every_n_epoch=1,
            log_every_n_steps=10,
            flush_logs_every_n_steps=100,
            accelerator="ddp",
        )

    # trainer.fit(model, data_module)
    data_module.setup()
    trainer.fit(model, train_dataloaders= data_module.train_dataloader(), val_dataloaders=data_module.val_dataloader())

if __name__ == "__main__":
    main()
