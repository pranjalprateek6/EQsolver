import cv2
import numpy as np

TARGET_WIDTH = 1320
PIXEL_SET = 255
MIN_CONTOUR_AREA = 50
# specks this small are kept only long enough to see if they are the dots
# of a division sign
MIN_DOT_AREA = 8
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


def _x_overlap(a, b):
	return min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])


def _contains(outer, inner, slack=2):
	return (outer['x'] - slack <= inner['x'] and outer['y'] - slack <= inner['y']
			and inner['x'] + inner['w'] <= outer['x'] + outer['w'] + slack
			and inner['y'] + inner['h'] <= outer['y'] + outer['h'] + slack)


def _union(a, b, shape=None):
	x, y = min(a['x'], b['x']), min(a['y'], b['y'])
	return {'x': x, 'y': y,
			'w': max(a['x'] + a['w'], b['x'] + b['w']) - x,
			'h': max(a['y'] + a['h'], b['y'] + b['h']) - y,
			'area': a['area'] + b['area'], 'shape': shape}


def _bar_between(a, b, bars):
	"""True if a horizontal bar separates a and b vertically (a fraction's
	numerator and denominator, which must stay apart)."""
	top, bottom = sorted((a, b), key=lambda r: r['y'])
	for bar in bars:
		if (top['y'] + top['h'] / 2 < bar['y'] + bar['h'] / 2 < bottom['y'] + bottom['h'] / 2
				and _x_overlap(bar, top) > 0 and _x_overlap(bar, bottom) > 0):
			return True
	return False


def _merge_division_signs(rects):
	"""A short bar with a small dot directly above and below it is a '÷'."""
	for bar in [r for r in rects if r['shape'] == 'bar']:
		def dot(r, above):
			if r is bar or r['shape'] is not None or max(r['w'], r['h']) > 0.4 * bar['w']:
				return False
			cx = r['x'] + r['w'] / 2
			if not bar['x'] <= cx <= bar['x'] + bar['w']:
				return False
			gap = bar['y'] - (r['y'] + r['h']) if above else r['y'] - (bar['y'] + bar['h'])
			return 0 <= gap <= bar['w']
		above = [r for r in rects if dot(r, True)]
		below = [r for r in rects if dot(r, False)]
		if above and below:
			merged = _union(_union(bar, above[0]), below[0])
			rects = [r for r in rects if r not in (bar, above[0], below[0])] + [merged]
	return rects


def _merge_strokes(rects):
	"""Join pieces that are strokes of one glyph. Handwriting often leaves
	gaps (a 'y' written as two strokes, a 'z' with a separate crossbar, an
	'x' as two arcs), and each gap would otherwise become a bogus glyph.

	Two pieces are joined when they share most of a column and no bar lies
	between them, or when a bar sits wholly inside another glyph's box. A
	large piece inside another's box is a radicand under a '√' and is left
	alone, as are fraction parts (a bar lies between them)."""
	changed = True
	while changed:
		changed = False
		bars = [r for r in rects if r['shape'] == 'bar']
		for i, a in enumerate(rects):
			for b in rects[i + 1:]:
				if a['shape'] == 'equals' or b['shape'] == 'equals':
					continue
				if a['shape'] == 'bar' and b['shape'] == 'bar':
					# two stacked bars with nothing between them are an '='
					# that get_letter_rect's stricter pairing missed (one
					# stroke slanted, or the two of quite different lengths)
					top, bottom = sorted((a, b), key=lambda r: r['y'])
					gap = bottom['y'] - (top['y'] + top['h'])
					between = any(r is not a and r is not b and _x_overlap(r, a) > 0
								  and top['y'] < r['y'] + r['h'] / 2 < bottom['y'] + bottom['h']
								  for r in rects)
					if (_x_overlap(a, b) >= 0.5 * min(a['w'], b['w'])
							and gap <= 0.6 * max(a['w'], b['w']) and not between):
						rects = [r for r in rects if r is not a and r is not b] + \
							[_union(a, b, shape='equals')]
						changed = True
						break
					continue
				if a['shape'] == 'bar' or b['shape'] == 'bar':
					bar, other = (a, b) if a['shape'] == 'bar' else (b, a)
					join = other['shape'] is None and _contains(other, bar)
				else:
					big, small = (a, b) if a['h'] >= b['h'] else (b, a)
					if _contains(big, small) and small['h'] >= 0.45 * big['h']:
						continue  # a radicand inside a root sign
					overlap = _x_overlap(a, b)
					join = (overlap >= 0.5 * min(a['w'], b['w'])
							and not _bar_between(a, b, bars))
				if join:
					rects = [r for r in rects if r is not a and r is not b] + [_union(a, b)]
					changed = True
					break
			if changed:
				break
	return rects


