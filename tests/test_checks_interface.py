from checks_interface import deserialise_simple_csv


def test_deserialise_simple_csv():
    csv_list = deserialise_simple_csv("yolo,barry white,george soros,tilda swinton,None,bill gates")
    assert csv_list == ['yolo', 'barrywhite', 'george soros', 'tilda swinton', None, 'bill gates']
