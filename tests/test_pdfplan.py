"""PDF plan digitiser (planarena/sources/pdfplan.py) on synthetic maps with a known georeference."""
import numpy as np
import shapely
import shapely.affinity

from planarena.sources import crosswalk, pdfplan


def _lots(n=24, size=100.0, gap=20.0):
    """An n x n grid of square lots (map feet) with streets between them; an L-shaped district so the footprint
    has a unique orientation."""
    lots = [shapely.box(i * (size + gap), j * (size + gap), i * (size + gap) + size, j * (size + gap) + size)
            for i in range(n) for j in range(n) if not (i > n // 2 and j > n // 2)]
    return lots


def _to_page(geoms, s, deg, t):
    """Map feet -> page points (y down) for map = s R(deg) (x, -y) + t."""
    out = []
    for g in geoms:
        g = shapely.affinity.translate(g, -t[0], -t[1])
        g = shapely.affinity.rotate(g, -deg, origin=(0, 0))
        g = shapely.affinity.scale(g, 1 / s, -1 / s, origin=(0, 0))
        out.append(g)
    return np.array(out, dtype=object)


def test_umeyama_recovers_a_similarity():
    rng = np.random.default_rng(0)
    src = rng.uniform(0, 100, (50, 2))
    th = np.radians(12)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    dst = 3.5 * (R @ src.T).T + [10, -4]
    s, R2, t = pdfplan._umeyama(src, dst)
    assert abs(s - 3.5) < 1e-9 and np.allclose(R2, R) and np.allclose(t, [10, -4])


def test_registration_and_classification_on_a_synthetic_map():
    lots = _lots()
    s, deg, t = 20.0, -7.0, np.array([5000.0, 9000.0])
    page = _to_page(lots, s, deg, t)
    labels = np.array(["Residential Low Density" if i % 3 else "Industrial" for i in range(len(lots))])
    pts = shapely.point_on_surface(lots)
    xy = np.c_[shapely.get_x(pts), shapely.get_y(pts)]
    district = shapely.union_all(lots).envelope
    tf = pdfplan.georeference(page, district, xy, parcels=lots)
    assert abs(tf["s"] - s) / s < 0.01
    assert abs(tf["rotation_deg"] - deg) < 0.5
    assert tf["median_match_ft"] < 5
    got = pdfplan.classify(page, labels, tf, xy)
    assert (got == labels).mean() > 0.99


def test_colour_matching_is_perceptual_and_refuses_far_matches():
    legend = [(0.99, 1.0, 0.76), (0.35, 0.21, 1.0), (0.2, 0.43, 1.0), (0.46, 1.0, 0.75)]  # CMYK converted naively
    labs = ["Residential Low Density", "Industrial", "Civic/Institution", "Culture/Amusement"]
    on_map = {(1.0, 1.0, 0.8): 500, (0.549, 0.0, 1.0): 40, (0.0, 0.439, 1.0): 60, (0.8, 0.8, 0.8): 900}
    table = pdfplan.match_colours(legend, labs, on_map)
    assert table[(1.0, 1.0, 0.8)] == "Residential Low Density"
    assert table[(0.549, 0.0, 1.0)] == "Industrial"
    assert table[(0.0, 0.439, 1.0)] == "Civic/Institution"
    assert (0.8, 0.8, 0.8) not in table  # grey streets are not "Culture/Amusement"


def test_visibility_drops_shapes_the_page_does_not_show():
    a, b = shapely.box(10, 10, 20, 20), shapely.box(40, 10, 50, 20)
    img = np.ones((int(72 * 300 / 72), int(72 * 300 / 72), 3), dtype=np.float32)
    k = 300 / 72
    img[int(10 * k):int(20 * k), int(10 * k):int(20 * k)] = (1.0, 0.0, 0.0)  # only the first shape is drawn
    seen, _ = pdfplan.visible(np.array([a, b], dtype=object), np.array([[1.0, 0, 0], [1.0, 0, 0]]), [img], [72.0])
    assert seen.tolist() == [True, False]


def test_philadelphia_plan_categories_all_map():
    for label in crosswalk.PHILADELPHIA_PLAN:
        assert crosswalk.philadelphia_plan(label) != "unknown"
    assert crosswalk.philadelphia_plan("Commercial Business/Professional") == "off"  # legend spacing varies
    assert crosswalk.philadelphia_plan("Park/Open Space") == "opn"
    assert crosswalk.philadelphia_plan("Something else") == "unknown"