def _line_letters(line_img):
	"""Extract character crops from one binary line image, left to right."""
	contours, _ = cv2.findContours(line_img.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	rects = []
	for k in range(len(contours)):
		# tiny specks are kept for now: they may be the dots of a '÷'
		area = cv2.contourArea(contours[k])
		if area < MIN_DOT_AREA:
			continue
		valid, x, y, w, h = get_letter_rect(k, contours)
		if not valid:
			continue
		# what the stroke geometry alone says about the glyph, which the
		# context decoder trusts over the classifier: a single wide bar can
		# only be a minus or fraction bar, and two merged bars only an '='
		if (x, y, w, h) != cv2.boundingRect(contours[k]):
			shape = 'equals'
		elif _is_bar(w, h):
			shape = 'bar'
		else:
			shape = None
		rects.append({'x': x, 'y': y, 'w': w, 'h': h, 'area': area, 'shape': shape})

	rects = _merge_division_signs(rects)
	rects = _merge_strokes(rects)
	# whatever is still tiny after merging is noise
	rects = [r for r in rects if r['area'] >= MIN_CONTOUR_AREA or r['shape'] is not None]

	letters = []
	for r in sorted(rects, key=lambda r: (r['x'], r['y'])):
		x, y, w, h, shape = r['x'], r['y'], r['w'], r['h'], r['shape']
		y0 = max(y - CROP_MARGIN, 0)
		x0 = max(x - CROP_MARGIN, 0)
		crop = line_img[y0:y + h + CROP_MARGIN, x0:x + w + CROP_MARGIN]
		if crop.size:
			# invert to black character on white background, and keep the box
			# (x, y are in line-image coordinates; y is offset to the full image
			# by the caller) so the spatial parser can read the 2D layout
			letters.append({'crop': PIXEL_SET - crop, 'x': x, 'y': y, 'w': w, 'h': h,
							'shape': shape})
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
	height = max(1, int(width * orig_height / orig_width))
	src_img = cv2.resize(gray_img, dsize=(width, height), interpolation=cv2.INTER_AREA)

	kernel_size = 21
	normalized_mean = 20
	bin_img = cv2.adaptiveThreshold(src_img, PIXEL_SET, cv2.ADAPTIVE_THRESH_MEAN_C,
									cv2.THRESH_BINARY_INV, kernel_size, normalized_mean)

	# The app reads one equation at a time, and a single equation is 2D:
	# exponents sit above the baseline and fractions stack three rows. The
	# old histogram line splitter cut those rows apart, so the whole inked
	# band is treated as one line and the spatial parser reads the layout.
	rows = np.where((bin_img == PIXEL_SET).any(axis=1))[0]
	if len(rows) == 0:
		return []
	top = max(int(rows[0]) - CROP_MARGIN, 0)
	bottom = min(int(rows[-1]) + CROP_MARGIN + 1, bin_img.shape[0])

	pieces = []
	for piece in _line_letters(bin_img[top:bottom, :]):
		piece['y'] += top  # band-relative y -> full-image y
		pieces.append(piece)
	return pieces
