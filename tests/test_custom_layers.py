import numpy as np
from cvnn.layers import ComplexDense, ComplexFlatten, ComplexInput, ComplexConv2D, ComplexMaxPooling2D, \
    ComplexAvgPooling2D, ComplexConv2DTranspose, ComplexUnPooling2D, ComplexMaxPooling2DWithArgmax, \
    ComplexUpSampling2D, ComplexBatchNormalization, ComplexAvgPooling1D
import cvnn.layers as complex_layers
from tensorflow.keras.models import Sequential
import tensorflow as tf
import tensorflow_datasets as tfds

from pdb import set_trace

"""
This module tests:
    Correct result of Complex AVG and MAX pooling layers.
    Init ComplexConv2D layer and verifies output dtype and shape.
    Trains using:
        ComplexDense
        ComplexFlatten
        ComplexInput 
        ComplexDropout
"""


@tf.autograph.experimental.do_not_convert
def dense_example():
    img_r = np.array([[
        [0, 1, 2],
        [0, 2, 2],
        [0, 5, 7]
    ], [
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ]]).astype(np.float32)
    img_i = np.array([[
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ], [
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ]]).astype(np.float32)
    img = img_r + 1j * img_i
    c_flat = ComplexFlatten()
    c_dense = ComplexDense(units=10)
    res = c_dense(c_flat(img.astype(np.complex64)))
    assert res.shape == [2, 10]
    assert res.dtype == tf.complex64
    model = tf.keras.models.Sequential()
    model.add(ComplexInput(input_shape=(3, 3)))
    model.add(ComplexFlatten())
    model.add(ComplexDense(32, activation='cart_relu'))
    model.add(ComplexDense(32))
    assert model.output_shape == (None, 32)
    res = model(img.astype(np.complex64))


@tf.autograph.experimental.do_not_convert
def serial_layers():
    model = Sequential()
    model.add(ComplexDense(32, activation='relu', input_shape=(32, 32, 3)))
    model.add(ComplexDense(32))
    print(model.output_shape)

    img_r = np.array([[
        [0, 1, 2],
        [0, 2, 2],
        [0, 5, 7]
    ], [
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ]]).astype(np.float32)
    img_i = np.array([[
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ], [
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ]]).astype(np.float32)
    img = img_r + 1j * img_i

    model = Sequential()
    # model.add(ComplexInput(img.shape[1:]))
    model.add(ComplexFlatten(input_shape=img.shape[1:]))
    model.add(ComplexDense(units=10))

    res = model(img)


@tf.autograph.experimental.do_not_convert
def shape_ad_dtype_of_conv2d():
    input_shape = (4, 28, 28, 3)
    x = tf.cast(tf.random.normal(input_shape), tf.complex64)
    y = ComplexConv2D(2, 3, activation='cart_relu', padding="same", input_shape=input_shape[1:], dtype=x.dtype)(x)
    assert y.shape == (4, 28, 28, 2)
    assert y.dtype == tf.complex64


@tf.autograph.experimental.do_not_convert
def normalize_img(image, label):
    """Normalizes images: `uint8` -> `float32`."""
    return tf.cast(image, tf.float32) / 255., label


def get_dataset():
    (ds_train, ds_test), ds_info = tfds.load(
        'mnist',
        split=['train', 'test'],
        shuffle_files=False,
        as_supervised=True,
        with_info=True,
    )

    ds_train = ds_train.map(normalize_img, num_parallel_calls=tf.data.experimental.AUTOTUNE)
    ds_train = ds_train.cache()
    # ds_train = ds_train.shuffle(ds_info.splits['train'].num_examples)
    ds_train = ds_train.batch(128)
    ds_train = ds_train.prefetch(tf.data.experimental.AUTOTUNE)

    ds_test = ds_test.map(normalize_img, num_parallel_calls=tf.data.experimental.AUTOTUNE)
    ds_test = ds_test.batch(128)
    ds_test = ds_test.cache()
    ds_test = ds_test.prefetch(tf.data.experimental.AUTOTUNE)

    return ds_train, ds_test


