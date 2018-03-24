import keras.backend as K
from keras import optimizers
from keras.layers import AtrousConvolution1D, SpatialDropout1D, Activation, Lambda, \
    Convolution1D, Merge, Dense
from keras.models import Input, Model


def channel_normalization(x):
    # Normalize by the highest activation
    max_values = K.max(K.abs(x), 2, keepdims=True) + 1e-5
    out = x / max_values
    return out


def wave_net_activation(x):
    tanh_out = Activation('tanh')(x)
    sigm_out = Activation('sigmoid')(x)
    return Merge(mode='mul')([tanh_out, sigm_out])


def residual_block(x, s, i, activation, causal, nb_filters, kernel_size):
    original_x = x

    if causal:
        # x = ZeroPadding1D(((2 ** i) // 2, 0))(x)
        conv = AtrousConvolution1D(filters=nb_filters, kernel_size=kernel_size,
                                   atrous_rate=2 ** i, padding='causal',
                                   name='dilated_conv_%d_tanh_s%d' % (2 ** i, s))(x)
        # conv = Cropping1D((0, (2 ** i) // 2))(conv)
    else:
        conv = AtrousConvolution1D(filters=nb_filters, kernel_size=kernel_size,
                                   atrous_rate=2 ** i, padding='causal',
                                   name='dilated_conv_%d_tanh_s%d' % (2 ** i, s))(x)

    if activation == 'norm_relu':
        x = Activation('relu')(conv)
        x = Lambda(channel_normalization)(x)
    elif activation == 'wavenet':
        x = wave_net_activation(conv)
    else:
        x = Activation(activation)(conv)

    x = SpatialDropout1D(0.05)(x)

    # 1x1 conv.
    x = Convolution1D(nb_filters, 1, padding='same')(x)
    res_x = Merge(mode='sum')([original_x, x])
    return res_x, x


def dilated_tcn(num_feat, num_classes, nb_filters,
                kernel_size, dilatations, nb_stacks, max_len,
                activation='wavenet', use_skip_connections=True,
                causal=False, return_param_str=False):
    """
    dilation_depth : number of layers per stack
    nb_stacks : number of stacks.
    """

    input_layer = Input(name='input_layer', shape=(max_len, num_feat))
    x = input_layer

    # DEBUG ON
    # import numpy as np
    # from mnist_pixel.utils import data_generator
    # (x_train, y_train), (x_test, y_test) = data_generator()
    # K.get_session().run(x, feed_dict={input_layer: x_train[0:1]})
    # np.array(K.get_session().run(x, feed_dict={input_layer: x_train[0:1] + 1}))
    # DEBUG OFF

    if causal:
        # x = ZeroPadding1D((kernel_size - 1, 0))(x)
        x = Convolution1D(nb_filters, kernel_size, padding='causal', name='initial_conv')(x)
        # x = Cropping1D((kernel_size - 1, 0))(x)
    else:
        x = Convolution1D(nb_filters, kernel_size, padding='causal', name='initial_conv')(x)
    print('Kernel size back')

    skip_connections = []
    for s in range(nb_stacks):
        for i in dilatations:
            x, skip_out = residual_block(x, s, i, activation, causal, nb_filters, kernel_size)
            skip_connections.append(skip_out)

    if use_skip_connections:
        x = Merge(mode='sum')(skip_connections)
    x = Activation('relu')(x)

    # x = Convolution1D(nb_filters, tail_conv, padding='same')(x)
    # x = Activation('relu')(x)

    x = Lambda(lambda tt: tt[:, -1, :])(x)  # TODO: remove this zero. just for testing.
    print('x.shape=', x.shape)
    x = Dense(num_classes)(x)
    # x = Convolution1D(num_classes, tail_conv, padding='same')(x)

    x = Activation('softmax', name='output_softmax')(x)
    output_layer = x

    print(f'model.x = {input_layer.shape}')
    print(f'model.y = {output_layer.shape}')
    model = Model(input_layer, output_layer)

    adam = optimizers.Adam(lr=0.002, clipnorm=1.)
    model.compile(adam, loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    print('Adam with norm clipping.')

    if return_param_str:
        param_str = 'D-TCN_C{}_B{}_L{}'.format(2, nb_stacks, dilatations)
        if causal:
            param_str += '_causal'

        return model, param_str
    else:
        return model


if __name__ == '__main__':
    pass
    # import numpy as np
    # from mnist_pixel.utils import data_generator
    # (x_train, y_train), (x_test, y_test) = data_generator()
    # K.get_session().run(x, feed_dict={input_layer :x_train[0:1]})
    # np.array(K.get_session().run(x, feed_dict={input_layer: x_train[0:1]}))