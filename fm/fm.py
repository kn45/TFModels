#!/usr/bin/env python
import tensorflow as tf


class FMCore(object):
    """Factorization Machine Core
    """

    def _sparse_mul(self, x, w):
        """dense_res = sparse_x * dense_w
        """
        return tf.nn.embedding_lookup_sparse(
            w, x, sp_weights=None, combiner='sum', name='mul_sparse')

    def _sparse_pow(self, x, p):
        """sparse_res = pow(sparse_x, p)
        """
        return tf.SparseTensor(x.indices, tf.pow(x.values, p), x.dense_shape)

    def build_graph(self, inp_dim=None, hid_dim=8, lambda_w=0.0, lambda_v=0.0):
        self.inp_x = tf.sparse_placeholder(dtype=tf.int64, name='input_x')
        self.inp_y = tf.placeholder(tf.float32, [None, 1], name='input_y')
        self.global_step = tf.Variable(0, name='global_step', trainable=False)
        self.w0 = tf.Variable(tf.constant(0.1, shape=[1]), name='w0')
        with tf.name_scope('1-way'):
            self.W = tf.get_variable(
                'W', shape=[inp_dim, 1],
                initializer=tf.contrib.layers.xavier_initializer())
            self.degree1 = self._sparse_mul(self.inp_x, self.W) + self.w0
        with tf.name_scope('2-way'):
            self.V = tf.get_variable(
                'V', shape=[inp_dim, hid_dim],
                initializer=tf.contrib.layers.xavier_initializer())
            with tf.name_scope('2-way_left'):
                self.left = tf.pow(
                    self._sparse_mul(self.inp_x, self.V), 2)  # (bs, hid_dim)
            with tf.name_scope('2-way_right'):
                self.right = self._sparse_mul(
                    self._sparse_pow(self.inp_x, 2), tf.pow(self.V, 2))
            self.degree2 = tf.reduce_sum(
                tf.subtract(self.left, self.right), axis=1) * 0.5
        with tf.name_scope('prediction'):
            self.preds = self.degree1 + self.degree2
        with tf.name_scope('loss/reg_loss'):
            self.reg_loss = lambda_w * tf.nn.l2_loss(self.w0) + \
                lambda_w * tf.nn.l2_loss(self.W) + \
                lambda_v * tf.nn.l2_loss(self.V)

        def train_step(self, sess, inp_x, inp_y):
            input_dict = {
                self.inp_x: inp_x,
                self.inp_y: inp_y}
            sess.run(self.opt, feed_dict=input_dict)

        def eval_step(self, sess, inp_x, inp_y):
            input_dict = {
                self.inp_x: inp_x,
                self.inp_y: inp_y}
            sess.run(self.loss, feed_dict=input_dict)

        def _predict(self, sess, inp_x, inp_y):
            input_dict = {
                self.inp_x: inp_x,
                self.inp_y: inp_y}
            sess.run(self.preds, feed_dict=input_dict)


class FMClassifier(FMCore):
    """Factorization Machine Classifier
    """
    def __init__(self, inp_dim=None, hid_dim=16, lambda_w=0.0, lambda_v=0.0,
                 lr=1e-4):
        # init graph from input to predict y_hat
        self.build_graph(inp_dim, hid_dim, lambda_w, lambda_v)
        with tf.name_scope('loss/cross_entropy'):
            self.loss = tf.nn.sigmoid_cross_entropy_with_logits(
                labels=self.inp_y,
                logits=self.preds)
        with tf.name_scope('loss/total_loss'):
            self.total_loss = self.loss + self.reg_loss
        self.opt = tf.contrib.opt.LazyAdamOptimizer(lr).minimize(
            self.total_loss, global_step=self.global_step)


if __name__ == '__main__':
    mdl = FMClassifier(5)
    sess = tf.Session()
    file_writer = tf.summary.FileWriter('./log', sess.graph)
    sess.close()
