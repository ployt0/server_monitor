from email.message import EmailMessage
from unittest.mock import Mock

import pytest

from html_tabulating import find_invariant_cols, tabulate_csv_as_html, get_row, display_constants, \
    RangeFinder, display_statistics


def test_find_invariant_cols():
    results = [
        "why,319,48,carpool,41.23,71.31,99.14,1.4Gi,48_64,31,cirencester,hartlepool".split(","),
        "rye,319,48,carpool,41.23,71.31,99.14,1.3Gi,48_65,31,cirencester,hartlepool".split(","),
        "why,319,48,oillube,41.23,71.31,99.14,1.2Gi,48_66,30,constantine,hartlepool".split(","),
        "why,319,48,carpool,41.23,71.31,99.99,1.3Gi,48_64,None,cirencester,hartlepool".split(","),
        "why,319,48,carpool,41.23,71.31,99.14,1.5Gi,48_65,31,cirencester,hartlepool".split(","),
    ]
    invariants = find_invariant_cols(results)
    assert set(invariants.keys()) == {1, 2, 4, 5, 11}
    assert set(invariants.values()) == {"319", "48", "41.23", "71.31", "hartlepool"}


def test_tabulate_csv_as_html():
    header = "orcs,trolls,goblins,hobgoblins"
    msg = EmailMessage()
    results = [
        Mock(to_csv=Mock(return_value="5,1,30,4")),
        Mock(to_csv=Mock(return_value="10,2,10,4")),
        Mock(to_csv=Mock(return_value="10,4,0,4"))
    ]
    content = ""
    content = tabulate_csv_as_html(header, results)
    assert content == """<table>
<tr>
<th>orcs</th><th>trolls</th><th>goblins</th>
</tr>
<tr>
<td>5</td><td>1</td><td>30</td>
</tr>
<tr>
<td>10</td><td>2</td><td>10</td>
</tr>
<tr>
<td>10</td><td>4</td><td>0</td>
</tr>
</table>

<h3>Constants:</h3>
<ul>
<li><em>hobgoblins<em>: 4</li>
</ul>

<h3>Statistics:</h3>
<ul>
<li><em>orcs:</em>
<ul>
<li><em>mean:</em> 8.33</li>
<li><em>stdev:</em> 2.89</li>
<li><em>min:</em> 5</li>
<li><em>max:</em> 10</li>
</ul></li>

<li><em>trolls:</em>
<ul>
<li><em>mean:</em> 2.33</li>
<li><em>stdev:</em> 1.53</li>
<li><em>min:</em> 1</li>
<li><em>max:</em> 4</li>
</ul></li>

<li><em>goblins:</em>
<ul>
<li><em>mean:</em> 13.33</li>
<li><em>stdev:</em> 15.28</li>
<li><em>min:</em> 0</li>
<li><em>max:</em> 30</li>
</ul></li>
</ul>
"""
    assert msg.get_content_type() == "text/plain"
    msg.set_content(content, subtype='html')
    assert msg.get_content_type() == "text/html"


def test_get_row():
    row = get_row(["alpha", "beta", "gamma", "delta"], 4, "td")
    assert row == """
<tr>
<td>alpha</td><td>beta</td><td>gamma</td><td>delta</td>
</tr>"""


def test_display_constants():
    header = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"]
    invariant_cols = {0: "Garage", 5: "Saloon", 8: "Amphitheatre"}
    constant_content = display_constants(header, invariant_cols)
    assert constant_content == """
<h3>Constants:</h3>
<ul>
<li><em>C1<em>: Garage</li>

<li><em>C6<em>: Saloon</li>

<li><em>C9<em>: Amphitheatre</li>
</ul>
"""


