from abc import ABC, abstractmethod
from itertools import count
import tensorflow as tf
from collections.abc import Iterable
import sys
import numpy as np
from pdb import set_trace
# My package
from cvnn.activation_functions import apply_activation
from cvnn.utils import get_func_name
from cvnn import logger
from time import time
import cvnn.initializers as initializers
# Typing
from tensorflow import dtypes
from numpy import dtype, ndarray
from typing import Union, Callable, Optional, List, Set, Tuple
from cvnn.initializers import RandomInitializer

SUPPORTED_DTYPES = (np.complex64, np.float32)  # , np.complex128, np.float64) Gradients return None when complex128
DATA_FORMAT = {
    "channels_last",
    "channels_first"
}
layer_count = count(0)  # Used to count the number of layers

t_input_shape = Union[int, tuple, list]
t_kernel_shape = t_input_shape
t_padding_shape = Union[str, t_input_shape]
t_Callable_shape = Union[t_input_shape, Callable]  # Either a input_shape or a function that sets self.output
t_Dtype = Union[dtypes.DType, dtype]

PADDING_MODES = {
    "valid",
    "same",
    "full"
}


class ComplexLayer(ABC):
    # Being ComplexLayer an abstract class, then this can be called using:
    #   self.__class__.__bases__.<variable>
    # As all child's will have this class as base, mro gives a full list so won't work.
    last_layer_output_dtype = None  # TODO: Make it work both with np and tf dtypes
    last_layer_output_size = None

    def __init__(self, output_size: t_Callable_shape, input_size: Optional[t_input_shape], input_dtype: t_Dtype,
                 **args):
        """
        Base constructor for a complex layer. The first layer will need a input_dtype and input_size.
        For the other classes is optional,
            if input_size or input_dtype does not match last layer it will throw a warning
        :param output_size: Output size of the layer.
            If the output size depends on the input_size, a function must be passed as output_size.
        :param input_size: Input size of the layer
        :param input_dtype: data type of the input
        """
        if output_size is None:
            logger.error("Output size = None not supported")
            sys.exit(-1)

        if input_dtype is None and self.__class__.__bases__[0].last_layer_output_dtype is None:
            # None input dtype given but it's the first layer declared
            logger.error("First layer must be given an input dtype", exc_info=True)
            sys.exit(-1)
        elif input_dtype is None and self.__class__.__bases__[0].last_layer_output_dtype is not None:
            # Use automatic mode
            self.input_dtype = self.__class__.__bases__[0].last_layer_output_dtype
        elif input_dtype is not None:
            if input_dtype not in SUPPORTED_DTYPES:
                logger.error(f"Layer::__init__: unsupported input_dtype {input_dtype}", exc_info=True)
                sys.exit(-1)
            if self.__class__.__bases__[0].last_layer_output_dtype is not None:
                if self.__class__.__bases__[0].last_layer_output_dtype != input_dtype:
                    logger.warning(f"Input dtype {input_dtype} is not equal to last layer's output dtype {self.__class__.__bases__[0].last_layer_output_dtype}")
            self.input_dtype = input_dtype

        # This will be normally the case.
        # Each layer must change this value if needed.
        self.__class__.__bases__[0].last_layer_output_dtype = self.input_dtype

        # Input Size
        if input_size is None:
            if self.__class__.__bases__[0].last_layer_output_size is None:
                # None input size given but it's the first layer declared
                logger.error("First layer must be given an input size")
                sys.exit(-1)
            else:  # self.__class__.__bases__[0].last_layer_output_dtype is not None:
                self.input_size = self.__class__.__bases__[0].last_layer_output_size
        elif input_size is not None:
            if self.__class__.__bases__[0].last_layer_output_size is not None:
                if input_size != self.__class__.__bases__[0].last_layer_output_size:
                    logger.warning(f"Input size {input_size} is not equal to last layer's output "
                                   f"size {self.__class__.__bases__[0].last_layer_output_size}")
            self.input_size = input_size
        self._verify_input_size()

        if callable(output_size):
            output_size()
            assert self.output_size is not None, "Error: output_size function must set self.output_size"
        else:
            self.output_size = output_size
        for x in self.__class__.mro():
            if x == ComplexLayer:
                x.last_layer_output_size = self.output_size
        # self.__class__.__bases__[0].last_layer_output_size = self.output_size
        self.layer_number = next(layer_count)   # Know it's own number
        self.__class__.__call__ = self.call     # Make my object callable

    @abstractmethod
    def __deepcopy__(self, memodict=None):
        pass

    def get_input_dtype(self):
        return self.input_dtype

    @abstractmethod
    def get_real_equivalent(self):
        """
        :return: Gets a real-valued COPY of the Complex Layer.
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        :return: a string containing all the information of the layer
        """
        pass

    def _save_tensorboard_output(self, x, summary, step):
        x = self.call(x)
        with summary.as_default():
            if x.dtype == tf.complex64 or x.dtype == tf.complex128:
                tf.summary.histogram(name="Activation_value_" + str(self.layer_number) + "_real",
                                     data=tf.math.real(x), step=step)
                tf.summary.histogram(name="Activation_value_" + str(self.layer_number) + "_imag",
                                     data=tf.math.imag(x), step=step)
            elif x.dtype == tf.float32 or x.dtype == tf.float64:
                tf.summary.histogram(name="Activation_value_" + str(self.layer_number),
                                     data=x, step=step)
            else:
                logger.error("Input_dtype not supported. Should never have gotten here!", exc_info=True)
                sys.exit(-1)
        return x

    def save_tensorboard_checkpoint(self, x, weight_summary, activation_summary, step=None):
        self._save_tensorboard_weight(weight_summary, step)
        return self._save_tensorboard_output(x, activation_summary, step)

    @abstractmethod
    def _verify_input_size(self) -> None:
        """
        Rewrite function to check input size is Ok
        """
        pass

    @abstractmethod
    def _save_tensorboard_weight(self, weight_summary, step):
        pass

    @abstractmethod
    def trainable_variables(self):
        pass

    @abstractmethod
    def call(self, inputs):
        pass

    def get_output_shape_description(self) -> str:
        # output_string = ""
        if isinstance(self.output_size, Iterable):
            output_string = "(None, " + ", ".join([str(x) for x in self.output_size]) + ")"
        else:
            output_string = "(None, " + str(self.output_size) + ")"
        return output_string