def get_img():
    img_r = np.array([[
        [0, 1, 2],
        [0, 2, 2],
        [0, 5, 7]
    ], [
        [0, 7, 5],
        [3, 7, 9],
        [4, 5, 3]
    ]]).astype(np.float32)
    img_i = np.array([[
        [0, 4, 5],
        [3, 7, 9],
        [4, 5, 3]
    ], [
        [0, 4, 5],
        [3, 2, 2],
        [4, 8, 9]
    ]]).astype(np.float32)
    img = img_r + 1j * img_i
    img = np.reshape(img, (2, 3, 3, 1))
    return img


@tf.autograph.experimental.do_not_convert
def complex_avg_pool_1d():
    x = tf.constant([1., 2., 3., 4., 5.])
    x = tf.reshape(x, [1, 5, 1])
    avg_pool_1d = tf.keras.layers.AveragePooling1D(pool_size=2, strides=1, padding='valid')
    tf_res = avg_pool_1d(x)
    own_res = ComplexAvgPooling1D(pool_size=2, strides=1, padding='valid')(x)
    assert np.all(tf_res.numpy() == own_res.numpy())
    avg_pool_1d = tf.keras.layers.AveragePooling1D(pool_size=2, strides=2, padding='valid')
    tf_res = avg_pool_1d(x)
    own_res = ComplexAvgPooling1D(pool_size=2, strides=2, padding='valid')(x)
    assert np.all(tf_res.numpy() == own_res.numpy())
    avg_pool_1d = tf.keras.layers.AveragePooling1D(pool_size=2, strides=1, padding='same')
    tf_res = avg_pool_1d(x)
    own_res = ComplexAvgPooling1D(pool_size=2, strides=1, padding='same')(x)
    assert np.all(tf_res.numpy() == own_res.numpy())
    img_r = np.array([[
        [0, 1, 2, 0, 2, 2, 0, 5, 7]
    ], [
        [0, 4, 5, 3, 7, 9, 4, 5, 3]
    ]]).astype(np.float32)
    img_i = np.array([[
        [0, 4, 5, 3, 7, 9, 4, 5, 3]
    ], [
        [0, 4, 5, 3, 2, 2, 4, 8, 9]
    ]]).astype(np.float32)
    img = img_r + 1j * img_i
    img = np.reshape(img, (2, 9, 1))
    avg_pool = ComplexAvgPooling1D()
    res = avg_pool(img.astype(np.complex64))
    expected = tf.expand_dims(tf.convert_to_tensor([[0.5 + 2.j, 1. + 4.j, 2. + 8.j, 2.5 + 4.5j],
                                                    [2. + 2.j, 4. + 4.j, 8. + 2.j, 4.5 + 6.j]], dtype=tf.complex64),
                              axis=-1)
    assert np.all(res.numpy() == expected.numpy())


