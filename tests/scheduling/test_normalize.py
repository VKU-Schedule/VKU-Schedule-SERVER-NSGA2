"""Chuẩn hoá giá trị (design.md mục 6.7, 7.1–7.3)."""
import math

import pytest

from app.scheduling import normalize as n
from app.scheduling.normalize import NormalizeError

ALL = (0, 24 * 60 - 1)


def ok(result):
    """Kết quả không kèm warning."""
    value, warnings = result
    assert warnings == []
    return value


# --- Gập chuỗi ------------------------------------------------------------------

@pytest.mark.parametrize("text, folded", [
    ("Thứ Hai", "thuhai"),
    ("  thứ   7 ", "thu7"),
    ("Chủ nhật", "chunhat"),
    ("Đình", "dinh"),
])
def test_fold(text, folded):
    assert n.fold(text) == folded


def test_fold_words_keeps_single_spaces():
    assert n.fold_words("  Cấu trúc   dữ liệu ") == "cau truc du lieu"


# --- Thứ -----------------------------------------------------------------------

@pytest.mark.parametrize("raw, codes", [
    ("thứ 2", {"T2"}), ("Thứ Hai", {"T2"}), ("thu2", {"T2"}), ("T2", {"T2"}), ("t2", {"T2"}),
    ("thứ 3", {"T3"}), ("thứ ba", {"T3"}),
    ("thứ 4", {"T4"}), ("thứ tư", {"T4"}),
    ("thứ 5", {"T5"}), ("thứ năm", {"T5"}),
    ("thứ 6", {"T6"}), ("thứ sáu", {"T6"}),
    ("thứ 7", {"T7"}), ("thứ bảy", {"T7"}),
    ("chủ nhật", {"CN"}), ("CN", {"CN"}),
    ("cuối tuần", {"T7", "CN"}),
    ("ngày thường", {"T2", "T3", "T4", "T5", "T6"}),
    ("các ngày trong tuần", {"T2", "T3", "T4", "T5", "T6"}),
    (["thứ 2", "thứ 4"], {"T2", "T4"}),
])
def test_day(raw, codes):
    assert ok(n.normalize_day(raw)) == codes


def test_day_list_keeps_usable_values_with_warning():
    codes, warnings = n.normalize_day(["thứ 2", "thứ 9"])
    assert codes == {"T2"}
    assert warnings == ["Bỏ một giá trị của 'day': Thứ không xác định: 'thứ 9'"]


def test_day_unknown():
    with pytest.raises(NormalizeError, match="Thứ không xác định"):
        n.normalize_day("hôm nay")


# --- Buổi ----------------------------------------------------------------------

@pytest.mark.parametrize("raw, periods", [
    ("sáng", {1, 2, 3, 4, 5}),
    ("buổi sáng", {1, 2, 3, 4, 5}),
    ("chiều", {6, 7, 8, 9, 10}),
    ("Buổi chiều", {6, 7, 8, 9, 10}),
    ("sáng sớm", {1, 2}),
    ("chiều muộn", {8, 9, 10}),
    (["sáng sớm", "chiều muộn"], {1, 2, 8, 9, 10}),
])
def test_session(raw, periods):
    assert ok(n.normalize_session(raw)) == periods


@pytest.mark.parametrize("raw", ["trưa", "tối"])
def test_session_unknown(raw):
    with pytest.raises(NormalizeError, match="Buổi không xác định"):
        n.normalize_session(raw)


# --- Tiết ----------------------------------------------------------------------

@pytest.mark.parametrize("raw, periods", [
    ([1, 2], {1, 2}),
    (3, {3}),
    ({"min": 1, "max": 2}, {1, 2}),
    ({"min": 8}, {8, 9, 10}),
    ({"max": 2}, {1, 2}),
    ("1-3", {1, 2, 3}),
    ("tiết 6 đến tiết 8", {6, 7, 8}),
    (["1-2", 5], {1, 2, 5}),
])
def test_periods(raw, periods):
    assert ok(n.normalize_periods(raw)) == periods


@pytest.mark.parametrize("raw, reason", [
    (11, "Tiết phải từ 1 đến 10"),
    ("3-1", "tiết đầu lớn hơn tiết cuối"),
    ("abc", "Tiết không đọc được"),
])
def test_periods_invalid(raw, reason):
    with pytest.raises(NormalizeError, match=reason):
        n.normalize_periods(raw)


# --- Khoảng: tiết bắt đầu/kết thúc, thời lượng ---------------------------------

@pytest.mark.parametrize("name, raw, intervals", [
    ("start_period", {"min": 3}, ((3, 10),)),
    ("start_period", 3, ((3, 3),)),
    ("start_period", [3, 4, 8], ((3, 4), (8, 8))),
    ("end_period", {"max": 4}, ((1, 4),)),
    ("duration", {"min": 4}, ((4, 10),)),
    ("duration", {"max": 2}, ((1, 2),)),
])
def test_int_range(name, raw, intervals):
    assert ok(n.normalize_range(name, raw)) == intervals


def test_int_range_out_of_domain():
    with pytest.raises(NormalizeError, match="phải từ 1 đến 10"):
        n.normalize_range("start_period", {"min": 12})


# --- Giờ -----------------------------------------------------------------------

@pytest.mark.parametrize("raw, minutes", [
    ("10:00", 600), ("10h", 600), ("10h30", 630), ("10 giờ", 600), ("10 giờ 30", 630),
    (10, 600), ("9:00", 540), ("16:00", 960),
    ("3 giờ chiều", 900), ("4h chiều", 960), ("7 giờ tối", 1140), ("10 giờ sáng", 600),
    ("13:00 chiều", 780),
])
def test_parse_time(raw, minutes):
    assert n.parse_time(raw) == minutes