class Flatten(ComplexLayer):

    def __init__(self, input_size=None, input_dtype=None):
        # Win x2: giving None as input_size will also make sure Flatten is not the first layer
        super().__init__(input_size=input_size, output_size=self._get_output_size, input_dtype=input_dtype)

    def __deepcopy__(self, memodict=None):
        return Flatten()

    def _get_output_size(self):
        self.output_size = np.prod(self.input_size)

    def get_real_equivalent(self):
        return self.__deepcopy__()

    def get_description(self) -> str:
        return "Complex Flatten"

    def _save_tensorboard_weight(self, weight_summary, step):
        return None

    def call(self, inputs):
        return tf.reshape(inputs, (inputs.shape[0], self.output_size))

    def trainable_variables(self):
        return []

    def _verify_input_size(self) -> None:
        return None


class Dense(ComplexLayer):
    """
    Fully connected complex-valued layer
    Implements the operation:
        activation(dot(input, weights) + bias)
    - where data types can be either complex or real.
    - activation is the element-wise activation function passed as the activation argument,
    - weights is a matrix created by the layer
    - bias is a bias vector created by the layer
    """

    def __init__(self, output_size, input_size=None, activation=None, input_dtype=None,
                 weight_initializer: Optional[RandomInitializer] = None,
                 bias_initializer: Optional[RandomInitializer] = None,
                 dropout: Optional[float] = None):
        """
        Initializer of the Dense layer
        :param output_size: Output size of the layer
        :param input_size: Input size of the layer
        :param activation: Activation function to be used.
            Can be either the function from cvnn.activation or tensorflow.python.keras.activations
            or a string as listed in act_dispatcher
        :param input_dtype: data type of the input. Default: np.complex64
            Supported data types:
                - np.complex64
                - np.float32
        :param weight_initializer: Initializer for the weights.
            Default: cvnn.initializers.GlorotUniform
        :param bias_initializer: Initializer fot the bias.
            Default: cvnn.initializers.Zeros
        :param dropout: Either None (default) and no dropout will be applied or a scalar
            that will be the probability that each element is dropped.
            Example: setting rate=0.1 would drop 10% of input elements.
        """
        super(Dense, self).__init__(output_size=output_size, input_size=input_size, input_dtype=input_dtype)
        if activation is None:
            activation = 'linear'
        self.activation = activation
        # Test if the activation function changes datatype or not...
        self.__class__.__bases__[0].last_layer_output_dtype = \
            apply_activation(self.activation,
                             tf.cast(tf.complex([[1., 1.], [1., 1.]], [[1., 1.], [1., 1.]]), self.input_dtype)
                             ).numpy().dtype
        self.dropout = dropout  # TODO: I don't find the verification that it is between 0 and 1. I think I omitted
        if weight_initializer is None:
            weight_initializer = initializers.GlorotUniform()
        self.weight_initializer = weight_initializer
        if bias_initializer is None:
            bias_initializer = initializers.Zeros()
        self.bias_initializer = bias_initializer
        self.w = None
        self.b = None
        self._init_weights()

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return Dense(output_size=self.output_size, input_size=self.input_size,
                     activation=self.activation,
                     input_dtype=self.input_dtype,
                     weight_initializer=self.weight_initializer,
                     bias_initializer=self.bias_initializer, dropout=self.dropout
                     )

    def get_real_equivalent(self, output_multiplier=2, input_multiplier=2):
        """
        :param output_multiplier: Multiplier of output and input size (normally by 2)
        :return: real-valued copy of self
        """
        return Dense(output_size=int(round(self.output_size * output_multiplier)),
                     input_size=int(round(self.input_size * input_multiplier)),
                     activation=self.activation, input_dtype=np.float32,
                     weight_initializer=self.weight_initializer,
                     bias_initializer=self.bias_initializer, dropout=self.dropout
                     )

    def _init_weights(self):
        self.w = tf.Variable(self.weight_initializer(shape=(self.input_size, self.output_size), dtype=self.input_dtype),
                             name="weights" + str(self.layer_number))
        self.b = tf.Variable(self.bias_initializer(shape=self.output_size, dtype=self.input_dtype),
                             name="bias" + str(self.layer_number))

    def get_description(self):
        fun_name = get_func_name(self.activation)
        out_str = "Dense layer:\n\tinput size = " + str(self.input_size) + "(" + str(self.input_dtype) + \
                  ") -> output size = " + str(self.output_size) + \
                  ";\n\tact_fun = " + fun_name + ";\n\tweight init = " \
                                                 "\n\tDropout: " + str(self.dropout) + "\n"
        # + self.weight_initializer.__name__ + "; bias init = " + self.bias_initializer.__name__ + \
        return out_str

    def call(self, inputs):
        """
        Applies the layer to an input
        :param inputs: input
        :param kwargs:
        :return: result of applying the layer to the inputs
        """
        # TODO: treat bias as a weight. It might optimize training (no add operation, only mult)
        with tf.name_scope("ComplexDense_" + str(self.layer_number)) as scope:
            if tf.dtypes.as_dtype(inputs.dtype) is not tf.dtypes.as_dtype(np.dtype(self.input_dtype)):
                logger.warning("Dense::apply_layer: Input dtype " + str(inputs.dtype) + " is not as expected ("
                               + str(tf.dtypes.as_dtype(np.dtype(self.input_dtype))) +
                               "). Casting input but you most likely have a bug")
            out = tf.add(tf.matmul(tf.cast(inputs, self.input_dtype), self.w), self.b)
            y_out = apply_activation(self.activation, out)

            if self.dropout:
                drop_filter = tf.nn.dropout(tf.ones(y_out.shape), rate=self.dropout)
                y_out_real = tf.multiply(drop_filter, tf.math.real(y_out))
                y_out_imag = tf.multiply(drop_filter, tf.math.imag(y_out))
                y_out = tf.cast(tf.complex(y_out_real, y_out_imag), dtype=y_out.dtype)
            return y_out

    def _save_tensorboard_weight(self, summary, step):
        with summary.as_default():
            if self.input_dtype == np.complex64 or self.input_dtype == np.complex128:
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_w_real",
                                     data=tf.math.real(self.w), step=step)
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_w_imag",
                                     data=tf.math.imag(self.w), step=step)
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_b_real",
                                     data=tf.math.real(self.b), step=step)
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_b_imag",
                                     data=tf.math.imag(self.b), step=step)
            elif self.input_dtype == np.float32 or self.input_dtype == np.float64:
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_w",
                                     data=self.w, step=step)
                tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_b",
                                     data=self.b, step=step)
            else:
                # This case should never happen. The constructor should already have checked this
                logger.error("Input_dtype not supported.", exc_info=True)
                sys.exit(-1)

    def trainable_variables(self):
        return [self.w, self.b]

    def _verify_input_size(self) -> None:
        return None