@tf.autograph.experimental.do_not_convert
def complex_max_pool_2d(test_unpool=True):
    img = get_img()
    max_pool = ComplexMaxPooling2DWithArgmax(strides=1, data_format="channels_last")
    max_pool_2 = ComplexMaxPooling2D(strides=1, data_format="channels_last")
    res, argmax = max_pool(img.astype(np.complex64))
    res2 = max_pool_2(img.astype(np.complex64))
    expected_res = np.array([
        [[
            [2. + 7.j],
            [2. + 9.j]],
            [[2. + 7.j],
             [2. + 9.j]]],
        [[
            [7. + 4.j],
            [9. + 2.j]],
            [
                [5. + 8.j],
                [3. + 9.j]]]
    ])
    assert np.all(res.numpy() == res2.numpy())
    assert (res.numpy() == expected_res.astype(np.complex64)).all()
    if test_unpool:
        max_unpooling = ComplexUnPooling2D(img.shape[1:])
        unpooled = max_unpooling([res, argmax])
        expected_unpooled = np.array([[[0. + 0.j, 0. + 0.j, 0. + 0.j],
                                       [0. + 0.j, 4. + 14.j, 4. + 18.j],
                                       [0. + 0.j, 0. + 0.j, 0. + 0.j]],
                                      [[0. + 0.j, 7. + 4.j, 0. + 0.j],
                                       [0. + 0.j, 0. + 0.j, 9. + 2.j],
                                       [0. + 0.j, 5. + 8.j, 3. + 9.j]]]).reshape(2, 3, 3, 1)
        assert np.all(unpooled.numpy() == expected_unpooled)

    x = tf.constant([[1., 2., 3.],
                     [4., 5., 6.],
                     [7., 8., 9.]])
    x = tf.reshape(x, [1, 3, 3, 1])
    max_pool_2d = tf.keras.layers.MaxPooling2D(pool_size=(2, 2), strides=(1, 1), padding='valid')
    complex_max_pool_2d = ComplexMaxPooling2D(pool_size=(2, 2), strides=(1, 1), padding='valid')
    assert np.all(max_pool_2d(x) == complex_max_pool_2d(x))


def new_max_unpooling_2d_test():
    img = get_img()
    new_imag = tf.stack((img.reshape((2, 3, 3)), img.reshape((2, 3, 3))), axis=-1)
    max_pool = ComplexMaxPooling2DWithArgmax(strides=1, data_format="channels_last")
    res, argmax = max_pool(tf.cast(new_imag, dtype=np.complex64))
    max_unpooling = ComplexUnPooling2D(new_imag.shape[1:])
    unpooled = max_unpooling([res, argmax])


@tf.autograph.experimental.do_not_convert
def complex_avg_pool():
    img = get_img()
    avg_pool = ComplexAvgPooling2D(strides=1)
    res = avg_pool(img.astype(np.complex64))
    expected_res = np.array([[[[0.75 + 3.5j], [1.75 + 6.25j]], [[1.75 + 4.75j], [4. + 6.j]]],
                             [[[4.25 + 2.25j], [7 + 3.25j]], [[4.75 + 4.25j], [6. + 5.25j]]]])
    assert (res.numpy() == expected_res.astype(np.complex64)).all()


@tf.autograph.experimental.do_not_convert
def complex_conv_2d_transpose():
    value = [[1, 2, 1], [2, 1, 2], [1, 1, 2]]
    init = tf.constant_initializer(value)
    transpose_2 = ComplexConv2DTranspose(1, kernel_size=3, kernel_initializer=init, dtype=np.float32)
    input = np.array([[55, 52], [57, 50]]).astype(np.float32).reshape((1, 2, 2, 1))
    expected = np.array([
        [55., 162., 159., 52.],
        [167., 323., 319., 154.],
        [169., 264., 326., 204.],
        [57., 107., 164., 100.]
    ], dtype=np.float32)
    assert np.allclose(transpose_2(input).numpy().reshape((4, 4)), expected)  # TODO: Check why the difference
    value = [[1, 2], [2, 1]]
    init = tf.constant_initializer(value)
    transpose_3 = ComplexConv2DTranspose(1, kernel_size=2, kernel_initializer=init, dtype=np.float32)
    expected = np.array([
        [55., 162., 104],
        [167., 323., 152],
        [114., 157, 50]
    ], dtype=np.float32)
    assert np.allclose(transpose_3(input).numpy().reshape((3, 3)), expected)
    complex_transpose = ComplexConv2DTranspose(1, kernel_size=2, dtype=np.complex64)
    complex_input = (input + 1j * np.zeros(input.shape)).astype(np.complex64)
    assert complex_transpose(complex_input).dtype == tf.complex64


