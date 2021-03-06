from __future__ import absolute_import, division, print_function

import os
import multiprocessing
import tensorflow as tf

from . import flowers, ptb_reader, cifar_input
from .. import tfhelper

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


slim = tf.contrib.slim


def find_data_dir(dataset_name, *args):
    # find data dir
    for p in Path(".").absolute().parents:
        candidate = p/'data'
        if candidate.exists():
            candidate = candidate/dataset_name
            candidate = candidate.joinpath(*args)
            return str(candidate)
    raise ValueError("Can not find data for {}".format(dataset_name))


def fake_data_ex(batch_size, variable_specs=None):
    if variable_specs is None:
        variable_specs = [
            ((256, 256, 3), {'dtype': tf.float32}, 'images'),
            ((1,), {'minval': 0, 'maxval': 1000}, 'truths'),
        ]

    inputs = []
    for shape, kwargs, name in variable_specs:
        var = tf.Variable(tf.random_normal(shape, **kwargs), name=name+'/sample', trainable=False)

        input_queue = tf.train.input_producer(tf.expand_dims(var, 0))

        inp = input_queue.dequeue_many(batch_size, name=name)
        inputs.append(inp)
    return inputs


def fake_data(batch_size, batch_num, is_train=True, height=256, width=256, num_classes=1000, depth=3):
    """Generate a fake dataset that matches the dimensions of ImageNet."""
    if not is_train:
        batch_num = 1
        batch_size = 1
    with tf.name_scope('fake_data'):
        image = tf.Variable(tf.random_normal([height, width, depth], dtype=tf.float32),
                            name='sample_image', trainable=False)
        label = tf.Variable(tf.random_uniform([1], minval=0, maxval=num_classes,
                                              dtype=tf.int32),
                            name='ground_truth', trainable=False)

        image_queue = tf.train.input_producer(tf.expand_dims(image, 0))
        label_queue = tf.train.input_producer(tf.expand_dims(label, 0))

        images = image_queue.dequeue_many(batch_size, name='images')
        labels = label_queue.dequeue_many(batch_size, name='labels')
        labels = tf.squeeze(labels)  # remove the second dim (10, 1) => (10, )
        return images, labels, num_classes


def flowers_data(batch_size, batch_num, height=256, width=256, is_train=True, num_threads=None):
    """Flowers dataset from Facebook"""
    if num_threads is None:
        num_threads = multiprocessing.cpu_count()
        num_readers = num_threads // 2

    with tf.name_scope('flowers_data'):
        data_dir = find_data_dir('flowers')
        if is_train:
            dataset = flowers.get_split('train', data_dir)
        else:
            dataset = flowers.get_split('validation', data_dir)

        if is_train:
            num_epochs = (batch_num * batch_size + dataset.num_samples - 1) // dataset.num_samples
        else:
            num_epochs = 1
        provider = slim.dataset_data_provider.DatasetDataProvider(dataset, num_readers=num_readers,
                                                                  num_epochs=num_epochs)
        image, label = provider.get(['image', 'label'])
        tfhelper.image_summary('image', tf.expand_dims(image, 0))
        # Transform the image to floats.
        image = tf.to_float(image)

        # Resize and crop if needed.
        resized_image = tf.image.resize_image_with_crop_or_pad(image, height, width)
        tfhelper.image_summary('resized_image', tf.expand_dims(resized_image, 0))

        # Subtract off the mean and divide by the variance of the pixels.
        resized_image = tfhelper.image_standardization(resized_image)

        images, labels = tf.train.batch([resized_image, label], batch_size=batch_size,
                                        capacity=1000 * batch_size, num_threads=num_readers)
        return images, labels, 5


def ptb_data(config, eval_config):
    data_dir = find_data_dir('ptb', 'data')
    raw_data = ptb_reader.ptb_raw_data(data_dir)
    train_data, valid_data, test_data, _ = raw_data
    return (
        ptb_reader.PTBInput(config, train_data, "TrainInput"),
        ptb_reader.PTBInput(eval_config, valid_data, "ValidInput"),
        ptb_reader.PTBInput(eval_config, test_data, "TestInput"),
    )


def cifar10_data(batch_size, is_train=True):
    data_path = find_data_dir('cifar-10-batches-bin', 'data_batch_*')
    images, labels = cifar_input.build_input('cifar10', data_path, batch_size,
                                             "train" if is_train else "eval")
    return images, labels, 10


def cifar100_data(batch_size, is_train=True):
    data_path = find_data_dir('cifar-100', 'train.bin')
    images, labels = cifar_input.build_input('cifar100', data_path, batch_size,
                                             "train" if is_train else "eval")
    return images, labels, 100