class Dropout(ComplexLayer):

    def __init__(self, rate, noise_shape=None, seed=None):
        """
        :param rate: A scalar Tensor with the same type as x.
            The probability that each element is dropped.
            For example, setting rate=0.1 would drop 10% of input elements.
        :param noise_shape: A 1-D Tensor of type int32, representing the shape for randomly generated keep/drop flags.
        :param seed:  A Python integer. Used to create random seeds. See tf.random.set_seed for behavior.
        """
        # tf.random.set_seed(seed)
        self.rate = rate
        self.noise_shape = noise_shape
        self.seed = seed
        # Win x2: giving None as input_size will also make sure Dropout is not the first layer
        super().__init__(input_size=None, output_size=self.dummy, input_dtype=None)

    def dummy(self):
        self.output_size = self.input_size

    def call(self, inputs):
        drop_filter = tf.nn.dropout(tf.ones(inputs.shape), rate=self.rate, noise_shape=self.noise_shape, seed=self.seed)
        y_out_real = tf.multiply(drop_filter, tf.math.real(inputs))
        y_out_imag = tf.multiply(drop_filter, tf.math.imag(inputs))
        return tf.cast(tf.complex(y_out_real, y_out_imag), dtype=inputs.dtype)

    def _save_tensorboard_weight(self, weight_summary, step):
        # No tensorboard things to save
        return None

    def get_description(self):
        return "Complex Dropout:\n\trate={}".format(self.rate)

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return Dropout(rate=self.rate, noise_shape=self.noise_shape, seed=self.seed)

    def get_real_equivalent(self):
        return self.__deepcopy__()  # Dropout layer is dtype agnostic

    def trainable_variables(self):
        return []

    def _verify_input_size(self) -> None:
        return None