@tf.autograph.experimental.do_not_convert
def upsampling_near_neighbour():
    input_shape = (2, 2, 1, 3)
    x = np.arange(np.prod(input_shape)).reshape(input_shape).astype(np.float32)
    z = tf.complex(real=x, imag=x)
    upsample = ComplexUpSampling2D(size=(2, 3))
    y = upsample(z)
    expected = np.array([[[[0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j]],
                          [[0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j]],
                          [[3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j]],
                          [[3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j]]],
                         [[[6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j]],
                          [[6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j]],
                          [[9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j]],
                          [[9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j]]]])
    assert np.all(y.numpy() == expected)
    upsample = ComplexUpSampling2D(size=(1, 3))
    y = upsample(z)
    expected = np.array([[[[0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j],
                           [0. + 0.j, 1. + 1.j, 2. + 2.j]],
                          [[3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j],
                           [3. + 3.j, 4. + 4.j, 5. + 5.j]]],
                         [[[6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j],
                           [6. + 6.j, 7. + 7.j, 8. + 8.j]],
                          [[9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j],
                           [9. + 9.j, 10. + 10.j, 11. + 11.j]]]])
    assert np.all(y.numpy() == expected)
    upsample = ComplexUpSampling2D(size=(1, 2))
    y = upsample(z)
    # print(y)
    y_tf = tf.keras.layers.UpSampling2D(size=(1, 2))(x)
    my_y = upsample.get_real_equivalent()(x)
    assert np.all(my_y == y_tf)
    x = tf.convert_to_tensor([[[[1., 2.], [3., 4.]]]])
    upsample = ComplexUpSampling2D(size=2, data_format='channels_first')
    my_y = upsample(x)
    y_tf = tf.keras.layers.UpSampling2D(size=(2, 2), data_format='channels_first')(x)
    assert np.all(my_y == y_tf)


@tf.autograph.experimental.do_not_convert
def upsampling_bilinear_corners_aligned():
    # Pytorch examples
    # https://pytorch.org/docs/stable/generated/torch.nn.Upsample.html
    x = tf.convert_to_tensor([[[[1., 2.], [3., 4.]]]])
    z = tf.complex(real=x, imag=x)
    expected = np.array([[[[1.0000, 1.3333, 1.6667, 2.0000],
                           [1.6667, 2.0000, 2.3333, 2.6667],
                           [2.3333, 2.6667, 3.0000, 3.3333],
                           [3.0000, 3.3333, 3.6667, 4.0000]]]])
    upsample = ComplexUpSampling2D(size=2, interpolation='bilinear', data_format='channels_first', align_corners=True)
    y_complex = upsample(z)
    assert np.allclose(expected, tf.math.real(y_complex).numpy(), 0.0001)
    x = tf.convert_to_tensor([[[[1., 2., 0.],
                                [3., 4., 0.],
                                [0., 0., 0.]]]])
    expected = np.array([[[[1.0000, 1.4000, 1.8000, 1.6000, 0.8000, 0.0000],
                           [1.8000, 2.2000, 2.6000, 2.2400, 1.1200, 0.0000],
                           [2.6000, 3.0000, 3.4000, 2.8800, 1.4400, 0.0000],
                           [2.4000, 2.7200, 3.0400, 2.5600, 1.2800, 0.0000],
                           [1.2000, 1.3600, 1.5200, 1.2800, 0.6400, 0.0000],
                           [0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 0.0000]]]])
    upsample = ComplexUpSampling2D(size=2, interpolation='bilinear', data_format='channels_first', align_corners=True)
    y = upsample(x)
    assert np.allclose(expected, tf.math.real(y).numpy(), 0.00001)

    # https://blogs.sas.com/content/iml/2020/05/18/what-is-bilinear-interpolation.html#:~:text=Bilinear%20interpolation%20is%20a%20weighted,the%20point%20and%20the%20corners.&text=The%20only%20important%20formula%20is,x%20%5B0%2C1%5D.
    x = tf.convert_to_tensor([[[[0., 4.], [2., 1.]]]])
    z = tf.complex(real=x, imag=x)
    upsample = ComplexUpSampling2D(size=3, interpolation='bilinear', data_format='channels_first', align_corners=True)
    y_complex = upsample(z)
    expected = np.array([[[[0. + 0.j, 0.8 + 0.8j,
                            1.6 + 1.6j, 2.4 + 2.4j,
                            3.2 + 3.2j, 4. + 4.j],
                           [0.4 + 0.4j, 1. + 1.j,
                            1.6 + 1.6j, 2.2 + 2.2j,
                            2.8 + 2.8j, 3.4 + 3.4j],
                           [0.8 + 0.8j, 1.2 + 1.2j,
                            1.6 + 1.6j, 2. + 2.j,
                            2.4 + 2.4j, 2.8 + 2.8j],
                           [1.2 + 1.2j, 1.4 + 1.4j,
                            1.6 + 1.6j, 1.8 + 1.8j,
                            2. + 2.j, 2.2 + 2.2j],
                           [1.6 + 1.6j, 1.6 + 1.6j,
                            1.6 + 1.6j, 1.6 + 1.6j,
                            1.6 + 1.6j, 1.6 + 1.6j],
                           [2. + 2.j, 1.8 + 1.8j,
                            1.6 + 1.6j, 1.4 + 1.4j,
                            1.2 + 1.2j, 1. + 1.j]]]])
    assert np.allclose(expected, y_complex.numpy(), 0.000001)


