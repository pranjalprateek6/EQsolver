import cv2
import numpy as np

TARGET_WIDTH = 1320
PIXEL_SET = 255
MIN_CONTOUR_AREA = 50
CROP_MARGIN = 5
# a contour at least this many times wider than tall is a horizontal bar
# (a stroke of '=', a minus, or a fraction bar) rather than a glyph
BAR_ASPECT_RATIO = 2.5


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


def _is_bar(w, h):
	"""A wide, short contour: an '=' stroke, a minus, or a fraction bar."""
	return w >= BAR_ASPECT_RATIO * h


def get_letter_rect(k, contours):
	"""Resolve one contour into a character box.

	Only the two short strokes of '=' are merged into a single box. Tall glyphs
	and fraction bars are left alone, so a fraction's numerator, bar and
	denominator stay as separate boxes for the spatial parser to read. Returns
	(valid, x, y, w, h); valid is False for the lower stroke of an '=' pair,
	which the upper stroke already absorbed.
	"""
	x, y, w, h = cv2.boundingRect(contours[k])
	if not _is_bar(w, h):
		return (True, x, y, w, h)

	# k is a short bar; look for its partner stroke in an '=' sign: another
	# short bar of similar width, horizontally aligned and vertically close.
	for i in range(len(contours)):
		if i == k or cv2.contourArea(contours[i]) < MIN_CONTOUR_AREA:
			continue
		x1, y1, w1, h1 = cv2.boundingRect(contours[i])
		if not _is_bar(w1, h1):
			continue
		aligned = abs((x1 + w1 / 2) - (x + w / 2)) < 0.6 * max(w, w1)
		similar_width = 0.5 <= (w1 / w) <= 2.0
		# the two strokes together are still wider than tall (an '=' sign);
		# a fraction's numerator/denominator would make this span much taller
		span = max(y + h, y1 + h1) - min(y, y1)
		close = span < max(w, w1)
		if not (aligned and similar_width and close):
			continue
		if y1 > y:
			# this is the upper stroke; grow the box to cover both
			nx = min(x, x1)
			return (True, nx, y, max(x + w, x1 + w1) - nx, (y1 + h1) - y)
		# this is the lower stroke; the upper one absorbs it
		return (False, x, y, w, h)

	return (True, x, y, w, h)


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
			# invert to black character on white background, and keep the box
			# (x, y are in line-image coordinates; y is offset to the full image
			# by the caller) so the spatial parser can read the 2D layout
			letters.append({'crop': PIXEL_SET - crop, 'x': x, 'y': y, 'w': w, 'h': h})
	return letters


def segment_characters(gray_img):
	"""Segment a grayscale equation image into per-character pieces.

	Takes a 2D numpy array and returns a list of dicts, each with a 'crop'
	(black character on white background) and its 'x','y','w','h' bounding box
	in the resized-image coordinate space, ordered left to right, top line
	first. Raises ValueError if no clean text lines can be detected.
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

	pieces = []
	for top, bottom in zip(upperlines, lowerlines):
		for piece in _line_letters(bin_img[top:bottom, :]):
			piece['y'] += top  # line-relative y -> full-image y
			pieces.append(piece)
	return pieces