class FFT2DTransform(ComplexLayer):
    """
    FFT 2D Transform
    Layer that implements the Fast Fourier Transform to the 2D images.
    """

    def __init__(self, input_size: t_input_shape = None, input_dtype: t_Dtype = None, padding: t_padding_shape = 0,
                 data_format: str = "Channels_last"):
        """
        :param input_size: Input shape of the layer, must be of size 3.
        :param input_dtype: Must be given because of herency, but it is irrelevant. TODO
        :param padding: Padding to be done before applying FFT. To perform Conv latter, this value must be the kernel_shape - 1.
            - int: Apply same padding to both axes at the end.
            - tuple, list: Size 2, padding to be applied to each axis.
            - str: "valid" No padding is used.
        :param data_format: A string, one of 'channels_last' (default) or 'channels_first'. 
            - 'channels_last' corresponds to inputs with shape (batch_size, height, width, channels) 
            - 'channels_first' corresponds to inputs with shape (batch_size, channels, height, width).
        """
        if data_format.lower() in DATA_FORMAT:
            self.data_format = data_format.lower()
        self.padding_shape = padding
        super().__init__(input_size=input_size, output_size=self._calculate_output_shape, input_dtype=input_dtype)
        self.last_layer_output_dtype = np.complex64

    def _calculate_output_shape(self) -> None:
        self.output_size = self.input_size

    def _verify_input_size(self) -> None:
        if len(self.input_size) == 2:
            logger.warning("Assuming channel was implicit. Adding axis.")
            if self.data_format == "channels_last":
                self.input_size = self.input_size + (1,)
            elif self.data_format == "channels_first":
                self.input_size = self.input_size.insert(0, 1)
            else:
                logger.error(f"Unknown data_format {self.data_format}")
                sys.exit(-1)
        assert len(self.input_size) == 3, f"Input size must be lenght 3 of the form (" \
                                     f"{'channels, height, width' if self.data_format == 'channels_first' else 'height, width, channels'}). " \
                                     f"Got {self.input_size} "
        self._check_padding()
        if self.data_format == "channels_last":
            self.input_size = (self.input_size[0]+self.padding_shape[0], self.input_size[1]+self.padding_shape[1], self.input_size[2])
        elif self.data_format == "channels_first":
            self.input_size = (self.input_size[0], self.input_size[1]+self.padding_shape[0], self.input_size[2]+self.padding_shape[1])
        else:
            logger.error(f"Unknown data_format {self.data_format}")
            sys.exit(-1)

    def apply_padding(self, inputs):
        pad = [[0, 0]]      # Don't add pad to the images
        for p in self.padding_shape:
            pad.append([0, p])  # This method add pad only at the end
        if self.data_format == "channels_last":
            pad.append([0, 0])
        elif self.data_format == "channels_first":
            pad = pad.insert(0, 1)
        else:
            logger.error(f"Unknown data_format {self.data_format}")
            sys.exit(-1)
        return tf.pad(inputs, tf.constant(pad), "CONSTANT", 0)

    def _check_padding(self):
        # Padding
        if isinstance(self.padding_shape, int):
            self.padding_shape = (self.padding_shape,) * (len(self.input_size) - 1)  # -1 because the last is the channel
            # I call super first in the case input_shape is none
        elif isinstance(self.padding_shape, (tuple, list)):
            self.padding_shape = tuple(self.padding_shape)
            if len(self.padding_shape) != 2:
                logger.error("Padding should have length 2")
                exit(-1)
        elif isinstance(self.padding_shape, str):
            self.padding_shape = self.padding_shape.lower()
            if self.padding_shape in PADDING_MODES:
                if self.padding_shape == "valid":
                    self.padding_shape = (0,) * (len(self.input_size) - 1)
                else:
                    logger.error(f"Unknown padding {self.padding_shape} but listed in PADDING_MODES!")
                    sys.exit(-1)
            else:
                logger.error(f"Unknown padding {self.padding_shape}")
                sys.exit(-1)
        else:
            logger.error(f"Padding: {self.padding_shape} format not supported. It must be an int or a tuple")
            sys.exit(-1)

    def trainable_variables(self):
        return []

    def get_real_equivalent(self):
        return self.__deepcopy__()

    def get_description(self) -> str:
        return "FFT 2D Transform"

    def _save_tensorboard_weight(self, weight_summary, step):
        return None

    def _verify_inputs(self, inputs):
        if len(inputs.shape) == 3:
            logger.warning("Assuming channel was implicit. Adding axis.")
            if self.data_format == "channels_last":
                inputs = tf.reshape(inputs, inputs.shape + (1,))
            elif self.data_format == "channels_first":
                inputs = tf.reshape(inputs, (inputs.shape[0],) + (1,) + inputs.shape[1:])
            else:
                logger.error(f"Unknown data_format {self.data_format}")
                sys.exit(-1)
        assert len(inputs.shape) == 4, f"Input size must be lenght 3 of the form (" \
                                     f"{'images, channels, height, width' if self.data_format == 'channels_first' else 'images, height, width, channels'}). " \
                                     f"Got {inputs.shape} "
        return inputs

    def __deepcopy__(self, memodict=None):
        return FFT2DTransform(input_size=self.input_size, input_dtype=self.input_dtype, padding=self.padding)

    def call(self, inputs):
        inputs = self._verify_inputs(inputs)
        in_pad = self.apply_padding(inputs)
        if self.data_format == "channels_last":
            in_pad = tf.transpose(in_pad, perm=[0, 3, 1, 2])
        out = tf.signal.fft2d(tf.cast(in_pad, tf.complex64))
        if self.data_format == "channels_last":
            out = tf.transpose(out, perm=[0, 2, 3, 1])
        return out