@tf.autograph.experimental.do_not_convert
def upsampling_bilinear_corner_not_aligned():
    # Pytorch
    #   https://pytorch.org/docs/stable/generated/torch.nn.Upsample.html
    x = tf.convert_to_tensor([[[[1., 2.], [3., 4.]]]])
    z = tf.complex(real=x, imag=x)
    y_tf = tf.keras.layers.UpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(x)
    y_own = ComplexUpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(z)
    # set_trace()
    assert np.all(y_tf == tf.math.real(y_own).numpy())
    x = tf.convert_to_tensor([[[[1., 2., 0.],
                                [3., 4., 0.],
                                [0., 0., 0.]]]])
    z = tf.complex(real=x, imag=x)
    y_tf = tf.keras.layers.UpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(x)
    y_own = ComplexUpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(z)
    assert np.all(y_tf == tf.math.real(y_own).numpy())
    x = tf.convert_to_tensor([[[[1., 2.], [3., 4.]]]])
    z = tf.complex(real=x, imag=x)
    y_tf = tf.keras.layers.UpSampling2D(size=3, interpolation='bilinear', data_format='channels_first')(x)
    y_own = ComplexUpSampling2D(size=3, interpolation='bilinear', data_format='channels_first')(z)
    assert np.allclose(y_tf, tf.math.real(y_own).numpy())
    y_tf = tf.keras.layers.UpSampling2D(size=6, interpolation='bilinear', data_format='channels_first')(x)
    y_own = ComplexUpSampling2D(size=6, interpolation='bilinear', data_format='channels_first')(z)
    assert np.allclose(y_tf, tf.math.real(y_own).numpy())
    y_tf = tf.keras.layers.UpSampling2D(size=8, interpolation='bilinear', data_format='channels_first')(x)
    y_own = ComplexUpSampling2D(size=8, interpolation='bilinear', data_format='channels_first')(z)
    assert np.all(y_tf == tf.math.real(y_own).numpy())
    # to test bicubic= https://discuss.pytorch.org/t/what-we-should-use-align-corners-false/22663/17
    # https://www.tensorflow.org/api_docs/python/tf/keras/layers/UpSampling2D
    input_shape = (2, 2, 1, 3)
    x = np.arange(np.prod(input_shape)).reshape(input_shape)
    y_tf = tf.keras.layers.UpSampling2D(size=(1, 2), interpolation='bilinear')(x)
    y_own = ComplexUpSampling2D(size=(1, 2), interpolation='bilinear')(x)
    assert np.all(y_tf == y_own)