@pytest.mark.parametrize("raw", ["abc", "25:00", "10:75", 3.5])
def test_parse_time_invalid(raw):
    with pytest.raises(NormalizeError):
        n.parse_time(raw)


@pytest.mark.parametrize("name, raw, intervals", [
    ("start_time", {"min": "10:00"}, ((600, ALL[1]),)),
    ("end_time", {"max": "16:00"}, ((0, 960),)),
    ("start_time", {"min": "9h", "max": "15h"}, ((540, 900),)),
])
def test_time_range(name, raw, intervals):
    assert ok(n.normalize_range(name, raw)) == intervals


def test_time_range_min_greater_than_max():
    with pytest.raises(NormalizeError, match="min lớn hơn max"):
        n.normalize_range("start_time", {"min": "15:00", "max": "9:00"})


# --- Khu, phòng ----------------------------------------------------------------

@pytest.mark.parametrize("raw, areas", [
    ("K", {"K"}), ("k", {"K"}), ("khu K", {"K"}), ("Khu V", {"V"}), ("V", {"V"}), (["K", "V"], {"K", "V"}),
])
def test_area(raw, areas):
    assert ok(n.normalize_area(raw)) == areas


def test_area_unknown():
    with pytest.raises(NormalizeError, match="Khu không xác định"):
        n.normalize_area("khu Z")


@pytest.mark.parametrize("raw, rooms, areas", [
    ("A212", {"A212"}, None),
    ("a212", {"A212"}, None),
    ("V.A201", {"A201"}, {"V"}),
    (["A101", "A102"], {"A101", "A102"}, None),
    (["V.A201", "V.A202"], {"A201", "A202"}, {"V"}),
    ("T3-TTSV.1", {"T3-TTSV.1"}, None),  # dấu chấm không phải tiền tố khu
])
def test_room(raw, rooms, areas):
    got_rooms, got_areas, warnings = n.normalize_room(raw)
    assert (got_rooms, got_areas, warnings) == (rooms, areas, [])


def test_room_mixed_prefix_drops_area_with_warning():
    rooms, areas, warnings = n.normalize_room(["V.A201", "A102"])
    assert rooms == {"A201", "A102"} and areas is None and len(warnings) == 1


# --- Ngôn ngữ, nhóm lớp ---------------------------------------------------------

@pytest.mark.parametrize("raw, language", [
    ("tiếng Anh", "Tiếng Anh"), ("English", "Tiếng Anh"), ("TA", "Tiếng Anh"),
    ("tiếng Việt", "Tiếng Việt"), ("TV", "Tiếng Việt"),
])
def test_language(raw, language):
    assert ok(n.normalize_language(raw)) == {language}


def test_language_unknown():
    with pytest.raises(NormalizeError, match="Ngôn ngữ không xác định"):
        n.normalize_language("tiếng Pháp")


@pytest.mark.parametrize("raw, groups", [
    (2, {2}), ("2", {2}), ("nhóm 2", {2}), ("lớp 13", {13}), ([13, 14], {13, 14}),
])
def test_class_group(raw, groups):
    assert ok(n.normalize_class_group(raw)) == groups


@pytest.mark.parametrize("raw", ["nhóm", 0])
def test_class_group_invalid(raw):
    with pytest.raises(NormalizeError, match="Nhóm lớp không đọc được"):
        n.normalize_class_group(raw)


def test_value_normalizers_cover_every_attribute_except_entities():
    from app.scheduling import vocab
    assert set(n.VALUE_NORMALIZERS) | {"course", "teacher", "room"} == set(vocab.ATTRIBUTES)


# --- Dữ liệu lớp ----------------------------------------------------------------

@pytest.mark.parametrize("day, code", [
    ("Thứ Hai", "T2"), ("Thứ Ba", "T3"), ("Thứ Tư", "T4"), ("Thứ Năm", "T5"), ("Thứ Sáu", "T6"), ("Thứ Bảy", "T7"),
    ("Thứ _", None), ("", None), (None, None), (math.nan, None),
])
def test_class_day_code(day, code):
    assert n.class_day_code(day) == code


def test_class_has_schedule():
    assert n.class_has_schedule("Thứ Hai", [1, 2])
    assert not n.class_has_schedule("Thứ _", [])
    assert not n.class_has_schedule("Thứ Hai", [])


@pytest.mark.parametrize("area, code", [
    ("K", "K"), ("V", "V"), ("Khác", None), ("(Chọn)", None), ("Chưa xếp phòng", None), ("-", None), ("", None),
])
def test_class_area(area, code):
    assert n.class_area(area) == code


@pytest.mark.parametrize("room, code", [("A212", "A212"), ("_", None), ("", None), ("V.A201", "A201")])
def test_class_room(room, code):
    assert n.class_room(room) == code


@pytest.mark.parametrize("teacher, known", [
    ("ThS.Trần Đình Sơn", True), ("Khoa.KH MT", False), (".", False), ("", False), (None, False),
])
def test_class_teacher_known(teacher, known):
    assert n.class_teacher_known(teacher) is known


@pytest.mark.parametrize("value, group", [("2", 2), (2, 2), (2.0, 2), ("2.0", 2), ("", None), (math.nan, None), (None, None)])
def test_class_group_number(value, group):
    assert n.class_group_number(value) == group


def test_class_time_range():
    assert n.class_time_range([8, 9]) == (15 * 60, 16 * 60 + 50)
    assert n.class_time_range([]) is None