class Convolutional(ComplexLayer):
    # http://datahacker.rs/convolution-rgb-image/   For RGB images
    # https://towardsdatascience.com/a-beginners-guide-to-convolutional-neural-networks-cnns-14649dbddce8

    def __init__(self, filters: int, kernel_shape: t_kernel_shape,
                 input_shape: Optional[t_input_shape] = None, padding: t_padding_shape = 0,
                 stride: t_kernel_shape = 1, input_dtype: Optional[t_Dtype] = None,
                 activation=None,  # TODO: Check type
                 weight_initializer: RandomInitializer = initializers.GlorotUniform(),
                 bias_initializer: RandomInitializer = initializers.Zeros(),
                 data_format='channels_last'  # TODO: Only supported format for the moment.
                 # dilatation_rate=(1, 1)       # TODO: Interesting to add
                 ):
        """
        :param data_format: A string, one of channels_last (default) or channels_first.
            The ordering of the dimensions in the inputs.
            channels_last corresponds to inputs with shape (batch_size, ..., channels) while channels_first corresponds
            to inputs with shape (batch_size, channels, ...)
        """

        super(Convolutional, self).__init__(lambda: self._calculate_shapes(kernel_shape, padding, stride),
                                            input_size=self.input_size, input_dtype=input_dtype)
        # Test if the activation function changes datatype or not...
        self.__class__.__bases__[0].last_layer_output_dtype = \
            apply_activation(self.activation,
                             tf.cast(tf.complex([[1., 1.], [1., 1.]], [[1., 1.], [1., 1.]]), self.input_dtype)
                             ).numpy().dtype
        self.weight_initializer = weight_initializer
        self.bias_initializer = bias_initializer  # TODO: Not working yet

        self._init_kernel(data_format)

    def _calculate_shapes(self, kernel_shape, padding, stride):
        if isinstance(kernel_shape, int):
            self.kernel_shape = (kernel_shape,) * (len(self.input_size) - 1)  # -1 because the last is the channel
        elif isinstance(kernel_shape, (tuple, list)):
            self.kernel_shape = tuple(kernel_shape)
        else:
            logger.error("Kernel shape: " + str(kernel_shape) + " format not supported. It must be an int or a tuple")
            sys.exit(-1)
        if not np.all(np.asarray(self.kernel_shape) > 1):
            logger.error("Kernel shape must have all values bigger than 1: " + str(self.kernel_shape))
            sys.exit(-1)
        # Padding
        if isinstance(padding, int):
            self.padding_shape = (padding,) * (len(self.input_size) - 1)  # -1 because the last is the channel
            # I call super first in the case input_shape is none
        elif isinstance(padding, (tuple, list)):
            self.padding_shape = tuple(padding)
        elif isinstance(padding, str):
            padding = padding.lower()
            if padding in PADDING_MODES:
                if padding == "valid":
                    self.padding_shape = (0,) * (len(self.input_size) - 1)
                elif padding == "same":
                    if np.all(np.asarray(self.kernel_shape) % 2 == 0):
                        logger.warning("Same padding needs the kernel to have an odd value")
                    self.padding_shape = tuple(np.floor(np.asarray(self.kernel_shape) / 2).astype(int))
                elif padding == "full":
                    self.padding_shape = tuple(np.floor(np.asarray(self.kernel_shape) - 1))
                else:
                    logger.error("Unknown padding " + padding + " but listed in PADDING_MODES!")
                    sys.exit(-1)
            else:
                logger.error("Unknown padding " + padding)
                sys.exit(-1)
        else:
            logger.error("Padding: " + str(padding) + " format not supported. It must be an int or a tuple")
            sys.exit(-1)
        # Stride
        if isinstance(stride, int):
            self.stride_shape = (stride,) * (len(self.input_size) - 1)
            # I call super first in the case input_shape is none
        elif isinstance(stride, (tuple, list)):
            self.stride_shape = tuple(stride)
        else:
            logger.error("stride: " + str(stride) + " format not supported. It must be an int or a tuple")
            sys.exit(-1)
        out_list = []
        for i in range(len(self.input_size) - 1):  # -1 because the number of input channels is irrelevant
            # 2.4 on https://arxiv.org/abs/1603.07285
            out_list.append(int(np.floor(
                (self.input_size[i] + 2 * self.padding_shape[i] - self.kernel_shape[i]) / self.stride_shape[i]
            ) + 1))
        out_list.append(self.filters)  # New channels are actually the filters
        self.output_size = tuple(out_list)
        return self.output_size

    def _verify_inputs(self, inputs):
        # TODO: DATA FORMAT!
        # Expected inputs shape: (images, image_shape, channel (optional))
        inputs = tf.convert_to_tensor(inputs)  # This checks all images are same size! Nice
        if inputs.dtype != self.input_dtype:
            logger.warning("input dtype (" + str(inputs.dtype) + ") not what expected ("
                           + str(self.input_dtype) + "). Attempting cast...")
            inputs = tf.dtypes.cast(inputs, self.input_dtype)
        if len(inputs.shape) == len(self.input_size):  # No channel was given
            # case with no channel
            if self.input_size[-1] == 1:
                inputs = tf.reshape(inputs, inputs.shape + (1,))  # Then I have only one channel, I add dimension
            else:
                logger.error("Expected shape " + self._get_expected_input_shape_description())
                # TODO: Add received shape
                sys.exit(-1)
        elif len(inputs.shape) != len(self.input_size) + 1:  # This is the other expected input.
            logger.error("inputs.shape should at least be of size 3 (case of 1D inputs) "
                         "with the shape of (images, channels, vector size)")
            sys.exit(-1)
        if inputs.shape[1:] != self.input_size:  # Remove # of images (index 0) and remove channels (index -1)
            expected_shape = self._get_expected_input_shape_description()

            received_shape = "(images=" + str(inputs.shape[0]) + ", "
            received_shape += "x".join([str(x) for x in inputs.shape[1:-1]])
            received_shape += ", channels=" + str(inputs.shape[-1]) + ")"
            logger.error("Unexpected image shape. Expecting image of shape " +
                         expected_shape + " but received " + received_shape)
            sys.exit(-1)
        return inputs

    def _verify_input_size(self) -> None:
        return None
    
    def call(self, inputs):
        """
        :param inputs:
        :return:
        """
        # TODO: DATA FORMAT!
        with tf.name_scope("ComplexConvolution_" + str(self.layer_number)) as scope:
            inputs = self._verify_inputs(inputs)  # Check inputs are of expected shape and format
            inputs = self.apply_padding(inputs)  # Add zeros if needed
            output_np = tf.Variable(tf.zeros(
                (inputs.shape[0],) +  # Per each image
                self.output_size,  # Image out size
                dtype=self.input_dtype
            ))
            img_index = 0  # I do this ugly thing because https://stackoverflow.com/a/62467248/5931672
            for image in inputs:  # Cannot use enumerate because https://github.com/tensorflow/tensorflow/issues/32546
                for filter_index in range(self.filters):
                    for i in range(int(np.prod(self.output_size[:-1]))):  # for each element in the output
                        index = np.unravel_index(i, self.output_size[:-1])
                        start_index = tuple([a * b for a, b in zip(index, self.stride_shape)])
                        end_index = tuple([a + b for a, b in zip(start_index, self.kernel_shape)])
                        sector_slice = tuple(
                            [slice(start_index[ind], end_index[ind]) for ind in range(len(start_index))]
                        )
                        sector = image[sector_slice]
                        # I use Tied Bias https://datascience.stackexchange.com/a/37748/75968
                        new_value = tf.reduce_sum(sector * self.kernels[filter_index]) + self.bias[filter_index]
                        indices = (img_index,) + index + (filter_index,)
                        output_np = self._assign_value(output_np, indices, new_value)
                img_index += 1

            output = apply_activation(self.activation, output_np)
        return output

    def _assign_value(self, array, indices, value):
        """
        I did this function because of the difficutly on this simple step. I save all references.
        Assigns value on a tensor as array[index] = value
        Original version:
        ```
        indices = (img_index,) + index + (filter_index,)
        output_np[indices] = new_value
        ```
        Options:
        1. All in tensorflow. Issue:
            *** TypeError: 'tensorflow.python.framework.ops.EagerTensor' object does not support item assignment
            References:
                Item alone (My case):
                    https://github.com/tensorflow/tensorflow/issues/14132
                1.1. Solution using tf.tensor_scatter_nd_update. It recreates matrix from scratch.
                    https://stackoverflow.com/questions/55652981/tensorflow-2-0-how-to-update-tensors
                    ```
                    tf_new_value = tf.constant([new_value.numpy()], dtype=self.input_dtype)
                    indices = tf.constant([list((img_index,) + index + (filter_index,))])
                    output_np = tf.tensor_scatter_nd_update(output_np, indices, tf_new_value)
                    ```
                1.2. Solution using assign:
                    https://stackoverflow.com/a/45184132/5931672
                    ```
                    indices = (img_index,) + index + (filter_index,)
                    output_np = output_np[indices].assign(new_value)
                    ```
                1.3. Using tf.stack https://www.tensorflow.org/api_docs/python/tf/stack
                    Not yet tested. Unsure on how to do it
                    https://stackoverflow.com/a/37706972/5931672
                b. Slices:
                The github issue:
                    https://github.com/tensorflow/tensorflow/issues/33131
                    https://github.com/tensorflow/tensorflow/issues/40605
                A workaround (Highly inefficient): Create new matrix using a mask (Memory inefficient isn't it?)
                    THIS IS MY CURRENT SOLUTION!
                    ```
                    mask = tf.Variable(tf.fill(array.shape, 1))
                    mask = mask[indices].assign(0)
                    mask = tf.cast(mask, dtype=self.input_dtype)
                    return array * mask + (1 - mask) * value
                    ```
                    https://github.com/tensorflow/tensorflow/issues/14132#issuecomment-483002522
                    https://towardsdatascience.com/how-to-replace-values-by-index-in-a-tensor-with-tensorflow-2-0-510994fe6c5f
                Misc:
                    https://stackoverflow.com/questions/37697747/typeerror-tensor-object-does-not-support-item-assignment-in-tensorflow
                    https://stackoverflow.com/questions/62092147/how-to-efficiently-assign-to-a-slice-of-a-tensor-in-tensorflow
        1.1.1. Issue: Cannot use tf.function decorator
            AttributeError: 'Tensor' object has no attribute 'numpy'
            References:
                Github issue:
                    https://github.com/cvxgrp/cvxpylayers/issues/56
                Why I need it:
                    https://www.tensorflow.org/guide/function
                Misc:
                    https://stackoverflow.com/questions/52357542/attributeerror-tensor-object-has-no-attribute-numpy
        1.1.2. Removing .numpy() method:
            ValueError: Sliced assignment is only supported for variables
        2. Using numpy.zeros: Issue:
            NotImplementedError: Cannot convert a symbolic Tensor (placeholder_1:0) to a numpy array.
            Github Issue:
                https://github.com/tensorflow/tensorflow/issues/36792
        0. Best option:
            Do it without loops :O (Don't know how possible is this but it will be optimal)
        """
        mask = tf.Variable(tf.fill(array.shape, 1))
        mask = mask[indices].assign(0)
        mask = tf.cast(mask, dtype=self.input_dtype)
        return array * mask + (1 - mask) * value

    def apply_padding(self, inputs):
        pad = [[0, 0]]  # No padding to the images itself
        for p in self.padding_shape:
            pad.append([p, p])  # This method add same pad to beginning and end
        pad.append([0, 0])  # No padding to the channel
        return tf.pad(inputs, tf.constant(pad), "CONSTANT", 0)

    def _save_tensorboard_weight(self, weight_summary, step):
        return None  # TODO

    def get_description(self):
        fun_name = get_func_name(self.activation)
        out_str = "Complex Convolutional layer:\n\tinput size = " + self._get_expected_input_shape_description() + \
                  "(" + str(self.input_dtype) + \
                  ") -> output size = " + self.get_output_shape_description() + \
                  "\n\tkernel shape = (" + "x".join([str(x) for x in self.kernel_shape]) + ")" + \
                  "\n\tstride shape = (" + "x".join([str(x) for x in self.stride_shape]) + ")" + \
                  "\n\tzero padding shape = (" + "x".join([str(x) for x in self.padding_shape]) + ")" + \
                  ";\n\tact_fun = " + fun_name + ";\n\tweight init = " \
                  + self.weight_initializer.__name__ + "; bias init = " + self.bias_initializer.__name__ + "\n"
        return out_str

    def _get_expected_input_shape_description(self) -> str:
        expected_shape = "(images, "
        expected_shape += "x".join([str(x) for x in self.input_size[:-1]])
        expected_shape += ", channels=" + str(self.input_size[-1]) + ")\n"
        return expected_shape

    def get_output_shape_description(self) -> str:
        expected_out_shape = "(None, "
        expected_out_shape += "x".join([str(x) for x in self.output_size[:-1]])
        expected_out_shape += ", " + str(self.output_size[-1]) + ")"
        return expected_out_shape

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return Convolutional(filters=self.filters, kernel_shape=self.kernel_shape, input_shape=self.input_size,
                             padding=self.padding_shape, stride=self.stride_shape, input_dtype=self.input_dtype)

    def get_real_equivalent(self):
        return Convolutional(filters=self.filters, kernel_shape=self.kernel_shape, input_shape=self.input_size,
                             padding=self.padding_shape, stride=self.stride_shape, input_dtype=np.float32)

    def trainable_variables(self):
        return self.kernels + [self.bias]