def test_is_considered_rangeable():
    assert RangeFinder.is_considered_rangeable("1.3Gi")
    assert RangeFinder.is_considered_rangeable("1.3G")
    assert RangeFinder.is_considered_rangeable("1.3")
    assert RangeFinder.is_considered_rangeable("13")
    assert RangeFinder.is_considered_rangeable(".13")
    assert RangeFinder.is_considered_rangeable("13.13")
    assert RangeFinder.is_considered_rangeable("48_64")
    assert RangeFinder.is_considered_rangeable("None")
    assert RangeFinder.is_considered_rangeable("None_None")
    assert RangeFinder.is_considered_rangeable("None_64")
    assert not RangeFinder.is_considered_rangeable("1.3Megs")
    assert not RangeFinder.is_considered_rangeable("Megs")
    assert not RangeFinder.is_considered_rangeable("13.13.13.13")
    # The next five were from an unescaped dot causing a non trailing non-digit
    # to slip through.
    assert not RangeFinder.is_considered_rangeable("80+443")
    assert not RangeFinder.is_considered_rangeable("80-443")
    assert not RangeFinder.is_considered_rangeable("a1")
    assert not RangeFinder.is_considered_rangeable("a4")
    assert not RangeFinder.is_considered_rangeable("z4")


@pytest.mark.parametrize("num, unit, number", [
    ("1", "Ki", 2 ** 10),
    ("10", "Ki", 10 * 2 ** 10),
    ("1.5", "Ki", 1.5 * 2 ** 10),
    ("1.5", "KB", 1.5 * 2 ** 10),
    ("1.5", "K", 1.5 * 2 ** 10),
    ("1", "Mi", 2 ** 20),
    ("10", "Mi", 10 * 2 ** 20),
    ("1.5", "Mi", 1.5 * 2 ** 20),
    ("1", "Gi", 2 ** 30),
    ("10", "Gi", 10 * 2 ** 30),
    ("1.5", "Gi", 1.5 * 2 ** 30),
    ("1", "Ti", 2 ** 40),
    ("10", "Ti", 10 * 2 ** 40),
    ("1.5", "Ti", 1.5 * 2 ** 40),
])
def test_get_scaled(num, unit, number):
    assert RangeFinder.get_scaled(num, unit) == number


@pytest.mark.parametrize("IEC3SF, numeric_list", [
    ("1.3Ki", [1.3 * 2 ** 10]),
    ("1.3Mi", [1.3 * 2 ** 20]),
    ("1.3Gi", [1.3 * 2 ** 30]),
    ("1.3Ti", [1.3 * 2 ** 40]),
    ("1.3K", [1.3 * 2 ** 10]),
    ("1.3M", [1.3 * 2 ** 20]),
    ("1.3G", [1.3 * 2 ** 30]),
    ("1.3T", [1.3 * 2 ** 40]),
    ("1.3GB", [1.3 * 2 ** 30]),
    ("1.3", [1.3]),
    ("13", [13]),
    (".13", [0.13]),
    ("13.13", [13.13]),
    ("48_64", [48, 64]),
    ("64_12", [64, 12]),
    ("None", [None]),
    ("None_None", [None, None]),
    ("48_None", [48, None]),
])
def test_to_numeric_list(IEC3SF, numeric_list):
    assert RangeFinder.to_numeric_list(IEC3SF) == numeric_list


def test_find_ranged_cols():
    results = [
        "why,319,48,carpool,41.23,71.31,99.14,1.4Gi,48_64,31,cirencester,hartlepool".split(","),
        "rye,319,48,carpool,41.23,71.31,99.14,1.3Gi,48_65,31,cirencester,hartlepool".split(","),
        "why,319,48,oillube,41.23,71.31,99.14,1.2Gi,48_66,30,constantine,hartlepool".split(","),
        "why,319,48,carpool,41.23,71.31,99.99,1.3Gi,48_64,None,cirencester,hartlepool".split(","),
        "why,319,48,carpool,41.23,71.31,99.14,1.5Gi,48_65,31,cirencester,hartlepool".split(","),
    ]
    numeric_cols = RangeFinder.find_numeric_cols(results)
    expected_result = {
        1: [[319], [319], [319], [319], [319]],
        2: [[48], [48], [48], [48], [48]],
        4: [[41.23], [41.23], [41.23], [41.23], [41.23]],
        5: [[71.31], [71.31], [71.31], [71.31], [71.31]],
        6: [[99.14], [99.14], [99.14], [99.99], [99.14]],
        7: [[1.4 * 2**30], [1.3 * 2**30], [1.2 * 2**30], [1.3 * 2**30], [1.5 * 2**30]],
        8: [[48, 64], [48, 65], [48, 66], [48, 64], [48, 65]],
        9: [[31], [31], [30], [None], [31]]
    }
    assert set(numeric_cols.keys()) == set(expected_result.keys())
    for k in numeric_cols.keys():
        assert numeric_cols[k] == expected_result[k]


