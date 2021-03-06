import cv2
import numpy as np

import config


class FrameEditor:

    # Internal configuration

    DIRECTION_WIDTH = 10
    DIRECTION_HEIGHT = 50
    DIRECTION_MARGIN = 10
    DIRECTION_PADDING = 10
    DIRECTION_ICONS = [
        '../res/left_arrow.png',
        '../res/up_arrow.png',
        '../res/right_arrow.png'
    ]

    SENSOR_MARGIN = 10
    SENSOR_PADDING = 20
    SENSOR_SIZE = 10

    def __init__(self, height: int, width: int, channel: int,
                 ob_height: int, ob_width: int):
        """
        Create a display engine.
        :param height: the height of the frame
        :param width: the width of the frame
        :param channel: the channel of the frame
        :param ob_height: the height of the watch region
        :param ob_width: the width of the watch region
        """
        self.frame = np.zeros([height, width, channel])
        self.direction = [0,0,0]
        self.height = height
        self.width = width
        self.channel = channel
        self.image = None
        self.left_sensor: bool = False
        self.right_sensor: bool = False
        # Watch region
        self.watch_height = ob_height
        self.watch_width = ob_width
        self.watch_left = 0
        self.watch_right = self.width
        self.watch_top = self.height - int(self.width / self.watch_width * self.watch_height)
        self.watch_bottom = self.height
        self.mask = None

        self.mask_color = np.zeros([self.height, self.width, 3])
        self.mask_color[:, :, 1] = 255
        self.mask_full = np.zeros([self.height, self.width, 1])

    def set_frame(self, frame: np.ndarray):
        """
        Set current video frame
        :param image: current video frame
        """
        # Reset frame
        self.image = frame.copy()
        self.frame = frame.copy()
        # Clear mask
        self.mask = None

    def set_salient(self, mask: np.ndarray):
        """
        Feed the salient map of current sampled region back
        :param mask: current salient map
        """
        self.mask = cv2.resize(mask, (self.watch_width, self.watch_height))

    def set_direction(self, direction: list):
        """
        Feed probabilities of three directions back.
        :param direction: probabilities
        """
        # assert len(direction) == 3
        self.direction = np.asarray([direction[0], direction[2], direction[1]])

    def render(self, draw_salient: bool=True, draw_prob: bool=True, draw_border: bool=True):
        """
        Render a frame for display.
        :param draw_salient: whether draw the salient map
        :param draw_prob: whether draw direction probabilities
        :param draw_border: whether draw the watch region
        :return: the rendered image
        """
        output_img = self.frame.copy()
        # Draw directions
        if draw_prob:
            bar_overlay = output_img.copy()
            icon_top = self.DIRECTION_PADDING
            icon_bottom = self.DIRECTION_PADDING + self.DIRECTION_WIDTH
            bar_bottom = icon_bottom+self.DIRECTION_PADDING + self.DIRECTION_HEIGHT
            for i in range(len(self.direction)):
                # Draw background rectangle
                bar_left = self.DIRECTION_PADDING + (self.DIRECTION_WIDTH + self.DIRECTION_MARGIN) * i
                bar_right = bar_left+self.DIRECTION_WIDTH
                bar_top = icon_bottom + self.DIRECTION_PADDING
                bar_overlay = cv2.rectangle(bar_overlay, (bar_left,bar_top), (bar_right,bar_bottom), (255,255,255), -1)
            output_img = cv2.addWeighted(output_img, 0.5, bar_overlay, 0.5, 0)
            for i in range(len(self.direction)):
                # Draw foreground rectangle
                bar_left = self.DIRECTION_PADDING + (self.DIRECTION_WIDTH + self.DIRECTION_MARGIN) * i
                bar_right = bar_left+self.DIRECTION_WIDTH
                bar_top = bar_bottom-int(self.DIRECTION_HEIGHT * self.direction[i])
                output_img = cv2.rectangle(output_img, (bar_left, bar_top), (bar_right, bar_bottom), (255, 255, 255), -1)
                # Draw icon
                icon = cv2.imread(self.DIRECTION_ICONS[i])
                output_img = self.draw_image(output_img, icon, bar_left, icon_top, bar_right, icon_bottom)
        # Draw watch area
        if draw_border:
            output_img = cv2.rectangle(output_img, (self.watch_left, self.watch_top), (self.watch_right - 1, self.watch_bottom - 1), (255, 255, 255))
        # Draw salient map
        if draw_salient and self.mask is not None:
            min_weight = np.min(self.mask)
            max_weight = np.max(self.mask)
            if np.abs(max_weight-min_weight) > 0:
                mask_normed = (self.mask-min_weight)/(max_weight-min_weight)
                mask_scaled = cv2.resize(mask_normed, (self.watch_right - self.watch_left, self.watch_bottom - self.watch_top))

                self.mask_full[self.watch_top:self.watch_bottom, self.watch_left:self.watch_right, 0] = mask_scaled
                output_img = output_img * (1 - self.mask_full) + self.mask_color * self.mask_full
        return output_img.astype(np.uint8)

    def get_observation(self) -> np.ndarray:
        """
        Sample for neural network.
        :return: the sampled image
        """
        height, width, _ = self.image.shape
        watch_left = 0
        watch_right = width
        watch_top = height - int(width / self.watch_width * self.watch_height)
        watch_bottom = height
        clip = self.image[watch_top:watch_bottom, watch_left:watch_right, :]
        return cv2.resize(clip, (self.watch_width, self.watch_height))

    @staticmethod
    def draw_image(src: np.ndarray, img: np.ndarray,
                   left: int, top: int, right: int, bottom: int, threshold: int=10) -> np.ndarray:
        """
        Draw a image into another image, the dark area will be reduced.
        :param src: the image draw object to
        :param img: the image draw object from
        :param left: the left position of draw area
        :param top: the top position of draw area
        :param right: the right position of draw area
        :param bottom: the bottom position of draw area
        :param threshold: the threshold for reducing
        :return: the new image
        """
        # Resize image
        resize_width = right - left
        resize_height = bottom - top
        img = cv2.resize(img, (resize_width, resize_height))
        # Put img to src
        rows, cols, _ = img.shape
        roi = src[top:bottom, left:right]
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, mask = cv2.threshold(img_gray, threshold, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        src_bg = cv2.bitwise_and(roi, roi, mask=mask_inv)
        img_fg = cv2.bitwise_and(img, img, mask=mask)
        dst = cv2.add(src_bg, img_fg)
        src[top:bottom, left:right] = dst
        return src