@tf.autograph.experimental.do_not_convert
def upsampling():
    x = tf.convert_to_tensor([[[[1., 2.], [3., 4.]]]])
    z = tf.complex(real=x, imag=x)
    y_tf = tf.keras.layers.UpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(x)
    y_cvnn = ComplexUpSampling2D(size=2, interpolation='bilinear', data_format='channels_first')(z)
    assert np.all(y_tf == tf.math.real(y_cvnn).numpy())
    upsampling_near_neighbour()
    # test_upsampling_bilinear_corners_aligned()
    upsampling_bilinear_corner_not_aligned()


def check_proximity(x1, x2, name: str):
    th = 0.1
    diff = np.max(np.abs(x1 - x2))
    if 0 < diff < th:
        print(f"{name} are equal with an error of {diff}")
    if diff >= th:
        return False
    return True


def batch_norm():
    # z = tf.transpose(tf.convert_to_tensor([[[-1, 1] * 10] * 20] * 2))
    # c_bn = ComplexBatchNormalization(dtype=np.float32)
    # c_out = c_bn(z, training=True)
    # # set_trace()
    # assert check_proximity(c_out, z, "Normalized input")

    z = np.random.rand(3, 43, 12, 10)  # + np.random.rand(3, 43, 12, 75)*1j
    # z = np.random.rand(100, 10)
    bn = tf.keras.layers.BatchNormalization(epsilon=0)
    c_bn = ComplexBatchNormalization(dtype=np.float32)  # If I use the complex64 then the init is different
    c_bn_2 = ComplexBatchNormalization(dtype=np.float32, cov_method=2)
    input = tf.convert_to_tensor(z.astype(np.float32), dtype=np.float32)
    out = bn(input, training=False)
    c_out = c_bn(input, training=False)
    assert check_proximity(out, c_out, "Results before training")
    assert check_proximity(bn.moving_mean, c_bn.moving_mean, "Moving mean before training")
    assert check_proximity(bn.moving_variance, c_bn.moving_var[..., 0, 0], "Moving variance before training")
    assert check_proximity(bn.gamma, c_bn.gamma, "Gamma before training")
    assert check_proximity(bn.beta, c_bn.beta, "Beta before training")
    out = bn(input, training=True)
    c_out = c_bn(input, training=True)
    assert check_proximity(out, c_out, "Results after training")
    assert check_proximity(bn.moving_mean, c_bn.moving_mean, "Moving mean after training")
    assert check_proximity(bn.moving_variance, c_bn.moving_var[..., 0, 0], "Moving variance after training")
    assert check_proximity(bn.gamma, c_bn.gamma, "Gamma after training")
    assert check_proximity(bn.beta, c_bn.beta, "Beta after training")
    c_out_2 = c_bn_2(input, training=True)
    assert check_proximity(c_out, c_out_2, "Method comparison results after training")
    assert check_proximity(c_bn_2.moving_mean, c_bn.moving_mean, "Method comparison Moving mean after training")
    assert check_proximity(c_bn_2.moving_var, c_bn.moving_var, "Method comparison Moving variance after training")
    assert check_proximity(c_bn_2.gamma, c_bn.gamma, "Method comparison Gamma after training")
    assert check_proximity(c_bn_2.beta, c_bn.beta, "Method comparison Beta after training")


def pooling_layers():
    complex_max_pool_2d()
    complex_avg_pool_1d()
    complex_avg_pool()


@tf.autograph.experimental.do_not_convert
def test_layers():
    new_max_unpooling_2d_test()
    pooling_layers()
    batch_norm()
    upsampling()
    complex_conv_2d_transpose()
    shape_ad_dtype_of_conv2d()
    dense_example()


if __name__ == "__main__":
    test_layers()
