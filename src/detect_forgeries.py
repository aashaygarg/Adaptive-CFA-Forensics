#!/usr/bin/env python3
"""Detect forgeries with the proposed method."""

import os
import sys
import argparse

import numpy as np
from tqdm import tqdm
import matplotlib as mpl
from matplotlib import pyplot as plt
import torch

from utils import img_to_tensor, jpeg_compress
from structure import FullNet


def get_parser():
    parser = argparse.ArgumentParser(
        description="Detect forgeries with the proposed method.")
    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default="models/pretrained.pt",
        help="Model to use for the network. Default: models/pretrained.pt.")
    parser.add_argument(
        "-j",
        "--jpeg",
        type=int,
        default=None,
        help=
        "JPEG compression quality. Default: no compression is done before analysis."
    )
    parser.add_argument("-b",
                        "--block-size",
                        type=int,
                        default=32,
                        help="Block size. Default: 32.")
    parser.add_argument(
        "-o",
        "--out",
        type=str,
        default=None,
        help=
        "If provided; path to output image. By default, results will be plotted interactively."
    )
    parser.add_argument("input", type=str, help="Image to analyse.")
    return parser


if __name__ == "__main__":
    mpl.rcParams['figure.figsize'] = (30.0, 10.0)
    parser = get_parser()
    args = parser.parse_args(sys.argv[1:])
    image_name = args.input
    block_size = args.block_size
    quality = args.jpeg
    model = args.model
    out = args.out
    confidences = {}
    net = FullNet().cuda()
    net.load_state_dict(torch.load(model))
    img = plt.imread(image_name)
    Y_o, X_o, C = img.shape
    img = img[:Y_o - Y_o % 2, :X_o - X_o % 2, :3]
    if img.max() > 1:
        img /= 255
    if quality is not None:
        img = jpeg_compress(img, quality)
    img_t = img_to_tensor(img).cuda().type(torch.float)
    res = np.exp(net(img_t, block_size).detach().cpu().numpy())
    res[:, 1] = res[([1, 0, 3, 2], 1)]
    res[:, 2] = res[([2, 3, 0, 1], 2)]
    res[:, 3] = res[([3, 2, 1, 0], 3)]
    res = np.mean(res, axis=1)
    best_grid = np.argmax(np.mean(res, axis=(1, 2)))
    authentic = np.argmax(res, axis=(0)) == best_grid
    confidence = 1 - np.max(res, axis=0)
    confidence[confidence < 0] = 0
    confidence[confidence > 1] = 1
    confidence[authentic] = 1
    if out is not None:
        error_map = 1 - confidence  # highest values (white) correspond to suspected forgeries
        # Resample the output to match the original image size
        error_map = np.repeat(np.repeat(error_map, block_size, axis=0),
                              block_size,
                              axis=1)
        output = np.zeros((Y_o, X_o))
        output[:error_map.shape[0], :error_map.shape[1]] = error_map
        plt.imsave(out, output)
    else:
        confidence = confidence.repeat(block_size, axis=0).repeat(
            block_size, axis=1)  # Make it the same size as image
        img = img[4:-4, 4:-4]
        Y, X, C = img.shape
        Y -= Y % block_size
        X -= X % block_size
        img = img[:Y, :X]
        fig, ax = plt.subplots(1, 2, sharex=True, sharey=True)
        ax[0].imshow(img)
        ax[0].axis('off')
        ax[0].set_title('Input image')
        ax[1].matshow(confidence, vmin=0, vmax=1)
        cbar = plt.colorbar(
            mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(0, 1)),
            ax=ax,
            ticks=[0, .2, .4, .6, .8, 1])
        cbar.ax.set_yticklabels(
            ['0 (Forged)', '.2', '.4', '.6', '.8', '1 (No detection)'])
        ax[1].axis('off')
        ax[1].set_title('Detected forgeries')
        plt.show()
        plt.imshow(img * confidence[:, :, None] +
                   np.array([1., 0., 0.])[None, None] *
                   (1 - confidence[:, :, None]))
        plt.title('Detected forgeries')
        plt.axis('off')
        plt.show()
