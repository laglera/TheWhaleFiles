"""Partido de los congresistas a partir del registro público de legisladores."""

import unittest

from app.legislators import LegislatorIndex, party_of


def legislator(bioguide, first, last, state, party, nickname=None, end="2027-01-03"):
    name = {"first": first, "last": last, "official_full": f"{nickname or first} {last}"}
    if nickname:
        name["nickname"] = nickname
    return {
        "id": {"bioguide": bioguide},
        "name": name,
        "terms": [{"type": "rep", "state": state, "party": party, "end": end}],
    }


INDEX = LegislatorIndex(
    [
        legislator("J000289", "James", "Jordan", "OH", "Republican", nickname="Jim"),
        legislator("O000171", "Tom", "O’Halleran", "AZ", "Democrat"),
        legislator("V000137", "Matt", "Van Epps", "TN", "Republican"),
        legislator("T000001", "David", "Taylor", "OH", "Republican"),
        legislator("T000002", "Mark", "Taylor", "OH", "Democrat"),
        # Fuera del periodo del dataset: no debe pisar a nadie.
        legislator("X000001", "James", "Jordan", "OH", "Whig", end="1850-03-03"),
    ]
)


class MatchingTests(unittest.TestCase):
    def test_the_portrait_id_wins(self):
        self.assertEqual(party_of(INDEX.find("Anything", "OH", "J000289")), "Republican")

    def test_formal_first_name_and_nickname_are_the_same_person(self):
        self.assertEqual(party_of(INDEX.find("James Jordan", "OH")), "Republican")
        self.assertEqual(party_of(INDEX.find("Jim Jordan", "OH")), "Republican")

    def test_straight_and_curly_apostrophes_match(self):
        self.assertEqual(party_of(INDEX.find("Tom O'Halleran", "AZ")), "Democrat")

    def test_compound_surnames_with_a_middle_name(self):
        self.assertEqual(party_of(INDEX.find("Matthew Robert Van Epps", "TN")), "Republican")

    def test_a_shared_surname_is_not_enough(self):
        # Dos Taylor en Ohio: sin nombre de pila que desempate, no se adivina.
        self.assertIsNone(INDEX.find("Bob Taylor", "OH"))
        self.assertEqual(party_of(INDEX.find("David Taylor", "OH")), "Republican")

    def test_the_state_has_to_match(self):
        self.assertIsNone(INDEX.find("James Jordan", "TX"))


if __name__ == "__main__":
    unittest.main()
