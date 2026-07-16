import cv2
import numpy as np

TARGET_WIDTH = 1320
PIXEL_SET = 255
MIN_CONTOUR_AREA = 50
CROP_MARGIN = 5


def line_array(x):
	upper, lower = [], []
	for y in range(5, len(x) - 5):
		s_a, s_p = strtline(y, x)
		e_a, e_p = endline(y, x)
		if s_a >= 7 and s_p >= 5:
			upper.append(y)
		if e_a >= 5 and e_p >= 7:
			lower.append(y)
	return upper, lower


def strtline(y, array):
	prev, ahead = 0, 0
	for i in array[y:y + 10]:
		if i > 3:
			ahead += 1
	for i in array[y - 10:y]:
		if i == 0:
			prev += 1
	return ahead, prev


def endline(y, array):
	ahead = 0
	prev = 0
	for i in array[y:y + 10]:
		if i == 0:
			ahead += 1
	for i in array[y - 10:y]:
		if i > 3:
			prev += 1
	return ahead, prev


def refine_array(array_upper, array_lower):
	upper, lower = [], []
	for y in range(len(array_upper) - 1):
		if array_upper[y] + 5 < array_upper[y + 1]:
			upper.append(array_upper[y] - 10)
	for y in range(len(array_lower) - 1):
		if array_lower[y] + 5 < array_lower[y + 1]:
			lower.append(array_lower[y] + 10)
	if array_upper:
		upper.append(array_upper[-1] - 10)
	if array_lower:
		lower.append(array_lower[-1] + 10)
	return upper, lower


def get_letter_rect(k, contours):
	"""Merge vertically stacked contours (e.g. the two bars of '=') into one box."""
	valid = True
	x, y, w, h = cv2.boundingRect(contours[k])
	for i in range(len(contours)):
		cnt = contours[i]
		if i == k:
			continue
		elif cv2.contourArea(cnt) < MIN_CONTOUR_AREA:
			continue

		x1, y1, w1, h1 = cv2.boundingRect(cnt)

		if abs(x1 + w1 / 2 - (x + w / 2)) < 50:
			if y1 > y:
				h = abs(y - (y1 + h1))
				w = abs(x - (x1 + w1))
			else:
				valid = False
			break

	return (valid, x, y, w, h)


def _line_letters(line_img):
	"""Extract character crops from one binary line image, left to right."""
	contours, _ = cv2.findContours(line_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	rects = []
	for k in range(len(contours)):
		if cv2.contourArea(contours[k]) < MIN_CONTOUR_AREA:
			continue
		valid, x, y, w, h = get_letter_rect(k, contours)
		if valid:
			rects.append((x, y, w, h))

	letters = []
	for x, y, w, h in sorted(rects):
		y0 = max(y - CROP_MARGIN, 0)
		x0 = max(x - CROP_MARGIN, 0)
		crop = line_img[y0:y + h + CROP_MARGIN, x0:x + w + CROP_MARGIN]
		if crop.size:
			# invert to black character on white background
			letters.append(PIXEL_SET - crop)
	return letters


def segment_characters(gray_img):
	"""Segment a grayscale equation image into per-character crops.

	Takes a 2D numpy array and returns a list of numpy arrays (black
	character on white background), ordered left to right, top line first.
	Raises ValueError if no clean text lines can be detected.
	"""
	orig_height, orig_width = gray_img.shape
	width = TARGET_WIDTH
	height = int(width * orig_height / orig_width)
	src_img = cv2.resize(gray_img, dsize=(width, height), interpolation=cv2.INTER_AREA)

	kernel_size = 21
	normalized_mean = 20
	bin_img = cv2.adaptiveThreshold(src_img, PIXEL_SET, cv2.ADAPTIVE_THRESH_MEAN_C,
									cv2.THRESH_BINARY_INV, kernel_size, normalized_mean)

	# horizontal pixel-density histogram for line detection
	count_x = (bin_img == PIXEL_SET).sum(axis=1)

	upper_lines, lower_lines = line_array(count_x)
	upperlines, lowerlines = refine_array(upper_lines, lower_lines)

	if len(upperlines) != len(lowerlines):
		raise ValueError("could not detect equation lines, the image is too noisy")

	crops = []
	for top, bottom in zip(upperlines, lowerlines):
		crops.extend(_line_letters(bin_img[top:bottom, :]))
	return crops
