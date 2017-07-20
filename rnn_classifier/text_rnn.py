#!/usr/bin/env python

import random
import numpy as np
import sys
import tensorflow as tf
import time


class TextRNNClassifier(object):
    """Text RNN Classifier
    """
    def __init__(self, vocab_size, emb_dim=256, hid_dim=128, nclass=1,
                 seq_len=50, cellt='LSTM', nlayer=1, reg_lambda=0,
                 lr=1e-3, init_embed=None):

        # prepare input and output placeholder
        self.inp_x = tf.placeholder(tf.int32, [None, seq_len], 'input_x')
        self.inp_y = tf.placeholder(tf.float32, [None, nclass], 'input_y')
        self.dropout_prob = tf.placeholder(tf.float32, name='dropout_prob')
        inp_len = tf.reduce_sum(tf.sign(self.inp_x), reduction_indices=1)

        self.global_step = tf.Variable(0, name='global_step', trainable=False)

        # embedding
        if init_embed is not None:
            embedding = tf.Variable(
                tf.convert_to_tensor(init_embed, dtype=tf.float32),
                trainable=emb_trainable, name='embedding')
        else:
            embedding = tf.get_variable(
                'embedding', shape=[vocab_size, emb_dim],
                initializer=tf.random_uniform_initializer(
                    minval=-0.2,
                    maxval=0.2,
                    dtype=tf.float32))
        inp_emb = tf.nn.embedding_lookup(embedding, self.inp_x)

        # construct basic cell
        if cellt == 'LSTM':
            cell = tf.nn.rnn_cell.LSTMCell(
                num_units=hid_dim,
                initializer=tf.random_uniform_initializer(
                    minval=-1./emb_dim**0.5,
                    maxval=+1./emb_dim**0.5))
        elif cellt == 'GRU':
            cell = tf.nn.rnn_cell.GRUCell(num_units=hid_dim)
        elif cellt == 'BasicRNN':
            cell = tf.nn.rnn_cell.BasicRNNCell(num_units=hid_dim)
        else:
            sys.stderr.write('invalid cell type')
            sys.exit(1)

        # layers
        if nlayer > 1:
            cell = tf.nn.rnn_cell.MultiRNNCell(cells=[cell] * nlayer)

        # dropout
        # set keep_prob = 1.0 when predicting
        cell = tf.nn.rnn_cell.DropoutWrapper(
            cell, output_keep_prob=self.dropout_prob)

        # construct rnn
        outputs, states = tf.nn.dynamic_rnn(
            cell=cell,
            dtype=tf.float32,
            sequence_length=inp_len,
            inputs=inp_emb)

        # extract res from dynamic series by given series_length
        batch_size = tf.shape(outputs)[0]  # [batch_size, seq_len, dimension]
        oup_idx = tf.range(0, batch_size) * seq_len + (inp_len - 1)
        oup_flat = tf.reshape(outputs, [-1, hid_dim])  # [batch*seq_len, dim]
        oup_rnn = tf.gather(oup_flat, oup_idx)

        # make prediction
        w = tf.get_variable(
            'W', shape=[hid_dim, nclass],
            initializer=tf.contrib.layers.xavier_initializer())
        b = tf.Variable(tf.constant(0.1, shape=[nclass]), name='b')
        self.scores = tf.nn.xw_plus_b(oup_rnn, w, b, name='scores')
        self.preds = tf.argmax(self.scores, 1, name='predictions')

        # calculate loss
        self.loss = tf.reduce_mean(
            tf.nn.softmax_cross_entropy_with_logits(
                logits=self.scores, labels=self.inp_y))
        reg_loss = reg_lambda * (tf.nn.l2_loss(w) + tf.nn.l2_loss(b))  # l2 reg
        self.total_loss = self.loss + reg_loss

        # bptt
        self.opt = tf.train.AdamOptimizer(lr).minimize(
            self.total_loss, global_step=self.global_step)

        # accuracy
        correct_preds = tf.equal(
            self.preds, tf.argmax(self.inp_y, 1))
        self.accuracy = tf.reduce_mean(
            tf.cast(correct_preds, 'float'), name='accuracy')

        # auc
        labels_c = tf.argmax(self.inp_y, 1)
        preds_c = tf.nn.softmax(self.scores)[:, 1]
        self.auc = tf.metrics.auc(labels=labels_c, predictions=preds_c)

    def train_step(self, sess, inp_batch_x, inp_batch_y, evals=None):
        input_dict = {
            self.inp_x: inp_batch_x,
            self.inp_y: inp_batch_y,
            self.dropout_prob: 0.5}
        sess.run(self.opt, feed_dict=input_dict)

    def eval_step(self, sess, dev_x, dev_y):
        eval_dict = {
            self.inp_x: dev_x,
            self.inp_y: dev_y,
            self.dropout_prob: 1.0}
        loss, auc = sess.run([self.loss, self.auc], feed_dict=eval_dict)
        return loss, auc

    def predict(self, sess, input_x):
        pred_dict = {self.inp_x: input_x}
        return sess.run(self.preds, feed_dict=pred_dict)

    def predict_proba(self, sess, input_x):
        pred_dict = {self.inp_x: input_x}
        return sess.run(self.scores, feed_dict=pred_dict)