def test_unzip():
    three_tuple = RangeFinder.unzip([["a", 22, 1], ["b", 44, 2]])
    # Makes 3 series of 2 entries each:
    assert three_tuple == (('a', 'b'), (22, 44), (1, 2))


def test_superfluous_unzip():
    three_tuple = RangeFinder.unzip([[22], [44], [66]])
    # Makes 3 series of 2 entries each:
    assert three_tuple == ((22, 44, 66),)


@pytest.mark.parametrize("data, expected_smry", [
    ([31, 31, 30, None, 31], {
        "nulls": "1",
        "stdev": "0.5",
        "mean": "30.75",
        "min": "30",
        "max": "31",
    }),
    ([31000000, 31000000, 30000000, None, 31000000], {
        "mean": "29Mi",
        "stdev": "488Ki",
        "min": "29Mi",
        "max": "30Mi",
        "nulls": "1"
    }),
    ([40000], {
        "mean": "39Ki"
    }),
    ([], None),
])
def test_summarise_numbers(data, expected_smry):
    smry_dict = RangeFinder.summarise_numbers(data)
    assert smry_dict == expected_smry


@pytest.mark.parametrize("num_str, IEC3SF", [
    ("31000000", "30Mi"),
    ("999", "999"),
    ("1000", "1Ki"),
    ("1023", "1Ki"),
    ("1024", "1Ki"),
    ("1134", "1.1Ki"),
    (str(1024 * 1024), "1Mi"),
    (str(999 * 1024), "999Ki"),
    (str(1000 * 1024), "1Mi"),
    (str(1024 * 1024 * 1024), "1Gi"),
    (str(1024 * 1024 * 1024 * 1024), "1Ti"),
])
def test_shrink_dps(num_str, IEC3SF):
    assert RangeFinder.shrink_dps(num_str) == IEC3SF


def test_display_statistics_simple():
    test_data = {1: [[31], [31], [30], [None], [31]]}
    header = ["C1", "C2", "C3"]
    constant_content = display_statistics(header, test_data)
    assert constant_content == """
<h3>Statistics:</h3>
<ul>
<li><em>C2:</em>
<ul>
<li><em>mean:</em> 30.75</li>
<li><em>stdev:</em> 0.5</li>
<li><em>min:</em> 30</li>
<li><em>max:</em> 31</li>
<li><em>nulls:</em> 1</li>
</ul></li>
</ul>
"""


def test_display_statistics():
    test_data = {1: [[31, 42, 78], [31, 38, 75], [30, 46, 76], [None, 41, 82], [31, 39, 81]]}
    header = ["C1", "C2", "C3"]
    constant_content = display_statistics(header, test_data)
    assert constant_content == """
<h3>Statistics:</h3>
<ul>
<li><em>C2:</em>
<ul>
<li><em>0:</em>
<ul>
<li><em>mean:</em> 30.75</li>
<li><em>stdev:</em> 0.5</li>
<li><em>min:</em> 30</li>
<li><em>max:</em> 31</li>
<li><em>nulls:</em> 1</li>
</ul></li>
<li><em>1:</em>
<ul>
<li><em>mean:</em> 41.2</li>
<li><em>stdev:</em> 3.11</li>
<li><em>min:</em> 38</li>
<li><em>max:</em> 46</li>
</ul></li>
<li><em>2:</em>
<ul>
<li><em>mean:</em> 78.4</li>
<li><em>stdev:</em> 3.05</li>
<li><em>min:</em> 75</li>
<li><em>max:</em> 82</li>
</ul></li>
</ul></li>
</ul>
"""