class FrequencyConvolutional2D(ComplexLayer):
    def __init__(self, filters: int, kernel_shape: t_kernel_shape,
                 input_shape: Optional[t_input_shape] = None,
                 padding: t_padding_shape = "same",  # TODO: This should only be to crop the output
                 # stride: t_kernel_shape = 1,          # TODO: The method is stride = 1. It may be possible to simulate a stride?
                 activation=None,  # TODO: Check type
                 weight_initializer: Optional[RandomInitializer] = None,
                 bias_initializer: Optional[RandomInitializer] = None,
                 data_format: str = "channels_last", dropout: Optional[float] = None
                 # dilatation_rate=(1, 1)   # TODO: Interesting to add
                 ):
        self.filters = filters
        self.dropout = dropout
        if activation is None:
            activation = 'linear'
        self.activation = activation
        if weight_initializer is None:
            weight_initializer = initializers.GlorotUniform()
        self.weight_initializer = weight_initializer
        if bias_initializer is None:
            bias_initializer = initializers.Zeros()
        self.bias_initializer = bias_initializer
        if padding.lower() != "same":
            logger.warning("Only same padding mode supported, changing it.")
        self.padding = "same"  # Input data ignored
        if input_shape is None:
            self.input_size = None
        elif isinstance(input_shape, (tuple, list)):
            self.input_size = tuple(input_shape)
        else:
            logger.error(f"Input shape: {input_shape} format not supported. It must be a tuple or None.")
            sys.exit(-1)
        # TODO: Assert input_size is for 2D input
        self.data_format = data_format.lower()
        if self.data_format not in DATA_FORMAT:
            logger.error(f"data_format = {self.data_format} unknown")
            sys.exit(-1)
        super(FrequencyConvolutional2D, self).__init__(output_size=self._calculate_output_shape,
                                                       input_size=input_shape,
                                                       input_dtype=np.complex64)  # dtype is always complex!
        # self._verify_input_size()
        self._init_kernel(data_format=data_format, kernel_shape=kernel_shape)

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return FrequencyConvolutional2D(filters=self.filters, kernel_shape=self.kernel_shape,
                                        input_shape=self.input_size, padding=self.padding,
                                        activation=self.activation,
                                        weight_initializer=self.weight_initializer,
                                        bias_initializer=self.bias_initializer,
                                        data_format=self.data_format
                                        )

    def get_real_equivalent(self):
        return self.__deepcopy__()

    def get_description(self):
        fun_name = get_func_name(self.activation)
        out_str = "requencyConvolutional2D layer:\n\t" \
                  f"input size = {self.input_size}({self.input_dtype})" \
                  f" -> output size = {self.output_size}" \
                  f";\n\tact_fun = {fun_name};\n\tweight init = \n"
        return out_str

    def _init_kernel(self, data_format, kernel_shape):
        self._verify_kernel_shape(kernel_shape)
        kernels_tmp = []
        if data_format == 'channels_last':
            pad = [[0, s - k] for k, s in zip(self.kernel_shape, self.input_size[:-1])]
            pad.append([0, 0])
            this_shape = self.kernel_shape + (self.input_size[-1],)
        elif data_format == 'channels_first':
            pad = [[0, s - k] for k, s in zip(self.kernel_shape, self.input_size[1:])]
            pad.insert(0, [0, 0])
            this_shape = (self.input_size[1:],) + self.kernel_shape
        else:
            logger.error(f"data_format not supported, should be either 'channels_last' (default) "
                         f"or 'channels_first'. Got {data_format}")
            sys.exit(-1)
        for f in range(self.filters):  # Kernels should be features*channels.
            time_kernel = self.weight_initializer(shape=this_shape, dtype=self.input_dtype)
            time_kernel_padded = tf.pad(time_kernel, pad)
            if self.data_format == "channels_last":
                time_kernel_padded = tf.transpose(time_kernel_padded, perm=[2, 0, 1])  # Move channels to the beginning
            freq_kernel = tf.signal.fft2d(tf.cast(time_kernel_padded, tf.complex64))
            if self.data_format == "channels_last":
                freq_kernel = tf.transpose(freq_kernel, perm=[1, 2, 0])  # Return channels to the end
            kernels_tmp.append(freq_kernel)
        self.kernels = tf.convert_to_tensor(
            tf.transpose(kernels_tmp, perm=[1, 2, 3, 0]),  # Take filter to last
            name="Kernels")
        self.bias = tf.Variable(self.bias_initializer(shape=self.filters, dtype=self.input_dtype),
                                name=f"bias {self.layer_number}")

    def _verify_input_size(self) -> None:
        if len(self.input_size) == 2:
            if self.data_format == "channels_last":
                self.input_size = self.input_size + (1,)
            elif self.data_format == "channels_first":
                self.input_size = (1,) + self.input_size
            else:
                logger.error(f"data_format = {self.data_format} unknown", exc_info=True)
                sys.exit(-1)
        elif len(self.input_size) != 3:
            logger.error(f"Input shape must be of size 3. Gotten {len(self.input_size)}", exc_info=True)
            sys.exit(-1)
        return None

    def _verify_kernel_shape(self, kernel_shape: t_kernel_shape):
        """
        Verifies Kernel shape and creates self.kernel_shape variable
        """
        if isinstance(kernel_shape, int):
            self.kernel_shape = (kernel_shape,) * (len(self.input_size) - 1)  # -1 because the last is the channel
        elif isinstance(kernel_shape, (tuple, list)):
            self.kernel_shape = tuple(kernel_shape)
        else:
            logger.error(f"Kernel shape: {kernel_shape} format not supported. It must be an int or a tuple")
            sys.exit(-1)
        if not np.all(np.asarray(self.kernel_shape) > 1):
            logger.error(f"Kernel shape must have all values bigger than 1: {self.kernel_shape}.")
            sys.exit(-1)
        assert len(self.kernel_shape) == 2, f"Kernel size must be 2 but it was {len(self.kernel_shape)}."

    def _calculate_output_shape(self) -> None:
        """
        returns the output shape of the layer
        """
        if self.data_format == "channels_last":
            self.output_size = self.input_size[:-1] + (self.filters,)
        elif self.data_format == "channels_first":
            self.output_size = (self.filters,) + self.input_size[:-1]
        else:
            logger.error(f"data_format = {self.data_format} unknown")
            sys.exit(-1)

    def trainable_variables(self):
        return [self.kernels, self.bias]

    def _save_tensorboard_weight(self, summary, step):
        with summary.as_default():
            tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_kernel_real",
                                 data=tf.math.real(self.kernels), step=step)
            tf.summary.histogram(name="ComplexConv2D_" + str(self.layer_number) + "_kernel_imag",
                                 data=tf.math.imag(self.kernels), step=step)
            tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_bias_real",
                                 data=tf.math.real(self.bias), step=step)
            tf.summary.histogram(name="ComplexDense_" + str(self.layer_number) + "_bias_imag",
                                 data=tf.math.imag(self.bias), step=step)

    def call(self, inputs):
        inputs = tf.reshape(inputs, shape=inputs.shape + (1,))  # Add a last axis of "filters"
        broadcast = tf.multiply(inputs, self.kernels)  # Broadcasting should work good for all images.
        reduced = tf.reduce_sum(broadcast, axis=-2 if self.data_format == "channels_last" else 1)
        y_out = apply_activation(self.activation, reduced)
        if self.dropout:
            drop_filter = tf.nn.dropout(tf.ones(y_out.shape), rate=self.dropout)
            y_out_real = tf.multiply(drop_filter, tf.math.real(y_out))
            y_out_imag = tf.multiply(drop_filter, tf.math.imag(y_out))
            y_out = tf.cast(tf.complex(y_out_real, y_out_imag), dtype=y_out.dtype)
        return y_out


t_layers_shape = Union[ndarray, List[ComplexLayer], Set[ComplexLayer]]

__author__ = 'J. Agustin BARRACHINA'
__copyright__ = 'Copyright 2020, {project_name}'
__credits__ = ['{credit_list}']
__license__ = '{license}'
__version__ = '0.0.28'
__maintainer__ = 'J. Agustin BARRACHINA'
__email__ = 'joseagustin.barra@gmail.com; jose-agustin.barrachina@centralesupelec.fr'
__status__ = '{dev_status}'
